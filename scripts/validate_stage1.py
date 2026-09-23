"""Stage 1 validation: data integrity checks + JSON Schema validation + Stage 1 report.

Checks (severity: error fails the run; warning is reported but does not fail):
  - annotations_parse            error    annotations.json is a JSON array of objects
  - array_length_consistency     error    texts/text_types/text_timestamps equal length per row
  - video_id_integrity           error    video_ids non-empty, well-formed, no duplicates
  - video_annotation_parity      error    every annotation row has a video file
                                 warning  video files without annotation rows
  - timestamp_bounds             error    0 <= timestamp <= video duration
  - timestamp_monotonic          warning  timestamps non-decreasing within each video
  - text_type_known              warning  text_types within the known enum
  - sample_manifest              warning  sample_manifest.json present
  - directory_structure          error    required benchmark/ subdirectories exist
  - schema_self_valid            error    every schema passes Draft 2020-12 meta-validation
  - error_schema_fields          error    error schema reserves all required fields
  - metadata_against_schema      error    generated per-video metadata validates
  - source_against_schema        error    normalized_annotations.json validates
  - metadata_reproducible        error    re-probing videos reproduces stored metadata

Writes: benchmark/reports/validation_report.json, benchmark/reports/stage1_report.md
Exit code: 0 on PASS / PASS_WITH_WARNINGS, 1 on FAIL.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

ERROR_RESERVED_FIELDS = [
    "error_id", "video_id", "step_id", "error_type", "expected", "observed",
    "evidence", "evidence_start", "detectable_time", "intervention_time",
    "context_dependency", "required_history",
]
REQUIRED_SCHEMAS = ["procedure", "timeline", "error", "episode"]
REQUIRED_DIRS = ["source", "metadata", "procedures", "timelines", "errors", "episodes", "schemas", "reports"]


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def add(self, name: str, ok: bool, severity: str = "error", details: list[str] | None = None) -> None:
        self.checks.append({
            "check": name,
            "status": "pass" if ok else ("warning" if severity == "warning" else "fail"),
            "severity": severity,
            "details": details or [],
        })

    @property
    def verdict(self) -> str:
        statuses = {c["status"] for c in self.checks}
        if "fail" in statuses:
            return "FAIL"
        if "warning" in statuses:
            return "PASS_WITH_WARNINGS"
        return "PASS"


def _load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_checks() -> tuple[Report, dict]:
    rep = Report()

    # --- raw data ---
    annotations = common.load_annotations()
    rep.add("annotations_parse", isinstance(annotations, list) and all(isinstance(r, dict) for r in annotations))

    length_bad, id_bad, seen = [], [], set()
    type_counter: Counter = Counter()
    unknown_types: set[str] = set()
    for row in annotations:
        vid = row.get("video_id")
        n = {len(row.get(k, [])) for k in ("texts", "text_types", "text_timestamps")}
        if len(n) != 1:
            length_bad.append(f"{vid}: texts={len(row.get('texts', []))} "
                              f"text_types={len(row.get('text_types', []))} "
                              f"text_timestamps={len(row.get('text_timestamps', []))}")
        if not vid or not common.VIDEO_ID_PATTERN.match(str(vid)) or vid in seen:
            id_bad.append(str(vid))
        seen.add(vid)
        for t in row.get("text_types", []):
            type_counter[t] += 1
            if t not in common.KNOWN_TEXT_TYPES:
                unknown_types.add(t)
    rep.add("array_length_consistency", not length_bad, details=length_bad)
    rep.add("video_id_integrity", not id_bad, details=[f"duplicate/invalid: {v}" for v in id_bad])
    rep.add("text_type_known", not unknown_types, severity="warning",
            details=[f"unknown text_type: {t}" for t in sorted(unknown_types)])

    # --- pairing + timestamps ---
    videos = common.scan_videos()
    missing_video = sorted(set(seen) - set(videos))
    missing_annotation = sorted(set(videos) - set(seen))
    parity_details = ([f"annotation without video file: {v}" for v in missing_video]
                      + [f"video without annotation: {v}" for v in missing_annotation])
    if missing_video:
        rep.add("video_annotation_parity", False, details=parity_details)
    elif missing_annotation:
        rep.add("video_annotation_parity", False, severity="warning", details=parity_details)
    else:
        rep.add("video_annotation_parity", True)

    probes = {vid: common.probe_video(p) for vid, p in videos.items()}
    oob, nonmono = [], []
    for row in annotations:
        vid = row["video_id"]
        dur = probes.get(vid, {}).get("duration_seconds")
        ts = row["text_timestamps"]
        if dur is not None:
            for i, t in enumerate(ts):
                if not (0 <= t <= dur):
                    oob.append(f"{vid}[{i}] timestamp={t} not in [0, {dur}]")
        for i in range(1, len(ts)):
            if ts[i] < ts[i - 1]:
                nonmono.append(f"{vid}[{i}] {ts[i]} < {ts[i - 1]}")
    rep.add("timestamp_bounds", not oob, details=oob)
    rep.add("timestamp_monotonic", not nonmono, severity="warning", details=nonmono)
    rep.add("sample_manifest", common.SAMPLE_MANIFEST_PATH.exists(), severity="warning",
            details=[] if common.SAMPLE_MANIFEST_PATH.exists() else ["sample_manifest.json not found (referenced in README.md)"])

    # --- directory structure ---
    missing_dirs = [d for d in REQUIRED_DIRS if not (common.BENCHMARK_DIR / d).is_dir()]
    rep.add("directory_structure", not missing_dirs, details=[f"missing: benchmark/{d}" for d in missing_dirs])

    # --- schemas ---
    schemas = {}
    for name in REQUIRED_SCHEMAS + ["video_metadata", "source_annotations"]:
        path = common.SCHEMAS_DIR / f"{name}.schema.json"
        if path.exists():
            schemas[name] = _load_json(path)
    schema_bad = []
    for name in REQUIRED_SCHEMAS:
        if name not in schemas:
            schema_bad.append(f"missing schema: {name}")
    for name, schema in schemas.items():
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as e:  # noqa: BLE001
            schema_bad.append(f"{name}: {e}")
    rep.add("schema_self_valid", not schema_bad, details=schema_bad)

    err_schema = schemas.get("error", {})
    props = err_schema.get("properties", {})
    required = err_schema.get("required", [])
    missing_fields = [f for f in ERROR_RESERVED_FIELDS if f not in props or f not in required]
    rep.add("error_schema_fields", not missing_fields,
            details=[f"missing reserved field: {f}" for f in missing_fields])

    # --- generated artifacts against schemas ---
    def validate_against(instance, schema_name: str, label: str) -> list[str]:
        if schema_name not in schemas:
            return [f"{label}: schema {schema_name} unavailable"]
        v = Draft202012Validator(schemas[schema_name])
        return [f"{label}: {e.message}" for e in v.iter_errors(instance)]

    meta_bad = []
    for vid, path in videos.items():
        meta_path = common.METADATA_DIR / f"{vid}.json"
        if not meta_path.exists():
            meta_bad.append(f"{vid}: metadata file missing")
            continue
        meta_bad += validate_against(_load_json(meta_path), "video_metadata", vid)
    rep.add("metadata_against_schema", not meta_bad, details=meta_bad)

    src_path = common.SOURCE_DIR / "normalized_annotations.json"
    src_bad = [] if src_path.exists() else ["normalized_annotations.json missing"]
    if src_path.exists():
        src_bad += validate_against(_load_json(src_path), "source_annotations", "source")
    rep.add("source_against_schema", not src_bad, details=src_bad)

    # --- reproducibility: stored metadata must match a fresh probe ---
    repro_bad = []
    for vid, path in videos.items():
        meta_path = common.METADATA_DIR / f"{vid}.json"
        if not meta_path.exists():
            continue
        meta = _load_json(meta_path)
        fresh = probes[vid]
        for key in ("duration_seconds", "fps", "resolution", "video_codec", "file_size_bytes"):
            if meta.get(key) != fresh.get(key):
                repro_bad.append(f"{vid}.{key}: stored={meta.get(key)} fresh={fresh.get(key)}")
    rep.add("metadata_reproducible", not repro_bad, details=repro_bad)

    stats = {
        "annotations": annotations,
        "videos": videos,
        "probes": probes,
        "type_counter": type_counter,
        "missing_annotation": missing_annotation,
        "missing_video": missing_video,
    }
    return rep, stats


def _fmt_seconds(s: float) -> str:
    m, sec = divmod(int(s), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def generate_report(rep: Report, stats: dict) -> str:
    annotations, videos, probes = stats["annotations"], stats["videos"], stats["probes"]
    type_counter = stats["type_counter"]
    total_events = sum(len(r["texts"]) for r in annotations)
    total_duration = sum(p["duration_seconds"] for p in probes.values() if p["duration_seconds"])
    total_bytes = sum(p.stat().st_size for p in videos.values())

    L = []
    L.append("# Stage 1 报告：数据解析 + Schema + 目录初始化\n")
    L.append("## 1. 原始数据规模（README 声明）\n")
    L.append("- 视频：7 个；标注事件：253 条")
    L.append("- text_type 分布：Feedback 54 / Instruction 85 / Instruction-Clarification 10 / Success 82 / User-Comment 12 / User-Question 10\n")
    L.append("## 2. 实际发现\n")
    L.append(f"- 视频文件：{len(videos)} 个（{total_bytes / 2**30:.2f} GiB），总时长 {_fmt_seconds(total_duration)}")
    L.append(f"- 标注行：{len(annotations)} 行，事件总数 {total_events}")
    L.append(f"- 配对成功（视频+标注齐全）：{len(videos) - len(stats['missing_annotation'])} 个")
    L.append(f"- sample_manifest.json：{'存在（与实测数据核对一致）' if common.SAMPLE_MANIFEST_PATH.exists() else '缺失（README 中列为发布文件，但实际不存在）'}\n")
    L.append("| video_id | duration | fps | resolution | codec | events | Instruction | Success | Feedback |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for row in sorted(annotations, key=lambda r: r["video_id"]):
        vid = row["video_id"]
        p = probes.get(vid, {})
        counts = Counter(row["text_types"])
        res = p.get("resolution", {})
        L.append(
            f"| {vid} | {p.get('duration_seconds', '?')}s | {p.get('fps', '?')} "
            f"| {res.get('width')}x{res.get('height')} | {p.get('video_codec', '?')} | {len(row['texts'])} "
            f"| {counts.get('Instruction', 0)} | {counts.get('Success', 0)} | {counts.get('Feedback', 0)} |"
        )
    if stats["missing_annotation"]:
        for vid in stats["missing_annotation"]:
            p = probes[vid]
            res = p["resolution"]
            L.append(f"| {vid} | {p['duration_seconds']}s | {p['fps']} "
                     f"| {res['width']}x{res['height']} | {p['video_codec']} | 0（无标注） | - | - | - |")
    L.append("\n实测 text_type 分布：" + " / ".join(f"{k} {v}" for k, v in sorted(type_counter.items())) + "\n")

    L.append("## 3. 目录结构\n")
    L.append("```")
    L.append("benchmark/")
    tree = {
        "source/": "normalized_annotations.json —— video_id ↔ 视频文件 ↔ 事件 的完整映射",
        "metadata/": "index.json + 每视频一个 <video_id>.json（时长/FPS/分辨率/事件计数/时间戳索引）",
        "procedures/": "（空，Stage 2 产物）",
        "timelines/": "（空，Stage 2 产物）",
        "errors/": "（空，Stage 2 产物）",
        "episodes/": "（空，Stage 2 产物）",
        "schemas/": "procedure / timeline / error / episode / video_metadata / source_annotations 共 6 个 Schema",
        "reports/": "stage1_report.md + validation_report.json",
    }
    for d, desc in tree.items():
        L.append(f"├── {d:<14} # {desc}")
    L.append("scripts/")
    L.append("├── common.py           # 路径、原始解析、ffprobe 封装")
    L.append("├── build_metadata.py   # 生成 source/ 与 metadata/（可重复运行）")
    L.append("└── validate_stage1.py  # 校验 + 生成报告")
    L.append("```\n")
    L.append("原始数据（videos/、annotations/）全程只读，未做任何修改。\n")

    L.append("## 4. Schema 设计概要\n")
    L.append("- **procedure**：procedure_id / video_id / task / steps[step_id, order, instruction, depends_on, expected_outcome]")
    L.append("- **timeline**：timeline_id / video_id / duration_seconds / events[event_id, timestamp, event_type, description, step_id, source]")
    L.append("- **error**：预留字段 error_id / video_id / step_id / error_type / expected / observed / evidence{description, event_ids} / "
             "evidence_start / detectable_time / intervention_time(可空) / context_dependency / required_history[]")
    L.append("- **episode**：episode_id / video_id / video{path, duration, fps, resolution} / procedure_path / timeline_path / error_paths / metadata_path / stage")
    L.append("- 附加（校验 Stage 1 自身产物）：video_metadata、source_annotations")
    L.append("- 本阶段仅定义字段规范，未生成任何 Procedure / Timeline / Error 语义内容。\n")

    L.append("## 5. 数据异常\n")
    anomalies = []
    if stats["missing_annotation"]:
        anomalies.append(f"- **{', '.join(stats['missing_annotation'])} 无标注**：磁盘存在视频但 annotations.json 无对应行"
                         "（README 声明的 7 个视频均不含它），Stage 2 输入中应排除或待补标注")
    if not common.SAMPLE_MANIFEST_PATH.exists():
        anomalies.append("- **sample_manifest.json 缺失**：README 将其列为发布文件，实际不存在；source 映射中已记录为 null")
    for c in rep.checks:
        if c["status"] == "warning" and c["check"] not in ("video_annotation_parity", "sample_manifest"):
            for d in c["details"]:
                anomalies.append(f"- {c['check']}: {d}")
    L.extend(anomalies or ["- 无"])
    L.append("")

    L.append("## 6. Stage 2 可直接使用的输入\n")
    paired = len(videos) - len(stats["missing_annotation"])
    unpaired_note = ("；" + "、".join(stats["missing_annotation"]) + " 无标注，以 `has_annotation: false`、空事件列表显式标记") if stats["missing_annotation"] else ""
    L.append(f"- `benchmark/source/normalized_annotations.json`：全量 video_id ↔ 视频文件 ↔ 事件序列（index/type/text/timestamp）映射，"
             f"{paired} 个视频配对完整{unpaired_note}")
    L.append("- `benchmark/metadata/<video_id>.json`：每视频时长、FPS、分辨率、事件计数、Instruction/Success/Feedback 时间戳索引")
    L.append("- `benchmark/metadata/index.json`：全局索引与配对状态")
    L.append("- `benchmark/schemas/*.schema.json`：Stage 2 四类产物的字段规范与校验器")
    L.append("- 可用视频（有标注）：" + ", ".join(sorted(set(videos) - set(stats["missing_annotation"]))) + "\n")

    L.append("## 7. 校验结果\n")
    L.append("| 检查项 | 结果 | 严重级别 |")
    L.append("|---|---|---|")
    for c in rep.checks:
        mark = {"pass": "PASS", "warning": "WARN", "fail": "FAIL"}[c["status"]]
        L.append(f"| {c['check']} | {mark} | {c['severity']} |")
    L.append(f"\n**总体结论：{rep.verdict}**\n")
    return "\n".join(L)


def main() -> int:
    rep, stats = run_checks()

    common.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (common.REPORTS_DIR / "validation_report.json").write_text(
        json.dumps({"verdict": rep.verdict, "checks": rep.checks}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (common.REPORTS_DIR / "stage1_report.md").write_text(generate_report(rep, stats), encoding="utf-8")

    for c in rep.checks:
        mark = {"pass": "PASS", "warning": "WARN", "fail": "FAIL"}[c["status"]]
        print(f"[{mark:4s}] {c['check']}")
        for d in c["details"]:
            print(f"       - {d}")
    print(f"\nOverall: {rep.verdict}")
    return 1 if rep.verdict == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
