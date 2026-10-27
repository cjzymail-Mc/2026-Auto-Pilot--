import json
import tempfile
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

import bpm.template as bpm_template
from bpm.template import (normalize_template, cached_template, CHILDREN, parse_list_items,
                          exact_list_item, captured_list_identity, fetch_template)


class TemplateTests(unittest.TestCase):
    def test_captured_identity_is_exact_and_fresh_main_mismatch_stops_child_reads(self):
        number, uid = "00123456789", "a" * 32
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "captured-list.json"
            path.write_text(json.dumps([{"bizNumber": number, "id": uid, "unused": "not-exported"}]), encoding="utf-8")
            hint, proof = captured_list_identity(path, number)
            self.assertEqual(hint, {"id": uid, "bizNumber": number})
            self.assertEqual(proof["kind"], "captured_exact_list_identity")
            with self.assertRaises(ValueError):
                captured_list_identity(path, number + "0")
            request = mock.Mock()
            request.get.return_value = SimpleNamespace(status=200, text=lambda: json.dumps(
                {"id": uid, "bizNumber": number + "0", "submitType": "15"}))
            probe = SimpleNamespace(ctx=SimpleNamespace(request=request))
            with mock.patch("bpm.template._target_list", return_value=(hint, {"accept": "application/json"})):
                with self.assertRaisesRegex(ValueError, "fresh main response"):
                    fetch_template(probe, number, lookup_list=path)
            self.assertEqual(request.get.call_count, 1)

    def test_observed_list_response_wrappers_and_ambiguity(self):
        rows = [{"id": "a" * 32, "bizNumber": "00123456789"}]
        for wrapped in (rows, {"content": rows}, {"data": {"content": rows}}, {"items": rows}):
            self.assertEqual(parse_list_items(json.dumps(wrapped)), rows)
        for malformed in ({"data": rows, "content": rows}, {"unrecognized": rows}, {"content": [None]}, None):
            with self.assertRaises(ValueError):
                parse_list_items(json.dumps(malformed))

    def test_full_number_and_uuid_are_exact_and_unique(self):
        target = {"id": "a" * 32, "bizNumber": "00123456789"}
        prefix = {"id": "b" * 32, "bizNumber": "001234567890"}
        self.assertEqual(exact_list_item([prefix, target], "00123456789"), target)
        self.assertEqual(exact_list_item([target, dict(target)], "00123456789"), target)
        for items in ([prefix], [target, {"id": "b" * 32, "bizNumber": target["bizNumber"]}],
                      [{"id": "bad", "bizNumber": target["bizNumber"]}]):
            with self.assertRaises(ValueError):
                exact_list_item(items, "00123456789")

    def test_exact_identity_all_children_and_whitelist(self):
        uid = "a" * 32
        main = {"id": uid, "bizNumber": "00123456789", "submitType": "08", "qd_access_token": "do-not-export", "description": "测试"}
        kids = {k: [] for k in CHILDREN}
        snap = normalize_template("00123456789", main, kids, {"kind": "fixture"})
        self.assertNotIn("qd_access_token", json.dumps(snap))
        self.assertEqual(snap["biz_number"], "00123456789")
        with self.assertRaises(ValueError):
            normalize_template("123456789", main, kids, {})
        kids["banks"] = [{"reimburseId": "b" * 32, "cost": "1"}]
        with self.assertRaises(ValueError):
            normalize_template("00123456789", main, kids, {})

    def test_cached_full_number_unique_and_incomplete_reads_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "census.json"
            doc = {"bizNumber": "00123456789", "fetch": {"status": 200, "body": json.dumps({"id": "a" * 32, "bizNumber": "00123456789", "submitType": "08"})},
                   "children": {k: {"status": 200, "body": "[]"} for k in CHILDREN}}
            path.write_text(json.dumps({"docs": [doc]}), encoding="utf-8")
            self.assertEqual(cached_template(path, "00123456789")["source"]["kind"], "cached")
            path.write_text(json.dumps({"docs": [doc, doc]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                cached_template(path, "00123456789")
            doc["children"]["costs"]["status"] = 503
            path.write_text(json.dumps({"docs": [doc]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                cached_template(path, "00123456789")


class ResearchRawFlagTests(unittest.TestCase):
    """--research-raw 只读研究旁路：仅限 --live；census 模式拒绝；raw 分支跳过 normalize。"""

    def test_research_raw_rejected_with_census_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            with self.assertRaises(SystemExit) as caught:
                bpm_template.main(["--census", str(Path(tmp) / "census.json"), "--research-raw",
                                   "--template-number", "00123456789", "--output", str(out)])
            self.assertEqual(caught.exception.code, 2)

    def test_research_raw_requires_live_identity_arguments(self):
        # live 模式缺 --expect-name 仍在输出路径校验前被拒（与既有 live 纪律一致）
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                bpm_template.main(["--live", "--research-raw", "--template-number", "00123456789",
                                   "--output", str(Path(tmp) / "x" / "y.json")])

    def test_fetch_template_raw_branch_skips_normalize(self):
        import types

        class FakeResponse:
            def __init__(self, payload):
                self.status, self._payload = 200, payload

            def text(self):
                return json.dumps(self._payload)

        class FakeRequest:
            def __init__(self):
                self.calls = []

            def get(self, path, headers=None, timeout=None):
                self.calls.append(path)
                if "/reimburse/list" in path or path.endswith("/list"):
                    return FakeResponse({"data": {"rows": [{"bizNumber": "00123456789", "id": "a" * 32}]}})
                if path.endswith("/reimburse/" + "a" * 32):
                    return FakeResponse({"bizNumber": "00123456789", "id": "a" * 32, "submitType": "低值易耗品办公用品",
                                         "totalCost": 9974.76})
                return FakeResponse([{"reimburseId": "a" * 32, "amount": 24.5}])

        probe = types.SimpleNamespace(ctx=types.SimpleNamespace(request=FakeRequest()),
                                      log_event=lambda **kwargs: events.append(kwargs))
        events = []

        def fake_target_list(p, number, identity_hint=None):
            return {"bizNumber": number, "id": "a" * 32}, {"x": "witnessed"}

        original_target = bpm_template._target_list
        original_normalize = bpm_template.normalize_template
        bpm_template._target_list = fake_target_list
        bpm_template.normalize_template = lambda *a, **k: (_ for _ in ()).throw(AssertionError("raw must skip normalize"))
        try:
            raw = bpm_template.fetch_template(probe, "00123456789", raw=True)
        finally:
            bpm_template._target_list = original_target
            bpm_template.normalize_template = original_normalize
        self.assertEqual(raw["kind"], "research_raw_read_only")
        self.assertEqual(raw["biz_number"], "00123456789")
        self.assertEqual(raw["uuid"], "a" * 32)
        self.assertEqual(raw["main"]["submitType"], "低值易耗品办公用品")
        self.assertEqual(set(raw["children"]), set(CHILDREN))
        # _read_json(parse_float=Decimal)：真实 API 数值在 raw 转储中以 Decimal 存在，
        # CLI 转储必须可序列化且保留精确十进制文本（与 _scalars 同约定）。
        self.assertIsInstance(raw["main"]["totalCost"], Decimal)
        self.assertEqual(raw["main"]["totalCost"], Decimal("9974.76"))
        dumped = json.dumps(raw, ensure_ascii=False, indent=2, default=bpm_template._json_default)
        self.assertIn('"totalCost": "9974.76"', dumped)
        self.assertEqual(json.loads(dumped)["main"]["totalCost"], "9974.76")
        with self.assertRaises(TypeError):
            json.dumps({"bad": object()}, default=bpm_template._json_default)


if __name__ == "__main__":
    unittest.main()
