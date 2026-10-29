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

# 长程流式视频 Agent Benchmark：开发底座

本仓库包含原始 Ego-MC 子集和一套最小数据基础结构。原始 `videos/`、`annotations/`、
`docs/`、`sample_manifest.json` 保留原位，不移动、不覆盖、不重新下载。上方原始数据卡
及发行信息继续保留。

当前底座提供：统一 Schema（`benchmark/schema.json`，0.1.0 准备版）、可执行校验器
（`benchmark/validate.py`）、保守可复现的文本候选转换器（`datasets/ego_mc/convert.py`）、
Track 定义（`configs/tracks.json`）与数据门禁回归测试（`benchmark/tests/`）。
没有调用大模型、运行 Agent 或正式评测。

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
│   │   └── convert.py              # 保守、可复现的本地转换
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
├── configs/
│   ├── tracks.json                # T1 状态维护 / T2 前置约束 / T3 历史依赖
│   └── datasets.json              # 来源登记与接入状态
├── results/                        # 结果占位，尚无实验输出
└── requirements.txt
```

## 统一 Schema 与可信度

实体定义和完整字段见 [benchmark/schema.json](benchmark/schema.json) 及
[字段说明](benchmark/README.md)。Schema 版本为 **0.1.0 准备版**，不是最终冻结协议。
所有实体共有版本、全局 ID、Episode ID、时间区间、`known_at`、证据引用、派生关系、来源方法、
成熟度和审核记录；证据单独记录源文件、SHA-256、精确定位、原话、时间锚点和发布时刻。

| 实体 | 作用 |
|---|---|
| Event | 原始发言与后续实际观察事件分层 |
| State | 对象/过程实际状态 |
| Dependency | 前置、替代与跨时间关系 |
| Rule | 指令内容、版本与有效期 |
| Task | Track、查询时刻、证据集合、目标 |
| Gold | 经审核任务答案与支持引用 |
| Intervention | 反馈、偏差、可检测区间、截止、恢复 |

转换器产出的所有证据和派生实体均为 `maturity: CANDIDATE`、`review.status: PENDING`，
Gold 为空。没有人工核验的内容不能升级为 `REVIEWED/GOLD`。`Success` 不等于动作实际完成；
`Feedback` 时间不等于错误开始或最早可检测时间。来源是文字标注时不会补造视频帧、
动作区间或对象轨迹。

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
可选的本地 `ffprobe` 只读取时长元数据，不转换或重写视频。

```powershell
python -m pip install -r requirements.txt

# 生成候选数据包（输出目录必须不存在，不覆盖人工工作）
python -m datasets.ego_mc.convert --output datasets/ego_mc/GX010021_candidate_v1

# 校验数据包
python -m benchmark.validate --data datasets/ego_mc/GX010021_candidate_v1

# 数据门禁回归测试
python -m unittest discover -s benchmark/tests -v
```

转换器对既有输出目录直接拒绝；不提供会覆盖审核结果的 `--force`。
校验器退出码 0 表示结构检查通过，1 表示数据/门禁错误。报告中的 warnings
提醒待审状态，PASS 不代表事实正确或已可正式评测。

## 后续步骤

1. 人工观看原视频，核对动作、对象、规范与事实；新增证据必须指向实际看过的区间。
2. 写入真实审核者、审核时间和理由后，方可升级成熟度并人工编写 `gold.jsonl`。
3. 实现因果 Runner、隔离 Probe、Agent 和评分器，校准窗口/阈值/预算后再启用实验。

本子集共 7 个视频；后续转换应覆盖全部视频，并按完整原视频及实际可获得的
参与者/任务关联分组，避免近重复片段跨集合。

## 接入 Assembly101、HoloAssist

两个来源都只建立适配入口说明，未下载数据，也没有声称其字段已兼容。
具体步骤见 [Assembly101 接入说明](datasets/assembly101/README.md) 和
[HoloAssist 接入说明](datasets/holoassist/README.md)。统一做法是确认实际版本/许可 →
登记原始路径、哈希和时间基准 → 独立适配器转换到同一 Schema → 先交付一个候选
Episode 并校验 → 人工审核后再扩展。
