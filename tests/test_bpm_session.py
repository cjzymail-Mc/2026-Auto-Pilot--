import base64
import json
import os
import tempfile
import unittest
from pathlib import Path

from bpm.session import (LEGACY_MAX_DAYS, META_KEY, REUSE_DAYS, _meta_valid,
                         attach_metadata, persist_state, read_state, state_usable,
                         write_record)


def token(subject, exp):
    payload = {"sub": subject}
    if exp is not None:
        payload["exp"] = exp
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return "eyJhbGciOiJub25lIn0." + body + ".test"


def state(now, subject="person-a", days=30):
    return {"_page_storage": {"https://bpm.qiaodan.com": {
        "qd_access_token": token(subject, now + 1800),
        "qd_refresh_token": token(subject, now + days * 86400)}}}


def legacy_state(now, days, subject="person-a", refresh_days=120):
    """60 天时期写入的旧合法记录：meta 按旧默认 days（≤60），扫码起点 now。"""
    value = state(now, subject=subject, days=refresh_days)
    value[META_KEY] = {"schema_version": "1.0", "profile_id": "a" * 32,
                       "session_generation": "b" * 32, "last_scan_epoch": now,
                       "local_reuse_days": days}
    return value


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"
        self.now = 1800000000

    def save(self, value):
        self.path.write_text(json.dumps(value), encoding="utf-8")

    def test_defaults_migrated_to_thirty_days(self):
        self.assertEqual(REUSE_DAYS, 30)
        self.assertEqual(LEGACY_MAX_DAYS, 60)

    def test_fresh_scan_window_is_thirty_days(self):
        value = state(self.now)
        attach_metadata(value, {}, fresh_scan=True, now=self.now)
        self.assertEqual(value[META_KEY]["local_reuse_days"], 30)
        self.save(value)
        self.assertTrue(state_usable(self.path, now=self.now + 29 * 86400))
        self.assertFalse(state_usable(self.path, now=self.now + 30 * 86400))
        os.utime(self.path, (self.now + 35 * 86400,) * 2)
        self.assertFalse(state_usable(self.path, now=self.now + 35 * 86400))

    def test_scan_bound_is_not_extended_by_updates(self):
        old = state(self.now, days=120)
        attach_metadata(old, {}, fresh_scan=True, now=self.now)
        new = state(self.now + 10 * 86400, days=120)
        attach_metadata(new, old, now=self.now + 10 * 86400)
        self.assertEqual(new[META_KEY]["last_scan_epoch"], self.now)
        self.assertEqual(new[META_KEY]["local_reuse_days"], 30)
        self.save(new)
        self.assertTrue(state_usable(self.path, now=self.now + 29 * 86400))
        self.assertFalse(state_usable(self.path, now=self.now + 30 * 86400))
        self.assertFalse(state_usable(self.path, now=self.now - 1))

    def test_legacy_sixty_day_record_tightened_not_voided(self):
        # 第 29/30/31 天三档：未满 30 不拒、恰满失效、超过失效；不延长到 60。
        self.save(legacy_state(self.now, days=60))
        self.assertTrue(state_usable(self.path, now=self.now + 29 * 86400))
        self.assertFalse(state_usable(self.path, now=self.now + 30 * 86400))
        self.assertFalse(state_usable(self.path, now=self.now + 31 * 86400))
        self.assertFalse(state_usable(self.path, now=self.now + 59 * 86400))

    def test_shorter_legacy_window_not_extended(self):
        self.save(legacy_state(self.now, days=7))
        self.assertTrue(state_usable(self.path, now=self.now + 6 * 86400))
        self.assertFalse(state_usable(self.path, now=self.now + 7 * 86400))

    def test_earlier_refresh_expiry_caps_below_thirty(self):
        self.save(legacy_state(self.now, days=60, refresh_days=10))
        self.assertTrue(state_usable(self.path, now=self.now + 9 * 86400))
        self.assertFalse(state_usable(self.path, now=self.now + 10 * 86400))

    def test_unknown_refresh_expiry_uses_thirty_day_cap(self):
        value = {"_page_storage": {"https://bpm.qiaodan.com": {
            "qd_access_token": token("person-a", self.now + 1800),
            "qd_refresh_token": token("person-a", None)}}}
        value[META_KEY] = {"schema_version": "1.0", "profile_id": "a" * 32,
                           "session_generation": "b" * 32, "last_scan_epoch": self.now,
                           "local_reuse_days": 60}
        self.save(value)
        self.assertTrue(state_usable(self.path, now=self.now + 29 * 86400))
        self.assertFalse(state_usable(self.path, now=self.now + 30 * 86400))

    def test_invalid_meta_rejected(self):
        for days in (0, 61, 60.5, True, "60"):
            with self.subTest(days=days):
                value = legacy_state(self.now, days=30)
                value[META_KEY]["local_reuse_days"] = days
                self.save(value)
                self.assertFalse(state_usable(self.path, now=self.now + 86400))
        future = legacy_state(self.now, days=30)
        future[META_KEY]["last_scan_epoch"] = self.now + 10 * 86400  # 未来扫码时间
        self.save(future)
        self.assertFalse(state_usable(self.path, now=self.now))
        bad_schema = legacy_state(self.now, days=30)
        bad_schema[META_KEY]["schema_version"] = "2.0"
        self.save(bad_schema)
        self.assertFalse(state_usable(self.path, now=self.now + 86400))

    def test_legacy_keeps_one_day_and_unknown_scan_not_invented(self):
        self.save({})
        os.utime(self.path, (self.now,) * 2)
        self.assertTrue(state_usable(self.path, now=self.now + 86399))
        self.assertFalse(state_usable(self.path, now=self.now + 86400))
        value = state(self.now)
        self.assertIsNone(attach_metadata(value, {}, now=self.now))
        self.assertNotIn(META_KEY, value)

    def test_changed_person_does_not_inherit_scan_window(self):
        old = state(self.now)
        attach_metadata(old, {}, fresh_scan=True, now=self.now)
        new = state(self.now, subject="person-b")
        self.assertIsNone(attach_metadata(new, old, now=self.now))
        self.assertNotIn(META_KEY, new)

    def test_subject_mismatch_rejected(self):
        value = state(self.now)
        value["_page_storage"]["https://bpm.qiaodan.com"]["qd_access_token"] = token("person-b", self.now + 100)
        with self.assertRaises(ValueError):
            attach_metadata(value, {}, fresh_scan=True, now=self.now)

    def test_record_contains_no_credentials_and_unknown_fields_remain_null(self):
        value = state(self.now)
        attach_metadata(value, {}, fresh_scan=True, now=self.now)
        principal = {"user_id": "person-a", "name": "测试用户", "employee_id": None, "company": None, "department": None}
        path = write_record(value, principal, root=Path(self.temp.name) / "records", now=self.now)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["local_reuse_days"], 30)
        self.assertIsNone(data["server_expires_at"])
        self.assertIsNone(data["principal"]["company"])
        for secret in value["_page_storage"]["https://bpm.qiaodan.com"].values():
            self.assertNotIn(secret, path.read_text(encoding="utf-8"))
        self.assertEqual(json.loads((path.parent.parent / "current.json").read_text())["profile_id"], data["profile_id"])

    def test_record_display_matches_tightened_read_decision(self):
        # 显示口径与读取判定一致：旧 60 天记录 local_reuse_until=扫码+30 天，
        # 且该日期与 state_usable 的翻转边界重合（非扫码写回不改变窗口）。
        value = legacy_state(self.now, days=60)
        self.save(value)
        self.assertTrue(state_usable(self.path, now=self.now + 29 * 86400))
        record = write_record(value, {"user_id": "person-a", "name": "测试用户", "employee_id": None,
                                      "company": None, "department": None},
                              root=Path(self.temp.name) / "records2", now=self.now + 29 * 86400)
        data = json.loads(record.read_text(encoding="utf-8"))
        self.assertEqual(data["local_reuse_days"], 60)  # 存储值保留旧默认（lineage）
        from datetime import datetime, timezone
        until = datetime.fromtimestamp(self.now + 30 * 86400, timezone.utc).isoformat()
        self.assertEqual(data["local_reuse_until"], until)  # 显示=扫码+30 天（收紧后）
        # 写回后判定窗口未变：仍以原扫码起点为锚
        self.assertFalse(state_usable(self.path, now=self.now + 30 * 86400))


