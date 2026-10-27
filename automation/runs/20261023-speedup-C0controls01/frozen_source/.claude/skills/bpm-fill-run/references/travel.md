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

关系类型限已观测的“公出单”与“出差单”；`isLast` 为“是”或“否”。页面候选必须按计划的完整编号唯一命中，目标消耗或不可选时报告缺口，不换第一张可用单。预算单、预算科目和银行资料都按每行计划精确核对；不使用“差旅”前缀命中“差旅费”这类旧回归宽松规则。

报销类别 `submitType` 必须显式为配置支持的“差旅费”，不接受旧计划的默认留空。`corpCode` 在 v1 计划中填写已解析的公司显示名称，并与 `applicant.company` 一致；不能把历史 API 公司代码直接写进显示名称计划。

## 支持边界与金额

`header.totalCost`、全部 details.cost、全部 banks.cost 以 Decimal 精确闭合。costs 非空必须声明 `costs=sum`，并指定金额是 `line_total` 还是 `unit_price_times_count`；空 costs 只能显式标记 `not_applicable` 并说明理由。零抵借款之外的借款抵扣、产品表、附件与发票上传不在当前支持范围，不猜出新分支。

原件中的 PDF/图片必须逐个有来源地分类；发票通过复核提取的原件哈希、唯一票号、票面金额及主要费用行分配核对，补贴免票行需本次明确规则证据。部分票面报销和数量乘单价的票据分配当前不支持。具体 image_documents、no_invoice_rows 及 corroborates 结构见 [计划契约](plan-contract.md)。

关联单产生的自动 `detailrels` 通过配置投影核对：与 relations 一一对应、完整 bizNo 对应 bizNumber、bizTypeName 相同、cost 对应 nowCost；bizDetailCost、bizDetailNum、usedCost 必须为零。不支持的分摊、额外行或表必须拒绝，不能忽略后报告成功。

执行器新增各主表行后重新定位，终局快照重新读整个页面，与计划独立比较。可见行数、额外/缺失/重复行、错账号、错误日期和金额、身份以及额外表数据都参与验收。只读带出的资料不符合计划时停止，不强改身份或用输入绕过选择器。

新草稿保存仍需本任务明确授权及专用保存控制器。当前实现已具备离线测试；是否完成真实填写、真实保存，以当次 run 证据为准。没有用户指定本次真实模板与材料，不能用虚构报销完成实单验收。

配置 capabilities 保留各阶段状态：历史模板读取为 historical_evidence_verified（63 单缓存证据），v1 行数组填写与草稿 UI 保存/重开为 offline_validated_production_pending。关系名称的历史观测不等于当前完整新路径已实单验收。第二类型、非零关联明细分摊、借款抵扣、自动恢复未保存页均不应报告已支持。
