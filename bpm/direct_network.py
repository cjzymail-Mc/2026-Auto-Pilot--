"""Credential-free direct-connect checks for the long-running OA watcher."""
import csv
import ipaddress
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time


OA_HOSTS = ("bpm.qiaodan.com", "static.qiaodan.com", "admin.api.qiaodan.com")


def proxy_environment():
    """Report presence only; proxy URLs may contain credentials."""
    result = {"proxy_environment_present": any(
        os.environ.get(key) for key in os.environ if key.lower() in
        {"http_proxy", "https_proxy", "all_proxy"}),
        "system_proxy_enabled": None, "pac_present": None, "auto_detect_proxy": None,
        "clash_running": None, "tun_interface_present": None, "route_verified": None}
    if sys.platform != "win32":
        return result
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
            result["system_proxy_enabled"] = bool(winreg.QueryValueEx(key, "ProxyEnable")[0])
            try:
                result["pac_present"] = bool(winreg.QueryValueEx(key, "AutoConfigURL")[0])
            except FileNotFoundError:
                result["pac_present"] = False
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Internet Settings\Connections") as key:
            settings = winreg.QueryValueEx(key, "DefaultConnectionSettings")[0]
            if isinstance(settings, bytes) and len(settings) > 8:
                result["auto_detect_proxy"] = bool(settings[8] & 8)
    except OSError:
        pass
    try:
        completed = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                                   capture_output=True, text=True, errors="replace", timeout=3,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        if completed.returncode == 0:
            names = [row[0].lower() for row in csv.reader(completed.stdout.splitlines()) if row]
            result["clash_running"] = any(
                "clash" in name or "mihomo" in name for name in names)
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        completed = subprocess.run(["netsh", "interface", "ipv4", "show", "interfaces"],
                                   capture_output=True, text=True, errors="replace", timeout=3,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        if completed.returncode == 0:
            rows = completed.stdout.splitlines()[3:]
            result["tun_interface_present"] = any(
                any(word in row.lower() for word in ("mihomo", "clash", "wintun", "tun", "tap", "vpn"))
                for row in rows)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return result


def _tls_probe(host, timeout=3):
    """Worker: connect only resolved/checked sockaddr; hostname stays as SNI."""
    deadline = time.monotonic() + timeout
    result = {"host": host, "status": "PASS", "stage": "dns"}
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        usable = [item for item in addresses if not (
            item[0] == socket.AF_INET and ipaddress.ip_address(item[4][0])
            in ipaddress.ip_network("198.18.0.0/15"))]
        if not usable:
            return dict(result, status="FAIL", reason="FAKE_IP_DNS")
        result["resolved_addresses"] = sorted({item[4][0] for item in usable})
        last_error = None
        for family, socktype, proto, _, sockaddr in usable:
            if time.monotonic() >= deadline:
                raise TimeoutError()
            try:
                result["stage"] = "tcp"
                with socket.socket(family, socktype, proto) as connection:
                    connection.settimeout(max(.01, deadline - time.monotonic()))
                    connection.connect(sockaddr)  # No second DNS lookup.
                    result["stage"] = "tls"
                    with ssl.create_default_context().wrap_socket(connection, server_hostname=host) as tls:
                        peer, local = tls.getpeername()[0], tls.getsockname()[0]
                        return dict(result, address_family="ipv6" if family == socket.AF_INET6 else "ipv4",
                                    peer=peer if isinstance(peer, str) else None,
                                    local=local if isinstance(local, str) else None)
            except ssl.SSLCertVerificationError:
                raise  # Never make a bad certificate pass via another address.
            except OSError as exc:
                last_error = exc
        raise last_error or OSError()
    except (OSError, ValueError) as exc:
        return dict(result, status="FAIL", error_type=type(exc).__name__)


def direct_tls_check(host, timeout=4):
    """Diagnostic only. A killable child bounds DNS, TCP and TLS together."""
    if host not in OA_HOSTS:
        raise ValueError("Diagnostic host is not approved")
    try:
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
        completed = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "bpm.direct_network", host, str(timeout)],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            capture_output=True, text=True, encoding="utf-8", timeout=timeout, **flags)
        if completed.returncode != 0:
            return {"host": host, "status": "FAIL", "reason": "DIAGNOSTIC_WORKER_FAILED"}
        return json.loads(completed.stdout)
    except subprocess.TimeoutExpired:
        return {"host": host, "status": "FAIL", "reason": "DIAGNOSTIC_DEADLINE"}


def check_oa_direct(timeout=12):
    deadline = time.monotonic() + timeout
    results = []
    for host in OA_HOSTS:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            results.append({"host": host, "status": "FAIL", "reason": "DIAGNOSTIC_DEADLINE"})
        else:
            results.append(direct_tls_check(host, min(4, remaining)))
    return results


def playwright_path_snapshot(playwright, resolved_addresses):
    """Read only this driver's company TCP peers and their Windows routes.

    A direct peer proves application proxy bypass; the selected OS interface
    remains a separate observation, not a claim that every TUN was bypassed.
    """
    result = {"driver_connections": [], "route_observation": "unknown"}
    if sys.platform != "win32":
        return result
    try:
        pid = playwright._impl_obj._connection._transport._proc.pid
        def run(args):
            return subprocess.run(args, capture_output=True, text=True, errors="replace",
                                  timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
        routes = []
        route_output = run(["netsh", "interface", "ipv4", "show", "route"])
        for line in route_output.stdout.splitlines() if route_output.returncode == 0 else []:
            match = re.search(r"\s(\d+)\s+(\d+\.\d+\.\d+\.\d+/\d+)\s+(\d+)\s+(.*)$", line)
            if match:
                routes.append((ipaddress.ip_network(match[2], strict=False), int(match[1]),
                               int(match[3]), match[4].strip()))
        connections = run(["netstat", "-ano", "-p", "tcp"])
        if connections.returncode != 0:
            return result
        for line in connections.stdout.splitlines():
            columns = line.split()
            if len(columns) != 5 or columns[0] != "TCP" or columns[-1] != str(pid):
                continue
            remote, _, port = columns[2].rpartition(":")
            remote = remote.strip("[]")
            if remote not in resolved_addresses or port != "443":
                continue
            address = ipaddress.ip_address(remote)
            matches = [r for r in routes if r[0].version == address.version and address in r[0]]
            selected = sorted(matches, key=lambda r: (-r[0].prefixlen, r[1]))[:1]
            result["driver_connections"].append({"local": columns[1], "peer": columns[2],
                "company_peer_without_http_proxy": True,
                "route_interface_index": selected[0][2] if selected else None,
                "route_prefix": str(selected[0][0]) if selected else None})
        result["route_observation"] = "observed" if result["driver_connections"] else "unknown"
    except (OSError, subprocess.TimeoutExpired, AttributeError, ValueError):
        pass
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in OA_HOSTS:
        raise SystemExit(2)
    print(json.dumps(_tls_probe(sys.argv[1], float(sys.argv[2]))))
