"""Approved company-domain and exact WeCom host guard for empty test contexts.

No proxy is introduced. Page requests are fetched without following redirects
and fulfilled only after that check, because Chromium's ordinary route.continue
does not re-route subsequent HTTP redirects. WebSockets are disabled for this
task. Persistent/restored contexts are deliberately rejected by install().
"""
from urllib.parse import urljoin, urlsplit
import re

APPROVED_HOSTS = frozenset({
    "login.work.weixin.qq.com", "wwcdn.weixin.qq.com", "res.wx.qq.com",
})
COMPANY_DOMAIN = "qiaodan.com"
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class NetworkBlocked(RuntimeError):
    pass


def authority(url):
    """Return safe host/port/allow decision, never path/query or credentials."""
    try:
        if not isinstance(url, str) or any(ord(c) < 32 or c.isspace() for c in url):
            return None, None, False
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        valid_host = (len(host) <= 253 and all(
            re.fullmatch(r"(?!-)[a-z0-9-]{1,63}(?<!-)", label)
            for label in host.split(".")))
        approved = (host in APPROVED_HOSTS or host == COMPANY_DOMAIN
                    or host.endswith("." + COMPANY_DOMAIN))
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme in {"https", "wss"} else 80)
        allowed = (valid_host and parsed.scheme == "https" and approved and port == 443
                   and parsed.username is None and parsed.password is None)
        return host if valid_host else None, port, allowed
    except (TypeError, ValueError):
        return None, None, False


def _emit(log, reason, url, channel):
    host, port, _ = authority(url)
    if callable(log):
        log(event="request_guard_blocked", reason=reason, channel=channel, host=host, port=port)


def guarded_get(probe, url, **kwargs):
    """The existing read-only API path: validate first, never auto-redirect."""
    log = getattr(probe, "log_event", None)
    if not authority(url)[2]:
        _emit(log, "UNAPPROVED_TARGET", url, "api_get")
        raise NetworkBlocked("API_TARGET_NOT_APPROVED")
    if kwargs.get("max_redirects", 0) != 0 or kwargs.get("ignore_https_errors", False) is not False:
        raise NetworkBlocked("API_GUARD_OVERRIDE_FORBIDDEN")
    response = probe.ctx.request.get(url, **dict(kwargs, max_redirects=0,
                                                max_retries=0, ignore_https_errors=False))
    if response.status in REDIRECT_STATUSES:
        location = response.headers.get("location", response.headers.get("Location", ""))
        _emit(log, "HTTP_REDIRECT_NOT_FOLLOWED", urljoin(url, location), "api_get")
        response.dispose()
        raise NetworkBlocked("API_REDIRECT_BLOCKED")
    return response


class ContextGuard:
    def __init__(self, log_event=None):
        self.log = log_event

    @staticmethod
    def _fetch(route):
        return route.fetch(max_redirects=0, max_retries=0, timeout=30000)

    def install(self, context):
        if context.pages:
            raise NetworkBlocked("GUARD_REQUIRES_CONTEXT_WITHOUT_EXISTING_PAGES")
        if not callable(getattr(context, "route_web_socket", None)):
            raise NetworkBlocked("WEBSOCKET_BLOCKING_UNAVAILABLE")

        def http(route):
            url = route.request.url
            if not authority(url)[2]:
                _emit(self.log, "UNAPPROVED_TARGET", url, "page_http")
                route.abort("blockedbyclient")
                return
            response = None
            try:
                response = self._fetch(route)
                if response.status in REDIRECT_STATUSES:
                    location = response.headers.get("location", response.headers.get("Location", ""))
                    _emit(self.log, "HTTP_REDIRECT_NOT_FOLLOWED", urljoin(url, location), "page_http")
                    route.abort("blockedbyclient")
                else:
                    route.fulfill(response=response)
            except Exception as exc:
                if callable(self.log):
                    self.log(event="request_guard_fetch_failed", error_type=type(exc).__name__,
                             host=authority(url)[0])
                try:
                    route.abort("failed")
                except Exception:
                    pass
            finally:
                if response is not None:
                    response.dispose()

        def websocket(route):
            # No WebSocket is required by the mature XHR-based test runbooks.
            # Denying all also avoids a second redirect path in WS handshakes.
            _emit(self.log, "WEBSOCKET_DISABLED_FOR_TASK", route.url, "websocket")
            # In 1.60 the mock socket opens only after this initial callback
            # returns; sync close() here deadlocks that opening handshake.
            # Never connect_to_server. Close after a client message instead;
            # messages remain local and are neither forwarded nor logged.
            route.on_message(lambda _message: route.close(
                code=1008, reason="WebSockets disabled for this task"))

        context.route("**/*", http)
        context.route_web_socket("**/*", websocket)
        if callable(self.log):
            self.log(event="request_guard_ready", exact_external_hosts=sorted(APPROVED_HOSTS),
                     company_domain=COMPANY_DOMAIN, company_subdomains=True,
                     redirects="not_followed", service_workers="block", websocket="blocked",
                     transport="existing_no_proxy_server", tls_validation=True)
        return self
