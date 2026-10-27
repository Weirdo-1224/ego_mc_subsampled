# Agent 接入契约（预留）

当前不实现模型、记忆模块或运行器。后续 Agent 可按下列最小接口接入：

```python
reset(episode_public_metadata, budget)
on_observation(window, available_at)       # 可输出 state_update 或 alarm
on_instruction(public_event, available_at)
query_snapshot(question, query_time)      # 隔离分支；不修改正常运行状态
flush()                                  # 返回时间线、调用及资源日志
```

同一 Episode 连续运行，不随 Track 重置。Agent 不可读取私有 `datasets/` 标注目录，
后续 Runner 应仅发送已核验发布时刻的公开观察/指令，并审计媒体时间和实际墙钟时间。
状态输出需要 `episode_id, media_time, evidence_refs`；报警另需
`incident_id, decision (raise/update/resolve), emission_wall_time, message`。
这里只约定语义，不把未实现的接口当成已通过因果隔离验证的系统。
