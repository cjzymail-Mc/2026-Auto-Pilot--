"""Real local Chromium shutdown fault injection; no real OA or profile access."""
import subprocess
import sys
import textwrap
import unittest


class LocalShutdownTests(unittest.TestCase):
    def test_polling_multiple_thirty_second_fetches_interrupt_and_lock_release(self):
        script = textwrap.dedent('''
            from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
            from pathlib import Path
            import faulthandler, json, tempfile, threading, time
            from unittest.mock import patch
            from playwright.sync_api import sync_playwright
            from bpm import browser_probe
            from bpm.browser_probe import Probe
            from bpm.network_guard import ContextGuard
            faulthandler.dump_traceback_later(65, exit=True)
            release=threading.Event()
            two_slow=threading.Event()
            counters={'slow':0,'poll':0}
            mutex=threading.Lock()
            class Fixture(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path.startswith('/slow'):
                        with mutex:
                            counters['slow']+=1
                            if counters['slow']>=2: two_slow.set()
                        release.wait(40)
                    elif self.path=='/poll':
                        with mutex: counters['poll']+=1
                    body=b'<title>synthetic polling only</title><link rel="icon" href="data:,">'
                    try:
                        self.send_response(200)
                        self.send_header('Content-Type','text/html')
                        self.send_header('Content-Length',str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                    except ConnectionError:
                        pass  # Fixture client intentionally times out before reply.
                def log_message(self,*args): pass
            server=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            phases=[]
            events=[]
            pw=sync_playwright().start()
            browser=pw.chromium.launch(headless=True,args=['--no-proxy-server'])
            ctx=browser.new_context(service_workers='block')
            guard=ContextGuard(lambda **e:events.append(e)).install(ctx)
            active=set()
            def fetch(route):
                path='/'+route.request.url.split('/')[-1]
                if path.startswith('/slow'): active.add(path)
                try:
                    # Real Node Route.fetch, real 30s deadline, synthetic server.
                    return route.fetch(url='http://127.0.0.1:'+str(server.server_address[1])+path,
                                       max_redirects=0,max_retries=0,timeout=30000)
                finally:
                    active.discard(path)
            guard._fetch=fetch
            page=ctx.new_page()
            page.goto('https://bpm.qiaodan.com/synthetic')
            page.evaluate("""() => {
                window.poller=setInterval(()=>fetch('/poll').catch(()=>{}),80);
                fetch('/slow-a').catch(()=>{}); fetch('/slow-b').catch(()=>{});
            }""")
            deadline=time.monotonic()+5
            while (not two_slow.is_set() or counters['poll']<2) and time.monotonic()<deadline:
                page.wait_for_timeout(60)
            assert two_slow.is_set() and len(active)==2 and counters['poll']>=2
            with tempfile.TemporaryDirectory() as temp:
                profile=Path(temp)/'synthetic-profile'
                probe=object.__new__(Probe)
                probe.ctx=ctx; probe._pw=pw; probe._guarded_browser=browser
                probe._lock_path=profile/'executor.lock'
                probe.log_event=lambda **e:events.append(e)
                with patch.object(browser_probe,'PROFILE',profile): probe.acquire_lock()
                assert probe._lock_path.exists()
                started=time.monotonic()
                # Record each real cleanup stage without replacing its behavior.
                def wrap(obj,name):
                    original=getattr(obj,name)
                    def measured(*args,**kwargs):
                        start=time.monotonic()
                        phases.append({'stage':name,'state':'start'})
                        try: return original(*args,**kwargs)
                        finally: phases.append({'stage':name,'state':'end','seconds':round(time.monotonic()-start,3)})
                    setattr(obj,name,measured)
                for obj,name in ((ctx,'set_offline'),(ctx,'unroute_all'),(ctx,'close'),
                                 (browser,'close'),(pw,'stop'),(probe,'release_lock')):
                    wrap(obj,name)
                try: raise KeyboardInterrupt
                except KeyboardInterrupt: pass
                finally:
                    try: probe._close_browser()
                    finally: probe.release_lock()
                elapsed=time.monotonic()-started
                assert elapsed < 38, elapsed
                assert not probe._lock_path.exists()
                assert not browser.is_connected()
                assert not active
                report={'multiple_inflight_at_interrupt':2,'request_timeout_ms':30000,
                        'shutdown_seconds':round(elapsed,3),'lock_released':True,
                        'poll_count':counters['poll'],'phases':phases,
                        'timed_out_fetches':sum(e.get('reason')=='TIMEOUT' for e in events)}
            release.set()
            server.shutdown(); server.server_close()
            faulthandler.cancel_dump_traceback_later()
            print(json.dumps(report))
        ''')
        result = subprocess.run([sys.executable, "-X", "utf8", "-c", script],
                                capture_output=True, text=True, encoding="utf-8", timeout=75)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("CancelledError", result.stderr)
        self.assertNotIn("Exception in callback", result.stderr)
        self.assertEqual(result.stderr, "")
        print("POLLING_SHUTDOWN_STDOUT", result.stdout.strip())
        print("POLLING_SHUTDOWN_STDERR", repr(result.stderr))

    def test_slow_fetch_dispose_failure_repeated_close_and_interrupt(self):
        script = textwrap.dedent('''
            from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
            import json, threading, time
            from unittest.mock import patch
            from playwright.sync_api import sync_playwright
            from bpm.network_guard import ContextGuard
            class Fixture(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == '/slow': time.sleep(.6)
                    body=b'<title>synthetic</title><link rel="icon" href="data:,">'
                    self.send_response(200)
                    self.send_header('Content-Type','text/html')
                    self.send_header('Content-Length',str(len(body)))
                    self.end_headers()
                    try: self.wfile.write(body)
                    except (BrokenPipeError,ConnectionResetError): pass
                def log_message(self,*args): pass
            server=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,args=['--no-proxy-server'])
                client=pw.request.new_context()
                for interrupted in (False,True):
                    ctx=browser.new_context(service_workers='block')
                    events=[]
                    guard=ContextGuard(lambda **e: events.append(e)).install(ctx)
                    calls=[]
                    def fetch(route):
                        path='/slow' if route.request.url.endswith('/slow') else '/'
                        calls.append(path)
                        return client.get('http://127.0.0.1:'+str(server.server_address[1])+path,timeout=3000)
                    guard._fetch=fetch
                    page=ctx.new_page()
                    page.goto('https://bpm.qiaodan.com/synthetic')
                    page.evaluate("() => {fetch('/slow').catch(()=>{});fetch('https://unknown.invalid/').catch(()=>{});}")
                    page.wait_for_timeout(60)
                    assert '/slow' in calls
                    started=time.monotonic()
                    try:
                        if interrupted: raise KeyboardInterrupt
                    except KeyboardInterrupt: pass
                    finally:
                        ContextGuard.close(ctx)
                    assert time.monotonic()-started < 5
                    ContextGuard.close(ctx)
                    assert any(e.get('reason')=='UNAPPROVED_TARGET' for e in events)
                    assert calls.count('/slow')==1
                # Dispose failure must remain a cleanup diagnostic, not an unhandled callback.
                ctx=browser.new_context(service_workers='block')
                events=[]
                guard=ContextGuard(lambda **e:events.append(e)).install(ctx)
                response=client.get('http://127.0.0.1:'+str(server.server_address[1])+'/')
                guard._fetch=lambda route:response
                with patch.object(response,'dispose',side_effect=RuntimeError('synthetic dispose failure')):
                    page=ctx.new_page()
                    page.goto('https://bpm.qiaodan.com/synthetic')
                    page.wait_for_timeout(50)
                    assert any(e.get('event')=='request_guard_dispose_failed' for e in events)
                    ContextGuard.close(ctx)
                client.dispose()
                browser.close()
            server.shutdown()
            server.server_close()
            print(json.dumps({'slow_fetch':True,'interrupt':True,'repeated_close':True,'dispose_failure':True,'unknown_domain_blocked':True}))
        ''')
        result = subprocess.run([sys.executable, "-X", "utf8", "-c", script],
                                capture_output=True, text=True, encoding="utf-8", timeout=40)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("CancelledError", result.stderr)
        self.assertNotIn("Exception in callback", result.stderr)
        # Capture real stdout/stderr in the acceptance log, including empty stderr.
        print("LOCAL_SHUTDOWN_STDOUT", result.stdout.strip())
        print("LOCAL_SHUTDOWN_STDERR", repr(result.stderr))


if __name__ == "__main__":
    unittest.main()
