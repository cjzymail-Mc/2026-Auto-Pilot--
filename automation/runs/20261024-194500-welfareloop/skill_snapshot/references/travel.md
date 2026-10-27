# 差旅分支：精确模板、行数组及独立验收

执行配置为 `automation/document-types/travel.json`。历史 `automation/form-schema.json` 只作结构参考；配置的 API 属性名、中文标签及编辑类型才是 v1 执行入口。API 枚举代码不等于页面显示名称，不把历史代码自动映射成猜测标签。

## 模板读取

有既有历史采集工件时，只从中挑唯一完整单号，校验主单 UUID 与每张子表的所属 UUID：

```powershell
python -X utf8 bpm_template.py --census "既有travel_census.json" --template-number "完整单号" --output "automation/runs/独立准备run/template_snapshot.json"
```

输出必须是 `automation/runs/` 内的新文件，标明 cached 来源及原采集文件哈希；这不是当前页面的新鲜核实。快照 `representation` 明确 API 代码需要当前显示解析。需要当前定向读取时使用：

```powershell
python -X utf8 bpm_template.py --live --expect-name "操作人" --template-number "完整单号" --output "automation/runs/独立准备run/template_snapshot.json"
```

live 路径取得同一 profile 执行锁，在独立临时 Chromium context 内注入内存中的登录态，不导航或关闭恢复的原页。列表通过完整单号精确查询，只取唯一命中 UUID，再由 `fetch_template(probe, number)` 读取已观察到的 GET 主表和子表；不要自拼接口或另起并发执行者。必要时传 `--login-wait` 等待人工扫码。无法取得明确模板就报告缺口。

模板保留完整单号、UUID、captured_at、来源及快照哈希。允许复用且已核对的稳定值包括申请人/公司/部门、支付方式、预算和收款资料。单据 UUID、旧单状态、旧发票、旧日期和旧金额不复制成新单事实。模板中费用项目的写法可作候选，但本次费用必须另有本次材料来源。

## 四张主表

| 计划表 | 页面标题 | 必填字段 |
|---|---|---|
| relations | 关联单据 | bizTypeName、bizNumber、nowCost、isLast |
| details | 报销明细 | reimItem、digest、budgetDeptName、budgetNo、subjectName、budgetItemName、cost |
| costs | 费用说明 | project、startDate、endDate、projectPlace、count、cost、reason |
| banks | 银行信息 | payee、account、bank、bankCode、cost |

每张表是 `{row_id, fields}` 行数组，支持多行计划及独立核对。金额字符串最多两位小数；账号、银行联行号、预算单号、关联单号必须是字符串，不进行数值归一。日期严格 ISO `YYYY-MM-DD`。

历史观测名称有“公出单”与“出差单”，当前正式执行范围仅“公出单、一对一关联明细”；出差单及一对多分配先报告未支持。`isLast` 为“是”或“否”。页面候选必须按计划的完整编号唯一命中，目标消耗或不可选时报告缺口，不换第一张可用单。预算单、预算科目和银行资料都按每行计划精确核对。

报销类别 `submitType` 必须显式为配置支持的“差旅费”，不接受旧计划的默认留空。`corpCode` 在 v1 计划中填写已解析的公司显示名称，并与 `applicant.company` 一致；不能把历史 API 公司代码直接写进显示名称计划。

## 支持边界与金额

`header.totalCost`、全部 details.cost、全部 banks.cost 以 Decimal 精确闭合。costs 非空必须声明 `costs=sum`，并指定金额是 `line_total` 还是 `unit_price_times_count`；空 costs 只能显式标记 `not_applicable` 并说明理由。零抵借款之外的借款抵扣、产品表、附件与发票上传不在当前支持范围，不猜出新分支。

原件中的 PDF/图片必须逐个有来源地分类；发票通过复核提取的原件哈希、唯一票号、票面金额及主要费用行分配核对，补贴免票行需本次明确规则证据。部分票面报销和数量乘单价的票据分配当前不支持。具体 image_documents、no_invoice_rows 及 corroborates 结构见 [计划契约](plan-contract.md)。

已声明的 `detailrels` 先核对存在性、列表类型及期望行数，空表也参与比较。当前一对一分支核对完整 bizNo、bizTypeName、cost 与计划关联一致；bizDetailCost、bizDetailNum、usedCost 为数字零，或在公出单分支、列实际只读且原始显示为精确空字符串时按配置的 readonly_zero 显示规则处理。依据是已保存样张 15426104612 的新鲜只读页面与 API 对照，见 automation/runs/20261023-speedup-preparation/attempt_001/evidence/protected_saved_sample.json。缺列、缺只读证据、未知类型、格式错误和非零分摊均拒绝；不把原始空值转为数字零。重复/额外明细、一对多分配与其他未支持表均不能放行。

执行器新增各主表行后重新定位，终局快照重新读整个页面，与计划独立比较。可见行数、额外/缺失/重复行、错账号、错误日期和金额、身份以及额外表数据都参与验收。只读带出的资料不符合计划时停止，不强改身份或用输入绕过选择器。

新草稿保存仍需本任务明确授权及专用保存控制器。提速方案第 2.1 节已允许复用已确认示范数据做真实未保存控件与整单回归，这类测试明确标记，不冒充真实新费用，也无需另找正式业务才能测试。已保存样张只读保护，新测试单禁止保存。正式入口 C0 已完成 3/2/6/1 行的严格真实回读；C0/C1 源码、配置、计划和结果分别留证。

配置 capabilities 区分已授权真实测试填写、历史缓存证据和真实保存待验收。关系名称的历史观测不等于全部关联分支已实单验收。快递与研发材料使用各自配置和参考资料，不能从差旅证据推定其实单验收。travel.json 中原第二类型历史能力备注为保持旧任务配置哈希保留，当前类型支持范围以封闭注册及各类验收记录为准。非零关联明细分摊、借款抵扣、自动恢复未保存页仍未支持。
