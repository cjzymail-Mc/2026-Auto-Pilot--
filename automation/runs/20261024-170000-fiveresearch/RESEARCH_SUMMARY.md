# 五类只读研究 run 总结（2026-10-24 17:00）

## 合同执行对照（round-7 ctr-381e0163 研究项）

- raw fetch 预算：合同 ≤5 次单发；**实际 CLI 调用 3 次**（15426101596 首发在转储层 Decimal 序列化缺陷失败、重试成功；15426071883 一次成功），全部 `--login-wait 0`、`--expect-name 陈晶`（当次登录探查身份）、captured_exact_list_identity 锚定 census 20261023-142146。
- 只读纪律：仅枚举 UI 查询 + observed GET；零注册、零启用、零写页面、零编辑页导航。
- 顺带修复（合同允许域）：`bpm_template.py` raw 转储 Decimal 序列化缺陷（`_json_default`，仅 Decimal→精确十进制文本，其余类型拒绝）；`tests/test_bpm_template.py` 增强断言（8/8 绿）。

## 产出

| 工件 | 内容 |
|---|---|
| raw_15426101596_dijiazhi.json | 低值办公（02）原始 main/children（sha 86bf99de…） |
| raw_15426071883_fulilabao.json | 福利劳保（04）原始 main/children（sha 54456f5f…） |
| research_dijiazhi_15426101596.md | 工件 1/2：结构/字段/差异/规则草案/能力清单/类型码 |
| research_fulilabao_15426071883.md | 工件 2/2：同上六节 |

## 核心结论

1. **类型码证据链闭合**：08 差旅 / 11 研发 / 15 快递 / 02 低值办公 / 04 福利劳保，五码两两互异且全部来自实测工件。
2. 主表 57 键五类同形——类别差异全部在子表形态与代码层。
3. 福利劳保 costs 全空 → primary=details（佐证现有 `_primary_table` 规则）。
4. 两类均文档级 `invoice=false`；低值办公 detailrels 非零绑定、福利劳保零金额——关联层需两种形态。
5. 低值办公 banks 三收款人分摊精确闭合（4856.75+3597.00+1521.01=9974.76）。
6. reimItem 前缀与 submitType 同源（02→02001、04→04003，双样本模式）。
7. 接入共享能力缺口集中在：类别码注册、reimItem/预算枚举来源、预算选择器（含跨部门）、文档级免票通道、detailrels 支持。

## 缺口（如实登记，不阻塞本轮）

- 编辑器联动未观察（合同零导航零点击）；reimItem/budget 枚举来源未捕获；genreId 语义未知；两类均单样本。
