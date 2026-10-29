# V0.2 State — 开发状态与恢复入口

> 2026-10-29 实施中；此文件记录真实执行情况。文档实际位于 `docs/v0.2_spec/`，用户所述 `task_mining/specs/v0.2/` 不存在，未搬迁已有文件。

## 0. 当前结论

- **版本**：V0.2 — PARTIAL；真实模型流程按用户要求暂停
- **当前主任务**：按用户追加要求，已将新工具集中到 `annotation_pipeline/`；模型流程仍暂停于 T2。
- **下一动作**：由用户检查独立配置、可替换提示词和已有 T1 离线审核页；本轮未恢复模型请求。
- **目标视频**：GX010029（不读取旧标注）
- **目标结果**：一个真实单视频 `runs/<run_id>/review.html` + 证据与候选文件
- **重要边界**：本轮不生成 Gold、不进行正式四条件评测、不扩展其它六个视频。

## 1. 已知基线（来自上一轮 V0.1 交付报告，非本轮重测）

- [x] V0.1 已建立视频预检查、默认命令、`contracts.py` 和 `AGENTS.md`。
- [x] 上一轮本地报告：7/7 READY（只检查元数据和约一秒视频包）；七个视频均未检测到音轨。
- [x] 上一轮本地报告：`python -m unittest discover -v` 33/33 通过。
- [x] 旧标注路径与新默认入口隔离；旧 Benchmark Schema 未改。
- [x] 本轮已确认百炼视频 API、粗采样视频输入及真实事件/依赖输出；任务、独立核验与完整闭环尚未完成。

## 2. 执行看板

| 任务 | 状态 | 真实产物 / 记录 | 阻塞 |
|---|---|---|---|
| T0 可用性与真实模型请求 | DONE | `runs/v02_GX010029_t0_20261029_03/`，1 次真实视频 POST 成功，原始响应与用量已保存 | 无；原 Kimi 凭据 401 后由用户明确提供百炼凭据 |
| T1 Event + Dependency | DONE | 主运行 `events.jsonl`：42 条；`dependencies.jsonl`：4 条；真实模型原始响应在 `raw/`，非法记录及理由见报告 `invalid_model_records` | 语义依赖、近期不足与前置解释仍是待核验假设 |
| T2 Task + 严格校验 | DOING | 已发起文本任务构造及一次结构修复；用户要求停止，进程已中止，尚无通过校验的 `tasks.jsonl` | 按用户要求暂停；最后请求响应/计费未知，不自动重发 |
| T3 Evidence + Filter + Review | TODO | — | 依赖 T2 |
| T4 真实闭环 + 测试 + 报告 | TODO | — | 依赖 T3 |
| 用户追加：独立目录与离线审核 | DONE | `annotation_pipeline/` 集中代码、配置、独立凭据、外置提示词与测试；本地 `runs/GX010029_T1_review_20261029/review.html` 已生成 | 本轮工程整理 0 次真实 API 调用；不代表 V0.2 E2E 完成 |

状态值只用：`TODO / DOING / DONE / BLOCKED`。只有有真实可核对文件或通过的命令，才标记 `DONE`。

## 3. 运行记录（由执行者填写）

