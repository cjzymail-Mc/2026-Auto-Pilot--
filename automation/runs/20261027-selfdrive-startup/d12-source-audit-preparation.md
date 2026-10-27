# D12 来源读取链只读调查（协调工程资料）

用途：原生 A 后续自足派工/独立核查的准备资料；不是 D12 阶段一输入包、不是新增人类授权、不是动态通过证明。来源为 `/root/skill_review` 本地只读代码调查，无 OA、凭证、会话记录或 registry 访问，无测试/业务执行/文件修改。行号为调查时定位，后续以最终冻结源码为准。

## 当前真实代码行为

- `automation/business-scenarios/self_drive.json` 的 `rule_source.contract` 仅是来源标识。`bpm_self_drive.load_self_drive_rules` 读取配置并校验字符串非空，不沿它打开合同；返回规则和 user_rule_statement，不返回合同正文。`rules_sha256` 只哈希配置，不是合同哈希。
- `bpm_plan.validate_plan` 的 `test_context.authorization_path` 经 `_proof_path` 后由 `file_hash` 二进制读取比对哈希，不解析授权正文。若绑定合同/旧证据，确实发生程序读取，不能宣称完全未读，但这本身不向生成模型返回正文。
- 同一验证器的模板/材料 manifest 会先哈希再解析 JSON，manifest 还展开材料来源。逐值 sources/corroborates 经 `bpm_materials.read_locator` 读取 JSON/CSV/XLSX 的定位值，直接参与业务判断；这不属于 hash-only。
- `bpm_template.cached_template` 会解析整个 census 再挑指定单号，返回该单归一化内容。D12 应使用允许的真实定向读取或本次快照，不能把旧大 census 当无答案材料。
- `fill_once` 加载计划、`StructuredProbe` 执行前会重新校验来源；`fill_once` 还会对构建 CODE 清单（含 AGENTS/README/skill）计算哈希，返回路径和哈希而非文档正文，不会为此执行构建测试。
- `bpm_chain` 当前历史测试的 authorization_path 绑定材料 JSON；该材料同时还被当业务输入解析，不能只按授权哈希文件登记。
- `automation/prepare_type_replay_test.read_authorization` 是显式历史回放辅助入口，解析授权 JSON 并拒绝保存/提交，不是 fill_once 自动调用的授权解析路径。

## 需在后续 D11/计划集成中补核的现状

`bpm_plan.validate_plan` 的 `oa_test_relations` 当前只检查声明、enumeration_path/hash 格式、索引和关联行引用，没有打开枚举路径核对内容哈希。不能把现有字段格式校验表述成当次枚举内容已经核实。后续将真实占位选择、真实匹配严格分离时，应在原范围内补足实际来源/哈希/集合验证与负例，继续保持 fill_only、同任务绑定、真实可选枚举和既有 registry 保护。

## D12 输入与读取审计必须分别登记

1. 给模型的正文输入必须无答案；合同、STATE、旧计划、旧解析和旧匹配不得作为业务事实来源。程序对授权/源码/构建清单的 hash-only 读取应提前声明实际路径、用途及不回传正文的机制，不能事后声称零读取。
2. 无答案授权摘录应由独立准备方据本次真实授权制作，保留原来源绑定和必要测试边界；不能用一个旧合同哈希创造许可，也不能关闭来源验证来回避污染。
3. 启动前展开最终计划的 sources、corroborates、模板、manifest、提取 JSON 及依赖路径/哈希。只审模型 Read 不足以覆盖 Python 间接读取；出现非白名单旧派生值参与事实生成即停止该次冷启动。

这份调查未实施修复，也未对任何最终计划或冷启动签字；原生 A/B 仍须在正式入口完工后据最终产物核实。
