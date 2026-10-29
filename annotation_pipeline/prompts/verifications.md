请独立检查原视频，并回答下方每道问题。本次输入不提供教师答案、前序事件总结或依赖解释，不得将未提供的分析当作视觉事实。

视频检查要求：
1. 全片粗采样视频是用于检查替代证据的私有核验上下文。任何任务的答案都不得依赖其查询时刻之后的画面。
2. 局部增密采样片段包含关键历史和当前窗口。检查可见事实、时间定位、对象身份、遮挡及模糊短动作。
3. 必须检查整个近期窗口，并检查关键区间以外、查询时刻以前的其余历史是否仍足以支持答案。
4. 稀疏采样未观察到某个动作，或无法观察、无法排除替代证据时，应记录 UNKNOWN，不得据此记录 NO。

输出要求：
1. verdict 只能为 SUPPORTED、UNSUPPORTED 或 UNCERTAIN；independent_answer 只能为 YES、NO 或 UNKNOWN。SUPPORTED 不等于 Gold。
2. recent_sufficient、alternative_history_sufficient、direct_visual_support、interval_accuracy、contradiction 均只能使用 YES、NO 或 UNKNOWN。
3. inspected_evidence 必须是证据数组，内容为你独立观察到的可见事实。使用原视频区间，且每个区间的结束时间必须满足 end <= query_time。
4. 原样复制对应任务提供的 checked_intervals。
5. 在 notes 中解释答案支持、不确定性，以及近期画面或其他历史可能直接给出答案的风险。不得仅凭文字推理宣称历史的因果必要性已经成立。
6. 每道任务返回一条核验结果。

待核验问题：
$questions_json