| 项目 | 当前值 |
|---|---|
| Git commit / branch | `25da9a85198cd19a27f2e3b4ed8290a974cc3f74` / `main` |
| run_id | T0：`v02_GX010029_t0_20261029_03`；主运行：`v02_GX010029_20261029_03`；失败 `_01`、`_02` 均保留 |
| video_path | `videos/GX010029.MP4`，400.366633 秒，29.970 fps，无音轨；本轮实际预检查 READY |
| video_sha256 | `7bcc01b16833f6601dd419ad0e9df5b145ee1631eb38938ebf595cefea761338` |
| provider / model | `dashscope` / `qwen3-vl-plus`，北京官方兼容入口 |
| prompt_version | T0：`v02-t0-observation-1`；主流程：`v02-mining-2` |
| current_window_seconds | 60（没有发现统一流式窗口配置，采用 Spec 默认） |
| API 调用数 / 成本 | 主运行 10 次尝试，9 次收到成功响应（8 次视频、1 次文本），已知用量估计 ¥0.575698；第 10 次中止、账单未知。T0 与前两次失败运行另见各自报告；本轮独立化/离线审核新增真实调用 0 次 |
| Events / Dependencies / Tasks | 42 / 4 / 尚未生成 |
| SEND_TO_HUMAN / REJECT / NEEDS_MORE_EVIDENCE | — / — / — |
| 测试 | 最新根目录 `python -m unittest discover -v`：49/49；独立目录 `python -m unittest discover -s tests -t .. -v`：16/16；新测试为合成记录，不充当实验结果 |
| review.html | `annotation_pipeline/runs/GX010029_T1_review_20261029/review.html`，离线 T1 候选复看页；不是已完成独立核验的任务审核包 |

## 4. 问题与决策日志

| 日期 | 问题 / 决策 | 处理状态 |
|---|---|---|
| — | 仅接入一个真实可用的视频 Provider，先完成 GX010029 | 已定策略 |
| — | 完整四条件实验及 Gold 发布留待后续 | 已定范围 |
| 2026-10-29 | 旧环境仅 KIMI_API_KEY；官方国内/国际 models 鉴权均 401 → 不能生成候选 → 保存真实失败；用户随后明确提供百炼凭据 → 北京 models 和视频 POST 成功 | T0 已解除阻塞 |
| 2026-10-29 | 原视频 drop-frame timecode 与 2fps 派生片段不兼容 → FFmpeg 失败且未发 API → 仅对派生片段使用 `-map_metadata -1` → 第二轮成功解码，原视频未修改 | 已修复；失败目录 `_01` 保留 |
| 2026-10-29 | 完整流水线首轮 `v02_GX010029_20261029_01` 的事件 evidence 两次均为对象而非数组 → 严格解析失败，未生成下游产物 → 明确数组提示及错误信息，prompt 升为 `v02-mining-2`，新 run 重新尝试；原响应和费用保留 | 真实失败，未放宽契约 |
| 2026-10-29 | `v02_GX010029_20261029_02` 的事件视频请求 60 秒读超时 → 保留 TRANSPORT_ERROR、费用未知和调用预留，不声称模型未计费 → 将单请求超时改为 240 秒，新 run 重试；不增加自动重试或模型抽象 | 待验证 |
| 2026-10-29 | 主运行事件成功后，依赖请求两次均混入近期证据/错误窗口 → 两份原始输出留档且没有任务进入下游 → 保留 42 条真实事件缓存，仅修订依赖阶段为 `v02-dependency-anchors-1`，由程序提供合法 60 秒查询锚点和可引用早期事件清单，模型仍须从视频挖掘语义依赖；不自动改写不合法候选 | 依赖阶段续跑中 |
| 2026-10-29 | 两版自由时间/引用响应失败后，改用 `v02-dependency-refs-1`：模型仅选锚点与合法历史事件 ID，程序复制原事件证据与 60 秒窗口，不生成新事实 → 真实两次响应共 15 条尝试中 4 条逐条通过，11 条不合法记录拒绝留档；复用两份已付费响应，无新增请求 → `dependencies.jsonl` 已落盘 | T1 完成；所有语义假设留给 T3 核验 |
| 2026-10-29 | 用户要求暂停后讨论工程组织，随后要求参照 `bench-demo/annotation_pipeline` → 只参考其配置、凭据、提示词与审计组织，未读取其凭据、会话标注/整合产物或复制其事实答案 → 当前新增代码已迁入本仓库 `annotation_pipeline/`；旧 V0.1 预检查及旧 Benchmark 保留 | 已完成目录独立化，未恢复 API |
| 2026-10-29 | 原提示词内嵌、模型地址锁死、产物难复看 → 提示词改为 `prompts/*.md`；模型/API 与密钥来源可配置；密钥从环境变量或忽略的 `credentials.local.json` 读取（本轮仅创建空模板，未存入用户真实密钥）；新增统一 inspect/probe/mine/review 入口 | 本地预检查与配置/缓存/凭据测试通过；替换模型的真实兼容性未测试 |
| 2026-10-29 | 旧 T1 只有 JSONL → 离线导入到独立工具运行目录，保留原响应和 provenance，按原 MP4 哈希生成视频复看页与空人工记录模板 → 42 事件、4 依赖；187 链接全部存在、49 派生视频哈希匹配，见 `review_qa.json` | 0 次 API；不声称事实已核验或人工已审核 |
| 2026-10-29 | 用户要求全部提示词改为中文 → `annotation_pipeline/prompts/` 下 system、events、dependencies、tasks、verifications、probe 六份模板已中文化，自然语言输出要求为中文；模板变量、JSON 字段与枚举值保留契约原样 → 六份模板渲染通过，根目录回归 49/49 通过 | 0 次真实 API；原运行与候选未改写，模型流程仍暂停；新模板哈希自动变化 |
| 2026-10-29 | 用户要求脚本和配置分目录 → 8 个实现模块迁入 `annotation_pipeline/scripts/`，配置与凭据迁入 `configs/`；更新导入、默认配置、直接启动和兼容入口，重算配置相对路径以保留原视频/提示词/运行目录位置；凭据文件字节保持不变 → 根目录回归 49/49，通过包入口 inspect 与 `scripts/cli.py --dry-run`，均 0 次 API；本地配置/凭据仍被 Git 忽略 | 整理完成；既有 runs 与审核产物未移动或覆盖 |

