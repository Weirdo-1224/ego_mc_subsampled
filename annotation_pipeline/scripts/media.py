"""Read-only ffprobe checks reused from V0.1; no dataset/annotation dependency."""
import json
import math
from fractions import Fraction
from pathlib import Path
import subprocess

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

