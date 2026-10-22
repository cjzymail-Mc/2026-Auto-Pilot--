# -*- coding: utf-8 -*-
"""form-schema.json v0.1 → v0.2 收敛（temp.md P3 规则 + attempt_023 实测回填）。
只把 023 实测命中(match=true)的字段标 VERIFIED 并附证据指针；未测项保持 PENDING，
可写性用 READ_ONLY/WRITABLE/UNKNOWN 枚举，斜杠合并条目拆分。"""
import io, json

P = "automation/form-schema.json"
EV = ("run 20261021-131724-1c1aadbd attempt_023 evidence/fill_readback.json"
      " + fill_final_grid.json")

d = json.load(io.open(P, encoding="utf-8"))

d["$schema_note"] = (
    "字段规则 v0.2（2026-10-22 收敛）。v0.1 依据 astra §5 初稿；v0.2 按探针实测"
    "（run 20261021-131724-1c1aadbd，attempt_023 新建报销单只填不存，28/32 项回读匹配）"
    "回填定位方法与可写性。表面结论：Web 表单为 Angular PrimeNG DOM（p-table/p-dropdown），"
    "无 iframe/无 canvas；表头字段 label[for=name] 解析；表格按 caption 文本 + thead prop-* "
    "列头定位；选择类字段=单元格点击弹表（footer 确定/取消），选择后回显格只读带出。"
    "VERIFIED 仅指实测通过；未测项保持 PENDING，绝不禁 default-to-pass。")
d["version"] = "0.2"

d["doc_identity"]["list_url_pattern"] = (
    "https://bpm.qiaodan.com/oa/reimburses（列表页，P2 扫码后实测核实；v0.1 误写 /oa/reimburse）")
d["doc_identity"]["form_url_pattern"] = (
    "新建走 UI 入口（首页『新建报销单』按钮，attempt_023 实测）；?type=new URL 直开未测")

d["doc_identity"]["blocks"] = [
    {"key": "link_detail", "name": "关联单据明细", "web_caption": "关联单据",
     "web_props": ["bizNumber", "是否为一次性(列)"],
     "columns": ["序号", "单据类型", "单据号", "已报销", "本次报销", "是否为一次性"],
     "verified": EV},
    {"key": "reimburse_detail", "name": "报销明细", "web_caption": "报销明细",
     "web_props": ["reimItem"], "columns": ["序号", "报销项目", "摘要", "预算部门",
     "预算单", "预算科目", "预算项目", "报销金额"], "verified": EV},
    {"key": "expense_note", "name": "费用说明", "web_caption": "费用说明",
     "web_props": ["project", "reason"], "columns": ["序号", "费用类型", "开始日期",
     "结束日期", "地点", "天数/次数", "金额", "项目说明(列 prop-reason)"], "verified": EV},
    {"key": "bank_info", "name": "银行信息", "web_caption": "银行",
     "web_props": ["payee"], "columns": ["序号", "收款人", "账号", "开户行(只读带出)",
     "联行号", "转账金额", "备注"], "verified": EV},
]

cats = d["categories"]

def fset(cat, key, **kw):
    for f in cats[cat]["fields"]:
        if f["业务键"] == key:
            f.update(kw)
            return
    raise KeyError(f"{cat}/{key}")

# C1：机制实测（表头 label[for=name]），值比对未执行 → 只升定位不升回读
for k in ("制单人", "部门", "公司"):
    fset("C1_系统自动带出项", k,
         定位方法=f"VERIFIED(机制：表头 label[for=name]→input，{EV})；值比对本次未执行",
         前置条件="登录态有效（企微 CorpApp QR SSO，session_state.json TTL≈4h）")

# C3：023 两行全匹配
fset("C3_普通文本_日期_金额", "报销明细.摘要",
     定位方法=f"VERIFIED(行内编辑，fill→blur→回读匹配；{EV})", 可写="WRITABLE")