class WriteChainDisciplineTests(unittest.TestCase):
    """写回链负例（Codex 窄审 r2-auth30-static-audit 两反例的修复固化）：
    无 meta 旧文件普通探查写回不滚动 24h 边界；坏 meta 读取/复制/写回三处一致拒绝。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"
        self.now = 1800000000
        self.principal = {"user_id": "person-a", "name": "测试用户", "employee_id": None,
                          "company": None, "department": None}

    def save(self, value):
        self.path.write_text(json.dumps(value), encoding="utf-8")

    def test_no_meta_writeback_keeps_anchored_window(self):
        """反例一修复：T+23h 写回后 T+46h 必须失效——锚点=最初 mtime，不滚动续期。"""
        self.save({"cookies": [{"name": "x", "value": "placeholder"}], "origins": []})
        os.utime(self.path, (self.now,) * 2)
        self.assertTrue(state_usable(self.path, now=self.now + 23 * 3600))
        new_state = state(self.now + 23 * 3600)
        # 普通探查（非扫码）：attach 无旧 meta 可复制 → 返回 None；persist 保留原 mtime
        self.assertIsNone(attach_metadata(new_state, read_state(self.path),
                                          now=self.now + 23 * 3600))
        persist_state(self.path, new_state, read_state(self.path))
        self.assertEqual(int(self.path.stat().st_mtime), self.now)   # 锚点保持
        self.assertTrue(state_usable(self.path, now=self.now + 23 * 3600 + 60))
        self.assertFalse(state_usable(self.path, now=self.now + 46 * 3600))   # 反例修复
        # 反复写回也不滑动
        persist_state(self.path, state(self.now + 30 * 3600), read_state(self.path))
        self.assertFalse(state_usable(self.path, now=self.now + 25 * 3600 + 60))

    def test_writeback_with_meta_refreshes_mtime_without_extending_window(self):
        """对照：有合法 meta 的写回 mtime 照常刷新，窗口仍由扫码起点决定。"""
        value = legacy_state(self.now, days=60)
        self.save(value)
        later = state(self.now + 10 * 86400)
        meta = attach_metadata(later, read_state(self.path), now=self.now + 10 * 86400)
        self.assertIsNotNone(meta)
        import time as time_module
        before_persist = time_module.time()
        persist_state(self.path, later, read_state(self.path))
        self.assertGreaterEqual(self.path.stat().st_mtime, before_persist - 1)   # mtime 照常刷新
        self.assertTrue(state_usable(self.path, now=self.now + 29 * 86400))
        self.assertFalse(state_usable(self.path, now=self.now + 30 * 86400))

    def test_explicit_null_meta_rejected_not_legacy_fallback(self):
        """反例 2c：META_KEY 显式 null 是损坏，不是"合法无元数据旧状态"。"""
        value = state(self.now)
        value[META_KEY] = None
        self.save(value)
        os.utime(self.path, (self.now,) * 2)
        self.assertFalse(state_usable(self.path, now=self.now + 3600))

    def test_incomplete_meta_rejected_consistently(self):
        """反例 2a：缺 profile_id/session_generation 时读取与写回同一拒绝。"""
        value = legacy_state(self.now, days=30)
        for key in ("profile_id", "session_generation"):
            broken = json.loads(json.dumps(value))
            broken[META_KEY].pop(key)
            self.save(broken)
            self.assertFalse(state_usable(self.path, now=self.now + 86400),
                             "state_usable 应拒绝缺 {0}".format(key))
            with self.assertRaises(ValueError):
                write_record(broken, self.principal, root=Path(self.temp.name) / "r", now=self.now)
        # 缺 profile_id 且 schema 坏：attach 也不复制
        corrupt = json.loads(json.dumps(value))
        corrupt[META_KEY].pop("profile_id")
        fresh = state(self.now)
        self.assertIsNone(attach_metadata(fresh, corrupt, now=self.now))
        self.assertNotIn(META_KEY, fresh)

    def test_attach_does_not_copy_corrupt_meta(self):
        """反例 2b：同 subject 的坏 schema/days 旧 meta 不被原样复制。"""
        previous = legacy_state(self.now, days=30)
        previous[META_KEY]["schema_version"] = "2.0"
        previous[META_KEY]["local_reuse_days"] = 999
        fresh = state(self.now)   # 同 subject person-a
        self.assertIsNone(attach_metadata(fresh, previous, now=self.now))
        self.assertNotIn(META_KEY, fresh)

    def test_write_record_rejects_corrupt_meta_with_valid_profile(self):
        """反例 2b 写回侧：即使 profile_id 合法，坏 schema meta 也进不了展示记录。"""
        value = legacy_state(self.now, days=30)
        value[META_KEY]["schema_version"] = "2.0"
        with self.assertRaises(ValueError):
            write_record(value, self.principal, root=Path(self.temp.name) / "r3", now=self.now)

    def test_no_meta_writeback_produces_no_record(self):
        """无扫码锚点不产会话记录（不编造 profile_id/扫码时间）；也不抛错阻断写回。"""
        self.assertIsNone(write_record(state(self.now), self.principal,
                                       root=Path(self.temp.name) / "r4", now=self.now))

    def test_corrupt_meta_downgrade_chain_refused_at_persist(self):
        """追加窄审组合链：坏 meta + 非扫码 attach(None) + persist 覆盖 = 删键降级回
        legacy 24h。修复后 persist 在覆盖前拒绝，原字节/判定保持不变（attach→persist→
        read 整链验证，非单函数）。"""
        for label, mutate in (("schema2.0", lambda m: m.update(schema_version="2.0")),
                              ("missing-profile", lambda m: m.pop("profile_id")),
                              ("explicit-null", None)):
            with self.subTest(corrupt=label):
                previous = legacy_state(self.now, days=30)
                if mutate is None:
                    previous[META_KEY] = None
                else:
                    mutate(previous[META_KEY])
                self.save(previous)
                bytes_before = self.path.read_bytes()
                mtime_before = self.path.stat().st_mtime
                self.assertFalse(state_usable(self.path, now=self.now + 3600))
                current = state(self.now + 3600)   # 同 subject 非扫码导出
                self.assertIsNone(attach_metadata(current, previous, now=self.now + 3600))
                with self.assertRaises(ValueError):
                    persist_state(self.path, current, previous)
                self.assertEqual(self.path.read_bytes(), bytes_before)   # 原字节不变
                self.assertEqual(self.path.stat().st_mtime, mtime_before)
                self.assertFalse(state_usable(self.path, now=self.now + 3600))   # 仍拒绝

    def test_fresh_scan_rebuild_over_corrupt_meta_still_works(self):
        """对照（不得堵死）：真实新扫码成功后 attach 产出全新合法 meta——即使旧文件
        meta 损坏，扫码重建路径照常覆盖并可复用。"""
        previous = legacy_state(self.now, days=30)
        previous[META_KEY]["schema_version"] = "2.0"
        self.save(previous)
        self.assertFalse(state_usable(self.path, now=self.now + 3600))
        fresh = state(self.now + 3600)
        meta = attach_metadata(fresh, previous, fresh_scan=True, now=self.now + 3600)
        self.assertTrue(_meta_valid(meta))
        persist_state(self.path, fresh, previous)   # 不抛：扫码重建合法
        self.assertTrue(state_usable(self.path, now=self.now + 3600 + 60))
        # 边界=扫码起点+30 天（扫码发生在 now+3600）
        self.assertFalse(state_usable(self.path, now=self.now + 3600 + 30 * 86400))


if __name__ == "__main__":
    unittest.main()
