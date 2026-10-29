# 自驾新规则：来源证明与正式计划绑定

这是供agent使用的内部接口，不要求用户编写JSON。用户仍只提供完整模板号、本次原件/公里表和执行意图。V3旧模型及冻结证据不变；本接口用于V1含餐补模型，当前验证层次以[结果记录](../../../../feature02-扩展更多单据类型/2026-10-28%20自驾来源绑定与新入口离线收尾结果.md)为准。

## 正式调用路径

1. 继续使用 `bpm.materials` 的材料清单、复核提取和双根派生登记。Excel公里/date/route通过精确单元格来源读取；票面用复核提取JSON，不以文件名代替事实。原件不改。
2. agent形成来源包：每条proof恰为 `path/locator/sha256`，所指文件必须属于本材料manifest，源文件字节哈希现场重算。保护目录（包括 `.pw-profile`、`.local-session`、`.git`、`legacy-ia2`）不可作为来源。相对proof路径按manifest所在目录解析。
3. 来源包本身先登记进同一manifest，再用正式离线入口：

```powershell
python -X utf8 -m bpm.self_drive_plan --inputs "来源包.json" --manifest "manifest.json" --output "独立新输出目录"
```

成功返回 `SCENARIO_PREPARED_OFFLINE`，写入 `self_drive_assessment.json`。不打开OA，不代表已填写/已保存；输出目录须全新且不与输入树嵌套。缺来源、冲突或覆盖不足返回 `NEEDS_INPUT`，不产生半成品输出。

4. 既有事实/蓝图生成仍走 `generate_fill_plan`。蓝图可包含 `self_drive_coverage`，其副本进入最终计划；油票仅作为覆盖凭据，用 `self_drive_image_documents` 携带已有image_documents格式的逐record有源排除，禁止将油票分配给费用。通行票仍走普通invoice_extractions/分配链，不绕过reconcile或材料全额校验。
5. `validate_plan`/`load_plan`每次重读来源包及全部proof、加载冻结规则、重算金额，并与最终计划逐费用组件/日期/行数/逐单金额核对；现有fill_once、oneshot及保存前复核沿用该入口，无需另一套执行器。旧无 `self_drive_coverage` 的V3计划保持原行为。

## 来源包形状（schema_version=1.0）

- `creator`：proof指向一个同源JSON对象 `{name, employee_id, department}`，不是本机会话元数据文件。
- `scope_dates`：proof指向本次范围的唯一ISO日期数组。不可从模板旧区间推导。
- `trips`：proof数组；每个locator指向**同一事实行** `{biz_number,date,route,participants}`，participants为 `{name,employee_id}` 数组。用人员精确工号、同一事实日和明确路线核对；不拼接不同事实行。不识别任意旧格式，若原始观测未形成可核对的同源事实行则报告适配缺口。
- `rows`：数组，每条 `{row_id,date,km,route,toll_ids}`；前三个业务值date/km/route均为proof，toll_ids引用本次唯一票据ID。按日期/路线/制单人精确匹配唯一公出单；多个候选不自动选择。
- `invoices`：数组，每条 `{invoice_id,kind,number,amount,date}`；四业务值均为proof，kind为toll/fuel。必须指向同一复核record，number应为精确字符串；不能把不同扫描拼成一张票。最终计划必须分类并引用相同的reviewed_extraction record，未分类或油票被当费用均拒绝。
- `meal_assignments`：数组，每条 `{date,trip_number}`，覆盖“本次范围∩真实制单人同一事实行已参与日”恰好一次；同日多单只计一次，归属一张确实参与的公出单，不能缺省零餐补。

来源包不包含旧案例答案、固定人员或固定金额。该接口核验来源/规则/计划的一致性，不能自行证明线上原件观测的真实性；agent仍负责实际观测和独立复核。

## 计划扩展键

`self_drive_coverage` 恰含 `schema_version/rules_version/rules_sha256/inputs/cost_bindings`。inputs恰为来源包 `path/sha256`（路径按计划base_dir解析），文件必须在同材料manifest。规则从既有self_drive.json加载且现场校验版本和哈希，不改该冻结配置来迁就计划。

cost_bindings为“组件ID→实际费用金额pointer”的映射：`km:<row_id>`、`toll:<row_id>`、`meal:<ISO日期>` 分别对应 `/tables/costs/N/fields/cost`。当前支持**拆分的纯组件费用行**，每项正金额一行、同日开始/结束、count=1、line_total；穷尽且无重复地覆盖全部费用行。公里/餐补行保持有源政策免票理由，通行票只分配给通行费组件，油票只进入覆盖池。混合交通行不能整体伪称免票；未建模的混合行输入先停止，不自动重排真实业务。

输入重算的R须等于主金额、明细/费用/银行各层合计；正常关联按真实公出单逐单分配，局部差额即使正负抵消也拒绝。已有受限占位仍只能fill_only，真实匹配分配独立重算，不扩大占位授权。`coverage`和新键不能同时存在。

当前身份分支要求制单人=申请人且有精确工号；代办/不明确人员映射是待输入/适配缺口，不能换人凑金额。真实页面选择器、实际同源公出数据格式、其他Excel版式、D12新会话实用验收与保存闭环仍须按当次材料验证（已知V3版式的正式副本回填/真实Excel引擎见下节）。新子进程合成测试不冒充D12真实验收。


## 已知V3版式Excel的正式副本回填

`bpm.self_drive_workbook`已复用V3的F/G/H/I版式和独立Excel COM重算策略。agent先形成完整来源包和内部“row_id→工作表行号”映射（不让用户编写）：

```powershell
python -X utf8 -m bpm.self_drive_workbook --inputs "来源包.json" --manifest "manifest.json" --workbook "公里原表.xlsx" --row-map "内部行映射.json" --output "全新独立输出目录"
```

`--sheet`默认为“汇总”。只接受原件manifest内的xlsx、F3/G3/H3/I3已观测表头和原有I列SUM总计，穷尽数据行并核对公里proof=该F单元格。原G补贴值与规则冲突或已有H金额冲突会停止，不直接改原值。只在副本写H和I公式；餐补另列核算，不扩原表结构。独立隐藏Excel实例禁宏/事件/外链更新，不接管用户Excel；保存关闭后，用新读取的公式与缓存逐行Decimal复核，并核对非授权单元格、源文件和输入哈希。成功仅为 `WORKBOOK_VERIFIED_OFFLINE`；引擎缺失/未知版式/漂移/无缓存均NEEDS_INPUT，不能用程序自报代替实际重算。

详见[Excel收尾结果](../../../../feature02-扩展更多单据类型/2026-10-28%20自驾Excel副本回填与重算收尾结果.md)。该本地接口不打开OA，不代表D12或真实填写/保存已通过。
