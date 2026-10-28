---
language:
- en
pretty_name: "Ego Mistake Corrections Benchmark - Subsampled"
license: other
task_categories:
- video-text-to-text
tags:
- streaming
- video
- text
- multimodal
- cooking
annotations_creators:
- expert-generated
multilinguality: monolingual
source_datasets:
- original
size_categories:
- 1K<n<10K
configs:
- config_name: default
  data_files:
  - split: test
    path: annotations/annotations.json
dataset_info:
- config_name: default
  features:
  - name: video_id
    dtype: string
  - name: texts
    sequence: string
  - name: text_types
    sequence: string
  - name: text_timestamps
    sequence: float64
  splits:
  - name: test
    num_examples: 7
---

# Ego Mistake Corrections Benchmark (Ego-MC-Bench) - Random Sample

> **GX010021 第一阶段视频核验准备（2026-10-27）**：已新增独立的
> [审核工作台](results/video_review/GX010021_phase1_20261027/index.html)、
> [视频时间线](results/video_review/GX010021_phase1_20261027/timeline.md)、
> [T1–T3候选分析](results/video_review/GX010021_phase1_20261027/tasks.md)及
> [方法与校验说明](results/video_review/GX010021_phase1_20261027/README.md)。
> 视频无音轨；全部新增实体均为 CANDIDATE/PENDING，Gold为空，未运行正式评测。
> 当前 E1–E6 定义采用 [phase1_20261027](experiments/phase1_20261027/README.md)。
> 下文旧准备阶段记录与旧实验编号作为历史材料保留；其“未观看视频”等说明只描述原始候选包。

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

---

# 长程流式视频 Agent Benchmark：实验准备底座

本仓库现包含原始 Ego-MC 子集和一套最小的派生数据基础结构。当前阶段只做 Schema、
GX010021 文本候选转换、审核契约、实验计划及数据校验；没有调用大模型、运行 Agent、
正式评测或开发前端。原始 `videos/`、`annotations/`、`docs/`、`sample_manifest.json` 保留原位，
不移动、不覆盖、不重新下载。上方原始数据卡及发行信息继续保留。

## Track 与实验分组

本次准备工作以以下编号为准：

| Track | 含义 | 主要实体 | 与现有总体设计 V1.0 的关系 |
|---|---|---|---|
| T1 | 状态维护 | Event、State | 对应原稿 T1 |
| T2 | 前置约束 | Rule、Dependency、Task | 对应原稿 T2.1 子集 |
| T3 | 历史依赖 | Rule、Dependency、Task | 对应原稿 T2.2/T2.3 子集 |

原稿 `docs/Long_Horizon_Streaming_Agent_Benchmark_Overall_Design_v1.0 (1).md` 中，
T2 表示长程依赖推理，T3 表示持续监测与及时干预。本次按当前需求组织目录，
映射写入 `configs/tracks.json`，原稿保持不变。干预时间语义保留为独立 `Intervention` 实体，
后续研究版 Track 命名还需确认。

E1–E6 是本次提出的准备计划，原稿没有既定 E1–E6 编号：
E1 近期窗口与历史基线，E2 状态/记忆消融，E3 前置约束，E4 历史证据/规则修订，
E5 可见性/捷径诊断，E6 跨来源与预算稳健性。各组 `plan.json` 均为 `DRAFT`、`enabled: false`，
可在 `experiments/README.md` 查看问题和前置条件。

## 项目结构

