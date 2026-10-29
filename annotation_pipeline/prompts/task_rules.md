# Codex 任务构造规则

RULES_PENDING

历史依赖与任务构造规则尚未制定。当前禁止生成任务，不使用旧 dependencies.md / tasks.md 替代。
此文件仅登记后续输出的基本约定，不定义筛选规则，也不是可执行的完整任务 Schema。

后续文件名：`task_candidates.jsonl`，UTF-8，每行一个 JSON 对象。当前不创建该文件。

| 字段 | 基本约定 |
|---|---|
| task_id | 候选任务 ID |
| video_id | 原始视频 ID |
| track | T1 / T2 / T3，具体构造规则待定 |
| query_time | 相对原始 MP4 起点的秒 |
| question | 候选问题 |
| proposed_answer | 未经人工确认的候选答案，不是真值 |
| evidence_refs | 原视频证据引用，包含 video_id 与相对原视频秒区间；具体结构待定 |
| dependency_reason | 历史依赖解释；具体构造与检查规则待定 |
| review_status | 固定 PENDING，模型与自动程序不得升级 |

所有模型产物只能为 CANDIDATE/PENDING。只有人工复看视频，确认必要证据、历史必要性和答案，
并记录真实审核者、时间及理由后，才能单独发布 Gold。
这份基本约定不替代仓库的历史必要性、遮蔽设计、因果访问与人工审核约束；完整契约后续讨论。
