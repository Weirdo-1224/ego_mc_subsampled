# 单视频历史依赖候选构造工具 · V0.2

代码、提示词、模型配置、密钥入口、测试和本地审核产物集中在本目录。
可以复制整个目录到其他位置，再修改视频路径；不导入当前仓库的 `task_mining`、旧标注或 Legacy 转换器。
Python 3.11+，Python 代码仅使用标准库；`ffmpeg`、`ffprobe` 需在 PATH。

当前真实结果是 **42 条事件候选、4 条依赖候选**。原模型流程按用户要求暂停于 T2，
尚未完成任务构造、独立视频核验或完整 E2E 验收。本轮目录整理和离线审核生成 **没有调用模型**。

## 目录

```text
annotation_pipeline/
  __main__.py               包启动入口；默认只做本地检查
  configs/                  配置与独立凭据
    config.example.json     视频、模型、API、采样、预算配置样例
    config.local.json       你自己的配置，Git 忽略
    credentials.example.json  空密钥样例
    credentials.local.json    你自己的密钥，Git 忽略
  scripts/                  全部实现脚本
    cli.py                  统一命令入口
    backend.py              OpenAI 兼容视频调用、缓存与预算
    mine.py                 顺序流水线与阶段落盘
    media.py                原视频预检查
    validation.py           引用、时序、遮蔽、候选状态校验
    contracts.py            独立中间类型
    review.py               离线导入与视频复看页面
    common.py               配置、独立凭据、提示词加载
  prompts/                  可直接修改或整体替换的 Markdown 提示词
    system.md               共同事实边界和输出契约提示
    events.md               可见事件发现
    dependencies.md         先挖掘历史依赖
    tasks.md                仅从已有依赖构造问题
    verifications.md        独立原视频核验
    probe.md                8 秒视频可用性探测
  tests/                    仅临时目录合成测试
  runs/                     本目录内的本地运行/审核产物，Git 忽略
```

## 先配置，再运行

在本目录打开 PowerShell：

```powershell
Copy-Item -LiteralPath configs/config.example.json -Destination configs/config.local.json
Copy-Item -LiteralPath configs/credentials.example.json -Destination configs/credentials.local.json
```

本机的两份本地文件已创建；上述复制命令仅用于尚无本地配置的新副本。
编辑 `configs/config.local.json`，可自行设置以下内容：

| 配置 | 用途 |
|---|---|
| `provider` | 来源名称，写入 provenance |
| `base_url` | OpenAI 兼容 API 的根地址；程序追加 `/chat/completions` |
| `model` | 你账户可用的视频模型名称，不在代码中锁死 |
| `api_key_env` | 环境变量名称，也作为本地凭据文件中的键名 |
| `credentials_file` | 默认 `credentials.local.json`，相对配置文件目录解析，即 `configs/credentials.local.json` |
| `request_options` | 模型特定参数；换模型时按对应接口要求修改或设为 `{}` |
| `video_fps_parameter` | 是否在视频输入中发送 `fps` 扩展字段；默认百炼为 `true` |
| `video_path` | 原始 GX010029 MP4 路径；路径相对配置文件所在目录解析 |
| `prompts_dir` | 默认 `../prompts`，可改为你自己的完整目录 |
| `output_dir` | 默认 `../runs`，即工具根目录下的 `runs/` |
| `current_window_seconds` | 默认 60 秒，写入每题并校验 |
| `max_calls` / `budget_cny` | 单运行内的调用次数与本地费用预留上限 |
| `cost_reserve_per_call_cny` | 每次发请求前的本地预留；是用户配置，不是官方账单保证 |

密钥填写在 `configs/credentials.local.json`，例如键名使用 `DASHSCOPE_API_KEY`，值由你在本机填写。
程序优先读取同名环境变量，其次读取本地凭据文件；不会自动遍历其他密钥。
密钥值不写入配置快照、提示词、请求清单或候选。示例文件中没有真实密钥。

当前运输格式为 **OpenAI 兼容 Chat Completions + Base64 MP4 `video_url` + JSON 输出**。
模型和地址可以替换，但接口需支持此格式；不同视频输入协议尚未实现。
换模型后先执行 `inspect`，再按需执行单次 `probe`，其真实兼容性需重新验证。
默认配置沿用已成功调用过的百炼北京 `qwen3-vl-plus`；模型别名不是固定权重快照。

