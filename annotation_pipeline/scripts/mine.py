"""V0.2 single-video offline mining; default package CLI remains preflight."""

import argparse
from collections import Counter
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys

from annotation_pipeline.scripts.validation import parse_json, validate
from annotation_pipeline.scripts.common import now, save
from annotation_pipeline.scripts.common import DEFAULT_CONFIG, ROOT, config_path as resolve_config_path, load_config, prompt_snapshot
from annotation_pipeline.scripts.media import inspect_video
from annotation_pipeline.scripts.backend import VideoBackend

STAGES = ("events", "dependencies", "tasks", "verifications", "filtering", "review")


def jsonl(path, rows):
    with path.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def filter_tasks(tasks, verifications, provenance, video_id):
    grouped = {}
    for row in verifications:
        grouped.setdefault(row["task_ref"], []).append(row)
    decisions, seen = [], set()
    for task in tasks:
        refs = grouped.get(task["id"], [])
        decision, reasons = "NEEDS_MORE_EVIDENCE", []
        signature = (re.sub(r"\W+", "", task["question"].lower()), task["query_time"])
        dependency_signature = tuple(task["dependency_refs"])
        if signature in seen or dependency_signature in seen:
            decision, reasons = "REJECT", ["Duplicate question or dependency reformulation"]
        elif len(refs) != 1:
            reasons = ["No unique independent visual verification; not automatically passed"]
        else:
            verification = refs[0]
            if verification["verdict"] == "UNSUPPORTED" or verification["contradiction"] == "YES":
                decision, reasons = "REJECT", ["Independent visual evidence unsupported or contradictory"]
            elif verification["recent_sufficient"] == "YES":
                decision, reasons = "REJECT", ["Recent window alone sufficient"]
            elif verification["alternative_history_sufficient"] == "YES":
                decision, reasons = "REJECT", ["Alternative causal history sufficient outside key mask"]
            elif verification["independent_answer"] != task["proposed_answer"]:
                reasons = ["Teacher and independent visual answers disagree"]
            elif (verification["verdict"] == "SUPPORTED"
                  and verification["direct_visual_support"] == "YES"
                  and verification["interval_accuracy"] == "YES"
                  and verification["recent_sufficient"] == "NO"
                  and verification["alternative_history_sufficient"] == "NO"
                  and verification["contradiction"] == "NO"
                  and task["proposed_answer"] in {"YES", "NO"}):
                decision, reasons = "SEND_TO_HUMAN", [
                    "Independent video answer agrees; direct evidence and intervals supported",
                    "No obvious recent or alternative-history shortcut reported in inspected video",
                    "Mask is structurally executable; causal necessity NOT experimentally established",
                    "Human must replay video and confirm facts, answer and necessity; not Gold",
                ]
            else:
                reasons = ["Uncertain evidence, timing, answer, visibility or shortcut risk"]
        seen.update((signature, dependency_signature))
        decisions.append({"id": "filter_" + task["id"], "video_id": video_id,
                          "maturity": "CANDIDATE", "review_status": "PENDING", "provenance": provenance,
                          "task_ref": task["id"], "verification_refs": [v["id"] for v in refs],
                          "decision": decision, "reasons": reasons})
    return decisions


