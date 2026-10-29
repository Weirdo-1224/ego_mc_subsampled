# Long-Horizon Streaming Video Agent Benchmark

本项目的主研究目标是从原始长视频构建具有**必要历史依赖**的流式视频 Agent 评测任务。
离线 Long-History Task Mining Pipeline 借助外部视频大模型发现事件和历史依赖，构造任务，
通过视频证据核验与程序化筛选获得高质量候选，最终由人工复看视频并确认 Gold。
当前版本为 **V0.1 开发底座**，尚未调用视频模型或生成新候选。

```text
Raw Video → Event Discovery → Dependency Mining → Task Construction
          → Evidence Verification → Automatic Filtering → Human Review → Gold
```

原始 MP4 是新流水线的唯一事实来源。原始文本标注和旧候选仅保留作历史资料，
不参与新流水线，不作为模型提示、参考答案或筛选依据。必须先挖掘依赖再生成问题。

| 任务 | 研究对象 | 每道任务必须具备 |
|---|---|---|
| T1 过程状态 | 由先前操作形成、在当前时刻仍相关的状态 | 查询时刻、当前窗口、必要历史视频证据、依赖解释、可执行历史遮蔽设计 |
| T2 前置约束 | 当前动作依赖的实际历史条件 | 同上，并核验前置条件与当前动作的关系 |
| T3 跨窗口历史关联 | 不同时间窗口中的对象、事件与关系 | 同上，并核验跨窗口关联与历史必要性 |

模型发现、模型核验、自动筛选都只能输出 `CANDIDATE/PENDING`。只有人工完成视频证据、
答案和历史必要性复核，记录真实审核者、时间及理由后，才能确认 Gold。
离线构造器可以访问全片；正式被测 Agent 必须严格遵守流式因果约束，
查询时刻之后的片段不得成为必要作答信息，也不能向被测 Agent 泄露构造推理或私有答案。

## 当前能力与边界

- 七个视频的显式本地登记/发现配置，支持外部视频目录；配置状态是 `VIDEO_MINING_NOT_STARTED`，不宣称已导入候选。
- 基于 ffprobe 的只读预检查：文件存在性、非空、时长、帧率、音频流及开头约一秒视频包的基本可读性。
  缺失或探测失败返回 ERROR；无音频记录为空数组，不虚构音频。
- `task_mining/` 的最小模块入口、视频模型接口和中间数据契约。复杂阶段尚未实现，没有模型请求、自动 Gold 或真实评测结果。
- 原有 `benchmark/schema.json`、`benchmark/validate.py` 和 26 项数据校验测试原样保留。
  新中间契约尚未导出到旧 Schema；结构校验 PASS 不代表视频事实正确。
- `datasets/ego_mc/convert.py` 标记为 **Legacy**，仅供显式历史复现和原测试，不再是默认开发入口。

本轮不实现 Agent Runtime、评测 Runner 或复杂审核平台。开发约束见 [AGENTS.md](AGENTS.md)，
阶段输入输出、证据和遮蔽约定见 [task_mining/README.md](task_mining/README.md)。

## 本地启动与验证

Python 3.11+；安装已有 Python 依赖，并把 FFmpeg 发行包中的 `ffprobe` 加入 PATH，
或通过 `--ffprobe` 指定可执行文件。视频是本地资产，不要求随 Git 分发。

```powershell
python -m pip install -r requirements.txt

# 默认发现并预检查七个 videos/<video_id>.MP4，生成本地登记结果
python -m task_mining --output runs/local_video_registry.json

# 视频在其他目录时；复跑使用新的输出文件名，已有结果不会覆盖
python -m task_mining --video-root D:/local/videos --output runs/local_video_registry_external.json

# 原校验测试 + 新流程回归测试（测试会显式调用 Legacy 转换器以验证兼容性）
python -m unittest discover -v

# 对已经存在的旧格式 bundle，继续使用原校验器
python -m benchmark.validate --data <existing_bundle_directory>
```