可用 `ANNOTATION_MODEL`、`ANNOTATION_BASE_URL`、`ANNOTATION_API_KEY_ENV` 环境变量覆盖三项设置。
价格估计仅在 `model == pricing_model` 且配置了价格表时计算；换模型未配价格则保持未知，
不会把原模型价格当成新模型账单。真实账单始终为未知，需由服务商对账。

## 统一命令

以下命令在本目录执行。所有配置内的相对路径都以 `configs/config.local.json` 所在目录为基准，
不以脚本目录为基准。

```powershell
# 不调用模型；默认命令也等同 inspect
python scripts/cli.py inspect --config configs/config.local.json
python scripts/cli.py mine --config configs/config.local.json --dry-run

# 以下两种会调用所配置的模型；按你自己的配置与预算执行
python scripts/cli.py probe --config configs/config.local.json --run-id probe_001
python scripts/cli.py mine --config configs/config.local.json --run-id GX010029_001 --stop-after dependencies
python scripts/cli.py mine --config configs/config.local.json --run-id GX010029_001 --resume

# 读取已有运行，生成独立的离线审核副本；不调用模型、不覆盖源运行
python scripts/cli.py review --config configs/config.local.json --run-dir ../runs/v02_GX010029_20261029_03 --output-dir runs/GX010029_T1_review_new

# 本目录独立测试；仓库总回归仍用根目录的 python -m unittest discover -v
python -m unittest discover -s tests -t .. -v
```

在仓库根目录也可使用包入口，例如：

```powershell
python -m annotation_pipeline inspect --config annotation_pipeline/configs/config.local.json
```

新运行从头依次执行 Event → Dependency → Task → Independent Video Verification → Filtering → Review。
事件和依赖先落盘，再生成问题。已有输出必须显式 `--resume`；程序检查源视频哈希、配置和提示词快照。
更换提示词或模型后请新建运行，避免把旧缓存当成新实验。
有成功原始响应时复用响应；中断/超时但没有响应的请求不自动重发，保留可能已计费的记录。
旧开发目录里的结果仅通过 `review` 离线读取，不能直接作为新配置的续跑实验。

## 替换提示词

直接编辑 `prompts/*.md`，无需改 Python。也可以复制完整 `prompts/` 后修改 `prompts_dir`。
模板使用 `$variable`，各阶段支持：

| 文件 | 变量 |
|---|---|
| `system.md` | `$stage`、`$fields_json`、`$video_id`、`$id_prefix` |
| `events.md` | `$start`、`$end` |
| `dependencies.md` | `$window_seconds`、`$events_json`、`$anchors_json` |
| `tasks.md` | `$target_candidates`、`$dependencies_json` |
| `verifications.md` | `$questions_json` |
| `probe.md` | `$start`、`$end` |

模板里的普通美元符号使用 `$$`。保留程序要求的字段与契约，否则响应会被拒绝；
修改研究指令不代表放宽时序、引用、遮蔽或 Gold 门禁。实际模板内容、哈希和渲染后的请求均留档。

## 人工复看

本机已有入口：[`runs/GX010029_T1_review_20261029/review.html`](runs/GX010029_T1_review_20261029/review.html)。
双击 HTML 即可打开；无需服务端、账户或 API Key。

页面集中展示 4 条依赖的解释、原视频区间、完整近期窗口、关键历史片段与相关事件链接，
并提供 42 条事件的折叠视频证据、原始 JSON、模型原始响应和运行报告。
审核记录空模板为同目录的 `review_notes.template.json`，请另存填写真实审核者、时间和理由。
离线导入保留旧运行 provenance 和原始报告；`review_report.json` 只记录本次离线工作及 0 次 API 调用。

所有产物保持 `CANDIDATE/PENDING`。当前 42/4 只是模型候选，未完成独立事实核验。
0.5fps 粗采样可能漏掉短动作；模型时间定位不是逐帧真值。程序检查合法性不能替代事实复看。
V0.2 不自动生成 Gold，不实现 Agent Runtime、四条件评测、批量视频或复杂审批平台。