def render_review(run_dir, video, tasks, dependencies, verifications, decisions, backend):
    def esc(value):
        return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
    chunks = [
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>GX010029 V0.2 人工复核</title>',
        '<style>body{font:16px system-ui;max-width:1180px;margin:30px auto;padding:0 20px}article{border-top:2px solid #888;margin-top:30px}video{max-width:100%;width:520px}pre{white-space:pre-wrap;overflow-wrap:anywhere}td,th{border:1px solid #ccc;padding:8px}table{border-collapse:collapse}a{color:#1463aa}</style>',
        '<h1>GX010029 V0.2：人工视频复核入口</h1>',
        '<p>全部 CANDIDATE / PENDING。模型答案和 SUPPORTED 均不是 Gold。历史必要性对照实验尚未执行；'
        '筛查仅排除明显近期/替代证据风险。请复看原视频，确认对象、动作、时间、答案和遮蔽后是否仍可答。'
        '审核者、真实时间及理由须由人另行记录；本页不伪造审批，也不发布 Gold。</p>',
        '<p><a href="run_report.json">实际报告与用量</a> · <a href="events.jsonl">事件</a> · '
        '<a href="dependencies.jsonl">依赖</a> · <a href="tasks.jsonl">任务</a> · '
        '<a href="verifications.jsonl">独立核验</a> · <a href="filtering.jsonl">筛选</a></p>',
        f'<p>原视频 SHA-256：<code>{esc(video["sha256"])}</code>；全部时间为原视频秒。</p>',
        '<p>遮蔽执行语义：在派生视频输入中跳过必要历史区间的帧（音频亦应同时过滤；本片无音轨），'
        '其余历史与查询窗口完整保留，并始终携带原视频时间坐标。原 MP4 不修改。'
        '当前仅交付遮蔽定义，未声称运行遮蔽比较。</p>',
    ]
    decision_map = {r["task_ref"]: r for r in decisions}
    verification_map = {r["task_ref"]: r for r in verifications}
    dep_map = {r["id"]: r for r in dependencies}
    tasks = sorted(tasks, key=lambda r: decision_map[r["id"]]["decision"] != "SEND_TO_HUMAN")
    if not tasks:
        chunks.append('<p>本轮无候选。请查看报告中的真实负结果或阻塞。</p>')
    for task in tasks:
        decision = decision_map[task["id"]]
        chunks += [f'<article id="{esc(task["id"])}"><h2>{esc(task["id"])} · {esc(decision["decision"])}</h2>',
                   f'<p><b>{esc(task["question"])}</b></p><p>Track {esc(task["track"])}；候选答案 '
                   f'{esc(task["proposed_answer"])}；查询 {task["query_time"]:g}s；当前窗口 {esc(task["current_window"])}</p>',
                   '<h3>关键历史及近期原视频片段</h3>']
        spans = [("关键历史", e["interval"]) for e in task["necessary_history_evidence"]] + [("近期窗口", task["current_window"])]
        for label, span in spans:
            clip = backend.clip(span["start"], span["end"], backend.config["verification_fps"])
            relative = clip.relative_to(run_dir).as_posix()
            chunks.append(f'<p>{label}：原视频 {span["start"]:g}–{span["end"]:g}s，播放时间 + {span["start"]:g} = 原秒。'
                          f'<a href="{relative}">打开 MP4</a> · <a href="{relative[:-4]}.json">提取与哈希记录</a></p>'
                          f'<video controls preload="none" src="{relative}"></video>')
        dep_rows = [dep_map[r] for r in task["dependency_refs"]]
        chunks += ['<h3>依赖链、近期不足与替代证据风险（模型假设）</h3>',
                   f'<pre>{esc(dep_rows)}</pre>', '<h3>独立核验（无教师答案上下文）</h3>',
                   f'<pre>{esc(verification_map.get(task["id"], "未执行；待补证据"))}</pre>',
                   '<h3>筛选与遮蔽定义</h3>', f'<pre>{esc(decision)}\n{esc(task["history_mask"])}</pre>', '</article>']
    chunks.append('</html>')
    with (run_dir / "review.html").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(chunks))


