"""Shared helpers for Stage 1 data engineering: paths, raw parsing, ffprobe metadata."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEOS_DIR = ROOT / "videos"
ANNOTATIONS_PATH = ROOT / "annotations" / "annotations.json"
SAMPLE_MANIFEST_PATH = ROOT / "sample_manifest.json"
BENCHMARK_DIR = ROOT / "benchmark"
SOURCE_DIR = BENCHMARK_DIR / "source"
METADATA_DIR = BENCHMARK_DIR / "metadata"
SCHEMAS_DIR = BENCHMARK_DIR / "schemas"
REPORTS_DIR = BENCHMARK_DIR / "reports"

VIDEO_EXTENSIONS = {".mp4", ".MP4", ".mov", ".MOV", ".mkv", ".MKV"}
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

KNOWN_TEXT_TYPES = [
    "Instruction",
    "Feedback",
    "Success",
    "User-Comment",
    "User-Question",
    "Instruction-Clarification",
]

SCHEMA_VERSION = "1.0.0"


def load_annotations(path: Path = ANNOTATIONS_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def load_sample_manifest(path: Path = SAMPLE_MANIFEST_PATH):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scan_videos(videos_dir: Path = VIDEOS_DIR) -> dict[str, Path]:
    """Return {video_id: path}; video_id is the filename stem."""
    videos = {}
    for p in sorted(videos_dir.iterdir()):
        if p.is_file() and p.suffix in VIDEO_EXTENSIONS:
            videos[p.stem] = p
    return videos


def _parse_fps(rate: str) -> float | None:
    if not rate or rate == "0/0":
        return None
    num, _, den = rate.partition("/")
    try:
        fps = float(num) / float(den)
    except (ValueError, ZeroDivisionError):
        return None
    return round(fps, 3)


def probe_video(path: Path) -> dict:
    """Extract duration / fps / resolution / codec via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    vstream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if vstream is None:
        raise ValueError(f"no video stream found in {path}")
    fmt = info.get("format", {})
    duration = fmt.get("duration") or vstream.get("duration")
    return {
        "duration_seconds": round(float(duration), 3) if duration else None,
        "fps": _parse_fps(vstream.get("avg_frame_rate", "")),
        "resolution": {"width": vstream.get("width"), "height": vstream.get("height")},
        "video_codec": vstream.get("codec_name"),
        "container": fmt.get("format_name"),
        "file_size_bytes": int(fmt.get("size", path.stat().st_size)),
    }


def build_events(row: dict) -> list[dict]:
    """Zip the three parallel annotation arrays into a typed event list."""
    texts = row.get("texts", [])
    types = row.get("text_types", [])
    timestamps = row.get("text_timestamps", [])
    if not (len(texts) == len(types) == len(timestamps)):
        raise ValueError(
            f"array length mismatch for {row.get('video_id')}: "
            f"texts={len(texts)} text_types={len(types)} text_timestamps={len(timestamps)}"
        )
    return [
        {"index": i, "type": types[i], "text": texts[i], "timestamp": timestamps[i]}
        for i in range(len(texts))
    ]
