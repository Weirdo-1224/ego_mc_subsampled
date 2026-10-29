# 派生数据区与适配器约定

> Legacy：下文是旧适配器和现有 Benchmark bundle 的兼容性说明。
> 新开发遵守根 `AGENTS.md`，从 [`task_mining/`](../task_mining/README.md) 的纯视频契约开始；
> 禁止把旧文本标注或旧候选接入新流水线。真实 VLM 接入在后续单独实现。

原始 `../videos/`、`../annotations/`、`../docs/`、`../sample_manifest.json` 保留原位。
每个 Episode 的派生包由 `episode.json`、`sources.json`、`evidence.jsonl` 及七类实体 JSONL 构成，
统一使用 `benchmark/schema.json`。空实体文件合法，例如当前 `gold.jsonl` 为空。

新适配器需实现“本地材料 → 来源哈希和原始定位 → 证据 → 候选实体”，不得调用大模型或自动升级真值。
ID 使用 `dataset:episode:entity:key`，时间单位为 Episode 相对秒，来源时间基准与偏移必须可追溯。
没有动作区间或人工核验时，不从相邻文本时间差虚构持续时间；不同数据源缺少的字段留空并说明原因。
转写点时间戳不等于整句已发布时间，未核验时保持 `PRIVATE, available_at: null`。

候选包人工修改前复制到新的版本目录；转换器拒绝覆盖已存在的输出目录。
审核记录使用真实审核者与 ISO 8601 时间，禁止脚本假填身份。候选关系、问题和检查点不代表已经可评分。