def run(config_path, run_id, resume=False, stop_after=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("Invalid run ID")
    config = load_config(config_path)
    run_dir = resolve_config_path(config, "output_dir") / run_id
    prompts = prompt_snapshot(config)
    if resume:
        report = parse_json((run_dir / "run_report.json").read_text(encoding="utf-8"))
        if report["config"] != config or report["run_id"] != run_id or report.get("prompt_snapshot") != prompts:
            raise ValueError("Resume config/run mismatch")
        report["resumed_at"] = now()
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        for name in ("raw", "clips"):
            (run_dir / name).mkdir()
        report = {
            "version": "0.2", "run_id": run_id, "status": "PARTIAL", "started_at": now(),
            "config": config, "prompt_snapshot": prompts, "video": None, "stages": {s: "TODO" for s in STAGES},
            "maturity": "CANDIDATE", "review_status": "PENDING",
            "api_attempts": 0, "successful_calls": 0, "successful_video_calls": 0,
            "cache_hits": 0, "calls": [], "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "estimated_cost_cny": 0, "reserved_cost_cny": 0, "billed_cost_cny": None,
            "cost_note": "Local per-call reservations are user configured, not a billing guarantee. Estimates require matching configured pricing_model; actual bill unavailable.",
            "errors": [], "validation_errors": [], "counts": {},
            "history_necessity_experiment": "NOT_RUN_optional_in_V0.2",
            "gold_published": False,
        }

    def checkpoint():
        path = run_dir / "run_report.json"
        tmp = run_dir / "run_report.checkpoint.tmp"
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        tmp.replace(path)

    checkpoint()
    stage = "preflight"
    try:
        path = resolve_config_path(config, "video_path")
        preflight = inspect_video("GX010029", path)
        if not (run_dir / "preflight.json").exists():
            save(run_dir / "preflight.json", preflight)
        if preflight["status"] != "READY":
            raise ValueError("Video not READY: " + str(preflight["errors"]))
        if preflight["audio_streams"]:
            raise ValueError("Unexpected source audio; requires explicit configuration review")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        video = {"video_id": "GX010029", "path": str(path), "sha256": digest,
                 "duration_seconds": preflight["duration_seconds"]}
        if resume and report["video"] != video:
            raise ValueError("Source video changed; refusing cache reuse")
        report["video"] = video
        checkpoint()
        backend = VideoBackend(config, run_dir, video, report, checkpoint)
        data = {}
        for stage in STAGES:
            if stage == "review":
                if report["stages"][stage] != "DONE":
                    render_review(run_dir, video, data["tasks"], data["dependencies"], data["verifications"], data["filtering"], backend)
            else:
                output = run_dir / (stage + ".jsonl")
                context = {k: {r["id"]: r for r in data.get(k, [])} for k in ("events", "dependencies", "tasks")}
                if output.exists():
                    rows = [parse_json(line) for line in output.read_text(encoding="utf-8").splitlines() if line.strip()]
                    if stage != "filtering":
                        validate(stage, rows, video, backend.stage_provenance(stage), window=config["current_window_seconds"], **context)
                    elif rows != filter_tasks(data["tasks"], data["verifications"], backend.provenance, video["video_id"]):
                        raise ValueError("Filtering cache differs from deterministic decisions or protected metadata")
                    report["cache_hits"] += 1
                else:
                    report["stages"][stage] = "DOING"
                    checkpoint()
                    if stage == "events":
                        rows = backend.discover_events(video)
                    elif stage == "dependencies":
                        rows = backend.mine_dependencies(video, data["events"]) if data["events"] else []
                    elif stage == "tasks":
                        rows = backend.construct_tasks(video, data["dependencies"]) if data["dependencies"] else []
                    elif stage == "verifications":
                        priorities = {r["id"]: r["priority"] for r in data["dependencies"]}
                        selected = sorted(data["tasks"], key=lambda t: not all(
                            priorities[ref] == "HIGH" for ref in t["dependency_refs"]
                        ))
                        rows = backend.verify_evidence(video, selected)
                    else:
                        rows = filter_tasks(data["tasks"], data["verifications"], backend.provenance, video["video_id"])
                    jsonl(output, rows)
                data[stage] = rows
                report["counts"][stage] = len(rows)
            report["stages"][stage] = "DONE"
            checkpoint()
            if stage == stop_after:
                report["status"] = "PARTIAL"
                checkpoint()
                return report
        report["counts"].update(Counter(r["decision"] for r in data["filtering"]))
        report["status"] = "SUCCESS" if report["counts"].get("SEND_TO_HUMAN", 0) else "PARTIAL"
        report["research_output"] = "PENDING_HUMAN_REVIEW" if report["status"] == "SUCCESS" else "NO_SENDABLE_CANDIDATES"
    except KeyboardInterrupt:
        report["status"] = "PARTIAL"
        report["execution_state"] = "INTERRUPTED"
        report["errors"].append({"stage": stage, "at": now(), "type": "KeyboardInterrupt", "message": "Stopped; pending request outcome may be unknown; no automatic resubmission"})
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        key = os.environ.get(config["api_key_env"], "")
        message = str(exc).replace(key, "[REDACTED]") if key else str(exc)
        report["status"] = "BLOCKED" if isinstance(exc, PermissionError) else "FAILED"
        report["errors"].append({"stage": stage, "at": now(), "type": type(exc).__name__, "message": message})
        if stage in report["stages"]:
            report["stages"][stage] = "BLOCKED"
    finally:
        report["updated_at"] = now()
        checkpoint()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-id", choices=["GX010029"], default="GX010029")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after", choices=STAGES)
    args = parser.parse_args(argv)
    try:
        report = run(args.config, args.run_id, args.resume, args.stop_after)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Mining setup failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: report[k] for k in ("run_id", "status", "stages", "counts", "api_attempts", "errors")}, ensure_ascii=True))
    return 0 if report["status"] in {"SUCCESS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
