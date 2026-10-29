只能从下方已提供的依赖候选构造问题，最多生成 $target_candidates 道。

任务要求：
1. 使用可客观核验的封闭式问题，候选答案只能为 YES、NO 或 UNKNOWN。
2. track 的含义为：T1 表示过程状态，T2 表示实际可观察的前置条件，T3 表示跨窗口历史关联。
3. 不得虚构规则，不得凭稀疏采样推断某个动作没有发生，不得新增未经依赖挖掘的关系。
4. 原样复制所引用依赖的 query_time、current_window、dependency_explanation，并将其 history_evidence 原样复制到 necessary_history_evidence。
5. dependency_refs 必须包含原依赖 ID。proposed_answer 只是模型提出的候选答案，不是真值。

历史遮蔽要求：
1. history_mask.operation 固定为 "omit_video_intervals"。
2. history_mask.intervals 必须与 necessary_history_evidence 中的区间完全一致。
3. history_mask.preserve_timestamps 固定为 true，comparison 固定为 "full_history_vs_masked_history"。
4. 遮蔽只移除必要历史区间；其余历史、当前窗口、问题及原视频时间坐标必须保留。

依赖候选：
$dependencies_json
