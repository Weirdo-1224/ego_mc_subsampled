"""LEGACY: copy source utterances for historical reproduction, never ground truth.

Excluded from the Long-History Task Mining pipeline; use python -m task_mining.
Explicit historical use only: python -m datasets.ego_mc.convert
An existing output directory is refused so a rerun cannot erase human reviews.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.1.0"
FILES = {
    "Event": "events.jsonl", "State": "states.jsonl",
    "Dependency": "dependencies.jsonl", "Rule": "rules.jsonl",
    "Task": "tasks.jsonl", "Gold": "gold.jsonl",
    "Intervention": "interventions.jsonl",
}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pending(notes="Requires human review against the video and source context."):
    return {"status": "PENDING", "reviewer": None, "reviewed_at": None, "notes": notes}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def convert(output, root=ROOT):
    """The first adapter deliberately handles only the audited text layout of GX010021."""
    output, root = Path(output), Path(root)
    if output.exists():
        raise ValueError(f"Output already exists; choose a new review/version directory: {output}")
    annotation_path = root / "annotations/annotations.json"
    rows = json.loads(annotation_path.read_text(encoding="utf-8"))
    matches = [(i, row) for i, row in enumerate(rows) if row["video_id"] == "GX010021"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one GX010021 annotation row")
    row_index, row = matches[0]
    # The hand-selected review hypotheses below use this exact source layout.
    # Fail explicitly when a new release changes it instead of silently reusing indices.
    row_hash = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if row_hash != "445ec08cfa2d561159d984bb943a6cf3502b7cc395f8fc70608f373b850c77bb":
        raise ValueError("GX010021 source layout changed; review the adapter's candidate anchors before converting")
    texts, labels, times = row["texts"], row["text_types"], row["text_timestamps"]
    if not len(texts) == len(labels) == len(times):
        raise ValueError("Unaligned source arrays; refusing silent zip truncation")
    if any(isinstance(t, bool) or not isinstance(t, (int, float)) or t < 0 for t in times):
        raise ValueError("Invalid source timestamps")
    if times != sorted(times):
        raise ValueError("Source timestamps are not monotonic")

    episode_id = "ego_mc:GX010021"
    video_path = root / "videos/GX010021.MP4"
    duration = None
    if shutil.which("ffprobe"):
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video_path)],
            check=True, capture_output=True, text=True,
        )
        duration = float(json.loads(result.stdout)["format"]["duration"])
    if duration is not None and times[-1] > duration:
        raise ValueError("Annotation extends beyond video duration")
    source_specs = [
        ("src:annotation", "annotations/annotations.json", "annotation"),
        ("src:video", "videos/GX010021.MP4", "video"),
        ("src:manifest", "sample_manifest.json", "manifest"),
        ("src:design", "docs/Long_Horizon_Streaming_Agent_Benchmark_Overall_Design_v1.0 (1).md", "design"),
    ]
    sources = [{"id": sid, "path": path, "kind": kind, "sha256": sha256(root / path)}
               for sid, path, kind in source_specs]
    evidence, records = [], []
    eid = lambda i: f"{episode_id}:evidence:{i:03d}"
    rid = lambda kind, key: f"{episode_id}:{kind.lower()}:{key}"
    event_id = lambda i: rid("Event", f"{i:03d}")
    rule_id = lambda i: rid("Rule", f"{i:03d}")

    def add(kind, key, indices, payload, parents=(), notes="Text-derived candidate; no video facts verified."):
        t = max(times[i] for i in indices)
        record = {
            "schema_version": VERSION, "id": rid(kind, key), "episode_id": episode_id,
            "type": kind, "interval": {"start": t, "end": t}, "known_at": t,
            "visibility": "PRIVATE", "maturity": "CANDIDATE", "review": pending(),
            "evidence_refs": [eid(i) for i in indices], "derived_from": list(parents),
            "provenance": {"method": "source_copy" if kind == "Event" else "text_candidate", "notes": notes},
            "payload": payload,
        }
        records.append(record)
        return record["id"]

    for i, (text, label, time) in enumerate(zip(texts, labels, times)):
        evidence.append({
            "id": eid(i), "episode_id": episode_id, "source_id": "src:annotation",
            "interval": {"start": time, "end": time},
            "available_at": None, "visibility": "PRIVATE",
            "source_pointer": f"/{row_index}/texts/{i}", "quote": text, "source_label": label,
            "maturity": "CANDIDATE", "review": pending(
                "Source timestamp is a point anchor, not an utterance end or verified online release time."),
        })
        add("Event", f"{i:03d}", [i], {"kind": "annotation_utterance", "text": text, "source_label": label},
            notes="Verbatim source annotation; a Success utterance does not prove action completion.")
        if label in {"Instruction", "Instruction-Clarification"}:
            add("Rule", f"{i:03d}", [i], {
                "text": text, "issued_at": time, "effective_from": None, "effective_to": None,
                "supersedes": [], "condition": None, "scope": "GX010021; semantic scope pending review",
            }, [event_id(i)], "Instruction text only; validity and replacement are not established.")
        if label == "Feedback":
            add("Intervention", f"{i:03d}", [i], {
                "kind": "feedback_anchor", "feedback_event_ref": event_id(i), "feedback_given_at": time,
                "error_onset": None, "detectable_from": None, "deadline": None, "resolved_at": None,
            }, [event_id(i)], "Only expert feedback is anchored; not an error or autonomous detection ground truth.")

    # These are explicitly review hypotheses grounded in the source dialogue.
    for old, new in [(12, 15), (38, 40), (40, 42)]:
        add("Dependency", f"revision-{old}-{new}", [old, new], {
            "relation": "supersedes", "from_ref": rule_id(new), "to_ref": rule_id(old),
            "rationale": "Dialogue suggests a possible revision/alternative; human must confirm scope and conditions.",
        }, [rule_id(old), rule_id(new)])
    dep = add("Dependency", "tray-before-pour", [37, 38, 51], {
        "relation": "candidate_precondition", "from_ref": rule_id(38), "to_ref": rule_id(51),
        "rationale": "Question about lining before transfer and subsequent lining instruction suggest a preparation constraint; necessity and actual execution remain unverified.",
    }, [rule_id(38), rule_id(51)])

    state_specs = [
        ("oven", 2, "oven", "preheated_to_350F"),
        ("mixture", 35, "cake_mixture", "smooth"),
        ("tray", 44, "baking_tray", "lined"),
    ]
    state_ids = {}
    for key, i, subject, prop in state_specs:
        state_ids[key] = add("State", key, [i], {
            "subject": subject, "property": prop, "value": None, "basis": "unknown",
        }, [event_id(i)], "Review checkpoint near a Success utterance; actual state deliberately left unknown.")

    task_specs = [
        ("T1", [0, 1, 2], [state_ids["oven"]], "此时烤箱是否实际已达到 350°F？区分设定温度与达到温度；证据不足则 unknown。", "state_or_unknown"),
        ("T2", [37, 38, 40, 42, 44, 51], [dep, state_ids["tray"]], "准备倒入面糊时，托盘准备约束是否适用且实际满足？无法确认则 unknown。", "satisfied_unsatisfied_unknown"),
        ("T3", [38, 39, 40, 41, 42], [rule_id(38), rule_id(40), rule_id(42)], "截至此时，对话允许使用什么材料处理烤盘？解释各次替代的上下文与证据。", "text_or_unknown"),
    ]
    for track, indices, targets, question, answer_type in task_specs:
        add("Task", track, indices, {
            "track": track, "question": question, "query_time": max(times[i] for i in indices),
            "earliest_answerable_time": None, "required_evidence_sets": [[eid(i) for i in indices]],
            "target_refs": targets, "answer_type": answer_type, "history_necessity": "PENDING", "enabled": False,
        }, targets, "Draft review question and proposed evidence set; sufficiency, minimality and history necessity pending. No answer generated.")

    episode = {
        "schema_version": VERSION, "id": episode_id, "dataset": "ego_mc_subsampled",
        "video_source_id": "src:video", "duration_seconds": duration,
        "duration_method": "ffprobe" if duration is not None else "unknown",
        "maturity": "CANDIDATE", "review": pending(), "split": "preparation",
        "provenance": "Local source annotation conversion only; video metadata probed but video content not reviewed. Track IDs follow current preparation requirements, not design v1.0 numbering.",
    }
    output.mkdir(parents=True)
    write_json(output / "episode.json", episode)
    write_json(output / "sources.json", sources)
    for filename, items in [("evidence.jsonl", evidence)] + [
        (filename, [r for r in records if r["type"] == kind]) for kind, filename in FILES.items()
    ]:
        (output / filename).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in items), encoding="utf-8")
    return {"output": str(output), "evidence": len(evidence),
            "records": {kind: sum(r["type"] == kind for r in records) for kind in FILES}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "datasets/ego_mc/GX010021")
    args = parser.parse_args()
    print("LEGACY: annotation conversion is excluded from the new video mining pipeline.", file=sys.stderr)
    try:
        print(json.dumps(convert(args.output), ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Conversion failed: {exc}\n")


if __name__ == "__main__":
    main()
