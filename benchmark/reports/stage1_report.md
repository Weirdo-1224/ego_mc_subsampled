# Stage 1 报告：数据解析 + Schema + 目录初始化

## 1. 原始数据规模（README 声明）

- 视频：7 个；标注事件：253 条
- text_type 分布：Feedback 54 / Instruction 85 / Instruction-Clarification 10 / Success 82 / User-Comment 12 / User-Question 10

## 2. 实际发现

- 视频文件：7 个（1.89 GiB），总时长 1:24:02
- 标注行：7 行，事件总数 253
- 配对成功（视频+标注齐全）：7 个
- sample_manifest.json：存在（与实测数据核对一致）

| video_id | duration | fps | resolution | codec | events | Instruction | Success | Feedback |
|---|---|---|---|---|---|---|---|---|
| GX010021 | 696.93s | 29.97 | 854x480 | h264 | 55 | 12 | 12 | 7 |
| GX010029 | 400.367s | 29.97 | 854x480 | h264 | 35 | 14 | 14 | 7 |
| GX010033 | 448.448s | 29.97 | 854x480 | h264 | 26 | 11 | 10 | 5 |
| GX010037 | 982.815s | 29.97 | 854x480 | h264 | 33 | 14 | 12 | 6 |
| GX010049 | 445.045s | 29.97 | 854x480 | h264 | 20 | 7 | 7 | 6 |
| GX010053 | 1216.348s | 29.97 | 854x480 | h264 | 45 | 17 | 17 | 11 |
| GX010063 | 852.385s | 29.97 | 854x480 | h264 | 39 | 10 | 10 | 12 |

实测 text_type 分布：Feedback 54 / Instruction 85 / Instruction-Clarification 10 / Success 82 / User-Comment 12 / User-Question 10

## 3. 目录结构

```
benchmark/
├── source/        # normalized_annotations.json —— video_id ↔ 视频文件 ↔ 事件 的完整映射
├── metadata/      # index.json + 每视频一个 <video_id>.json（时长/FPS/分辨率/事件计数/时间戳索引）
├── procedures/    # （空，Stage 2 产物）
├── timelines/     # （空，Stage 2 产物）
├── errors/        # （空，Stage 2 产物）
├── episodes/      # （空，Stage 2 产物）
├── schemas/       # procedure / timeline / error / episode / video_metadata / source_annotations 共 6 个 Schema
├── reports/       # stage1_report.md + validation_report.json
scripts/
├── common.py           # 路径、原始解析、ffprobe 封装
├── build_metadata.py   # 生成 source/ 与 metadata/（可重复运行）
└── validate_stage1.py  # 校验 + 生成报告
```

原始数据（videos/、annotations/）全程只读，未做任何修改。

## 4. Schema 设计概要

- **procedure**：procedure_id / video_id / task / steps[step_id, order, instruction, depends_on, expected_outcome]
- **timeline**：timeline_id / video_id / duration_seconds / events[event_id, timestamp, event_type, description, step_id, source]
- **error**：预留字段 error_id / video_id / step_id / error_type / expected / observed / evidence{description, event_ids} / evidence_start / detectable_time / intervention_time(可空) / context_dependency / required_history[]
- **episode**：episode_id / video_id / video{path, duration, fps, resolution} / procedure_path / timeline_path / error_paths / metadata_path / stage
- 附加（校验 Stage 1 自身产物）：video_metadata、source_annotations
- 本阶段仅定义字段规范，未生成任何 Procedure / Timeline / Error 语义内容。

## 5. 数据异常

- 无

## 6. Stage 2 可直接使用的输入

- `benchmark/source/normalized_annotations.json`：全量 video_id ↔ 视频文件 ↔ 事件序列（index/type/text/timestamp）映射，7 个视频配对完整
- `benchmark/metadata/<video_id>.json`：每视频时长、FPS、分辨率、事件计数、Instruction/Success/Feedback 时间戳索引
- `benchmark/metadata/index.json`：全局索引与配对状态
- `benchmark/schemas/*.schema.json`：Stage 2 四类产物的字段规范与校验器
- 可用视频（有标注）：GX010021, GX010029, GX010033, GX010037, GX010049, GX010053, GX010063

## 7. 校验结果

| 检查项 | 结果 | 严重级别 |
|---|---|---|
| annotations_parse | PASS | error |
| array_length_consistency | PASS | error |
| video_id_integrity | PASS | error |
| text_type_known | PASS | warning |
| video_annotation_parity | PASS | error |
| timestamp_bounds | PASS | error |
| timestamp_monotonic | PASS | warning |
| sample_manifest | PASS | warning |
| directory_structure | PASS | error |
| schema_self_valid | PASS | error |
| error_schema_fields | PASS | error |
| metadata_against_schema | PASS | error |
| source_against_schema | PASS | error |
| metadata_reproducible | PASS | error |

**总体结论：PASS**
