"""V0.2 tests use synthetic records only; not experiment results."""

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from annotation_pipeline.scripts import mine
from annotation_pipeline.scripts.common import PACKAGE
from annotation_pipeline.scripts.validation import parse_json, validate
from annotation_pipeline.scripts.backend import VideoBackend


def fixtures():
    video = {"video_id": "GX010029", "duration_seconds": 200, "sha256": "test-only", "path": "synthetic"}
    provenance = {"provider": "test", "model": "synthetic", "prompt_version": "test", "run_id": "test"}

    def base(identity):
        return {"id": identity, "video_id": video["video_id"], "maturity": "CANDIDATE",
                "review_status": "PENDING", "provenance": provenance}

    history = {"id": "h", "video_id": video["video_id"], "interval": {"start": 1, "end": 4}, "claim": "synthetic manipulation"}
    recent = {"id": "r", "video_id": video["video_id"], "interval": {"start": 130, "end": 140}, "claim": "synthetic later state"}
    events = {"e1": base("e1") | {"description": "synthetic early action", "evidence": [history], "observation_type": "DIRECT_VISUAL"},
              "e2": base("e2") | {"description": "synthetic later action", "evidence": [recent], "observation_type": "DIRECT_VISUAL"}}
    dep = base("d1") | {"event_refs": ["e1", "e2"], "query_time": 140, "current_window": {"start": 80, "end": 140},
                         "history_evidence": [history], "dependency_explanation": "synthetic dependency",
                         "dependency_type": "state", "recent_insufficiency": "synthetic ambiguity",
                         "alternative_evidence_risk": "unverified synthetic hypothesis", "priority": "HIGH"}
    task = base("t1") | {"track": "T1", "dependency_refs": ["d1"], "query_time": 140,
                          "current_window": dep["current_window"], "question": "Synthetic past state?",
                          "proposed_answer": "YES", "necessary_history_evidence": [history],
                          "dependency_explanation": dep["dependency_explanation"],
                          "history_mask": {"operation": "omit_video_intervals", "intervals": [history["interval"]],
                                           "preserve_timestamps": True, "comparison": "full_history_vs_masked_history"}}
    verification = base("v1") | {"task_ref": "t1", "inspected_evidence": [history, recent], "verdict": "SUPPORTED",
                                  "notes": "synthetic test only", "independent_answer": "YES", "recent_sufficient": "NO",
                                  "alternative_history_sufficient": "NO", "direct_visual_support": "YES",
                                  "checked_intervals": [history["interval"], task["current_window"]],
                                  "interval_accuracy": "YES", "contradiction": "NO"}
    return video, provenance, events, dep, task, verification


