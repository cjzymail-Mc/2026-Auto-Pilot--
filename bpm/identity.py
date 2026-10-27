# -*- coding: utf-8 -*-
"""身份关系字段与校验（BPM-SELFDRIVE-20261027-V1 R2 D5，用户 2026-10-27 指示）。

区分三个角色并各自带来源，不推定、不混用：
- login_operator 登录操作人：当前 OA 会话的登录身份（顶栏/个人资料只读核实）；
- form_creator   新页制单人：真实新报销页观测到的系统默认制单人；
- expense_owner  费用所属人：本批费用/公出事实行所属的人（可与操作人/制单人不同）。

规则（红线级）：
- 任何角色未知 ⇒ NEEDS_INPUT 缺口，不得猜名、不得沿用历史姓名顶替；
- 不为套用案例对照值换人：expense_owner 以本次材料事实为准，即使换人后与历史
  对照值不一致也不改人——差异本身就是上报内容；
- 不默认零餐补：餐补 C 只在 form_creator 身份合法成立（可核实来源+实名在案）时
  允许按其参与日计；身份不成立时返回缺口按 NEEDS_INPUT/外部认证处理，禁止把
  C 置 0 继续算；
- 身份关系是“如实分层报告”的一部分：不作为保存入口的拒绝条件（见 run 内
  §2(4) 纠正记录），保存许可仍由当次意图+同 task_id 授权+SaveController 链判定。
"""
from __future__ import annotations

ROLE_ORDER = ("login_operator", "form_creator", "expense_owner")
ROLE_LABELS = {"login_operator": "登录操作人", "form_creator": "新页制单人",
               "expense_owner": "费用所属人"}
# 可核实来源：真实新页/系统观测/官方资料。user_statement 只是声明，单独不构成
# “身份合法成立”，需与观测交叉。
VERIFIABLE_SOURCES = ("template_page", "system_observation", "oa_profile")
KNOWN_SOURCES = VERIFIABLE_SOURCES + ("user_statement", "workout_detail")
_REQUIRED_KEYS = ("name", "source", "source_locator")


def _gap(code, role, detail):
    entry = {"code": code, "detail": detail}
    if role:
        entry["role"] = role
    return entry


def validate_identity_relations(relations) -> list:
    """结构校验：返回缺口列表（空=通过）。未知/缺来源都如实列缺口，不猜值。"""
    if not isinstance(relations, dict) or not relations:
        return [_gap("IDENTITY_RELATIONS_MISSING", None,
                     "未提供身份关系（登录操作人/新页制单人/费用所属人）：按 NEEDS_INPUT 处理，不推定")]
    gaps = []
    for role in ROLE_ORDER:
        entry = relations.get(role)
        if entry is None:
            gaps.append(_gap("IDENTITY_ROLE_UNKNOWN", role,
                             "{0}未知：按 NEEDS_INPUT 留缺口，不猜身份、不沿用历史姓名".format(
                                 ROLE_LABELS[role])))
            continue
        if not isinstance(entry, dict):
            gaps.append(_gap("IDENTITY_ROLE_INVALID", role,
                             "{0}条目必须是对象".format(ROLE_LABELS[role])))
            continue
        for key in _REQUIRED_KEYS:
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                gaps.append(_gap("IDENTITY_ROLE_UNSOURCED", role,
                                 "{0}缺 {1}：身份必须有名字与来源定位".format(ROLE_LABELS[role], key)))
        if entry.get("source") not in KNOWN_SOURCES:
            gaps.append(_gap("IDENTITY_ROLE_UNSOURCED", role,
                             "{0}source 不在已知来源内: {1!r}".format(
                                 ROLE_LABELS[role], entry.get("source"))))
    extra = sorted(set(relations) - set(ROLE_ORDER))
    if extra:
        gaps.append(_gap("IDENTITY_ROLE_INVALID", None,
                         "未知角色字段: {0}".format(", ".join(extra))))
    return gaps


def creator_identity_established(relations) -> bool:
    """餐补前提：报销单制单人身份合法成立 = 实名在案 + 可核实来源。"""
    entry = (relations or {}).get("form_creator") if isinstance(relations, dict) else None
    return (isinstance(entry, dict)
            and isinstance(entry.get("name"), str) and entry["name"].strip()
            and entry.get("source") in VERIFIABLE_SOURCES)


def meal_basis_gap(relations):
    """餐补缺口判定：制单人身份不成立 → 返回缺口（NEEDS_INPUT），绝不返回“零餐补”。

    返回 None 表示前提成立，餐补按其参与日正常计。
    """
    if creator_identity_established(relations):
        return None
    return _gap("MEAL_BASIS_CREATOR_UNKNOWN", "form_creator",
                "报销单制单人身份未合法成立：餐补按 NEEDS_INPUT 上报外部核实，"
                "不为套用案例对照值换人、不默认零餐补")


def expected_mismatch_gap(relations, expected_name) -> list:
    """用户明确预期 vs 实测制单人不一致 → 真实缺口上报；不换人、不改预期。"""
    gaps = []
    entry = (relations or {}).get("form_creator") if isinstance(relations, dict) else None
    observed = entry.get("name") if isinstance(entry, dict) else None
    if expected_name and observed and observed != expected_name:
        gaps.append(_gap("IDENTITY_EXPECTATION_MISMATCH", "form_creator",
                         "用户预期制单人 {0!r} 与实测 {1!r} 不一致：按 NEEDS_INPUT 上报，"
                         "不换人凑对照值、不改预期".format(expected_name, observed)))
    return gaps
