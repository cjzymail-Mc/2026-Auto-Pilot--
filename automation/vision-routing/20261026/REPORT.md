# claude-glm 主模型与视觉路由安装验收（2026-10-26）

结果：主模型显式glm-5.3，Zhipu图片任务自动委派固定glm-5.3-flash、仅Read的vision-reader；主模型取得结果后继续工作。已通过新会话实际模型调用验收，并同步用户指定的claude-glm-dist配置包。

| 验收 | 结果 |
|---|---|
| 纯文字任务 | 2/2，无视觉委派，实际glm-5.3 |
| 随机合成图首次 | 路由正确；6/7，验证码多抄一字母，原记录保留 |
| 收紧通用格式/字符复核规则后，同图复测 | 7/7；一次Flash委派、一次子agent Read、主会话无直接Read |
| 真实0825行程单 | 15/15；同上，实际主glm-5.3/子glm-5.3-flash均有消息证据 |
| 启动参数 | 三provider主模型、Zhipu视觉隔离、用户显式--model优先，均通过无网络探针 |
| 配置包 | 临时用户目录两次安装通过；haiku迁移、其他设置/钩子保留、单启动函数、内容幂等且无新增重复备份 |
| 同步后 | 六个文件逐一哈希一致，重要旧配置备份存在；本机视觉规则与包中payload逐字节一致 |

本机settings.json只将model从haiku改成glm-5.3，其他字段不变。用户.bashrc仅修改claude-glm函数，其他函数和正文逐字节保留。Zhipu分支从私有vision-routing/载入agent定义和追加规则；DeepSeek/OpenRouter不加载该视觉模型。调用中显式--model优先；无需依赖Haiku别名，也没有更改模型别名、凭证、权限或hooks。

备份位置见installation-receipt.json和routing-tuning-receipt.json，原配置字节保留在用户私有目录；package-sync-receipt.json记录分发包的备份与同步哈希。回滚只恢复这些有记录的原文件，不删除其他配置或业务工件。

新开Git Bash，再启动新的claude-glm会话使用新参数；旧运行会话不等于已经接收了新启动规则。完整路由不是文件类型的硬拦截，仍依赖主模型遵循描述与规则。首次识别错误表明必须保留业务核验；本次样本不是生产准确率统计。

配置包更新与实测记录位于用户指定的Mc-emoji feature-04/[3]目录，见package-sync-receipt.json中的record路径。分发包未携带实际票据、原始识别结果或认证凭证。

工件：results/*.json保存实际提示词、主/子消息模型标识、父调用ID、Read与Agent调用和字段比较；图片块仅记录哈希/长度，省略base64。summary.json提供当前结果；package-install-check.json、launcher-dry-run.json记录独立检查。首次失败结果不覆盖。
