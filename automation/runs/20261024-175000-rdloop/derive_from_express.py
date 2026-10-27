"""从 express 驱动派生 rd 驱动（round-8；一次性转换脚本，留档可复跑）。"""
from pathlib import Path

src = Path("automation/runs/20261024-174500-expressloop/chain_driver.py").read_text(encoding="utf-8")
d = src
pairs = [
    ('"""Round-8 expressloop', '"""Round-8 rdloop'),
    ("材料为用户授权历史回放 express（", "材料为用户授权历史回放 rd_materials（"),
    ('TEMPLATE_NUMBER = "15426094780"', 'TEMPLATE_NUMBER = "15426104120"'),
    ('TASK_ID = "20261024-r8-expressloop-15426094780"', 'TASK_ID = "20261024-r8-rdloop-15426104120"'),
    ('original = RUN / "originals/replay_express_r8.json"', 'original = RUN / "originals/replay_rd_r8.json"'),
    ('locator = "originals/replay_express_r8.json#{0}"', 'locator = "originals/replay_rd_r8.json#{0}"'),
    ('bindings={"originals/replay_express_r8.json": material_sha}', 'bindings={"originals/replay_rd_r8.json": material_sha}'),
    ('hashes = {"originals/replay_express_r8.json": material_sha}', 'hashes = {"originals/replay_rd_r8.json": material_sha}'),
    ('material_basis="授权历史回放 express（live-test-authorization user_statement 授权）只读复制",',
     'material_basis="授权历史回放 rd_materials（live-test-authorization user_statement 授权）只读复制",'),
    ('template_basis="缓存快照 type-view-15426094780（lineage sha MATCH）"',
     'template_basis="缓存快照 type-view-15426104120（lineage sha MATCH）"'),
    ('generated_by="round8-expressloop/', 'generated_by="round8-rdloop/'),
    ('"statement": "快递费报销（授权历史回放）：样品寄送 8 笔结算明细、邮寄费预算明细 1 行、"\n                     "四名收款人分摊，合计 347.50；本轮 fill_only 只填不存。",\n        "declared_category": "快递费",',
     '"statement": "研发材料费报销（授权历史回放）：外购样品 18 项物品档案行、4 行预算明细、"\n                     "四名收款人分摊，合计 9935.16；本轮 fill_only 只填不存。",\n        "declared_category": "研发材料费",'),
    ('assert snapshot["document_type"] == "express" and snapshot["biz_number"] == TEMPLATE_NUMBER',
     'assert snapshot["document_type"] == "rd_materials" and snapshot["biz_number"] == TEMPLATE_NUMBER'),
    ('assert snapshot["header"]["submitType"] == "15", snapshot["header"]["submitType"]  # 快递费类别码（实测）',
     'assert snapshot["header"]["submitType"] == "11", snapshot["header"]["submitType"]  # 研发材料费类别码（实测）'),
    ('log("template_cached_snapshot_bound", status="RESOLVED", document_type="express",',
     'log("template_cached_snapshot_bound", status="RESOLVED", document_type="rd_materials",'),
    ('    details, costs = material["tables"]["details"], material["tables"]["costs"]\n    banks = material["tables"]["banks"]',
     '    details, products = material["tables"]["details"], material["tables"]["products"]\n    banks = material["tables"]["banks"]'),
    ('    cost_sum = sum((Decimal(row["fields"]["cost"]) for row in costs), Decimal("0"))',
     '    product_sum = sum((Decimal(row["fields"]["price"]) for row in products), Decimal("0"))'),
    ('    assert detail_sum == cost_sum == bank_sum == total, (detail_sum, cost_sum, bank_sum, total)',
     '    assert detail_sum == product_sum == bank_sum == total, (detail_sum, product_sum, bank_sum, total)'),
    ('"details_sum": str(detail_sum), "costs_sum": str(cost_sum), "banks_sum": str(bank_sum),\n            "header_totalCost": str(total), "closure": "四向闭合（details=costs=banks=totalCost）",',
     '"details_sum": str(detail_sum), "products_sum": str(product_sum), "banks_sum": str(bank_sum),\n            "header_totalCost": str(total), "closure": "四向闭合（details=products=banks=totalCost）",'),
    ('                                        "/table_applicability/relations/reason"],',
     '                                        "/table_applicability/relations/reason",\n                                        "/table_applicability/costs/reason"],'),
    ('        rows={"details": len(details), "costs": len(costs), "banks": len(banks)},',
     '        rows={"details": len(details), "products": len(products), "banks": len(banks)},'),
    ('note="单头显示值（转账/人民币/快递费…）"', 'note="单头显示值（转账/人民币/研发材料费…）"'),
    ('derivation="details 1 行 cost 求和；与 costs 8 行/banks 4 行及材料 totalCost 四方闭合"',
     'derivation="details 4 行 cost 求和；与 products 18 行 price/banks 4 行及材料 totalCost 四方闭合"'),
]
# costs facts → products facts（整段替换）
old_costs = '''    f_costs = [facts.add_expense(row["fields"]["cost"], source="material_extraction",
                                 layer="detail", category=row["fields"]["project"],
                                 date=row["fields"]["startDate"],
                                 value_extra={key: row["fields"][key] for key in
                                              ("project", "startDate", "endDate", "projectPlace",
                                               "count", "reason")},
                                 locator=locator.format("/tables/costs/{0}".format(index)),
                                 input_hashes=hashes)
               for index, row in enumerate(costs)]'''