```text
ego_mc_subsampled/
├── videos/                         # 原始 7 个 MP4，原位保留
├── annotations/annotations.json    # 原始文本标注，不改写
├── docs/                          # 原始总体设计稿，不改写
├── sample_manifest.json            # 原始抽样清单，不改写
├── datasets/
│   ├── README.md                   # 新来源适配契约
│   ├── ego_mc/
│   │   ├── convert.py              # 保守、可复现的本地转换
│   │   └── GX010021/
│   │       ├── episode.json
│   │       ├── sources.json
│   │       ├── evidence.jsonl
│   │       ├── events.jsonl
│   │       ├── states.jsonl
│   │       ├── dependencies.jsonl
│   │       ├── rules.jsonl
│   │       ├── tasks.jsonl
│   │       ├── gold.jsonl           # 当前为空，绝不自动生成 GOLD
│   │       └── interventions.jsonl
│   ├── assembly101/README.md       # 接入步骤；未下载、未导入
│   └── holoassist/README.md        # 接入步骤；未下载、未导入
├── benchmark/
│   ├── schema.json                # Draft 2020-12，可执行的准备版 0.1.0
│   ├── README.md                  # 字段/引用/时间/审核语义
│   ├── validate.py                # 结构、来源、引用、时间与门禁校验
│   ├── tracks/{T1,T2,T3}/README.md
│   └── tests/test_validate.py
├── agents/README.md                # 后续 Agent 接口契约，无模型实现
├── evaluation/README.md            # 后续评分边界，无正式评分器
├── experiments/
│   ├── README.md
│   └── E1/ … E6/plan.json          # 六组禁用的计划
├── configs/
│   ├── preparation.json           # 准备模式、窗口/阈值待校准
│   ├── tracks.json
│   └── datasets.json
├── results/
│   ├── preparation/
│   │   ├── original_assets.json    # 改动前原始资产大小与 SHA-256
│   │   ├── validation.json         # 数据结构与原始资产检查
│   │   ├── readiness.json          # GOLD 门禁，当前预期 FAIL
│   │   ├── tests.txt               # 数据门禁回归测试记录
│   │   ├── reproducibility.json    # 重新转换与已交付数据的逐文件比对
│   │   └── human_review.md         # 人工待办与原文定位
│   └── E1/ … E6/                  # 结果占位，尚无实验输出
└── requirements.txt
```

## 统一 Schema 与可信度

实体定义和完整字段见 [benchmark/schema.json](benchmark/schema.json) 及
[字段说明](benchmark/README.md)。Schema 版本为 **0.1.0 准备版**，不是设计稿设想的最终冻结协议。
所有实体共有版本、全局 ID、Episode ID、时间区间、`known_at`、证据引用、派生关系、来源方法、
成熟度和审核记录；证据单独记录源文件、SHA-256、精确定位、原话、时间锚点和发布时刻。

| 实体 | 作用 | 当前转换策略 |
|---|---|---|
| Event | 原始发言与后续实际观察事件分层 | 逐字复制 55 条发言，不当作实际动作 |
| State | 对象/过程实际状态 | 3 个待审核检查点，值均为 null、basis 为 unknown |
| Dependency | 前置、替代与跨时间关系 | 3 个替代假设 + 1 个托盘准备约束假设 |
| Rule | 指令内容、版本与有效期 | 19 条 Instruction/Clarification；有效期与 supersedes 留待审核 |
| Task | Track、查询时刻、证据集合、目标 | 每 Track 1 条草案，共 3 条，全部禁用，无答案 |
| Gold | 经审核任务答案与支持引用 | 空表 |
| Intervention | 反馈、偏差、可检测区间、截止、恢复 | 7 个 Feedback 锚点；其他错误时间均为 null |

所有导入证据和派生实体均为 `maturity: CANDIDATE`、`review.status: PENDING`。
没有人工核验的内容不能升级为 `REVIEWED/GOLD`。`Success` 不等于动作实际完成；
`Instruction-Clarification` 不自动等于规则替代；`Feedback` 时间不等于错误开始或最早可检测时间。
来源是文字标注时不会补造视频帧、动作区间或对象轨迹。

## 数据流与复现命令

```text
保留的本地原始数据
  → 来源哈希 / JSON Pointer / 原始时间锚点
  → PRIVATE 的证据与 CANDIDATE/PENDING 实体
  → 结构、来源、引用、时间与审核校验
  → 人工视频复核、必要证据集与裁决记录
  → 经审核的任务与私有 GOLD
  → 后续因果 Runner → Agent → Evaluator（尚未实现）
```

