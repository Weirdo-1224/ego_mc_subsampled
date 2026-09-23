"""Stage 1 build: parse raw Ego-MC-Bench data and emit normalized source + per-video metadata.

Reads (read-only):  videos/*, annotations/annotations.json, sample_manifest.json (if present)
Writes:             benchmark/source/normalized_annotations.json
                    benchmark/metadata/<video_id>.json
                    benchmark/metadata/index.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

CORE_TYPES = ("Instruction", "Feedback", "Success")


def _rel(path: Path) -> str:
    return path.relative_to(common.ROOT).as_posix()


def build_video_metadata(video_id: str, video_path: Path, events: list[dict]) -> dict:
    probe = common.probe_video(video_path)
    type_counts = Counter(e["type"] for e in events)
    timestamp_index = {
        t: [
            {"index": e["index"], "timestamp": e["timestamp"]}
            for e in events
            if e["type"] == t
        ]
        for t in CORE_TYPES
    }
    return {
        "video_id": video_id,
        "path": _rel(video_path),
        "file_size_bytes": probe["file_size_bytes"],
        "container": probe["container"],
        "duration_seconds": probe["duration_seconds"],
        "fps": probe["fps"],
        "resolution": probe["resolution"],
        "video_codec": probe["video_codec"],
        "has_annotation": len(events) > 0,
        "event_count": len(events),
        "type_counts": dict(sorted(type_counts.items())),
        "timestamp_index": timestamp_index,
        "schema_version": common.SCHEMA_VERSION,
    }


def main() -> None:
    annotations = {row["video_id"]: row for row in common.load_annotations()}
    videos = common.scan_videos()
    manifest = common.load_sample_manifest()

    all_ids = sorted(set(videos) | set(annotations))
    if not all_ids:
        raise SystemExit("no videos or annotations found")

    common.SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    common.METADATA_DIR.mkdir(parents=True, exist_ok=True)
    for stale in common.METADATA_DIR.glob("*.json"):
        if stale.stem not in all_ids and stale.name != "index.json":
            stale.unlink()

    source_videos = []
    metadata_files = {}
    for video_id in all_ids:
        video_path = videos.get(video_id)
        row = annotations.get(video_id)
        events = common.build_events(row) if row is not None else []

        source_videos.append({
            "video_id": video_id,
            "video_file": _rel(video_path) if video_path else None,
            "has_video": video_path is not None,
            "has_annotation": row is not None,
            "event_count": len(events),
            "events": events,
        })

        if video_path is not None:
            meta = build_video_metadata(video_id, video_path, events)
            meta_path = common.METADATA_DIR / f"{video_id}.json"
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            metadata_files[video_id] = _rel(meta_path)

    normalized = {
        "schema_version": common.SCHEMA_VERSION,
        "stage": "stage1",
        "source": {
            "annotations_file": _rel(common.ANNOTATIONS_PATH),
            "videos_dir": _rel(common.VIDEOS_DIR),
            "sample_manifest": _rel(common.SAMPLE_MANIFEST_PATH) if manifest is not None else None,
        },
        "videos": source_videos,
    }
    (common.SOURCE_DIR / "normalized_annotations.json").write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    index = {
        "schema_version": common.SCHEMA_VERSION,
        "stage": "stage1",
        "video_count": len(all_ids),
        "annotated_video_count": sum(1 for v in source_videos if v["has_video"] and v["has_annotation"]),
        "total_events": sum(v["event_count"] for v in source_videos),
        "videos": {
            v["video_id"]: {
                "metadata": metadata_files.get(v["video_id"]),
                "has_video": v["has_video"],
                "has_annotation": v["has_annotation"],
                "event_count": v["event_count"],
            }
            for v in source_videos
        },
    }
    (common.METADATA_DIR / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"videos on disk:        {len(videos)}")
    print(f"annotation rows:       {len(annotations)}")
    print(f"paired video+annot:    {index['annotated_video_count']}")
    print(f"total events:          {index['total_events']}")
    print(f"sample_manifest.json:  {'found' if manifest is not None else 'MISSING'}")
    for v in source_videos:
        if not (v["has_video"] and v["has_annotation"]):
            print(f"unpaired:              {v['video_id']} "
                  f"(video={v['has_video']}, annotation={v['has_annotation']})")


if __name__ == "__main__":
    main()