fset("C3_普通文本_日期_金额", "费用说明.开始日期",
     定位方法=f"VERIFIED(date 输入，两行 2026-09-22 回读匹配；结束日期列同法；{EV})",
     可写="WRITABLE")
fset("C3_普通文本_日期_金额", "费用说明.次数天",
     定位方法=f"VERIFIED(天数/次数列，1 回读匹配；{EV})", 可写="WRITABLE")
fset("C3_普通文本_日期_金额", "费用说明.金额",
     定位方法=f"VERIFIED(60.00/191.40 数值等价匹配；{EV})", 可写="WRITABLE")
fset("C3_普通文本_日期_金额", "费用说明.项目说明",
     定位方法=f"VERIFIED(列 prop-reason；表头级『项目说明/行程说明』字段 DOM 实证不存在"
             f"——模板值由此列承载；{EV})", 可写="WRITABLE")
fset("C3_普通文本_日期_金额", "关联单据明细.本次报销",
     定位方法="PENDING(023 未填此列，保持 0.00)")

# 拆分 v0.1 斜杠合并条目
for f in cats["C3_普通文本_日期_金额"]["fields"]:
    if f["业务键"] == "关联单据明细.备注 / 报销明细.报销金额 / 关联单据明细.摘要_数量_备注":
        f.update({
            "业务键": "关联单据明细.摘要 / .数量 / .备注（拆分自 v0.1 合并条目）",
            "可写": "UNKNOWN", "定位方法": "PENDING(023 未填；类型隔离规则同上)",
            "$split_note": "v0.1 曾把 报销明细.报销金额 与本组合并；报销金额已单列下方",
        })
        break
cats["C3_普通文本_日期_金额"]["fields"].append({
    "业务键": "报销明细.报销金额", "区块": "报销明细", "行身份": "按行", "类型": "decimal",
    "可写": "WRITABLE",
    "定位方法": f"VERIFIED(191.40 数值等价匹配；{EV})", "前置条件": "行已定位",
    "回读规则": "十进制定点比对（不做 float 相等）", "失败处理": "回读不符 → 停"})

# C4：选择器类全部实测
fset("C4_下拉_人员_部门_科目选择器", "报销明细.报销项目",
     定位方法=f"VERIFIED(单元格点击→『选择表格数据』弹表→模板原词白名单命中行→footer 确定"
             f"→回显提交；通行费 实测；{EV})",
     前置条件="弹表可开且选项唯一匹配（绝不盲选）", 可写="WRITABLE")
fset("C4_下拉_人员_部门_科目选择器", "报销明细.科目余额",
     定位方法="PENDING(Web 表报销明细列头未见此列；IA2 快照有——两表面列集差异待核)",
     可写="UNKNOWN")
fset("C4_下拉_人员_部门_科目选择器", "费用说明.费用类型",
     定位方法=f"VERIFIED(prescan 弹表白名单确认，伙食/其它交通 两行实测；{EV})",
     可写="WRITABLE")
fset("C4_下拉_人员_部门_科目选择器", "支付方式",
     定位方法=f"VERIFIED(p-dropdown 选项列表匹配转账；{EV})",
     前置条件="登录态有效", 可写="WRITABLE")
cats["C4_下拉_人员_部门_科目选择器"]["fields"].append({
    "业务键": "单据头.关联公出单", "区块": "单据头/关联单据明细", "行身份": "按行",
    "类型": "selector(两段式)", "可写": "WRITABLE",
    "定位方法": f"VERIFIED(类型下拉选『公出单』→单据选择弹表(列:单据状态/申请日期/单据编号"
               "/申请人/公出事由)→行点击高亮→确定→回显提交；12026075605 实测；thead 伪行须跳过、"
               "弹表搜索只匹配单据编号；{EV})",
    "前置条件": "目标单据未被一次性关联消耗；消耗后换选需用户显式授权（023 即此情形，留痕 note）",
    "回读规则": "关联单据表行文本含所选单据编号且 是否为一次性=是",
    "失败处理": "无命中行 → 守卫式关闭弹窗，绝不点表头/空行顶替"})
