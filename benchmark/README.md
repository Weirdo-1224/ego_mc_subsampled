# 数据契约 0.1.0（准备版）

采用 JSON/JSONL 和单一 JSON Schema，无数据库、服务端或模型依赖。
`schema.json` 描述逻辑 bundle；`validate.py` 将 Episode 目录中的文件装配成 bundle 后校验。
七个实体文件必须存在，但可以为空。后续修改字段需升版本并提供迁移，不能静默重解释旧 ID。

## 公共字段

| 字段 | 语义 |
|---|---|
| schema_version | 当前为 0.1.0；准备版协议 |
| id / episode_id | 数据集命名空间内全局唯一 ID / 所属完整 Episode |
| interval.start/end | 相对视频秒、闭区间；点锚点 start=end，不假装是动作持续区间 |
| known_at | 这条记录所含证据最晚的知识时间；不等同在线发布许可 |
| visibility | PRIVATE 或 TIMED_PUBLIC；当前全部 PRIVATE |
| evidence_refs | 指向独立 Evidence ID，至少一条 |
| derived_from | 指向其他实体，形成无环来源链；不能替代直接证据 |
| provenance.method/notes | source_copy、text_candidate、human；解释来源与限制 |
| maturity | CANDIDATE、REVIEWED、GOLD；不能代替审核状态 |
| review | PENDING/APPROVED/REJECTED、reviewer、reviewed_at、notes |

完成审核必须有身份、带时区的 ISO 8601 时间和理由。REVIEWED/GOLD 必须 APPROVED；
GOLD 的所有支持实体与证据也必须经审核。脚本不会验证审核者身份的真实性，人工审核仍是信任边界。
Gold 是“任务答案”实体，只有经批准的 GOLD 可进入 `gold.jsonl`，不接受候选答案占位。
`State.value: null, basis: unknown` 表示暂无已核验状态，不能当作经过审核的“确实无法观察”答案。

## 来源与证据

`sources.json` 保存仓库相对路径、类型和 SHA-256，引用本地原文件。
证据含 `source_id`、`source_pointer`、`quote`、`source_label`、`interval` 和审核记录。
例如 GX010021 第一条原话定位为 `annotations/annotations.json` 的 `/0/texts/0`，
同时核对同一下标的 `text_types` 和 `text_timestamps`，不改写原文。
视频证据后续可用可解释的片段定位字符串，但必须配真实区间、video 类型来源和人工审核；
当前没有生成任何视频内容证据。

`available_at` 是整份证据可以合法用于在线输入的时刻，必须不早于证据区间结束。
原始标注只有点时间，不足以确定完整句子结束，故不自动设置发布时刻。
`known_at` 保留文本点锚点，仅用于离线候选引用和查询检查，不能据此开放转写给 Agent。
TIMED_PUBLIC 实体仅允许原始发言 Event，且所需证据和所有来源实体均可见且不晚于发布时刻。
私有答案、任务、推断、状态和规则对象不直接进入在线输入，后续 Runner 应从审核过的原始观察派生输入。

## 实体关系与时间

Rule 分别记录 issued_at、effective_from、effective_to、supersedes、condition 和 scope。
没有复核时 effective 字段为 null、supersedes 为空；可能的替代关系保留在候选 Dependency，
不会直接改变原规则有效期。Dependency 的 from_ref/to_ref 必须解析，修订必须从新规则指向旧规则。

Task 的 `required_evidence_sets` 是可替代的充分证据集合；当前只是待核验提议，尚未确认充分或最小。
`target_refs` 指向状态/规则/依赖；引用闭包的时间和证据结束时间均不能晚于 query_time。
查询和题面属于私有评测材料。`earliest_answerable_time` 未确认时留空且禁用任务。
历史必要性 PENDING 不能被当作已证实的长程任务标签。

Intervention 分开保存 error_onset、detectable_from 区间、feedback_given_at、deadline、resolved_at。
没有客观依据时保留 null；Feedback 锚点不代表已核验异常，不能直接晋升为事件 GOLD。
事实状态、实际动作和已核验异常进入 GOLD 时，必须存在经过审核的视频证据。

## 校验范围

检查类型/枚举/必填字段、重复 ID、Episode 归属、时间范围及区间顺序、SHA-256、
Ego-MC 原文/标签/时间定位、跨文件引用、来源与依赖环、规则修订顺序、审核一致性、
干预时间、任务及其传递证据的未来引用、公开实体的私有证据泄漏、GOLD 支持闭包和任务启用门禁。

尚不能自动证明：视频语义正确、充分证据集真的充分、历史真的必要、题面没有语言捷径、
专家反馈是否构成真实错误、审核者身份是否真实、实际 Agent 是否绕过 Runner。
这些需要人工复核和后续运行时隔离/访问审计。当前没有实现 Runner 或真实评分器。
