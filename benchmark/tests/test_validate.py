import copy
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator

from benchmark.validate import ROOT, load_bundle, validate_bundle
from datasets.ego_mc.convert import convert


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        convert(Path(cls._tmp.name) / "gx010021")
        cls.original = load_bundle(Path(cls._tmp.name) / "gx010021")

    def setUp(self):
        self.bundle = copy.deepcopy(self.original)

    def record(self, kind):
        return next(r for r in self.bundle["records"] if r["type"] == kind)

    def errors(self):
        return validate_bundle(self.bundle, check_sources=False)["errors"]

    def rejects(self, code):
        self.assertTrue(any(code in err for err in self.errors()), self.errors())

    def test_schema_is_valid(self):
        Draft202012Validator.check_schema(json.loads((ROOT / "benchmark/schema.json").read_text(encoding="utf-8")))

    def test_candidate_bundle_passes_without_claiming_gold(self):
        report = validate_bundle(self.bundle, check_sources=False)
        self.assertEqual(report["errors"], [])
        self.assertTrue(any("No GOLD" in w for w in report["warnings"]))
        self.assertFalse(any(r["type"] == "Gold" for r in self.bundle["records"]))
        self.assertTrue(all(r["maturity"] == "CANDIDATE" and r["review"]["status"] == "PENDING" for r in self.bundle["records"]))

    def test_missing_field_and_invalid_type(self):
        del self.record("State")["review"]
        self.record("Rule")["payload"]["issued_at"] = "yesterday"
        self.rejects("SCHEMA")

    def test_non_finite_timestamp(self):
        self.record("Event")["known_at"] = float("nan")
        self.rejects("non-finite")

    def test_duplicate_id(self):
        self.bundle["evidence"][0]["id"] = self.record("Event")["id"]
        self.rejects("DUPLICATE_ID")

    def test_reversed_and_out_of_bounds_interval(self):
        self.record("State")["interval"] = {"start": 1000, "end": 2}
        self.rejects("TIME_INTERVAL")
        self.rejects("TIME_BOUNDS")

    def test_missing_record_and_evidence_refs(self):
        self.record("State")["derived_from"] = ["missing-record"]
        self.record("Event")["evidence_refs"] = ["missing-evidence"]
        self.rejects("REFERENCE")

    def test_wrong_episode(self):
        self.bundle["evidence"][0]["episode_id"] = "other"
        self.rejects("EPISODE")

    def test_future_evidence_at_query(self):
        task = self.record("Task")
        late = self.bundle["evidence"][-1]["id"]
        task["evidence_refs"].append(late)
        task["payload"]["required_evidence_sets"][0].append(late)
        self.rejects("FUTURE_LEAK")

    def test_transitive_future_record(self):
        task = self.record("Task")
        target = next(r for r in self.bundle["records"] if r["id"] == task["payload"]["target_refs"][0])
        target["derived_from"].append(self.bundle["records"][54]["id"])
        self.rejects("FUTURE_LEAK")

    def test_release_time_after_query(self):
        self.bundle["evidence"][0]["available_at"] = 100
        self.rejects("FUTURE_LEAK")

    def test_release_before_evidence_end(self):
        self.bundle["evidence"][0]["available_at"] = 0
        self.rejects("FUTURE_LEAK")

    def test_private_source_cannot_be_released(self):
        self.record("Event")["visibility"] = "TIMED_PUBLIC"
        self.rejects("PRIVATE_LEAK")

    def test_gold_and_task_cannot_be_public(self):
        self.record("Task")["visibility"] = "TIMED_PUBLIC"
        self.rejects("VISIBILITY")

    def test_unreviewed_material_cannot_be_promoted(self):
        self.record("State")["maturity"] = "GOLD"
        self.rejects("REVIEW")
        self.rejects("GOLD_GATE")

    def test_approved_needs_real_review_fields(self):
        self.record("Rule")["review"]["status"] = "APPROVED"
        self.rejects("REVIEW")

    def test_reference_cycle(self):
        events = [r for r in self.bundle["records"] if r["type"] == "Event"]
        events[0]["derived_from"] = [events[1]["id"]]
        events[1]["derived_from"] = [events[0]["id"]]
        self.rejects("CYCLE")

    def test_dependency_cycle(self):
        deps = [r for r in self.bundle["records"] if r["type"] == "Dependency"]
        deps[1]["payload"]["from_ref"] = deps[0]["payload"]["to_ref"]
        deps[1]["payload"]["to_ref"] = deps[0]["payload"]["from_ref"]
        self.rejects("CYCLE")

    def test_rule_validity(self):
        self.record("Rule")["payload"]["effective_from"] = 0
        self.rejects("RULE_TIME")

    def test_unknown_state_cannot_claim_value(self):
        self.record("State")["payload"]["value"] = True
        self.rejects("STATE")

    def test_invalid_detection_window(self):
        p = self.record("Intervention")["payload"]
        p.update(error_onset=20, detectable_from={"start": 21, "end": 23}, deadline=22)
        self.rejects("INTERVENTION_TIME")

    def test_enabled_task_without_gold(self):
        self.record("Task")["payload"]["enabled"] = True
        self.rejects("TASK_GATE")

    def test_source_text_cannot_be_changed(self):
        self.bundle["evidence"][0]["quote"] = "altered text"
        report = validate_bundle(self.bundle, check_sources=True)
        self.assertTrue(any("SOURCE_ALIGNMENT" in e for e in report["errors"]))

    def test_reviewed_gold_has_positive_path(self):
        # Synthetic review metadata exists only in this in-memory test, never in dataset output.
        for item in [self.bundle["episode"], *self.bundle["evidence"], *self.bundle["records"]]:
            item["maturity"] = "REVIEWED"
            item["review"] = {"status": "APPROVED", "reviewer": "TEST_FIXTURE_ONLY", "reviewed_at": "2026-10-27T00:00:00Z", "notes": "Synthetic review for gate test"}
        task = next(r for r in self.bundle["records"] if r["type"] == "Task" and r["payload"]["track"] == "T3")
        task["payload"].update(enabled=True, history_necessity="CONFIRMED", earliest_answerable_time=task["payload"]["query_time"])
        gold = copy.deepcopy(task)
        gold.update(id="test-only:gold", type="Gold", maturity="GOLD", derived_from=[task["id"]])
        gold["payload"] = {"task_ref": task["id"], "answer": "TEST_FIXTURE_ONLY", "supporting_refs": task["payload"]["target_refs"]}
        self.bundle["records"].append(gold)
        self.assertEqual(self.errors(), [])

    def test_converter_refuses_existing_review_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "review.txt"
            marker.write_text("preserve human work", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already exists"):
                convert(Path(tmp))
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve human work")

    def test_converter_rejects_changed_source_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "annotations").mkdir()
            rows = json.loads((ROOT / "annotations/annotations.json").read_text(encoding="utf-8"))
            next(r for r in rows if r["video_id"] == "GX010021")["texts"][0] = "changed instruction"
            (root / "annotations/annotations.json").write_text(json.dumps(rows), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source layout changed"):
                convert(root / "new-output", root=root)
            self.assertFalse((root / "new-output").exists())


if __name__ == "__main__":
    unittest.main()