class MiningTests(unittest.TestCase):
    def test_valid_chain_remains_pending(self):
        video, prov, events, dep, task, verification = fixtures()
        context = {"events": events, "dependencies": {dep["id"]: dep}, "tasks": {task["id"]: task}}
        for stage, rows in (("events", list(events.values())), ("dependencies", [dep]),
                            ("tasks", [task]), ("verifications", [verification])):
            validate(stage, rows, video, prov, **context)
        result = mine.filter_tasks([task], [verification], prov, video["video_id"])[0]
        self.assertEqual(result["decision"], "SEND_TO_HUMAN")
        self.assertEqual(result["review_status"], "PENDING")

    def test_rejects_future_out_of_bounds_dangling_and_gold(self):
        video, prov, events, dep, original, verification = fixtures()
        changes = [
            lambda t: t.update(query_time=210),
            lambda t: t.update(dependency_refs=["missing"]),
            lambda t: t.update(maturity="GOLD"),
            lambda t: t.update(review_status="APPROVED"),
            lambda t: t["necessary_history_evidence"][0]["interval"].update(end=150),
            lambda t: t["necessary_history_evidence"][0]["interval"].update(start=-1),
            lambda t: t["current_window"].update(end=141),
            lambda t: t.update(query_time=float("nan")),
        ]
        for change in changes:
            with self.subTest(change=change):
                task = deepcopy(original)
                change(task)
                with self.assertRaises(ValueError):
                    validate("tasks", [task], video, prov, dependencies={dep["id"]: dep})

    def test_mask_omits_exact_history_preserves_recent_and_coordinates(self):
        video, prov, events, dep, original, verification = fixtures()
        changes = [
            lambda m: m.update(intervals=[{"start": 1, "end": 100}]),
            lambda m: m.update(intervals=[]),
            lambda m: m.update(preserve_timestamps=False),
            lambda m: m.update(operation="rewrite_mp4"),
            lambda m: m.update(intervals=[{"start": 80, "end": 140}]),
        ]
        for change in changes:
            task = deepcopy(original)
            change(task["history_mask"])
            with self.assertRaises(ValueError):
                validate("tasks", [task], video, prov, dependencies={dep["id"]: dep})

    def test_shortcuts_uncertainty_and_disagreement_not_sent(self):
        video, prov, events, dep, task, original = fixtures()
        for changes, expected in [
            ({"recent_sufficient": "YES"}, "REJECT"),
            ({"alternative_history_sufficient": "YES"}, "REJECT"),
            ({"contradiction": "YES"}, "REJECT"),
            ({"interval_accuracy": "UNKNOWN"}, "NEEDS_MORE_EVIDENCE"),
            ({"alternative_history_sufficient": "UNKNOWN"}, "NEEDS_MORE_EVIDENCE"),
            ({"independent_answer": "NO"}, "NEEDS_MORE_EVIDENCE"),
        ]:
            result = mine.filter_tasks([task], [original | changes], prov, video["video_id"])[0]
            self.assertEqual(result["decision"], expected)
        self.assertEqual(mine.filter_tasks([task], [], prov, video["video_id"])[0]["decision"], "NEEDS_MORE_EVIDENCE")

    def test_verifier_cannot_claim_uninspected_or_future_intervals(self):
        video, prov, events, dep, task, original = fixtures()
        for change in (lambda v: v.update(checked_intervals=[]),
                       lambda v: v["inspected_evidence"][0]["interval"].update(end=141)):
            verification = deepcopy(original)
            change(verification)
            with self.assertRaises(ValueError):
                validate("verifications", [verification], video, prov, tasks={task["id"]: task})

    def test_json_duplicates_and_nonfinite_rejected(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(ValueError):
                parse_json(raw)

    def test_dependency_cannot_reference_a_future_event(self):
        video, prov, events, dep, task, verification = fixtures()
        events["e2"]["evidence"][0]["interval"]["end"] = 141
        with self.assertRaises(ValueError):
            validate("dependencies", [dep], video, prov, events=events)

    def test_request_cache_reuses_success_without_key_or_extra_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            config = mine.load_config(mine.DEFAULT_CONFIG)
            report = {"api_attempts": 0, "successful_calls": 0, "successful_video_calls": 0,
                      "cache_hits": 0, "reserved_cost_cny": 0, "calls": [],
                      "usage": {"prompt_tokens": 0, "completion_tokens": 0}}
            backend = VideoBackend(config, root, {"sha256": "synthetic"}, report, lambda: None)
            response = MagicMock()
            response.__enter__.return_value = response
            response.status = 200
            response.read.return_value = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": '{"events":[]}'}}],
                                                      "usage": {"prompt_tokens": 100, "completion_tokens": 10}}).encode()
            with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "synthetic-test-only"}), patch(
                "annotation_pipeline.scripts.backend.urllib.request.urlopen", return_value=response,
            ) as call:
                original = backend.request("test", "JSON synthetic request", [])
            with patch.dict(os.environ, {}, clear=True), patch(
                "annotation_pipeline.scripts.backend.urllib.request.urlopen",
            ) as second:
                cached = backend.request("test", "JSON synthetic request", [])
            self.assertEqual(original, cached)
            self.assertEqual(call.call_count, 1)
            second.assert_not_called()
            self.assertEqual(report["api_attempts"], 1)
            self.assertEqual(report["cache_hits"], 1)
            with self.assertRaisesRegex(ValueError, "cache mismatch"):
                backend.request("test", "different request", [])

    def test_independent_verification_omits_teacher_answers_and_analysis(self):
        video, prov, events, dep, task, verification = fixtures()
        task["dependency_explanation"] = "UNIQUE_TEACHER_REASON_MUST_NOT_BE_SENT"
        config = mine.load_config(mine.DEFAULT_CONFIG)
        with tempfile.TemporaryDirectory() as tmp:
            backend = VideoBackend(config, Path(tmp), video, {}, lambda: None)
            with patch.object(backend, "clip", return_value=Path("synthetic.mp4")), patch.object(
                backend, "structured", return_value=[],
            ) as request:
                backend.verify_evidence(video, [task])
            prompt = request.call_args.args[2]
            self.assertNotIn("UNIQUE_TEACHER_REASON_MUST_NOT_BE_SENT", prompt)
            self.assertNotIn('"proposed_answer"', prompt)
            self.assertNotIn('"history_evidence"', prompt)
            self.assertIn(task["question"], prompt)

    def test_compact_dependency_refs_derive_time_and_evidence_without_changing_claims(self):
        video, prov, events, dep, task, verification = fixtures()
        config = mine.load_config(mine.DEFAULT_CONFIG)
        captured = {}

        def structured(*args, **kwargs):
            captured.update(kwargs)
            return []

        with tempfile.TemporaryDirectory() as tmp:
            backend = VideoBackend(config, Path(tmp), video, {}, lambda: None)
            with patch.object(backend, "clip", return_value=Path("synthetic.mp4")), patch.object(
                backend, "structured", side_effect=structured,
            ):
                backend.mine_dependencies(video, list(events.values()))
        compact = {"id": "d", "anchor_ref": "A0", "history_event_refs": ["e1"],
                   "dependency_explanation": "synthetic hypothesis", "dependency_type": "synthetic",
                   "recent_insufficiency": "synthetic", "alternative_evidence_risk": "unknown", "priority": "HIGH"}
        expanded = captured["transform"]([compact])[0]
        self.assertEqual(expanded["query_time"], 140)
        self.assertEqual(expanded["current_window"], {"start": 80, "end": 140})
        self.assertEqual(expanded["history_evidence"], events["e1"]["evidence"])
        self.assertEqual(expanded["event_refs"], ["e1", "e2"])
        with self.assertRaises(ValueError):
            captured["transform"]([compact | {"history_event_refs": ["e2"]}])

    def test_partial_failure_keeps_real_stage_file_and_no_legacy_reads(self):
        video, prov, events, dep, task, verification = fixtures()

        class SyntheticBackend:
            def __init__(self, config, run_dir, source, report, checkpoint):
                self.provenance = prov

            def discover_events(self, source):
                return list(events.values())

            def mine_dependencies(self, source, rows):
                raise PermissionError("synthetic provider failure, not an experiment")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "GX010029.MP4"
            source.write_bytes(b"synthetic fixture")
            local_config = root / "config.local.json"
            local_config.write_text(json.dumps({"video_path": str(source), "output_dir": "runs", "prompts_dir": str(PACKAGE / "prompts")}), encoding="utf-8")
            original_open, reads = Path.open, []

            def guard(path, mode="r", *args, **kwargs):
                if "r" in mode:
                    reads.append(path.resolve())
                    if path.resolve() != mine.DEFAULT_CONFIG.resolve() and not path.resolve().is_relative_to(root) and not path.resolve().is_relative_to(PACKAGE / "prompts"):
                        raise AssertionError("Unexpected read: " + str(path))
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", guard), patch.object(mine, "ROOT", root), patch.object(
                mine, "VideoBackend", SyntheticBackend,
            ), patch.object(
                mine, "inspect_video", return_value={"status": "READY", "audio_streams": [], "duration_seconds": 200},
            ):
                report = mine.run(local_config, "test")
            run_dir = root / "runs/test"
            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["stages"]["events"], "DONE")
            self.assertEqual(report["stages"]["dependencies"], "BLOCKED")
            self.assertEqual(len((run_dir / "events.jsonl").read_text().splitlines()), 2)
            self.assertFalse((run_dir / "tasks.jsonl").exists())
            self.assertTrue((run_dir / "run_report.json").exists())
            self.assertIn(source.resolve(), reads)
            with self.assertRaises(FileExistsError):
                with patch.object(mine, "ROOT", root):
                    mine.run(local_config, "test")


if __name__ == "__main__":
    unittest.main()