cats["C4_下拉_人员_部门_科目选择器"]["fields"].append({
    "业务键": "报销明细.预算联动四列(预算部门/预算单/预算科目/预算项目)",
    "区块": "报销明细", "行身份": "按行", "类型": "selector(链式弹表)+readonly 回显",
    "可写": "READ_ONLY(回显格不可键入；由链式选择带出)",
    "定位方法": f"VERIFIED(选预算单弹表(候选迭代:15625120075 日常费用预算)→预算科目弹表"
               "(模板词差旅白名单，命中差旅费)→四列联动带出 科技中心/15625120075/差旅费/年度预算项目；{EV})",
    "前置条件": "预算弹表可开；科目表须含模板词命中的科目，否则留空留审(SUBJECT_MISS_NOTED)",
    "回读规则": "四列终读与模板词前缀包含比对（差旅→差旅费，_budget_pick 白名单同口径）",
    "失败处理": "候选预算单科目表均无模板词 → 不选非差旅科目顶替，记 SUBJECT_MISS_NOTED"})

# C5：通用行定位规则实测
fset("C5_表格单元格", "通用行定位规则",
     定位方法=f"VERIFIED(表容器=p-table[ caption 文本]；列=thead td[prop-* 或列头文本匹配"
             "→列索引运行时解析；行=tbody tr 序号+『新增』按钮加行后重确认；{EV})",
     可写="WRITABLE")

# C6：银行区实测
fset("C6_银行信息", "银行信息.收款人",
     定位方法=f"VERIFIED(新建单系统按登录人预填 陈晶，回读核对匹配，未键入；{EV})",
     可写="WRITABLE")
fset("C6_银行信息", "银行信息.账号",
     定位方法=f"VERIFIED(随收款人系统预填，全串回读匹配；键入路径未走；{EV})",
     可写="WRITABLE")
fset("C6_银行信息", "银行信息.开户行",
     类型="text(readonly 回显)",
     定位方法=f"VERIFIED(系统自动带出 中行，只读不可编辑；{EV})", 可写="READ_ONLY")
fset("C6_银行信息", "银行信息.联行号",
     定位方法="PENDING(模板未含值，023 未填)", 可写="UNKNOWN")
fset("C6_银行信息", "银行信息.转账金额",
     定位方法=f"VERIFIED(251.40 数值等价匹配；{EV})", 可写="WRITABLE")

# C7：明确未授权
fset("C7_附件", "附件上传", 可写="UNKNOWN",
     定位方法="PENDING(上传属 OA 写入高危动作，本轮零授权未测)")

d["pending_verification"] = [
    "报销明细合计(报销金额合计)回读与重算比对（023 未回读合计）",
    "科目余额列在 Web 表的存在性（IA2 快照与 Web 表面列集差异）",
    "联行号/关联单据明细.摘要·数量·备注 的填写路径（模板未含值或未填）",
    "『复制金额到本次报销金额』按钮语义与安全性（未测）",
    "附件上传（未授权，PENDING）",
    "表头 报销类别(submitType)：表单字段但模板未含值——FORM_FIELD_NOT_IN_TEMPLATE，留用户终审",
    f"以上 VERIFIED 证据：{EV}；截图 attempt_023/evidence/fill_99_after.png；"
    "浏览器保留在场待人工审核（只填不存）",
]

io.open(P, "w", encoding="utf-8").write(
    json.dumps(d, ensure_ascii=False, indent=2) + "\n")
print("v0.2 written; VERIFIED entries:",
      sum(1 for c in d["categories"].values() for f in c["fields"]
          if str(f.get("定位方法", "")).startswith("VERIFIED")))