## 4.1 当前工具与审核入口

- 工具说明：[`annotation_pipeline/README.md`](../../../annotation_pipeline/README.md)。
- 实现脚本：`annotation_pipeline/scripts/`；统一入口为 `scripts/cli.py`，根目录 `__main__.py` 仅负责启动。
- 本机配置：`annotation_pipeline/configs/config.local.json`；模板 `configs/config.example.json`。
- 密钥入口：`annotation_pipeline/configs/credentials.local.json`（Git 忽略，整理时原样移动）；模板 `configs/credentials.example.json`。
- 提示词：`annotation_pipeline/prompts/`，实际模板与哈希进入新运行快照；改变模板禁止误用旧缓存。
- T1 审核入口：`annotation_pipeline/runs/GX010029_T1_review_20261029/review.html`。
- 原始运行 `runs/v02_GX010029_20261029_03/` 未覆盖。离线副本保留原 provenance，不能直接当新配置的续跑实验。
- 新运行使用 `python -m annotation_pipeline`；默认只 inspect。显式 `probe` / `mine` 才可能调用所配置服务。

新增问题请按“**现象 → 影响 → 最小处理 → 验证结果**”记一行，不记录无意义的流水账。

## 5. 完成判定

只有以下条件全部满足才将 V0.2 状态改为 `DONE`：

- [ ] GX010029 的真实模型 API 请求与完整构造流程已执行；没有 Mock 冒充真实结果。
- [ ] 已生成可追踪的 `events / dependencies / tasks / verifications / filtering` 文件。
- [ ] 已生成可打开的 `review.html`，至少有一条真实、证据可核验的送审候选及其风险说明（目标 2–3 条，不强制凑数）。
- [ ] `run_report.json` 标明真实调用、时间合法性和候选筛选数；所有候选仍是 PENDING。
- [ ] 最小新增回归测试与仓库原有测试通过；原始视频、旧标注与 Gold 未改动。

**如果 API 阻塞**：状态填 `BLOCKED`，保存报错与下一动作；**如果产出为零**：技术流程可记为已执行，但总体验收仍为 `PARTIAL`（记录在运行报告），保留真实负结果和下一步，不擅自把低质量候选升级为合格。

**恢复方法**：下一次先读本文件 → 定位首个非 `DONE` 任务 → 检查该任务产物和缓存 → 继续，不重跑已成功的付费请求。
