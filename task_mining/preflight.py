"""Discover configured MP4s and probe metadata plus one second of video packets."""

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/datasets.json"


def discover_videos(config=DEFAULT_CONFIG, video_root=None):
    """Read only the video registration config, never annotations or old candidates.

    Configured roots are relative to the config file. An override is relative to cwd.
    Every expected video is returned, including absent files, for explicit reporting.
    """
    config = Path(config).resolve()
    spec = json.loads(config.read_text(encoding="utf-8"))["ego_mc"]["local_videos"]
    ids = spec["video_ids"]
    if not isinstance(ids, list) or not ids or any(not isinstance(v, str) or not v for v in ids):
        raise ValueError("local_videos.video_ids must be a nonempty list of video IDs")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate configured video IDs")
    root = Path(video_root) if video_root is not None else config.parent / spec["root"]
    return [(vid, (root / spec["filename_pattern"].format(video_id=vid)).resolve()) for vid in ids]


def _positive_number(value):
    number = float(Fraction(str(value)))
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"Expected positive finite metadata, got {value!r}")
    return number


def _probe(ffprobe, path, arguments):
    try:
        result = subprocess.run(
            [str(ffprobe), "-v", "error", *arguments, "-of", "json", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
    except FileNotFoundError as exc:
        raise ValueError(f"ffprobe executable not found: {ffprobe}") from exc
    if result.returncode or result.stderr.strip():
        raise ValueError(f"ffprobe failed: {result.stderr.strip() or result.returncode}")
    return json.loads(result.stdout)


def inspect_video(video_id, path, ffprobe="ffprobe"):
    """READY means metadata and sampled packets passed, not full decode or truth."""
    path = Path(path)
    entry = {
        "video_id": video_id, "path": str(path.resolve()), "status": "ERROR",
        "exists": path.is_file(), "size_bytes": None, "duration_seconds": None,
        "frame_rate": None, "fps": None, "audio_streams": None,
        "basic_readable": False, "errors": [],
    }
    try:
        if not entry["exists"]:
            raise ValueError(f"Missing video file: {path}")
        entry["size_bytes"] = path.stat().st_size
        if not entry["size_bytes"]:
            raise ValueError(f"Empty video file: {path}")
        metadata = _probe(ffprobe, path, ["-show_format", "-show_streams"])
        streams = metadata.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"
                      and not s.get("disposition", {}).get("attached_pic")), None)
        if video is None:
            raise ValueError("No video stream found")
        entry["duration_seconds"] = _positive_number(metadata.get("format", {}).get("duration"))
        # avg_frame_rate may be 0/0 on some containers; fall back to r_frame_rate.
        for rate in (video.get("avg_frame_rate"), video.get("r_frame_rate")):
            try:
                entry["fps"] = _positive_number(rate)
                entry["frame_rate"] = rate
                break
            except (ValueError, ZeroDivisionError):
                continue
        if entry["fps"] is None:
            raise ValueError("No valid video frame rate")
        entry["audio_streams"] = [
            {"index": s["index"], "codec_name": s.get("codec_name"),
             "sample_rate": s.get("sample_rate"), "channels": s.get("channels")}
            for s in streams if s.get("codec_type") == "audio"
        ]
        sample = _probe(ffprobe, path, [
            "-select_streams", str(video["index"]), "-read_intervals", "%+1",
            "-show_packets", "-show_entries", "packet=size",
        ])
        if not any(int(p.get("size", 0)) > 0 for p in sample.get("packets", [])):
            raise ValueError("No readable video packets in initial one-second sample")
        entry.update(status="READY", basic_readable=True)
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError, subprocess.SubprocessError) as exc:
        entry["errors"].append(str(exc))
    return entry


def precheck(config=DEFAULT_CONFIG, video_root=None, ffprobe="ffprobe"):
    videos = [inspect_video(vid, path, ffprobe) for vid, path in discover_videos(config, video_root)]
    return {
        "registry_version": "0.1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": str(Path(config).resolve()), "ffprobe": str(ffprobe),
        "status": "READY" if all(v["status"] == "READY" for v in videos) else "ERROR",
        "check_scope": "metadata_and_initial_one_second_video_packets; not_full_decode_or_evidence_verification",
        "videos": videos,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--video-root", type=Path, help="Override local video directory")
    parser.add_argument("--ffprobe", default="ffprobe", help="ffprobe executable or full path")
    parser.add_argument("--output", type=Path, default=ROOT / "runs/local_video_registry.json")
    args = parser.parse_args(argv)
    try:
        report = precheck(args.config, args.video_root, args.ffprobe)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Never overwrite previous run/review artifacts, even on a failed check.
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Precheck failed: {exc}", file=sys.stderr)
        return 1
    for video in report["videos"]:
        detail = "; ".join(video["errors"]) if video["errors"] else (
            f'{video["duration_seconds"]:.3f}s, {video["fps"]:.3f} fps, '
            f'audio streams={len(video["audio_streams"])}'
        )
        print(f'{video["video_id"]}: {video["status"]}: {detail}')
    print(f'Registry: {args.output} ({report["status"]})')
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
