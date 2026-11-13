"""企业微信 BPM 待审提醒。双击或用 python -X utf8 approval_watch.py 启动。

可最小化控制台，按 Ctrl+C 停止。首次运行在脚本同目录创建 approval_watch.local.json。
可用 --check-config 单独生成并检查配置。配置不包含登录凭证。
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from itertools import chain
import json
import os
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4


CONFIG_NAME = "approval_watch.local.json"
CONFIG_DEFAULTS = {"repo_root": None, "interval_seconds": 10, "expect_name": None}


class ConfigError(ValueError):
    pass


def repo_at(path):
    if (path / "AGENTS.md").is_file() and (path / "bpm/login.py").is_file():
        return path.resolve()
    return None

def write_config(path, settings):
    temp = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)

def load_config(script, repo_override=None):
    directory = script.resolve().parent
    path = directory / CONFIG_NAME
    try:
        saved = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        saved = {}
    except (ValueError, OSError) as exc:
        raise ConfigError(f"无法读取 {path}，请检查 JSON 格式和文件权限。") from exc
    if not isinstance(saved, dict) or saved.keys() - CONFIG_DEFAULTS.keys():
        raise ConfigError(f"{path} 只能包含 repo_root、interval_seconds 和 expect_name。")
    settings = CONFIG_DEFAULTS | saved
    for key in ("repo_root", "expect_name"):
        if settings[key] is not None and (not isinstance(settings[key], str) or not settings[key].strip()):
            raise ConfigError(f"{path} 的 {key} 必须是非空字符串或 null。")
    if type(settings["interval_seconds"]) is not int or settings["interval_seconds"] < 5:
        raise ConfigError(f"{path} 的 interval_seconds 必须是至少为 5 的整数。")

    configured = settings["repo_root"]
    saved_repo = repo_at(directory / Path(configured).expanduser()) if configured else None
    if repo_override:
        selected = repo_at(Path(repo_override).expanduser())
        if selected is None:
            raise ConfigError("BPM_REPO_ROOT 未指向有效的仓库根目录。")
    else:
        selected = saved_repo or next(
            (found for folder in chain((directory,), directory.parents) if (found := repo_at(folder))), None
        )
    if selected and not saved_repo:
        settings["repo_root"] = str(selected)
    if settings != saved:
        try:
            write_config(path, settings)
        except OSError as exc:
            raise ConfigError(f"无法写入 {path}，请确认脚本所在目录可写。") from exc
    if selected is None:
        raise ConfigError(f"找不到仓库，请在 {path} 的 repo_root 填入仓库根目录。")
    return selected, settings


HOST = "https://bpm.qiaodan.com"
INBOX = HOST + "/oa/taskcenter"
ACCOUNT = "a#user-profile-dd.profile-toggle-link > span"
TASK_TYPE = ".form-row.Status .ui-dropdown-label"
DATE_INPUTS = ".form-row.CreatedAt input"
DATE_CLEAR = ".form-row.CreatedAt .qd-date-picker-clear:visible"
DOC_NUMBER = "#BizNumber4"
TASK_QUERY = re.compile(r"/flowtask/query/[1-9][0-9]*/([1-9][0-9]*)")
DETAIL_PATH = re.compile(r"/oa/[a-z][a-z0-9-]*")
IDENTIFIER = re.compile(r"[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")


class WatchError(RuntimeError):
    pass


class LoginLost(WatchError):
    pass


def current_account(page):
    from bpm.session import claims

    url = urlsplit(page.url)
    if f"{url.scheme}://{url.netloc}" != HOST:
        raise LoginLost("OA 页面已离开登录域。")
    account = page.locator(ACCOUNT)
    if account.count() != 1 or not account.is_visible():
        raise LoginLost("无法确认 OA 顶栏账号。")
    name = account.inner_text(timeout=5000).strip()
    access = claims(page.evaluate("""() => sessionStorage.getItem('qd_access_token')
                                          || localStorage.getItem('qd_access_token')"""))
    subject = access.get("sub")
    if not name or not subject or str(access.get("full_name", "")).strip() != name:
        raise LoginLost("OA 顶栏账号与当前认证身份无法互证。")
    return str(subject), name


def approval_tasks(rows, subject):
    for row in rows:
        if (str(row.get("toUserCode")) == subject and row.get("bizStatus") == 7
                and row.get("status") in (0, 1) and row.get("kind") in (1, 2, 3)
                and row.get("isHeld") is not True):
            yield row


def inbox_response(response, page_index):
    url = urlsplit(response.url)
    match = TASK_QUERY.fullmatch(url.path)
    return (url.scheme == "https" and url.netloc == "admin.api.qiaodan.com"
            and match is not None and int(match[1]) == page_index
            and parse_qs(url.query).get("for") == ["1"]
            and response.request.method == "POST")


def read_response(response, page_index, number):
    if response.status in (401, 403):
        raise LoginLost("待办查询的登录或访问权限已失效。")
    if response.status != 200:
        raise WatchError("待办查询未成功。")
    args = response.request.post_data_json["args"]
    filters = [(arg["propertyName"], arg["text"]) for arg in args]
    expected = [("Status", None)] + ([("BizNumber", number)] if number else [])
    if sorted(filters) != sorted(expected):
        raise WatchError("查询条件已变化，无法确认完整待办范围。")
    result = response.json()
    if (result["pageIndex"] != page_index or type(result["totalCount"]) is not int
            or result["totalCount"] < 0 or type(result["hasNextPage"]) is not bool
            or not isinstance(result["data"], list)
            or any(not isinstance(row, dict) for row in result["data"])):
        raise WatchError("任务中心分页响应格式已变化。")
    return result


class Inbox:
    def __init__(self, page, account):
        self.page = page
        self.account = account

    def check_account(self):
        if current_account(self.page) != self.account:
            raise LoginLost("OA 登录账号已切换。")

    def open(self):
        self.page.goto(INBOX, wait_until="domcontentloaded", timeout=30000)
        self.page.locator("th.prop-bizNumber:visible").wait_for(timeout=20000)
        self.page.wait_for_timeout(600)
        self.check_account()
        dates = self.page.locator(DATE_INPUTS)
        if any(dates.evaluate_all("inputs => inputs.map(input => Boolean(input.value))")):
            clear = self.page.locator(DATE_CLEAR)
            if clear.count() != 1 or clear.get_attribute("aria-label") != "清除日期":
                raise WatchError("任务时间的清除控件无法唯一定位。")
            # OA 的日期输入挡住了按钮，触发已验证的原生清除事件。
            clear.dispatch_event("click", timeout=5000)

    def query(self, number=None):
        self.check_account()
        if self.page.url != INBOX:
            raise WatchError("监控标签页已离开任务中心。")
        if self.page.locator(TASK_TYPE).inner_text(timeout=5000).strip() != "待办任务":
            raise WatchError("任务类型已变化，无法确认待办范围。")
        number_input = self.page.locator(DOC_NUMBER)
        if number:
            number_input.fill(number, timeout=5000)
        if number_input.input_value(timeout=5000) != (number or ""):
            raise WatchError("任务中心的单据编号筛选已变化。")
        result = self.receive(self.page.get_by_role("button", name="查询", exact=True), 1, number)
        total = result["totalCount"]
        rows = list(result["data"])
        while result["hasNextPage"]:
            next_page = self.page.locator(".ui-paginator-next:visible:not(.ui-state-disabled)")
            result = self.receive(next_page, result["pageIndex"] + 1, number)
            if result["totalCount"] != total or not result["data"] or len(rows) >= total:
                raise WatchError("待办在翻页期间发生变化，将重新查询。")
            rows.extend(result["data"])
        keys = {row.get("id") for row in rows}
        if len(rows) != total or len(keys) != total or None in keys or "" in keys:
            raise WatchError("待办翻页结果有缺漏或重复，将重新查询。")
        self.check_account()
        return rows

    def receive(self, control, index, number):
        with self.page.expect_response(lambda response: inbox_response(response, index), timeout=18000) as event:
            control.click(timeout=5000)
        result = read_response(event.value, index, number)
        self.page.wait_for_timeout(600)
        return result


def detail_url(source, account, task):
    key, number, document, route = (task.get(field) for field in ("id", "bizNumber", "bizId", "url"))
    if (not isinstance(key, str) or not IDENTIFIER.fullmatch(key)
            or not isinstance(document, str) or not IDENTIFIER.fullmatch(document)
            or not isinstance(route, str) or not DETAIL_PATH.fullmatch(route) or route == "/oa/taskcenter"
            or not isinstance(number, str) or not number.strip() or len(number) > 100):
        raise WatchError("待办缺少可唯一打开的单据标识。")

    # 无界面页通过 OA 的原生「查看」获得真实详情地址，保留站点生成的任务参数。
    with source.expect_popup(timeout=8000) as event:
        source.evaluate("() => { window.open('about:blank', '_blank'); }")
    page = event.value
    try:
        inbox = Inbox(page, account)
        inbox.open()
        rows = inbox.query(number)
        exact = [row for row in rows if row.get("bizNumber") == number]
        if not any(row.get("id") == key for row in approval_tasks(exact, account[0])):
            return None
        if len(exact) != 1 or exact[0].get("bizId") != document or exact[0].get("url") != route:
            raise WatchError("任务中心无法唯一定位该条待审单。")
        page.locator("td.prop-bizNumber:visible").get_by_text(number, exact=True).click(timeout=5000)
        page.get_by_role("button", name="查看", exact=True).click(timeout=5000)
        page.wait_for_url(re.compile(re.escape(HOST + route) + r"\?"), timeout=15000)
        url = page.url
        target = parse_qs(urlsplit(url).query)
        if target.get("id") != [document] or len(target.get("task", [])) != 1:
            raise WatchError("OA 打开的详情与任务中心单据不一致。")
        return url
    finally:
        page.close()


class ApprovalWindow:
    def __init__(self, probe):
        self.probe = probe
        self.browser = None
        self.context = None

    @property
    def pages(self):
        return self.context.pages if self.context else []

    def open(self, account, url):
        source = self.probe.page
        if current_account(source) != account:
            raise LoginLost("OA 登录账号已切换。")
        # 会话只在本进程内交接给受相同网络守卫保护的可见浏览器。
        session = source.evaluate("""() => Object.fromEntries(
            ['qd_access_token', 'qd_refresh_token'].map(key => [key, sessionStorage.getItem(key)]))""")
        if not self.browser or not self.browser.is_connected():
            self.browser = self.probe._pw.chromium.launch(headless=False, args=["--no-proxy-server"])
            self.context = None
        if self.context is None:
            self.context = self.probe._new_guarded_context(self.browser, storage_state=source.context.storage_state())
        page = self.context.new_page()
        try:
            page.add_init_script(f"""(() => {{
                if (location.origin !== {json.dumps(HOST)}) return;
                const session = {json.dumps(session)};
                for (const [key, value] of Object.entries(session)) {{
                    if (value !== null && sessionStorage.getItem(key) === null) sessionStorage.setItem(key, value);
                }}
            }})();""")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.locator(ACCOUNT).wait_for(state="visible", timeout=15000)
            if page.url != url or current_account(page) != account:
                raise WatchError("可见详情页的地址或账号与后台核对结果不一致。")
        except BaseException:
            if not page.is_closed():
                page.close()
            if not self.pages:
                self.close()
            raise
        page.on("dialog", lambda _dialog: None)
        return page

    def close(self):
        if self.browser and self.browser.is_connected():
            self.browser.close()
        self.browser = self.context = None


class FlashInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]


def flash_browser(browser):
    cdp = browser.new_browser_cdp_session()
    try:
        processes = cdp.send("SystemInfo.getProcessInfo")["processInfo"]
        pid, = [process["id"] for process in processes if process["type"] == "browser"]
    finally:
        cdp.detach()

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.FlashWindowEx.argtypes = [ctypes.POINTER(FlashInfo)]
    windows = []

    @callback_type
    def visit(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            name = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, name, len(name))
            if name.value == "Chrome_WidgetWin_1":
                windows.append(hwnd)
        return True

    user32.EnumWindows(visit, 0)
    for hwnd in windows:
        if user32.IsIconic(hwnd):
            user32.ShowWindowAsync(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        info = FlashInfo(ctypes.sizeof(FlashInfo), hwnd, 0x03, 8, 0)  # FLASHW_ALL
        user32.FlashWindowEx(ctypes.byref(info))
    return bool(windows)


def login(probe, force_scan):
    from bpm.browser_probe import PASS, SESSION_STATE
    from bpm.session import state_usable

    if not force_scan and state_usable(SESSION_STATE):
        probe._launch_isolated_guarded_context(headless=True)
        probe._inject_session_state()
        probe.page = probe.ctx.new_page()
        # 登录门在无界面探测时无需提示用户找扫码窗。
        wait = probe.args.login_wait
        probe.args.login_wait = 0
        try:
            state = probe.phase_entry()
        finally:
            probe.args.login_wait = wait
        if state == PASS:
            account = current_account(probe.page)
            probe._save_session_state()
            return account
        if state != "LOGIN_REQUIRED":
            raise LoginLost("无法确认 OA 登录状态。可用 --force-scan 重新扫码。")
        probe._close_browser()

    probe.args.force_scan = True
    probe._launch_isolated_guarded_context()
    probe.page = probe.ctx.new_page()
    if probe.phase_entry() != "LOGIN_REQUIRED" or probe.wait_login() != PASS:
        raise LoginLost("登录未确认，请重新启动并扫码。")
    account = current_account(probe.page)
    probe._save_session_state()
    probe._close_browser()

    probe.args.force_scan = False
    probe.args.expect_name = probe._required_name = account[1]
    probe._launch_isolated_guarded_context(headless=True)
    probe._inject_session_state()
    probe.page = probe.ctx.new_page()
    if probe.phase_entry() != PASS or current_account(probe.page) != account:
        raise LoginLost("扫码后无法建立同一账号的后台会话。")
    probe._fresh_scan_confirmed = False
    probe._save_session_state()
    return account


def monitor(probe, window, account, interval):
    from playwright.sync_api import Error as BrowserError

    from bpm.browser_probe import SESSION_STATE
    from bpm.session import state_usable

    inbox = Inbox(probe.page, account)
    inbox.open()
    opened = set()
    retry_at = {}
    last_status = None
    probe.say(f"已登录 {account[1]}，每 {interval} 秒后台检查。可最小化控制台，按 Ctrl+C 退出。")
    while not probe.page.is_closed():
        try:
            if not state_usable(SESSION_STATE):
                raise LoginLost("本地认证复用期已到，请重新扫码。")
            pending = list(approval_tasks(inbox.query(), account[0]))
            new = 0
            for task in pending:
                key = task["id"]
                if key in opened or time.monotonic() < retry_at.get(key, 0):
                    continue
                if not state_usable(SESSION_STATE):
                    raise LoginLost("认证复用期已到，请重新扫码。")
                try:
                    url = detail_url(probe.page, account, task)
                    if not url:
                        continue
                    page = window.open(account, url)
                    opened.add(key)
                    retry_at.pop(key, None)
                    new += 1
                    if new == 1:
                        try:
                            page.bring_to_front()
                            if not flash_browser(window.browser):
                                probe.say("审批标签页已打开，未定位到 Windows 浏览器窗体。")
                        except (BrowserError, OSError, KeyError, ValueError):
                            probe.say("审批标签页已打开，Windows 窗体提醒未能启动。")
                except LoginLost:
                    raise
                except (WatchError, BrowserError, ValueError, KeyError, TypeError):
                    if key not in retry_at:
                        probe.say("发现待审任务，但详情未能打开。可在任务中心手工查看，脚本会重试。")
                    retry_at[key] = time.monotonic() + max(interval, 30)
            status = f"待审 {len(pending)} 条"
            if status != last_status or new:
                probe.say(status + (f"，已新开 {new} 个审批标签页。" if new else "。"))
                last_status = status
        except LoginLost:
            raise
        except (WatchError, BrowserError, KeyError, TypeError, ValueError) as exc:
            status = str(exc) if type(exc) is WatchError else "任务中心查询暂时失败。"
            if status != last_status:
                probe.say(status, "下一轮重试。")
                last_status = status
        probe.page.wait_for_timeout(interval * 1000)


def main(argv=None):
    parser = argparse.ArgumentParser(description="后台监控企业微信 BPM 待审任务（Windows）。")
    parser.add_argument("--interval", type=int, help="覆盖配置中的检查间隔，最短 5 秒")
    parser.add_argument("--expect-name", help="可选，核对预期登录人")
    parser.add_argument("--force-scan", action="store_true", help="用全新浏览器会话重新扫码")
    parser.add_argument("--check-config", action="store_true", help="仅生成并检查本地 JSON 配置")
    args = parser.parse_args(argv)
    if args.interval is not None and args.interval < 5:
        parser.error("--interval 至少为 5 秒。")
    if args.expect_name is not None and not args.expect_name.strip():
        parser.error("--expect-name 不能为空。")
    script = Path(__file__)
    try:
        repo, settings = load_config(script, os.environ.get("BPM_REPO_ROOT"))
    except ConfigError as exc:
        parser.error(str(exc))
    if args.check_config:
        print(f"配置已就绪：{script.resolve().with_name(CONFIG_NAME)}")
        return 0
    if sys.platform != "win32":
        parser.error("监控需要 Windows。")

    sys.path.insert(0, str(repo))
    try:
        from playwright.sync_api import Error as BrowserError
    except ModuleNotFoundError:
        parser.error("请先安装 Playwright 和 Chromium，再运行监控。")
    from bpm.login import LoginProbe

    interval = args.interval if args.interval is not None else settings["interval_seconds"]
    expected = args.expect_name if args.expect_name is not None else settings["expect_name"]

    probe = LoginProbe(SimpleNamespace(
        run=f"approval-watch-{uuid4().hex[:12]}", doc_id=None, expect_name=expected,
        force_scan=args.force_scan, tech_budget=900, login_wait=480, wall_cap=1200,
        fill_plan=None, login_only=True,
    ))
    try:
        probe.acquire_lock()
    except (OSError, RuntimeError):
        probe.say("无法取得 OA profile 锁。请先结束正在使用该 profile 的任务。")
        return 2

    window = ApprovalWindow(probe)
    try:
        account = login(probe, args.force_scan)
        monitor(probe, window, account, interval)
    except KeyboardInterrupt:
        pass
    except (BrowserError, RuntimeError, OSError) as exc:
        probe.say(str(exc) if isinstance(exc, WatchError) else "无法启动或继续监控。请检查 OA 网络和 Chromium。")
        if window.pages:
            probe.say("监控已暂停，现有审批标签保留。处理完后按 Ctrl+C 退出并重启。")
            try:
                while window.pages:
                    probe.page.wait_for_timeout(1000)
            except (KeyboardInterrupt, BrowserError):
                pass
        return 2
    finally:
        try:
            window.close()
        finally:
            probe._close_browser()
            probe.release_lock()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
