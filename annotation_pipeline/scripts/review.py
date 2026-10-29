"""Offline, read-only source import and simple candidate video review."""

import hashlib
import html
import json
from pathlib import Path
import shutil

from annotation_pipeline.scripts.backend import VideoBackend
from annotation_pipeline.scripts.common import now, save
from annotation_pipeline.scripts.validation import parse_json


def build_review(source, output, config):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or output.is_relative_to(source):
        raise ValueError("Review output must be a separate new directory outside the source run")
    original = parse_json((source / "run_report.json").read_text(encoding="utf-8"))
    video = original["video"]
    if not video or not video.get("sha256"):
        raise ValueError("Source run has no hashed video")
    path = Path(video["path"])
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != video["sha256"]:
        raise ValueError("Original MP4 hash mismatch; no review evidence generated")
    data = {}
    for stage in ("events", "dependencies", "tasks", "verifications", "filtering"):
        file = source / (stage + ".jsonl")
        data[stage] = [parse_json(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()] if file.exists() else []
        for row in data[stage]:
            if row.get("maturity") != "CANDIDATE" or row.get("review_status") != "PENDING":
                raise ValueError("This candidate viewer will not rewrite approved/Gold records")
    output.mkdir(parents=True, exist_ok=False)
    for name in ("raw", "clips"):
        if (source / name).is_dir():
            shutil.copytree(source / name, output / name)
        else:
            (output / name).mkdir()
    for name in ("run_report.json", "preflight.json", "events.jsonl", "dependencies.jsonl", "tasks.jsonl", "verifications.jsonl", "filtering.jsonl"):
        if (source / name).is_file():
            shutil.copy2(source / name, output / name)
    backend = VideoBackend(config, output, video, {}, lambda: None)

    def esc(value):
        return html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))

    def player(span):
        start, end = span["start"], span["end"]
        if not 0 <= start < end <= video["duration_seconds"]:
            raise ValueError("Invalid evidence span")
        clip = backend.clip(start, end, config["verification_fps"])
        relative = clip.relative_to(output).as_posix()
        return (f'<p>原视频 {start:g}–{end:g}s；播放时间 + {start:g} = 原秒。'
                f'<a href="{relative}">打开视频</a> · <a href="{relative[:-4]}.json">来源清单</a></p>'
                f'<video controls preload="none" src="{relative}"></video>')

    chunks = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>GX010029 候选复看</title>',
              '<style>body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:0 20px}article{border-top:1px solid #aaa;margin-top:24px;padding-top:12px}video{width:560px;max-width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}dt{font-weight:600;margin-top:10px}a{color:#1463aa}</style>',
              '<h1>GX010029 · 视频候选复看</h1>',
              '<p>此页离线生成，未调用模型。全部 CANDIDATE / PENDING。结构合法不等于视频事实正确。'
              '请复看动作、对象、时间、近期可答性及替代历史。此页不自动审批或发布 Gold。</p>',
              f'<p>事件 {len(data["events"])}；依赖 {len(data["dependencies"])}；任务 {len(data["tasks"])}；独立核验 {len(data["verifications"])}。</p>',
              '<p><a href="#dependencies">依赖候选</a> · <a href="#events">事件候选</a> · <a href="#tasks">任务候选</a> · '
              '<a href="run_report.json">原始运行报告</a> · <a href="review_report.json">本次离线记录</a> · '
              '<a href="review_notes.template.json">人工复核记录模板</a></p>',
              f'<p>源视频 SHA-256：<code>{esc(actual)}</code>。片段为采样派生视频，时间定位仍待人工确认。</p>',
              '<h2 id="dependencies">依赖候选</h2>']
    for dep in data["dependencies"]:
        chunks += [f'<article id="{esc(dep["id"])}"><h3>{esc(dep["id"])} · {esc(dep.get("priority", "未定"))}</h3>',
                   f'<p>查询 {dep["query_time"]:g}s；当前窗口 {dep["current_window"]["start"]:g}–{dep["current_window"]["end"]:g}s。</p><dl>']
        for field, label in (("dependency_type", "关系类型"), ("dependency_explanation", "依赖解释（模型假设）"),
                             ("recent_insufficiency", "近期不足理由（待核验）"), ("alternative_evidence_risk", "替代证据风险")):
            chunks.append(f'<dt>{label}</dt><dd>{esc(dep.get(field, "未提供"))}</dd>')
        chunks.append('</dl><p>关联事件：' + ' · '.join(f'<a href="#{esc(ref)}">{esc(ref)}</a>' for ref in dep["event_refs"]) + '</p>')
        for evidence in dep["history_evidence"]:
            chunks.append('<h4>关键历史 · ' + esc(evidence["claim"]) + '</h4>' + player(evidence["interval"]))
        chunks += ['<h4>完整近期窗口</h4>' + player(dep["current_window"]),
                   '<details><summary>原始依赖 JSON</summary><pre>' + esc(dep) + '</pre></details></article>']
    chunks.append('<h2 id="events">事件候选</h2>')
    for event in data["events"]:
        chunks.append(f'<article id="{esc(event["id"])}"><h3>{esc(event["id"])}</h3><p>{esc(event["description"])}</p>')
        for evidence in event["evidence"]:
            chunks.append('<details><summary>复看证据：' + esc(evidence["claim"]) + '</summary>' + player(evidence["interval"]) + '</details>')
        chunks.append('</article>')
    chunks.append('<h2 id="tasks">任务候选</h2>')
    if not data["tasks"]:
        chunks.append('<p>尚无通过校验并落盘的任务；独立核验、筛选和完整任务审核包未完成。</p>')
    for task in data["tasks"]:
        chunks.append('<article><h3>' + esc(task["question"]) + '</h3><pre>' + esc(task) + '</pre></article>')
    chunks.append('</html>')
    (output / "review.html").write_text("\n".join(chunks), encoding="utf-8")
    notes = [{"candidate_id": row["id"], "reviewer": None, "reviewed_at": None,
              "decision": "PENDING", "evidence_notes": "", "history_necessity_notes": "", "reason": ""}
             for row in data["dependencies"]]
    save(output / "review_notes.template.json", notes)
    report = {"scope": "OFFLINE_REVIEW_ONLY", "generated_at": now(), "source_run": str(source),
              "source_video_sha256": actual, "api_calls": 0,
              "counts": {stage: len(rows) for stage, rows in data.items()},
              "maturity": "CANDIDATE", "review_status": "PENDING", "gold_published": False}
    save(output / "review_report.json", report)
    return output / "review.html"
