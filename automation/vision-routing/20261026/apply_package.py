"""Sync only the tested config package to the exact user-authorized folder."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

HERE = Path(__file__).resolve().parent
DEST = Path(r"D:\Downloads\Mc Claude Code Workshop\Mc-emoji\[feature-04-Hot-Fix-Clash+wsl-codex]\[3-Openrouter+claude配置-glm]")
PACKAGE = DEST / "claude-glm-dist"
STAGE = HERE / "package-stage"

def load(p):
    return json.loads(p.read_text(encoding="utf-8"))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

for name, score in [('plain',2),('synthetic-format-v2',7),('real-format-v2',15)]:
    d=load(HERE/'results'/f'{name}.json')
    assert d['main_stayed_glm53'] and d['score']=={'correct':score,'total':score},name
    if name!='plain':
        assert d['vision_delegations']==1 and d['child_flash_messages']>0 and d['child_read_calls']==1 and d['main_read_calls']==0,name
assert load(HERE/'package-install-check.json')['status']=='PASS'
for name,digest in load(HERE/'package-source-hashes.json').items():
    assert sha(PACKAGE/name)==digest, f'Package changed concurrently: {name}'

names=['claude-glm-settings.json','claude-glm.bashrc.snippet','install-claude-glm.ps1','README.md',
       'vision-routing/agents.json','vision-routing/routing.md']
for name in names:
    p=(PACKAGE/name).resolve()
    assert p.is_relative_to(PACKAGE.resolve())
    if name.startswith('vision-routing/'):
        assert not p.exists(), f'Do not overwrite unexpected existing payload: {name}'
stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
changes=[]
for name in names:
    p=PACKAGE/name;backup=None
    if p.exists() and name!='README.md':
        backup=p.with_name(p.name+'.bak-vision-'+stamp)
        assert not backup.exists()
        backup.write_bytes(p.read_bytes())
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((STAGE/name).read_bytes())
    changes.append({'file':str(p),'sha256':sha(p),'backup':str(backup) if backup else None})

note=DEST/'2026-10-26 glm-5.3主模型与Flash视觉自动委派实测.md'
assert not note.exists(), 'Existing update record must be reviewed before overwriting'
note.write_text('''# glm-5.3主模型与Flash视觉自动委派（2026-10-26）

本次服务的主线：日常主会话继续使用glm-5.3，需要看图时自动委派固定glm-5.3-flash的只读视觉子agent，完成后交回主会话；同步到现有一键配置包。

## 当前配置

- 本机`~/.claude-glm/settings.json`默认模型从`haiku`改为明确的`glm-5.3`。
- Git Bash启动函数显式选择各provider主模型，用户手工`--model`优先，Haiku别名不再决定主会话。
- 仅Zhipu分支加载`vision-routing/agents.json`与`routing.md`。vision-reader固定Flash，仅Read；不是把整个会话切成Flash。
- 原模型别名、Key、hooks、权限及其他账户不变；没有新增Vision MCP或常驻窗口。DeepSeek/OpenRouter不加载GLM视觉配置。
- 启动参数只对后续启动生效。本轮验收使用新会话；既有A/B窗口未重启。新开Git Bash，或先`source ~/.bashrc`，再新开`claude-glm`会话。

## 真实链路实测

Claude Code 2.1.299，使用本机现有Git Bash claude-glm入口；测试命令本身没有额外提供model、agents或路由提示，必须由已安装配置加载。测试提示只要求完成文字任务或读取指定图片，没有点名Flash或vision-reader。

| 场景 | 结果 | 模型/工具证据 |
|---|---|---|
| 纯文字计算 | 2/2字段一致 | 全程glm-5.3，无视觉调用 |
| 随机合成图片复测 | 7/7字段一致 | 主glm-5.3→一次vision-reader→子glm-5.3-flash读取一次图片→主glm-5.3回答 |
| 用户授权的0825真实行程汇总单 | 15/15预设字段一致 | 同上，主会话没有直接Read图片 |

真实行程单的日期、金额、票号、跨行站名均与调用之外的标准答案一致；识别模型没有获得PDF文字层或历史答案。只读文件工具限定为测试用Agent/Read，未访问OA或认证profile。

首次合成图虽已正确委派，但验证码多抄一个字母（6/7），原记录保留。之后只收紧“完整转交JSON格式、不给子任务额外增加布局说明、逐字符复核号码”的通用规则，未注入正确答案；同图复测7/7。不能把路由成功等同于OCR永不出错。

合成图复测约43.51秒，真实行程单链路约93.17秒；这包含主模型与子agent多轮交互，比此前Flash直接读图的单次调用更慢。批量电子PDF仍优先文字提取，视觉用于扫描/图片/异常复核。耗时不是承诺，也未做大样本稳定性统计。

此前另做5份真实票据图片的Flash独立盲测，预设字段68/68一致；降清晰度副本15/15，正常Read路径15/15。另观察到模型会补推断的数量值，增加明确“未标注为空”规则后复测正确；输出仍须业务规则核验。

## 配置包同步与安装验证

`claude-glm-dist/`更新了启动片段、settings模板、安装器和README，新增两个私有视觉配置文件。保留既有可移植Git Bash路径探测、auto模式及PATH钩子；不将本机用户路径、Key、真实票据图片或原始识别结果放入分发包。

安装器会迁移已有model=haiku，部署和备份视觉配置，要求本轮实测的Claude Code 2.1.299或更新版。临时用户目录连续安装两次验证通过：旧默认迁移、其他Bash函数/自定义设置/钩子保留、只保留一个启动函数、二次安装内容不变且无额外备份。该安装验证使用-SkipSmoke，不冒充另一台机器的真实联网验收。

三provider启动参数以无网络探针核验，只有Zhipu加载视觉定义；显式`--model glm-5.3-flash`仍优先。原配置文件覆写前已生成`.bak-vision-时间戳`；7/8月历史记录不改写。

## 边界

自动委派依靠模型遵循启动规则，不是按MIME硬拦截。图片/附件需要子agent可访问的本地路径，扫描PDF先渲染。若CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1，须关闭后才能允许专用子模型。新机器仍须检查套餐、模型权限并跑一次实际图片任务。

原始路由工件在本机BPM仓库`automation/vision-routing/20261026/`，独立视觉测试在`automation/vision-benchmark/20261026-glm53flash/`；分发包仅保留配置与汇总说明，不携带业务票面信息。

官方依据：[子agent模型与优先级](https://code.claude.com/docs/en/sub-agents#choose-a-model)、[主模型设置](https://code.claude.com/docs/en/model-config#setting-your-model)。
''',encoding='utf-8')
receipt={'at':datetime.now(timezone.utc).isoformat(),'destination':str(DEST),'changes':changes,'record':str(note),'tests_passed_before_sync':True}
(HERE/'package-sync-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'synced_files':len(changes),'destination':str(DEST),'record':str(note)},ensure_ascii=False))
