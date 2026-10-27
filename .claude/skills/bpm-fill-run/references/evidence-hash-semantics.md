# 采集哈希口径规范（防复发）

来源：V3-R05 证据卫生轮（合同 ctr-82e59a70 §1 根因收口）。round-4 case03_probe._drain_capture
对捕获记录计 sha256 用的是**紧凑 `json.dumps(payload, ensure_ascii=False)`**，而落盘文件用
`indent=1` —— manifest 里的 sha256 与文件字节哈希不一致，程序化按字节校验会失配（A 验收 P2）。

## 规则（今后所有 run 内采集脚本）

1. **唯一权威口径 = 落盘文件字节 sha256**（读回文件再算，或对写入的同一字符串按写出编码编码后计算）。
2. 需要保留"逻辑内容哈希"时必须**双字段**并命名区分：`sha256_file`（文件字节，可复算）+
   `sha256_logical`（紧凑 JSON 口径，须在 manifest 顶层 `hash_semantics` 说明两者关系）。
   禁止把逻辑口径字段命名为裸 `sha256`（round-4 wide-query-manifest 的教训，已加法订正）。
3. 消费侧（A 验收/终审/下游脚本）按 `sha256_file` 复算；遇到旧工件只有裸 `sha256` 的，
   视为 logical 口径并用内容比对复核，不按字节强判失配。
4. run 内脚本若复用本模式（response 捕获 → `p.save()` → manifest 记录），写盘后调用
   `hashlib.sha256((evidence_dir / name).read_bytes()).hexdigest()`；case03_probe.py 内已有
   `_hash_file(name)` 助手即此语义。

## 附带口径（同轮 O2/P2-3 登记）

- 详情/候选单的"行程区间"字段：`factStartTime/factEndTime` = 实际公出时间；
  `factNatureStartDate/factNatureEndDate` = 含途自然区间。两者可能分歧（例：12025095297
  实际仅 09-18，自然区间 09-17..09-18）。采集与匹配必须显式声明所用口径，禁止单说"日期"。
- DOM 全量 innerText 采集会带门户菜单噪声（前 ~2000 字符）；证据文件为不可变历史不改，
  未来采集可在保存前裁剪到业务容器（#main/.ui-table 等）起点，并在 events 里记录裁剪规则。
