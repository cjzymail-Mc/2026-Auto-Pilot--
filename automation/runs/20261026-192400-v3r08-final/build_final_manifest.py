# -*- coding: utf-8 -*-
"""V3-R08 §12.3 最终交付 manifest 构建（机器可读 JSON，A 逐项抽验用）。

冻结依据：team-task src-82e4775e 待做条款 4；合同 ctr-3057b56a 冻结范围 4。
每项：path + sha256 + 内容要点。运行于 B6/CASE-08/B7 产物就绪后（closeout）。
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "automation/runs/20261026-192400-v3r08-final"


def sha(rel: str) -> str:
    p = ROOT / rel
    return hashlib.sha256(p.read_bytes()).hexdigest()


def item(rel: str, note: str) -> dict:
    return {"path": rel, "sha256": sha(rel), "note": note}


def main() -> int:
    sections = {
        "1_原件与解析": [
            item("automation/runs/20261026-100322-v3r00-inventory/case-file-manifest.json",
                 "73 原件清单+分组+sha256（第 8 轮零漂移基线）"),
            item("automation/runs/20261026-115500-v3r02-case01/case01-facts.json",
                 "CASE-01 事实层：52 唯一身份（27 通行费+5 油票+20 汇总单×2）、逐票票面+锚点"),
            item("automation/runs/20261026-115500-v3r02-case01/CASE-01-report.md",
                 "机器+人工双报告、交叉核验全绿、期间链"),
        ],
        "2_工作簿副本与重算": [
            item("automation/runs/20261026-131000-v3r03-case02/case02-mapping.json",
                 "20 行↔27 票逐票映射（cell 级变更清单）"),
            item("automation/runs/20261026-131000-v3r03-case02/case02-coverage.json",
                 "覆盖模型 fuel_pool_strict_surplus：K/M/T/R/O/F/margin/严格门槛"),
        ],
        "3_逐票公出单对照": [
            item("automation/runs/20261026-143340-v3r04-case03/actual_trip_matches.json",
                 "27 票逐票裁定：12 MATCHED Σ221.02 / 15 NO_MATCH Σ265.91（含查询/详情证据引用）"),
        ],
        "4_模板与计划": [
            item("automation/runs/20261026-172300-v3r06-template-plan/template_snapshot.json",
                 "模板 15426095951 快照（travel 兼容；三员=陈晶/116070053）"),
            item("automation/runs/20261026-172300-v3r06-template-plan/field-reuse-matrix.md",
                 "复用边界：template 14 仅身份/预算/收款；本次值零旧单推导"),
            item("automation/runs/20261026-172300-v3r06-template-plan/fill-plan.json",
                 "可执行计划 v1.0：details 2+costs 20+banks 1 三向闭合 1924.93；validate-only PLAN_VALIDATED"),
        ],
        "5_受限测试关联与执行变体": [
            item("automation/runs/20261026-181500-v3r07-fill/attempt_002/evidence/relation_enumeration.json",
                 "真实关联弹窗首屏枚举（20/76，零选择零副作用）"),
            item("automation/runs/20261026-181500-v3r07-fill/fill-plan-v11.json",
                 "执行变体 v1.1：占位意图块 oa_test_relations（种子先验 6074a757…→12024070132）"),
            item("automation/runs/20261026-181500-v3r07-fill/variant-diff.json",
                 "v1.1↔v1.0 零偏离断言（差异全落声明簇）+随机占位单独列表"),
        ],
        "6_真实执行与独立核验": [
            item("automation/runs/20261026-183000-v3r07-fill/attempt_001/stage1_result.json",
                 "SUCCESS_FILL_ONLY；save_status=NOT_ATTEMPTED；tech 309.5s"),
            item("automation/runs/20261026-183000-v3r07-fill/attempt_001/evidence/independent_readback.json",
                 "独立 DOM 全量回读（四表行数组+金额+身份）"),
            item("automation/runs/20261026-183000-v3r07-fill/attempt_001/evidence/independent_verification.json",
                 "全量 diff：ok=true、行数全等、金额四向 1924.93==R"),
            item("automation/runs/20261026-183000-v3r07-fill/attempt_001/evidence/v1_final.png",
                 "终局整页截图"),
            item("automation/runs/20261026-183000-v3r07-fill/attempt_001/evidence/test_page_close_inventory.json",
                 "未保存页盘点：编制中/无单号/无 UUID/干净关闭"),
            item("automation/runs/20261026-181500-v3r07-fill/B5-report.md",
                 "B5 独立回读 diff 报告（可读版+机器版 b5-diff-summary.json）"),
        ],
        "7_独立复核与新session验收": [
            item("automation/runs/20261026-192400-v3r08-final/B6-report.md",
                 "B6 全链独立复核报告（另一 agent 从原件到 DOM 重算，差异表）"),
            item("automation/runs/20261026-192400-v3r08-final/case08-input-manifest.md",
                 "CASE-08 输入白名单（启动前落盘可审计）"),
            item("automation/runs/20261026-192400-v3r08-final/B6-report.md.sha256", "（占位，构建时 B6 报告哈希）") if False else
            item("automation/runs/20261026-192400-v3r08-final/CASE-08-report.md",
                 "CASE-08 新 session 验收结论（含其自有 v1.0+validate-only+比对）"),
        ],
        "8_终局与交付": [
            item("automation/template-materials-program/progress.json",
                 "全链台账含 V3-R07 条目 + V3-R08 B7 终局标记（fill_only 完成/页面状态交接）"),
            item("automation/runs/20261026-192400-v3r08-final/用户报告.md",
                 "用户可读报告（不宣称重新报销成功）"),
            item("handoff-input.json", "本轮交接（round-8 实际哈希）"),
        ],
    }
    flat = [e for v in sections.values() for e in v]
    manifest = {
        "schema": "v3-final-manifest-1.0",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "case": "真实公出案例独立解析与 OA 填写（BPM-MATERIALS-20261026-V3）fill_only 考核",
        "sections": sections,
        "counts": {"items": len(flat)},
        "notes": ["A 逐项抽验以 path+sha256 为准；内容要点为索引非替代",
                  "每轮交接以 helper 状态 history（round 1–8 review_sha256）+ 各轮 run 目录 events 为准",
                  "凭证原值不在任何交付物中；automation/.pw-profile 与 .local-session 不入 Git"],
    }
    out = RUN / "final-manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("manifest:", out.name, "items:", len(flat))
    return 0


if __name__ == "__main__":
    sys.exit(main())