new_products = '''    f_products = [facts.add_expense(row["fields"]["price"], source="material_extraction",
                                     layer="detail", category=row["fields"]["code"],
                                     value_extra={key: row["fields"][key] for key in
                                                  ("code", "name", "purchaser", "description")},
                                     locator=locator.format("/tables/products/{0}".format(index)),
                                     input_hashes=hashes)
                  for index, row in enumerate(products)]'''
old_ta = '''    f_ta_relations = facts.add("scope", source="user_instruction",
                               value={"reason": material["table_applicability"]["relations"]["reason"]},
                               locator=locator.format("/table_applicability/relations/reason"),
                               note="空关联表当次来源理由（材料原文）")'''
new_ta = old_ta + '''
    f_ta_costs = facts.add("scope", source="user_instruction",
                           value={"reason": material["table_applicability"]["costs"]["reason"]},
                           locator=locator.format("/table_applicability/costs/reason"),
                           note="空费用说明表当次来源理由（材料原文；rd 范围=费用说明为空）")'''
old_basis = '''    f_basis = [facts.add_no_invoice_basis(fact, reason=waiver, source="user_instruction",
                                          locator=locator.format("/no_invoice_rule"))
               for fact in f_costs]'''
new_basis = '''    f_basis = [facts.add_no_invoice_basis(fact, reason=waiver, source="user_instruction",
                                          locator=locator.format("/no_invoice_rule"))
               for fact in f_products]  # 主表=products（config primary_expense_table）'''
old_empty = '''        {"group": "empty_tables", "field": "relations", "decision": "not_applicable",
         "reason": material["table_applicability"]["relations"]["reason"]},
        {"group": "empty_tables", "field": "details", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 1 行邮寄费预算明细"},
        {"group": "empty_tables", "field": "costs", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 8 行结算明细"},
        {"group": "empty_tables", "field": "banks", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 4 行收款信息"},'''
new_empty = '''        {"group": "empty_tables", "field": "relations", "decision": "not_applicable",
         "reason": material["table_applicability"]["relations"]["reason"]},
        {"group": "empty_tables", "field": "details", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 4 行预算明细"},
        {"group": "empty_tables", "field": "costs", "decision": "not_applicable",
         "reason": material["table_applicability"]["costs"]["reason"]},
        {"group": "empty_tables", "field": "banks", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 4 行收款信息"},
        {"group": "empty_tables", "field": "products", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 18 行现有档案物品（按完整编号选入，不新造档案）"},'''
old_tables = '''            "costs": [{"row_id": row["row_id"],
                       "fields": row_entries("costs", index, row, f_costs[index])}
                      for index, row in enumerate(costs)],
            "banks": [{"row_id": row["row_id"],
                       "fields": row_entries("banks", index, row, f_payees[index])}
                      for index, row in enumerate(banks)],
        },'''
new_tables = '''            "costs": [],
            "banks": [{"row_id": row["row_id"],
                       "fields": row_entries("banks", index, row, f_payees[index])}
                      for index, row in enumerate(banks)],
            "products": [{"row_id": row["row_id"],
                          "fields": row_entries("products", index, row, f_products[index])}
                         for index, row in enumerate(products)],
        },'''
old_applic = '''        "table_applicability": {
            "relations": {"value": material["table_applicability"]["relations"]["reason"],
                          "fact_id": f_ta_relations,
                          "locator": "/table_applicability/relations/reason"},
        },'''
new_applic = '''        "table_applicability": {
            "relations": {"value": material["table_applicability"]["relations"]["reason"],
                          "fact_id": f_ta_relations,
                          "locator": "/table_applicability/relations/reason"},
            "costs": {"value": material["table_applicability"]["costs"]["reason"],
                      "fact_id": f_ta_costs,
                      "locator": "/table_applicability/costs/reason"},
        },'''
more = [
    ('"document_type": "express", "task_id": TASK_ID, "operator": "陈晶",',
     '"document_type": "rd_materials", "task_id": TASK_ID, "operator": "陈晶",'),
    ('"template_value": "快递费(express)", "basis": "缓存快照 submitType=快递费，与请求声明一致"',
     '"template_value": "研发材料费(rd_materials)", "basis": "缓存快照 submitType=研发材料费(11)，与请求声明一致"'),
    ('"template_value": "relations/details/costs/banks 四表（relations 空）", "basis": "express 注册结构+材料空表理由"',
     '"template_value": "relations/details/costs/banks/products 五表（relations+costs 空）", "basis": "rd 注册结构+材料空表理由"'),
    ('"purpose": "授权历史业务回放的 express 真实闭环（round-8，只填不存）"',
     '"purpose": "授权历史业务回放的 rd_materials 真实闭环（round-8，只填不存）"'),
    ('"authorization_path": "originals/replay_express_r8.json",',
     '"authorization_path": "originals/replay_rd_r8.json",'),
]
for old, new in pairs + [(old_costs, new_products), (old_ta, new_ta), (old_basis, new_basis),
                         (old_empty, new_empty), (old_tables, new_tables), (old_applic, new_applic)] + more:
    assert old in d, "MISSING: " + old[:60]
    d = d.replace(old, new)
# 残留检查
for residue in ("expressloop", "replay_express", "f_costs", "cost_sum", "快递费"):
    assert residue not in d.replace("round8-rdloop", ""), "RESIDUE: " + residue
Path("automation/runs/20261024-175000-rdloop/chain_driver.py").write_text(d, encoding="utf-8")
print("rd driver written,", len(d), "chars, all replacements applied")