Python 3.11+，从项目根目录执行。除 `jsonschema` 外仅用标准库。
可选的本地 `ffprobe` 只读取时长元数据，不转换或重写视频。当前读取的 GX010021 时长为
696.929567 秒；最后一条标注为 692.608 秒。缺少 ffprobe 时保留未知时长并报告校验限制。

```powershell
python -m pip install -r requirements.txt

# 已附首批转换数据；重新生成请用全新的版本目录，不覆盖人工工作
python -m datasets.ego_mc.convert --output datasets/ego_mc/GX010021_candidate_v2

# 校验默认数据包，同时核对原始资产没有变化
python -m benchmark.validate --assets-snapshot results/preparation/original_assets.json --report results/preparation/validation.json

# 校验另一个版本目录
python -m benchmark.validate --data datasets/ego_mc/GX010021_candidate_v2

# 数据安全门禁回归测试
python -m unittest discover -s benchmark/tests -v

# 检查是否已有 GOLD；当前预期退出码 1，不启动评测
python -m benchmark.validate --require-gold --report results/preparation/readiness.json
```

转换器对既有输出目录直接拒绝；不提供会覆盖审核结果的 `--force`。
校验器退出码 0 表示结构检查通过，1 表示数据/门禁错误。
报告中的 warnings 提醒待审状态，**PASS 不代表事实正确、已满足全部因果运行条件或已可正式评测**。
本次结构与资产校验为 PASS、0 个错误；12 个原始资产的大小与哈希全部一致；26 个回归测试通过。
GOLD 门禁为预期 FAIL，因为 Gold 表为空。

## 实验准备流程

1. 冻结来源清单，保留原始文件，复制候选包到新的审核版本目录。
2. 按 `results/preparation/human_review.md` 播放原视频，核对动作、对象、规范与事实；
   新增的视频证据必须指向实际看过的区间，不能把原文本点时间扩成猜测区间。
3. 为证据/实体写入真实审核者、ISO 8601 审核时间和理由；关键分歧做独立复核并在新版本保留裁决。
   确认规则有效期、替代范围、前置约束，完成 T1/T2/T3 所需的充分证据和未知状态标注。
4. 核实在线发布时刻。当前标注没有句子结束时间，完整转写均为 `PRIVATE`，
   `available_at: null`；不允许把整份转写或未来指令预先交给 Agent。
5. 在查询时刻之前证据充分后，再人工写入 `gold.jsonl`、记录支持关系；
   启用任务还需通过审核闭包与 GOLD 门禁，T3 需确认历史必要性。答案文本本身也须人工审查。
6. 再实现因果 Runner、隔离 Probe、Agent 和评分器，校准窗口/阈值/预算后逐组启用实验。
   当前 `configs/preparation.json` 的模型与评测开关均为 false，未定参数均为 null。

本子集共 7 个视频，目前只转换 GX010021，未强行划分 train/dev/test。
后续应按完整原视频及实际可获得的参与者/任务关联分组，避免近重复片段跨集合。

## 接入 Assembly101、HoloAssist

两个来源都只建立适配入口说明，未下载数据，也没有声称其字段已兼容。
具体步骤见 [Assembly101 接入说明](datasets/assembly101/README.md) 和
[HoloAssist 接入说明](datasets/holoassist/README.md)。
统一做法是确认实际版本/许可 → 登记原始路径、哈希和时间基准 → 独立适配器转换到同一 Schema →
先交付一个候选 Episode 并校验 → 人工审核后再扩展。若有多视角或多模态，需明确主时钟与同步映射；
若只提供动作标签，不能自动补出对象状态、前置约束、错误或历史必要性。
来源差异保存在证据/来源层；T1/T2/T3 继续消费统一实体，缺失的能力报告数据缺口。
