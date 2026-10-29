# STATE.md — 当前接手快照

最后核对：2026-10-29。长期规则见[AGENTS.md](AGENTS.md)，当前验收以直接证据为准。

## 当前目标与阶段

- 用户已批准先同步状态/证据，再将既有保存、同单修订及会话复用接入统一正式CLI，验证后选择性本地提交。
- 当前文档/证据同步、选择性提交范围审查及统一CLI已完成；最终离线验收通过，版本边界以当前Git提交及构建摘要为准，未做新增业务首验。
- 本轮不打开OA、不改现有草稿、不改网络、不扩类型；无remote/upstream，不创建remote、不push。

## 最近已证实的结果

1. [10月29日脱敏证据索引](docs/oa-validation-20261029.md)：自驾/快递历史测试草稿保存和独立回读通过，均编制中，用户人工反馈效果不错。
   自驾交通1924.93＋10天餐补300＝2224.93，30费用/3明细/1银行；5天仅按明确模拟授权，关联跳过；同task/UUID修订、原创建journal及原Excel不变。
   快递347.50，8费用/1明细/4银行；研发当前首档案无可选匹配，未保存。未提交/流转，无未知保存，原始工件本地保留。
2. 修订组件10项守卫测试及最终全量571项（567通过/4跳过）、安装后selftest通过；源码哈希见[机器索引](docs/oa-validation-20261029.json)。
   真实调用为兼容入口/临时借用会话组件；最后修订一次会话贯通不等于正式oneshot --task全链验收。原生企微客户端也未验。
3. 本机公司域后缀直连（[验证边界](docs/oa-validation-20261029.md)）已激活并核物理出口/TLS；原认证复用成功，fresh_scan=false，扫码锚点仍10月24日。
   当前刷新值仅按正常helper持久化；不据此重算扫码有效期。公司网关/Clash活动脚本/profile是本机条件，不等于干净机器可移植验收。

本轮统一CLI最终构建：581项，577通过、4跳过，selftest通过；[脱敏构建摘要](docs/unified-cli-acceptance-20261029.json)与源码哈希已冻结，不能替代下一笔真实首验。

## 能力边界与下一步

- [六类成熟度](docs/runbook-maturity.md)：自驾历史基础最深，快递已有测试保存实证，研发保留历史填写成功；外购样品初版，办公/福利仍建设中。
- oneshot已有任务/既定计划分支、授权编译、同context只读副页与锁/驻留回归；尚缺正式任务分支真实材料全链首验，不重建这些组件。
- 同单修订bpm.revision已有原task/UUID/journal/新计划授权绑定与一次真实测试修订；统一CLI路由已按本轮最小接入，禁止换task重建。
- [自驾来源绑定](.claude/skills/bpm-fill-run/references/self-drive-inputs.md)已接plan_generate/validate_plan/load_plan；今天模拟计划无self_drive_coverage，不作为V1全真实来源验收。
- [已知V3 Excel副本回填与重算](feature02-扩展更多单据类型/2026-10-28%20自驾Excel副本回填与重算收尾结果.md)已实现并有真实Excel合成/历史回放证据；不改原件、不加餐补栏。
- 任意原件适配、其他Excel版式、真实同源参与日/逐单金额、全真实餐补、新V1 D12冷启动仍待验证；历史20混合交通行不能直接冒充新V1纯组件来源绑定。
- 下一笔材料齐全的成熟类型业务走正式oneshot：当前完整模板号、本次原件/事实与收款预算依据、明确执行意图、现场真实身份及可用网络。
- 自驾先补完整真实来源和餐补参与日；研发先确认当前可选既有档案。不擅自替代档案，不牵引办公/福利新类型。
- 提交前逐文件审归属与敏感内容；候选不等于可直接stage，私人原件/真实运行转储/认证/profile/订阅均排除，不git add .。

## 历史工程与恢复线索

- V3历史真实解析、Excel、公出裁定、填写和回读成功保留；[终局验收](team-progress/team-workflow/d91601924848489f84e317e68582de26/round-08/acceptance/A-verification.md)不因新增工程暂停而撤销。
- 新V1合同仍有缺口；10月27日workflow 242ccba1…已CANCELLED，不resume、不冒充DONE。旧V3 run已archive，R2未finish。
- 旧R2工件 automation/runs/20261027-121733-cb8b9bd6/ 及首次P2-1/P2-3、D5、manifest历史保留；若另行启动完整施工，按AGENTS合法新任务流程重冻当前哈希，不能改旧registry/合同。
- 历史run 20261027-074251-9d71443f仍是SUCCESS_FILL_ONLY；用户当时手动保存自述与agent当次证据分开，不改写成今日保存。
- [单会话入口施工结果](feature02-扩展更多单据类型/单会话贯通与自动保存接线施工结果.md)、[公共能力调用参考](.claude/skills/bpm-fill-run/references/common-operations.md)保留原验收层次。
- workflow prepare-new退役/归档能力已有隔离测试；当前不重启旧Claude-GLM施工，不动并发handoff/review/team工作文件或GLM配置。
- 原交通单保存曾晚于餐补提醒143.514107秒，错误时间记录原样保留；后续明确模拟授权下已同单纠正，不能倒写历史。
- 恢复任何业务前现场核profile锁、执行者、registry、未保存页、身份和网络；历史状态不证明当前登录仍有效，不强制扫码或恢复旧认证覆盖新状态。
