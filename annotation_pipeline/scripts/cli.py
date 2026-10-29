"""python -m annotation_pipeline: explicit analyze / prepare-tasks commands."""

import argparse
import json
from pathlib import Path
import sys

from annotation_pipeline.scripts.common import DEFAULT_CONFIG, load_config
from annotation_pipeline.scripts.pipeline import analyze, prepare_tasks


def main(argv=None):
    parser = argparse.ArgumentParser(description="Single full-video Qwen fact extraction and Codex context export")
    commands = parser.add_subparsers(dest="command", required=True)
    analyze_parser = commands.add_parser("analyze", help="Upload one complete local MP4; makes one paid model request")
    analyze_parser.add_argument("--video", type=Path, required=True)
    analyze_parser.add_argument("--video-id", required=True)
    analyze_parser.add_argument("--fps", type=float)
    prepare_parser = commands.add_parser("prepare-tasks", help="Export existing report; no API or task generation")
    for command_parser in (analyze_parser, prepare_parser):
        command_parser.add_argument("--run-id", required=True)
        command_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "analyze":
            result = analyze(config, args.video, args.video_id, args.run_id, args.fps)
            code = 0 if result["status"] == "SUCCESS" else 1
        else:
            result = prepare_tasks(config, args.run_id)
            code = 0
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return code
    except (OSError, ValueError, TypeError) as exc:
        print("Annotation pipeline failed: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
