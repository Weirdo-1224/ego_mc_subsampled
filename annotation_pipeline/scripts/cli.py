"""Run from parent with -m annotation_pipeline, or with python scripts/cli.py."""

if __package__ in {None, ""}:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import hashlib
import json
from pathlib import Path
import sys

from annotation_pipeline.scripts.backend import VideoBackend
from annotation_pipeline.scripts.common import DEFAULT_CONFIG, config_path, load_config, now, prompt_snapshot, save
from annotation_pipeline.scripts.media import inspect_video
from annotation_pipeline.scripts.mine import STAGES, run
from annotation_pipeline.scripts.review import build_review
from annotation_pipeline.scripts.validation import parse_json


def inspect(config):
    metadata = inspect_video(config["video_id"], config_path(config, "video_path"))
    return {"scope": "LOCAL_PREFLIGHT_ONLY", "api_calls": 0, "video": metadata,
            "provider": config["provider"], "model": config["model"], "base_url": config["base_url"],
            "output_dir": str(config_path(config, "output_dir")),
            "prompt_hashes": {name: item["sha256"] for name, item in prompt_snapshot(config).items()},
            "note": "No API request or factual verification performed"}


def probe(config, run_id):
    if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in run_id):
        raise ValueError("Invalid run ID")
    output = config_path(config, "output_dir") / run_id
    output.mkdir(parents=True, exist_ok=False)
    (output / "raw").mkdir()
    (output / "clips").mkdir()
    report = {"scope": "AVAILABILITY_PROBE_ONLY", "run_id": run_id, "started_at": now(), "status": "FAILED",
              "config": config, "prompt_snapshot": prompt_snapshot(config), "video": None,
              "api_attempts": 0, "successful_calls": 0, "successful_video_calls": 0, "cache_hits": 0,
              "calls": [], "reserved_cost_cny": 0, "estimated_cost_cny": None, "billed_cost_cny": None,
              "usage": {"prompt_tokens": 0, "completion_tokens": 0}, "errors": [],
              "maturity": "CANDIDATE", "review_status": "PENDING", "gold_published": False}

    def checkpoint():
        (output / "run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoint()
    try:
        path = config_path(config, "video_path")
        metadata = inspect_video(config["video_id"], path)
        save(output / "preflight.json", metadata)
        if metadata["status"] != "READY":
            raise ValueError("Video preflight failed")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        video = {"video_id": config["video_id"], "path": str(path), "sha256": digest,
                 "duration_seconds": metadata["duration_seconds"]}
        report["video"] = video
        backend = VideoBackend(config, output, video, report, checkpoint)
        end = min(8, video["duration_seconds"])
        raw = backend.request("probe", backend.prompt("probe", start=0, end=end), [backend.clip(0, end, 2)])
        observations = parse_json(raw)
        if not isinstance(observations, dict) or set(observations) != {"observations", "uncertainties"} or any(
            not isinstance(observations[field], list) or any(not isinstance(v, str) for v in observations[field])
            for field in observations
        ):
            raise ValueError("Invalid observation response")
        save(output / "probe_observations.json", {"maturity": "CANDIDATE", "review_status": "PENDING",
                                                 "observations": observations, "fact_verification": "NOT_PERFORMED"})
        report["status"] = "SUCCESS"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report["status"] = "BLOCKED" if isinstance(exc, PermissionError) else "FAILED"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    finally:
        report["finished_at"] = now()
        checkpoint()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Independent V0.2 video annotation/mining tool")
    parser.add_argument("command", nargs="?", choices=["inspect", "probe", "mine", "review"], default="inspect")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-id")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after", choices=STAGES)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "inspect" or args.dry_run:
            result = inspect(config)
            code = 0 if result["video"]["status"] == "READY" else 1
        elif args.command == "review":
            if not args.run_dir:
                parser.error("review requires --run-dir")
            output = args.output_dir or config_path(config, "output_dir") / (args.run_dir.name + "_review")
            page = build_review(args.run_dir, output, config)
            result, code = {"review_html": str(page), "api_calls": 0}, 0
        else:
            if not args.run_id:
                parser.error("probe/mine requires --run-id")
            result = probe(config, args.run_id) if args.command == "probe" else run(args.config, args.run_id, args.resume, args.stop_after)
            code = 0 if result["status"] in {"SUCCESS", "PARTIAL"} else 1
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return code
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("Annotation pipeline failed: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
