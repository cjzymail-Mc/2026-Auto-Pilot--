# V3-R07 CASE-07 B5 —— 新鲜 DOM 独立回读全量 diff 报告（可读版）

生成：2026-10-26 18:5x（B 窗口，round 7，合同 ctr-affef776 冻结范围 3–4）
机器版：`b5-diff-summary.json`（sha256 `7400d428…`，同目录）；原始证据在 `automation/runs/20261026-183000-v3r07-fill/`。

## 执行身份与输入绑定

- 正式入口：`fill_once.py --fill-plan <v1.1> --expect-name 陈晶 --run 20261026-183000-v3r07-fill --keep-open-minutes 15`，attempt_001，18:29:39 锁 profile → 18:34:50 `SUCCESS_FILL_ONLY`（tech 309.5s）。
- 执行输入 `input_plan_snapshot.json` sha256 **与 v1.1 变体文件字节相同**（`6c9d1b6f…`）；plan_hash `8eea9c05…` 已绑 registry journal（sha256(task_id)→FORM_INTENT）。
- 登录/身份：entry LOGGED_IN，operator=陈晶；页面 applicant=陈晶/厦门乔丹科技有限公司/运动表现研究部，appliedBy=116070053——与计划 operator/applicant 一致。
- 页面状态：`/oa/reimburse?type=new` 新建页、is_new=true、bizStatus=编制中、**bizNumber 与 uuid 均为空**（未保存的预期状态，本轮不验收保存）。

## 四表行数与全量 diff（额外/重复/缺失）

| 表 | 计划 | 实测 |
|---|---|---|
| relations | 1 | 1 |
| details | 2 | 2 |
| costs | 20 | 20 |
| banks | 1 | 1 |

- 独立核验 `independent_verification.json`：**ok=true，issues=[]**；全部计划值逐字段核对通过；额外/重复/缺失 = **0 / 0 / 0**。
- completeness 六区全 true（header/relations/details/costs/banks/detailrels）；invalid_fields=[]、pending=false。
- 回读快照 `independent_readback.json`（sha `868a920d…`，snapshot_hash `59a08d4c…`）为填写完成后独立读取路径重采的 DOM 全量。

## 金额各层复算 == R

- details 合计 = costs 合计 = banks 合计 = totalCost = **1924.93**，四向 == R（R_reimburse=1924.93，coverage F=2518.10>R 复验见 181500 run events 18:26:51）。

## 随机测试占位关联（单独一节，V3 §5.3）

- 候选来源：真实关联控件 relation dialog 默认首屏枚举（attempt_002，18:22:20，20 行/共 76 条，未翻页未检索；titlebar X 关闭，selection_performed=false，bizNumber_after_close=""——枚举本身零选择零副作用）。
- 随机方法与种子：`random.Random(seed).randrange`，seed=`6074a75771428d7e` = sha256("20261026-180546-c1c5d877-case07")[:16]（team_run 派生，先验提交，先于查看枚举）；chosen_index=6/20 → **12024070132**（陈晶 2024-07-01 项目跟进，状态结束）；排除项 12026096668 核验不在候选（0 命中）。
- 真实写入：relations/0/bizNumber picker_open 18:30:01 → picker_select_confirm 18:30:03（真实弹窗、精确单号唯一命中、行选择+确定——picker 确认为守卫允许的选取确认，非保存类）。
- 读回：bizTypeName=公出单、bizNumber=12024070132、nowCost=1,924.93（只读，系统按关联带出，数值==1924.93）、isLast=是。
- **带出字段零覆盖核查**：占位带出的系统只读字段 bizCost=0.00、totalReimedCost=0.00、description=陈晶(2024-06-24)；detailrels 投影唯一行 bizNo=12024070132、cost=1,924.93，其余（digest/bizDetailCost/bizDetailNum/usedCost/description）均为只读空白。costs 20 行与四向金额复算不受影响——**占位值零覆盖真实费用**。
- 分离声明：与 `actual_trip_matches`（automation/runs/20261026-143340-v3r04-case03/，12 MATCHED/15 NO_MATCH）两套数据分开建模、核验、报告；占位对象仅为 fill_only 测试占位，零冒充；模板旧单关联未动，未重新占用 12026096668；未观察到选择动作产生即时持久占用（页面始终编制中、无单号无 UUID、可干净关闭）。

## 零保存证据

- save_status=NOT_ATTEMPTED；保存/提交/发送/流转/上传/暂存/贴票/审批类点击 **0 次**；未知弹框零自动确认。
- keep_open 15 分钟（18:34:50→18:49:50）零业务动作；`own_test_page_close` unsaved=true、save_attempted=false；registry journal state=FORM_INTENT（无 SAVE_INTENT/SAVE_UNCERTAIN）。

## 证据索引（哈希）

| 工件 | sha256（前16） |
|---|---|
| fill-plan-v11.json（181500）/input_plan_snapshot.json（183000，同字节） | 6c9d1b6fd719124e |
| stage1_result.json | 6ef51f876152dd7a |
| independent_readback.json | 868a920d1c0310b1 |
| independent_verification.json | 170cbdb5d182240c |
| v1_relations_after.png | 7de5a12b9e44c6c2 |
| v1_final.png | f2705d97790c28fa |
| events.jsonl（183000） | d30ec412e4ce723f |
| relation_enumeration.json（attempt_002） | 369a47938da2215e |
| case07-task-material.json | 08767578dcb057c4 |
| b5-diff-summary.json | 7400d42839377786 |
