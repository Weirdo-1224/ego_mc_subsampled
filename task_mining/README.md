# Long-History Task Mining V0.1

默认可执行入口仅完成本地视频登记和预检查：`python -m task_mining`，等价于
`python -m task_mining.preflight`。没有事件挖掘、模型请求、筛选器实现或 Gold 导出。
下列阶段是后续实现契约；类型见 [`contracts.py`](contracts.py)。所有新阶段都只接受原始视频，
不能读取旧标注、旧候选、旧转换器输出或从中取提示。

| 阶段 | 输入 | 输出契约 | 当前实现 |
|---|---|---|---|
| Local Precheck | `configs/datasets.json` 的 `local_videos`、本地 MP4、ffprobe | 本地 registry JSON | 已实现 |
| Event Discovery | `VideoInput`（原视频路径、SHA-256、时长） | `EventCandidate[]`，带精确视频证据 | 仅接口 |
| Dependency Mining | 原视频、`EventCandidate[]` | `DependencyCandidate[]`，先提出必要历史与依赖解释 | 仅接口 |
| Task Construction | 原视频、已挖掘的 `DependencyCandidate[]` | `TaskCandidate[]`，T1/T2/T3、问题、候选答案、遮蔽设计 | 仅接口 |
| Evidence Verification | 原视频、`TaskCandidate[]` | `VerificationResult[]`，实际检查区间与核验结论 | 仅接口 |
| Automatic Filtering | 任务、核验结果、历史遮蔽比较结果 | `FilteringDecision[]` | 仅数据类型 |
| Human Review → Gold | 通过筛选的候选及原视频 | 人工裁决及独立 Gold 发布 | 未实现 |

所有类型可序列化为 JSON；未来各阶段按运行目录分别保存 JSONL（events、dependencies、tasks、
verifications、filtering），不得相互覆盖。`TypedDict` 和 `Protocol` 只是开发接口，
**不提供运行时模型响应校验**；真实模型接入时必须先增加严格解析、引用及时间范围校验。
阶段之间通过 ID 引用，不能先生成问题再伪造依赖记录。

登记配置中的 `root` 相对配置文件目录解析，因此默认 `../videos` 指向仓库的 `videos/`。
`filename_pattern` 配合显式 `video_ids` 列表发现七个文件，不依赖原抽样清单或标注。
外部视频目录可用 `--video-root D:/local/videos` 指定；覆盖路径相对当前工作目录解析。
登记不代表可用，只有实际 ffprobe 成功才报告 READY；更换机器后应重新检查。

registry JSON 顶层包含 `registry_version`、UTC `generated_at`、`config`、`ffprobe`、
`status`、`check_scope`、`videos`。每个视频记录 `video_id`、绝对 `path`、`exists`、
`size_bytes`、`duration_seconds`、原始有理数 `frame_rate` 和数值 `fps`、`audio_streams`、
`basic_readable`、`status` 与 `errors`。没有音频时为 `audio_streams: []`；尚未探测成功时
保持未知字段为 null。检查元数据并读取开头约一秒的视频包，**不保证全片可解码，也不核验内容**。
存在任一缺失、空文件、无效时长/帧率、无视频流、无可读视频包或 ffprobe 失败时，
对应项和总报告均为 ERROR，CLI 返回 1，同时保存报告。配置或输出路径错误也返回 1。
成功返回 0。输出使用独占创建，已有文件不会覆盖，复跑须选择新的 `--output`。

契约中的时间均为相对 MP4 起点的秒。后续实现必须检查 `0 <= start <= end <= duration_seconds`。
每个候选固定 `maturity: CANDIDATE, review_status: PENDING`，模型和自动代码不得升级。
`provenance` 必须包含 provider、model、prompt_version、run_id；视频 SHA-256 在真正模型调用前
从原文件计算并写入 `VideoInput`，预检查不做大文件哈希。候选答案 `proposed_answer` 不是 Gold。
核验的 SUPPORTED 也不等于人工 APPROVED。

任务必须有非空 `dependency_refs`、`necessary_history_evidence`、`dependency_explanation`，
以及 `query_time`、`current_window` 和 `history_mask`。当前窗口以查询时刻结束；必要历史
应早于当前窗口，所有作答证据必须不晚于查询时刻。遮蔽契约为
`operation: omit_video_intervals`、明确的秒区间、`preserve_timestamps: true`、
`comparison: full_history_vs_masked_history`：在送入模型的历史视频中跳过这些区间，
同时过滤对应音频，保留其他历史、当前窗口、查询和原始时间坐标；不得通过重编码截短
原始 MP4 或在当前窗口上做遮蔽。实现时必须检查遮蔽覆盖必要历史、与当前窗口不相交。
用同一问题比较完整历史与遮蔽历史；比较结果未取得时只能待定，不能声称历史必要性已通过。
T1 检查过程状态如何由历史形成，T2 检查实际前置条件，T3 检查跨窗口关联，三者均需历史必要性。

程序筛选至少应拒绝无依赖、悬空引用、越界/未来作答证据、未支持或矛盾证据、无效遮蔽、
仅当前窗口可答或遮蔽后仍有充分答案的任务。通过只产生 SEND_TO_HUMAN，不得自动发布 Gold。

最小真实模型开发入口是实现 `contracts.MiningBackend`，先为一个 READY 视频计算哈希构造
`VideoInput`，实现 `discover_events(video)`，再按顺序实现 `mine_dependencies`、
`construct_tasks` 和 `verify_evidence`。提供方、模型、采样/分窗策略、提示词版本、预算、
重试及超时应显式配置，密钥从环境读取，模型响应写入忽略的 `runs/<run_id>/`。
还需增加响应校验和遮蔽比较的结果记录，再实现程序筛选；本轮没有默认提供方或虚拟模型结果。

现有 `benchmark/schema.json` 和 `benchmark.validate` 保持原样；这里是流水线中间契约，
不是现有 bundle，不能直接送入旧校验器（旧 provenance 枚举等也尚不支持 VLM）。
未来导出时另行设计版本化适配及迁移，并保留证据、遮蔽和审核信息；禁止冒用 text_candidate
或 human 来标记 VLM 来源。Schema 检查通过只能说明结构与门禁符合约定，不能证明视频事实正确。
