"""Fail-closed validation for the separate V0.2 intermediate contract."""

import json
import math


def parse_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("Expected a finite numeric timestamp")
    return value


def interval(value, duration):
    if not isinstance(value, dict) or set(value) != {"start", "end"}:
        raise ValueError("Interval must contain start and end only")
    start, end = number(value["start"]), number(value["end"])
    if not 0 <= start < end <= duration:
        raise ValueError("Invalid or out-of-bounds interval")
    return start, end


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected nonempty text")


def evidence(items, video, latest=None):
    if not isinstance(items, list) or not items:
        raise ValueError("Video evidence must be a nonempty ARRAY of evidence objects, not a single object")
    ids = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "video_id", "interval", "claim"}:
            raise ValueError("Invalid video evidence fields")
        text(item["id"])
        text(item["claim"])
        if item["video_id"] != video["video_id"] or item["id"] in ids:
            raise ValueError("Wrong video or duplicate evidence ID")
        ids.add(item["id"])
        _, end = interval(item["interval"], video["duration_seconds"])
        if latest is not None and end > latest:
            raise ValueError("Future evidence after query")


def references(refs, records):
    if not isinstance(refs, list) or not refs or any(not isinstance(r, str) for r in refs):
        raise ValueError("Missing references")
    if len(refs) != len(set(refs)) or any(r not in records for r in refs):
        raise ValueError("Duplicate or dangling references")


COMMON = {"id", "video_id", "maturity", "review_status", "provenance"}
FIELDS = {
    "events": {"description", "evidence", "observation_type"},
    "dependencies": {"event_refs", "query_time", "current_window", "history_evidence",
                     "dependency_explanation", "dependency_type", "recent_insufficiency",
                     "alternative_evidence_risk", "priority"},
    "tasks": {"track", "dependency_refs", "query_time", "current_window", "question",
              "proposed_answer", "necessary_history_evidence", "dependency_explanation", "history_mask"},
    "verifications": {"task_ref", "inspected_evidence", "verdict", "notes", "independent_answer",
                      "recent_sufficient", "alternative_history_sufficient", "direct_visual_support",
                      "checked_intervals", "interval_accuracy", "contradiction"},
}


def validate(stage, records, video, provenance, events=None, dependencies=None, tasks=None, window=60):
    if not isinstance(records, list):
        raise ValueError("Stage output must be an array")
    ids = set()
    for row in records:
        if not isinstance(row, dict) or set(row) != COMMON | FIELDS[stage]:
            raise ValueError("Unexpected or missing fields for " + stage)
        text(row["id"])
        if row["id"] in ids:
            raise ValueError("Duplicate record ID")
        ids.add(row["id"])
        if row["video_id"] != video["video_id"]:
            raise ValueError("Wrong video ID")
        if row["maturity"] != "CANDIDATE" or row["review_status"] != "PENDING":
            raise ValueError("Automatic Gold/review promotion prohibited")
        if row["provenance"] != provenance:
            raise ValueError("Incorrect provenance")
        if stage == "events":
            text(row["description"])
            evidence(row["evidence"], video)
            if row["observation_type"] != "DIRECT_VISUAL":
                raise ValueError("Event must be directly observed")
        elif stage in {"dependencies", "tasks"}:
            query = number(row["query_time"])
            start, end = interval(row["current_window"], video["duration_seconds"])
            if not 0 <= query <= video["duration_seconds"] or end != query or abs(start - max(0, query - window)) > 0.001:
                raise ValueError("Current window must end at query and use configured length")
            history = row["history_evidence" if stage == "dependencies" else "necessary_history_evidence"]
            evidence(history, video, query)
            if any(e["interval"]["end"] >= start for e in history):
                raise ValueError("Necessary history must precede recent window")
            text(row["dependency_explanation"])
            if stage == "dependencies":
                references(row["event_refs"], events or {})
                for field in ("dependency_type", "recent_insufficiency", "alternative_evidence_risk"):
                    text(row[field])
                if row["priority"] not in {"HIGH", "LOW"}:
                    raise ValueError("Invalid dependency priority")
                available = [e for ref in row["event_refs"] for e in events[ref]["evidence"]]
                if any(e["interval"]["end"] > query for e in available):
                    raise ValueError("Dependency references future event evidence")
                if any(not any(e["interval"]["start"] <= h["interval"]["start"] < h["interval"]["end"] <= e["interval"]["end"] for e in available) for h in history):
                    raise ValueError("History is not grounded in referenced events")
                if not any(e["interval"]["start"] < query and e["interval"]["end"] >= start for e in available):
                    raise ValueError("Dependency lacks a referenced recent event")
            else:
                references(row["dependency_refs"], dependencies or {})
                if row["track"] not in {"T1", "T2", "T3"} or row["proposed_answer"] not in {"YES", "NO", "UNKNOWN"}:
                    raise ValueError("Invalid track or closed answer")
                text(row["question"])
                for ref in row["dependency_refs"]:
                    dep = dependencies[ref]
                    if row["query_time"] != dep["query_time"] or row["current_window"] != dep["current_window"]:
                        raise ValueError("Task changed dependency query/window")
                    if row["dependency_explanation"] != dep["dependency_explanation"]:
                        raise ValueError("Task must retain the mined dependency explanation")
                allowed = [e for ref in row["dependency_refs"] for e in dependencies[ref]["history_evidence"]]
                if any(e not in allowed for e in history):
                    raise ValueError("Task invented history not mined in dependency")
                mask = row["history_mask"]
                if not isinstance(mask, dict) or set(mask) != {"operation", "intervals", "preserve_timestamps", "comparison"} or mask["operation"] != "omit_video_intervals" or mask["preserve_timestamps"] is not True or mask["comparison"] != "full_history_vs_masked_history":
                    raise ValueError("Invalid masking operation")
                if mask["intervals"] != [e["interval"] for e in history]:
                    raise ValueError("Mask must omit exactly necessary history, preserving other frames")
        else:
            references([row["task_ref"]], tasks or {})
            task = tasks[row["task_ref"]]
            evidence(row["inspected_evidence"], video, task["query_time"])
            text(row["notes"])
            if row["verdict"] not in {"SUPPORTED", "UNSUPPORTED", "UNCERTAIN"}:
                raise ValueError("Invalid verification verdict")
            if row["independent_answer"] not in {"YES", "NO", "UNKNOWN"}:
                raise ValueError("Invalid independent answer")
            for field in ("recent_sufficient", "alternative_history_sufficient", "direct_visual_support", "interval_accuracy", "contradiction"):
                if row[field] not in {"YES", "NO", "UNKNOWN"}:
                    raise ValueError("Verification risk must be YES/NO/UNKNOWN")
            expected = [e["interval"] for e in task["necessary_history_evidence"]] + [task["current_window"]]
            if row["checked_intervals"] != expected:
                raise ValueError("Verifier did not check all supplied evidence and recent intervals")
    return records
