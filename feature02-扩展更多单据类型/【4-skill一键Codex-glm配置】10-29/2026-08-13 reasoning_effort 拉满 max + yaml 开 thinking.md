# codex-glm 配置对齐：reasoning_effort 拉满 max + yaml 开 thinking（2026-08-13）

> 性质：本分发包的更新记录。把 skill 包对齐到 live `~/.codex-glm` 的最新一改（2026-08-13 codex 改的），使「拷给同事跑一个 install」即拿到与本机等价的 reasoning 配置。

## 为什么更新

2026-08-13 codex 把 live `~/.codex-glm` 的 reasoning 强度统一拉满到 `max`，并给 LiteLLM 翻译桥显式开启 thinking。这次改的是**主对话模型（glm-5.2）**的推理强度，与 8/10 那次「补无人值守权限三件套」是不同维度的改动。包里的 config 模板落后这一改，同事装完拿到的是旧的 `high`。

## 改了什么

| 文件 | 改动 | 改前 → 改后 |
|---|---|---|
| **`codex-glm-config.toml`** | 主对话推理强度拉满 | `model_reasoning_effort = "high"` → **`"max"`** |
| **`litellm/glm-config.yaml`** | glm-5.2 段显式开 thinking + 锁 max | 仅 `api_key` → 补 `temperature: 1.0` + `extra_body.thinking.type=enabled` + `reasoning_effort=max` |

两处改动**互相对齐**：config.toml 的 `model_reasoning_effort=max`（codex 侧）与 yaml 的 `reasoning_effort: max`（z.ai 侧）是同一意图的两端，缺一端会被另一端的兜底值拽回去，所以必须同改。

## install 脚本怎么消费

install 第 6 步直接 `Copy-Item codex-glm-config.toml → ~/.codex-glm/config.toml`（install-codex-glm.ps1 line 241-243），litellm 段同理走 line 216 的 `$triplet` 拷贝。所以 repo 里这两个文件是 install 的**唯一真相源**——本记录改的是真相源，同事重装即拿到 `max`。

## 没动的（确认过有意保留）

- **`agents/mc-expert.toml`** —— 陪审子代理的 `model_reasoning_effort` 仍为 **`high`**，母本（Mc-Expert-repo/.codex-glm/agents/，live `~/.codex-glm/agents` junction 指向它）和包内副本都是 high，8/13 codex **没碰它**。
  - **为什么不跟主对话拉满 max**：mc-expert 的 `model` 不固定，注释明写「inherit session model so glm (glm-5.2) and gpt (gpt-5.6-sol) both work」——它**继承调用方的 session 模型**，不是写死某一个模型。固定 max 对继承 gpt 时未必合适，故留 high。
  - **别混淆**：mc-expert（陪审，继承 session 模型）≠ `codex-auto-review`（auto_review 自动审批用的轻模型 glm-4.5-air，见 glm-config.yaml 那条映射）。两者都是「不拉满」但理由不同，**不跟主对话同改**。

## 顺带修的（非本次改动的一部分，但同次发现）

- live `~/.codex-glm/litellm/glm-config.yaml` 头部注释此前被某次 gbk 编码事故搞成乱码（中文变 `??`）。实际配置行（model_list / master_key）全是 ASCII 未坏、翻译桥照常跑；本次把 repo 的干净注释版拷回 live 修复，留 `.bak-mojibake-<时间戳>`。注释是给人看的，不影响运行。

## 验证

- live 与 repo 两份 yaml 修后 `diff` 完全一致。
- config.toml 仅 `model_reasoning_effort` 一行从 high→max，其余字段（model/provider/权限三件套）未动。

## 验收要点（给下一棒 / 同事）

- 同事重装或升级后，主对话（glm-5.2）走 `max` 推理 + thinking 开启；mc-expert 陪审仍走 `high`（继承 session 模型、不固定拉满），两者刻意不同。
- yaml 注释若再现乱码 = 又被 gbk 写过一遍，回 repo 干净版即可（注释纯 ASCII，配置行不受影响）。
