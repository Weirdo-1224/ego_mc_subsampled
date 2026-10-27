"""Validate preparation data; this does not evaluate an agent or certify truth."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
ENTITY_FILES = {
    "Event": "events.jsonl", "State": "states.jsonl", "Dependency": "dependencies.jsonl",
    "Rule": "rules.jsonl", "Task": "tasks.jsonl", "Gold": "gold.jsonl",
    "Intervention": "interventions.jsonl",
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_bundle(directory):
    directory = Path(directory)
    read = lambda name: json.loads((directory / name).read_text(encoding="utf-8"))

    def lines(name):
        return [json.loads(line) for line in (directory / name).read_text(encoding="utf-8").splitlines() if line.strip()]

    records = []
    for kind, name in ENTITY_FILES.items():
        items = lines(name)
        if any(item.get("type") != kind for item in items):
            raise ValueError(f"Wrong entity type in {name}")
        records.extend(items)
    return {"episode": read("episode.json"), "sources": read("sources.json"),
            "evidence": lines("evidence.jsonl"), "records": records}


def validate_bundle(bundle, root=ROOT, check_sources=True):
    errors, warnings = [], []
    schema = json.loads((ROOT / "benchmark/schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(bundle), key=lambda e: str(list(e.absolute_path))):
        errors.append(f"SCHEMA {'.'.join(map(str, error.absolute_path))}: {error.message}")
    # Do not allow NaN/Infinity accepted by Python's permissive JSON parser.
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            errors.append("SCHEMA non-finite JSON number")
        elif isinstance(value, dict):
            for child in value.values():
                finite(child)
        elif isinstance(value, list):
            for child in value:
                finite(child)
    finite(bundle)
    if errors:
        return {"errors": errors, "warnings": warnings}

    episode = bundle["episode"]
    duration = episode["duration_seconds"]
    records, evidence, sources = {}, {}, {}
    all_ids = set()
    for collection, items in [(sources, bundle["sources"]), (evidence, bundle["evidence"]), (records, bundle["records"])]:
        for item in items:
            if item["id"] in all_ids or item["id"] == episode["id"]:
                errors.append(f"DUPLICATE_ID {item['id']}")
            all_ids.add(item["id"])
            collection[item["id"]] = item

    def fail(code, owner, detail):
        errors.append(f"{code} {owner}: {detail}")

    def time_ok(t, owner):
        if t is not None and (t < 0 or (duration is not None and t > duration)):
            fail("TIME_BOUNDS", owner, f"{t} outside [0, {duration}]")

    def interval_ok(interval, owner):
        for t in interval.values():
            time_ok(t, owner)
        if interval["start"] > interval["end"]:
            fail("TIME_INTERVAL", owner, "start > end")

    def review_ok(item):
        owner = item["id"]
        review, maturity = item["review"], item["maturity"]
        if review["status"] == "PENDING" and (review["reviewer"] or review["reviewed_at"]):
            fail("REVIEW", owner, "PENDING must not carry a completed review identity/date")
        if review["status"] in {"APPROVED", "REJECTED"}:
            if not all([review["reviewer"], review["reviewed_at"], review["notes"].strip()]):
                fail("REVIEW", owner, "completed review requires reviewer, date and notes")
        if maturity in {"REVIEWED", "GOLD"} and review["status"] != "APPROVED":
            fail("REVIEW", owner, "reviewed/gold material requires APPROVED human review")
        if review["status"] == "REJECTED" and maturity != "CANDIDATE":
            fail("REVIEW", owner, "rejected material cannot be reviewed/gold")

    review_ok(episode)
    if (duration is None) != (episode["duration_method"] == "unknown"):
        fail("DURATION", episode["id"], "duration and measurement method disagree")
    if duration is None:
        warnings.append("Video duration unknown; upper bounds require metadata review.")
    if episode["video_source_id"] not in sources or sources[episode["video_source_id"]]["kind"] != "video":
        fail("REFERENCE", episode["id"], "video source missing or wrong kind")

    source_data = {}
    if check_sources:
        root = Path(root).resolve()
        for source in sources.values():
            path = (root / source["path"]).resolve()
            if not path.is_relative_to(root):
                fail("SOURCE_PATH", source["id"], "source must be within repository")
                continue
            if not path.is_file():
                fail("SOURCE_MISSING", source["id"], source["path"])
            elif digest(path) != source["sha256"]:
                fail("SOURCE_HASH", source["id"], "source content differs from snapshot")
            elif source["kind"] == "annotation":
                try:
                    source_data[source["id"]] = json.loads(path.read_text(encoding="utf-8"))
                except (ValueError, OSError) as exc:
                    fail("SOURCE_JSON", source["id"], str(exc))

    for item in evidence.values():
        owner = item["id"]
        review_ok(item)
        interval_ok(item["interval"], owner)
        time_ok(item["available_at"], owner)
        if item["episode_id"] != episode["id"]:
            fail("EPISODE", owner, "cross-episode evidence")
        if item["source_id"] not in sources:
            fail("REFERENCE", owner, "unknown source")
        if item["visibility"] == "TIMED_PUBLIC" and item["available_at"] is None:
            fail("VISIBILITY", owner, "public evidence needs a verified release time")
        if item["available_at"] is not None and item["available_at"] < item["interval"]["end"]:
            fail("FUTURE_LEAK", owner, "release before evidence end")
        # Ego-MC source anchors: verify quote, type, episode and timestamp exactly.
        if item["source_id"] in source_data and episode["dataset"] == "ego_mc_subsampled":
            try:
                row_index, field, index = item["source_pointer"].strip("/").split("/")
                row, index = source_data[item["source_id"]][int(row_index)], int(index)
                if field != "texts" or index < 0 or int(row_index) < 0:
                    raise ValueError("invalid source pointer")
                if (row["video_id"] != episode["id"].split(":")[-1]
                        or row["texts"][index] != item["quote"]
                        or row["text_types"][index] != item["source_label"]
                        or item["interval"] != {"start": row["text_timestamps"][index], "end": row["text_timestamps"][index]}):
                    fail("SOURCE_ALIGNMENT", owner, "quote, label, video or timestamp mismatch")
            except (ValueError, IndexError, KeyError, TypeError) as exc:
                fail("SOURCE_POINTER", owner, str(exc))

    def record_refs(item):
        p, kind = item["payload"], item["type"]
        refs = list(item["derived_from"])
        if kind == "Rule":
            refs += p["supersedes"]
        elif kind == "Dependency":
            refs += [p["from_ref"], p["to_ref"]]
        elif kind == "Task":
            refs += p["target_refs"]
        elif kind == "Gold":
            refs += [p["task_ref"]] + p["supporting_refs"]
        elif kind == "Intervention":
            refs += [p["feedback_event_ref"]]
        return set(refs)

    graph = {rid: record_refs(item) for rid, item in records.items()}
    for item in records.values():
        owner, kind, p = item["id"], item["type"], item["payload"]
        review_ok(item)
        interval_ok(item["interval"], owner)
        time_ok(item["known_at"], owner)
        if item["episode_id"] != episode["id"]:
            fail("EPISODE", owner, "cross-episode record")
        if item["known_at"] < item["interval"]["end"]:
            fail("FUTURE_LEAK", owner, "known_at precedes record end")
        for ref in graph[owner]:
            if ref not in records:
                fail("REFERENCE", owner, f"unknown record {ref}")
            elif records[ref]["known_at"] > item["known_at"]:
                fail("FUTURE_LEAK", owner, f"record {ref} known later")
        for ref in item["evidence_refs"]:
            if ref not in evidence:
                fail("REFERENCE", owner, f"unknown evidence {ref}")
            elif evidence[ref]["interval"]["end"] > item["known_at"]:
                fail("FUTURE_LEAK", owner, f"evidence {ref} ends later")
            elif evidence[ref]["available_at"] is not None and evidence[ref]["available_at"] > item["known_at"]:
                fail("FUTURE_LEAK", owner, f"evidence {ref} available later")
        if item["visibility"] == "TIMED_PUBLIC":
            if kind != "Event" or p["kind"] != "annotation_utterance":
                fail("VISIBILITY", owner, "only source utterance events can be released by this preparation contract")
            for ref in item["evidence_refs"]:
                ev = evidence.get(ref)
                if ev and (ev["visibility"] != "TIMED_PUBLIC" or ev["available_at"] is None or ev["available_at"] > item["known_at"]):
                    fail("PRIVATE_LEAK", owner, f"evidence {ref} unavailable for release")
        if kind == "Event" and p["kind"] == "annotation_utterance":
            if len(item["evidence_refs"]) != 1:
                fail("SOURCE_ALIGNMENT", owner, "source utterance needs exactly one anchor")
            for ref in item["evidence_refs"]:
                ev = evidence.get(ref)
                if ev and (ev["quote"] != p["text"] or ev["source_label"] != p["source_label"]):
                    fail("SOURCE_ALIGNMENT", owner, "utterance differs from its source evidence")
        if kind == "State" and p["basis"] == "unknown" and p["value"] is not None:
            fail("STATE", owner, "unknown state must have null value")
        if kind == "Rule":
            for key in ["issued_at", "effective_from", "effective_to"]:
                time_ok(p[key], owner)
            if p["issued_at"] > item["known_at"]:
                fail("FUTURE_LEAK", owner, "rule issued after known_at")
            if p["effective_from"] is not None and p["effective_from"] < p["issued_at"]:
                fail("RULE_TIME", owner, "rule effective before issue")
            if p["effective_to"] is not None and (p["effective_from"] is None or p["effective_to"] < p["effective_from"]):
                fail("RULE_TIME", owner, "invalid rule validity interval")
            for ref in p["supersedes"]:
                old = records.get(ref)
                if old and (old["type"] != "Rule" or old["payload"]["issued_at"] >= p["issued_at"]):
                    fail("RULE_REVISION", owner, "replacement must target an earlier Rule")
        if kind == "Dependency":
            if p["from_ref"] == p["to_ref"]:
                fail("CYCLE", owner, "self dependency")
            if p["relation"] == "supersedes":
                new, old = records.get(p["from_ref"]), records.get(p["to_ref"])
                if new and old and (new["type"] != "Rule" or old["type"] != "Rule"
                                    or new["payload"]["issued_at"] <= old["payload"]["issued_at"]):
                    fail("RULE_REVISION", owner, "revision must connect newer Rule to older Rule")
        if kind == "Intervention":
            for key in ["feedback_given_at", "error_onset", "deadline", "resolved_at"]:
                time_ok(p[key], owner)
            feedback = records.get(p["feedback_event_ref"])
            if feedback and (feedback["type"] != "Event" or feedback["payload"].get("source_label") != "Feedback"
                             or feedback["interval"]["start"] != p["feedback_given_at"]):
                fail("INTERVENTION", owner, "feedback anchor must match a Feedback event and timestamp")
            detectable = p["detectable_from"]
            if detectable is not None:
                interval_ok(detectable, owner)
                if p["error_onset"] is not None and detectable["start"] < p["error_onset"]:
                    fail("INTERVENTION_TIME", owner, "detection before onset")
                for key in ["deadline", "resolved_at"]:
                    if p[key] is not None and p[key] < detectable["end"]:
                        fail("INTERVENTION_TIME", owner, f"{key} before detection window end")
            if p["kind"] == "verified_incident" and (p["error_onset"] is None or detectable is None):
                fail("INTERVENTION", owner, "verified incident needs onset and detectable interval")

    def acyclic(edges, label):
        visited, active = set(), set()
        def visit(node):
            if node in active:
                fail("CYCLE", node, label)
                return
            if node in visited:
                return
            active.add(node)
            for ref in edges.get(node, ()):
                if ref in edges:
                    visit(ref)
            active.remove(node)
            visited.add(node)
        for node in edges:
            visit(node)
    acyclic(graph, "provenance/references")
    relation_graph = {}
    for item in records.values():
        if item["type"] == "Dependency":
            p = item["payload"]
            relation_graph.setdefault(p["from_ref"], set()).add(p["to_ref"])
            relation_graph.setdefault(p["to_ref"], set())
    acyclic(relation_graph, "dependency/revision graph")

    def closure(start):
        seen, todo = set(), list(start)
        while todo:
            ref = todo.pop()
            if ref in seen or ref not in records:
                continue
            seen.add(ref)
            todo.extend(graph[ref])
        return seen

    def causal_cut(owner, refs, evrefs, cutoff):
        for ref in closure(refs):
            node = records[ref]
            if node["known_at"] > cutoff or node["interval"]["end"] > cutoff:
                fail("FUTURE_LEAK", owner, f"transitive record {ref} after query/release")
            evrefs = set(evrefs) | set(node["evidence_refs"])
        for ref in evrefs:
            ev = evidence.get(ref)
            if ev and (ev["interval"]["end"] > cutoff or (ev["available_at"] is not None and ev["available_at"] > cutoff)):
                fail("FUTURE_LEAK", owner, f"transitive evidence {ref} after query/release")

    def reviewed_closure(item):
        for ref in closure([item["id"]]):
            node = records[ref]
            if node["review"]["status"] != "APPROVED" or node["maturity"] == "CANDIDATE":
                fail("GOLD_GATE", item["id"], f"unreviewed support record {ref}")
            for evref in node["evidence_refs"]:
                ev = evidence.get(evref)
                if ev and (ev["review"]["status"] != "APPROVED" or ev["maturity"] == "CANDIDATE"):
                    fail("GOLD_GATE", item["id"], f"unreviewed evidence {evref}")

    for item in records.values():
        owner, kind, p = item["id"], item["type"], item["payload"]
        if item["visibility"] == "TIMED_PUBLIC":
            causal_cut(owner, graph[owner], item["evidence_refs"], item["known_at"])
            for ref in closure(graph[owner]):
                if records[ref]["visibility"] != "TIMED_PUBLIC":
                    fail("PRIVATE_LEAK", owner, f"private ancestor {ref}")
        if kind == "Task":
            time_ok(p["query_time"], owner)
            time_ok(p["earliest_answerable_time"], owner)
            if item["interval"] != {"start": p["query_time"], "end": p["query_time"]} or item["known_at"] != p["query_time"]:
                fail("TASK_TIME", owner, "task must be anchored at query_time")
            if p["earliest_answerable_time"] is not None and p["earliest_answerable_time"] > p["query_time"]:
                fail("FUTURE_LEAK", owner, "query before earliest answerable time")
            required = {ref for subset in p["required_evidence_sets"] for ref in subset}
            if not required.issubset(item["evidence_refs"]):
                fail("REFERENCE", owner, "required evidence must be declared in evidence_refs")
            causal_cut(owner, graph[owner], set(item["evidence_refs"]) | required, p["query_time"])
            if p["enabled"]:
                reviewed_closure(item)
                if p["earliest_answerable_time"] is None or (p["track"] == "T3" and p["history_necessity"] != "CONFIRMED"):
                    fail("TASK_GATE", owner, "enabled task needs calibrated answerability/history necessity")
                if not any(r["type"] == "Gold" and r["payload"]["task_ref"] == owner and r["maturity"] == "GOLD" for r in records.values()):
                    fail("TASK_GATE", owner, "enabled task needs GOLD answer")
        if kind == "Gold":
            if item["visibility"] != "PRIVATE":
                fail("PRIVATE_LEAK", owner, "Gold must be private")
            task = records.get(p["task_ref"])
            if not task or task["type"] != "Task":
                fail("REFERENCE", owner, "Gold task_ref must target Task")
            else:
                causal_cut(owner, p["supporting_refs"] + [task["id"]], item["evidence_refs"], task["payload"]["query_time"])
            if item["maturity"] != "GOLD":
                fail("GOLD_GATE", owner, "Gold table accepts only approved GOLD answers; draft answers stay outside it")
        if item["maturity"] == "GOLD":
            reviewed_closure(item)
            if kind == "Intervention" and p["kind"] != "verified_incident":
                fail("GOLD_GATE", owner, "feedback anchor cannot be incident GOLD")
            if kind == "Rule" and p["effective_from"] is None:
                fail("GOLD_GATE", owner, "rule validity must be reviewed")
            if kind == "Dependency" and p["relation"] == "candidate_precondition":
                fail("GOLD_GATE", owner, "candidate relation cannot be GOLD")
            if kind == "State" or (kind == "Event" and p["kind"] == "observed_action") or kind == "Intervention":
                evrefs = {ev for ref in closure([owner]) for ev in records[ref]["evidence_refs"]}
                if not any(sources.get(evidence.get(ev, {}).get("source_id"), {}).get("kind") == "video" for ev in evrefs):
                    fail("GOLD_GATE", owner, "factual state/action/incident requires reviewed video evidence")
    if episode["maturity"] == "GOLD":
        if any(x["maturity"] == "CANDIDATE" or x["review"]["status"] != "APPROVED" for x in [*records.values(), *evidence.values()]):
            fail("GOLD_GATE", episode["id"], "GOLD episode contains unreviewed material")
        if not any(r["type"] == "Gold" for r in records.values()):
            fail("GOLD_GATE", episode["id"], "GOLD episode needs gold answers")
    pending_count = sum(x["review"]["status"] == "PENDING" for x in [episode, *evidence.values(), *records.values()])
    if pending_count:
        warnings.append(f"{pending_count} items pending human review; structural validity does not establish evidence truth.")
    if not any(r["type"] == "Gold" for r in records.values()):
        warnings.append("No GOLD answers: preparation bundle is not ready for formal evaluation.")
    if any(e["available_at"] is None for e in evidence.values()):
        warnings.append("Evidence release times are unverified; private transcript must not be supplied as an online stream.")
    return {"errors": errors, "warnings": warnings}


def verify_assets(snapshot, root=ROOT):
    errors = []
    root = Path(root).resolve()
    items = json.loads(Path(snapshot).read_text(encoding="utf-8"))["files"]
    for item in items:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            errors.append(f"ORIGINAL_ASSET missing/invalid path: {item['path']}")
        elif path.stat().st_size != item["size_bytes"] or digest(path) != item["sha256"]:
            errors.append(f"ORIGINAL_ASSET changed: {item['path']}")
    return {"checked_files": len(items), "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "datasets/ego_mc/GX010021")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--assets-snapshot", type=Path)
    parser.add_argument("--require-gold", action="store_true", help="Additional readiness gate; expected to fail for preparation candidates")
    args = parser.parse_args()
    try:
        bundle = load_bundle(args.data)
        report = validate_bundle(bundle)
        counts = Counter(r["type"] for r in bundle["records"])
        report["record_counts"] = {kind: counts[kind] for kind in ENTITY_FILES}
        report["evidence_count"] = len(bundle["evidence"])
        if args.assets_snapshot:
            report["original_assets"] = verify_assets(args.assets_snapshot)
            report["errors"].extend(report["original_assets"]["errors"])
        if args.require_gold and not any(r["type"] == "Gold" and r["maturity"] == "GOLD" for r in bundle["records"]):
            report["errors"].append("READINESS: no approved GOLD answers")
        report["status"] = "PASS" if not report["errors"] else "FAIL"
    except (ValueError, KeyError, OSError) as exc:
        report = {"status": "FAIL", "errors": [f"LOAD: {exc}"], "warnings": []}
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