配置文件是 [configs/datasets.json](configs/datasets.json)。`local_videos.root` 相对配置文件目录解析；
`--video-root` 相对当前工作目录解析。固定登记 GX010021、GX010029、GX010033、GX010037、
GX010049、GX010053、GX010063；不会把配置中列出的文件直接视为可用。
预检查成功返回 0；任何视频缺失、ffprobe 不可用/探测失败或配置/输出错误返回 1。
逐视频报告保留错误和未知字段，结果默认写入已忽略的 `runs/`。
可读性检查只覆盖元数据和开头视频包，不等于全片解码或视频证据核验。

## 开发入口

```text
AGENTS.md                         # 后续开发必须遵守的研究边界
configs/datasets.json             # 七视频配置及其他来源的未导入状态
task_mining/
  __main__.py                     # 默认 CLI，只运行预检查
  preflight.py                    # 本地视频发现、ffprobe 检查与 registry
  contracts.py                    # Event/Dependency/Task/Verification/Filtering 接口
  README.md                       # 阶段契约及后续接入说明
  tests/test_preflight.py          # 无旧标注依赖、失败报告与预检查回归
benchmark/{schema.json,validate.py} # 原有数据包校验能力
benchmark/tests/test_validate.py   # 原有校验回归
datasets/ego_mc/convert.py         # Legacy，不参与新流程
videos/                           # 本地原始 MP4，不入 Git
annotations/、docs/、sample_manifest.json # 保留的原始资料，不修改
```

下一步从 [MiningBackend](task_mining/contracts.py) 接入一个真实视频模型：
选择一个 READY 视频，计算原文件 SHA-256 构造 `VideoInput`，先实现 `discover_events(video)`，
再实现 `mine_dependencies(video, events)`，最后才进入 `construct_tasks` 和独立视频核验。
接入时补充模型响应的严格解析、引用和时间范围校验，显式配置模型、提示词版本、采样/分窗、
预算、超时和重试；密钥从环境读取，模型响应及派生产物写入忽略的运行目录。
历史遮蔽比较与自动筛选随后实现，通过筛选仅送人工审核。

现有 Assembly101、HoloAssist 仍为 NOT_IMPORTED；来源接入说明保留，未下载或声称字段兼容。
原始设计稿和旧适配文档作为历史参考，新主线以根 README、AGENTS 和 task_mining 契约为准。

## 原始数据来源与许可（保留的发行信息）

本地原始数据来自 **Ego Mistake Corrections Benchmark (Ego-MC-Bench) - Random Sample**，
本仓库为其七视频子集，抽样清单版本 1.0.0。原始 `videos/`、`annotations/`、`docs/`、
`sample_manifest.json` 保留原位；历史标注的格式、统计与研究用途许可如下。
这些发行信息不代表旧文本标注属于新流水线输入，也不代表 Gold。

### Ego Mistake Corrections Benchmark (Ego-MC-Bench) - Random Sample


## Release Files

- `annotations/annotations.json`
- `videos/*.MP4`
- `sample_manifest.json`

## Sample Statistics

- Total videos: 7
- Total annotations: 253

Selected videos:
- `GX010021`
- `GX010029`
- `GX010033`
- `GX010037`
- `GX010049`
- `GX010053`
- `GX010063`

Text type counts:
- `Feedback`: 54
- `Instruction`: 85
- `Instruction-Clarification`: 10
- `Success`: 82
- `User-Comment`: 12
- `User-Question`: 10

## Data Format

Each row in `annotations.json` has schema:

```json
{
  "video_id": "GX010021",
  "texts": ["Let's first preheat the oven to 350 degrees Fahrenheit."],
  "text_types": ["Instruction"],
  "text_timestamps": [4.418]
}
```

Video asset convention:

- `videos/<video_id>.MP4`

## Dataset License

This dataset is released for research purposes only.
