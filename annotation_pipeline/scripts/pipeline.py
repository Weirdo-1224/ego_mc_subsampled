"""Full-video report and Codex context export. No candidate generation."""

import hashlib
import json
import os
from pathlib import Path

from annotation_pipeline.scripts import backend
from annotation_pipeline.scripts.common import (
    PROMPT, PROMPT_VERSION, TASK_RULES, now, positive_number, run_directory, save_manifest,
)
from annotation_pipeline.scripts.media import inspect_video


# Conservative decimal MB; never silently transform a larger source video.
MAX_LOCAL_VIDEO_BYTES = 100_000_000
FORMAT_VERSION = "full-video-facts-v1"


def analyze(config, video, video_id, run_id, fps=None):
    config = dict(config)
    if fps is not None:
        config["fps"] = positive_number(fps, "fps")
    run = run_directory(config, run_id)
    run.mkdir(parents=True, exist_ok=False)  # Block reuse, including failed/unknown calls.
    path = Path(video).resolve()
    manifest = {
        "format_version": FORMAT_VERSION, "run_id": run_id, "video_id": video_id,
        "video": {"path": str(path), "sha256": None, "size_bytes": None},
        "provider": config["provider"], "model": config["model"], "api_source": config["base_url"],
        "prompt_version": PROMPT_VERSION, "prompt_sha256": None, "fps": config["fps"],
        "timeout_seconds": config["timeout_seconds"], "max_retries": 0,
        "status": "PREPARING", "started_at": now(), "call_started_at": None,
        "call_finished_at": None, "api_attempts": 0, "usage": None,
        "estimated_cost_cny": None, "billed_cost_cny": None,
        "maturity": "CANDIDATE", "review_status": "PENDING", "fact_verification": "NOT_PERFORMED",
    }
    manifest_path = run / "manifest.json"
    save_manifest(manifest_path, manifest)
    api_key = None
    try:
        if not isinstance(video_id, str) or not video_id.strip():
            raise ValueError("video_id must be nonempty")
        if path.suffix.lower() != ".mp4" or not path.is_file():
            raise ValueError("A local, existing complete MP4 is required")
        manifest["video"]["size_bytes"] = path.stat().st_size
        if not manifest["video"]["size_bytes"]:
            raise ValueError("Video is empty")
        if manifest["video"]["size_bytes"] > MAX_LOCAL_VIDEO_BYTES:
            raise ValueError("Local video exceeds 100 MB (100,000,000 bytes). No upload attempted. "
                             "Use a provider-supported public URL workflow for the unchanged full video; "
                             "this CLI accepts local MP4 only and will not compress or slice it.")
        with path.open("rb") as stream:
            manifest["video"]["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        metadata = inspect_video(video_id, path, ffprobe=config["ffprobe"])
        manifest["video"]["metadata"] = metadata
        if metadata["status"] != "READY":
            raise ValueError("Video preflight failed: " + "; ".join(metadata["errors"]))
        prompt_bytes = PROMPT.read_bytes()
        prompt_text = prompt_bytes.decode("utf-8")
        manifest["prompt_sha256"] = hashlib.sha256(prompt_bytes).hexdigest()
        (run / "prompt.md").write_bytes(prompt_bytes)
        api_key = os.environ.get(config["api_key_env"], "").strip()
        if not api_key:
            raise ValueError(f"Missing API key environment variable: {config['api_key_env']}")
        with backend.create_client(config, api_key) as client:
            manifest.update(status="CALLING", call_started_at=now(), api_attempts=1)
            save_manifest(manifest_path, manifest)
            try:
                response = backend.extract_facts(client, config, path, prompt_text)
            finally:
                manifest["call_finished_at"] = now()
            text = response.output_text
            if not isinstance(text, str) or not text.strip():
                manifest["usage"] = backend.response_usage(response)
                raise ValueError("Qwen returned empty Markdown; no video_facts.md created")
            # Preserve whitespace and CRLF. Never repair headings or parse the report.
            report = text.encode("utf-8")
            with (run / "video_facts.md").open("xb") as stream:
                stream.write(report)
            manifest["report_sha256"] = hashlib.sha256(report).hexdigest()
            manifest["usage"] = backend.response_usage(response)
            choices = getattr(response, "choices", None)
            finish_reason = getattr(choices[0], "finish_reason", None) if choices else None
            manifest["finish_reason"] = finish_reason
            if finish_reason not in (None, "stop"):
                raise ValueError(f"Response ended with {finish_reason}; original report preserved, export blocked")
            manifest["status"] = "SUCCESS"
    except (Exception, KeyboardInterrupt) as exc:
        message = str(exc)
        if api_key:
            message = message.replace(api_key, "[REDACTED]")
        manifest.update(status="FAILED", error={"type": type(exc).__name__, "message": message})
    finally:
        manifest["finished_at"] = now()
        save_manifest(manifest_path, manifest)
    return manifest


def prepare_tasks(config, run_id):
    run = run_directory(config, run_id)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("format_version") != FORMAT_VERSION or manifest.get("run_id") != run_id
            or manifest.get("status") != "SUCCESS"):
        raise ValueError("prepare-tasks requires a successful run from the new full-video pipeline")
    report = (run / "video_facts.md").read_bytes()
    if not report.strip() or hashlib.sha256(report).hexdigest() != manifest.get("report_sha256"):
        raise ValueError("Report missing, empty or changed since analyze; export refused")
    rules = TASK_RULES.read_bytes()
    metadata = json.dumps(manifest, ensure_ascii=False, indent=2)
    header = (
        "# Codex 任务构造输入包\n\n"
        "状态：RULES_PENDING。当前仅打包上下文，不生成 Task 或 task_candidates.jsonl。\n\n"
        "报告是未经人工核验的模型描述；原始 MP4 是最终事实依据。"
        "后续产物只能为 CANDIDATE/PENDING，proposed_answer 不是标准答案。"
        "只有人工复看视频并记录真实审核者、时间和理由后，才能单独发布 Gold。\n\n"
        "本包供离线构造器使用，含全片上下文，不得直接提供给正式被测流式 Agent。\n\n"
        f"任务规则文件：{TASK_RULES.resolve().as_posix()}\n\n"
        "## 原始视频与调用元数据\n\n```json\n" + metadata + "\n```\n\n"
        "## 任务规则占位与基本输出约定\n\n"
    ).encode("utf-8")
    contents = header + rules + "\n\n## 完整视频事实报告（以下原文保留至文件末尾）\n\n".encode("utf-8") + report
    output = run / "codex_input.md"
    with output.open("xb") as stream:
        stream.write(contents)
    return {"run_id": run_id, "status": "RULES_PENDING", "codex_input": str(output), "api_attempts": 0}
