"""Synthetic-only tests: no real model, video analysis or legacy input reads."""

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from annotation_pipeline.scripts import backend, cli, pipeline
from annotation_pipeline.scripts.common import DEFAULT_CONFIG, PACKAGE, PROMPT, TASK_RULES, load_config
from annotation_pipeline.scripts.media import inspect_video


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.video = self.root / "\u5b8c\u6574 video.MP4"
        self.video.write_bytes(b"synthetic test bytes, not a real video")
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps({"output_dir": "runs", "api_key_env": "SYNTHETIC_QWEN_KEY"}), encoding="utf-8")
        self.config = load_config(self.config_path)
        self.report = "  ### A. \u5408\u6210\u54cd\u5e94\r\n\r\nNo headings are repaired.\n  "
        self.response = SimpleNamespace(
            output_text=self.report,
            usage=SimpleNamespace(model_dump=lambda **kwargs: {"input_tokens": 12, "output_tokens": 8}),
            choices=[SimpleNamespace(finish_reason="stop")],
        )
        self.client = MagicMock()
        self.client.__enter__.return_value = self.client
        self.client.multimodal.chat.create.return_value = self.response
        self.sdk = SimpleNamespace(Client=MagicMock(return_value=self.client))
        self.start(patch.dict("sys.modules", {"dashscope": self.sdk}))
        self.start(patch.dict(os.environ, {"SYNTHETIC_QWEN_KEY": "synthetic-secret"}))
        self.probe = self.start(patch("annotation_pipeline.scripts.pipeline.inspect_video", return_value={
            "status": "READY", "duration_seconds": 120, "fps": 30, "audio_streams": [], "errors": [],
        }))
        self.start(patch.object(socket.socket, "connect", side_effect=AssertionError("No network in tests")))
        # Every runtime file read must be a synthetic local input or one of the two new prompts.
        # This also forbids reading old runs, annotations, candidates, Gold or converter outputs.
        original_open = Path.open

        def guarded_open(path, *args, **kwargs):
            mode = args[0] if args else kwargs.get("mode", "r")
            if "r" in mode or "+" in mode:
                resolved = path.resolve()
                if not resolved.is_relative_to(self.root) and resolved not in (PROMPT.resolve(), TASK_RULES.resolve()):
                    raise AssertionError(f"Unexpected runtime file read: {path}")
            return original_open(path, *args, **kwargs)

        self.start(patch.object(Path, "open", guarded_open))

    def start(self, patcher):
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def analyze(self, run_id="test", **kwargs):
        return pipeline.analyze(self.config, self.video, "synthetic-video", run_id, **kwargs)

    def run_path(self, name="test"):
        return self.root / "runs" / name

    def test_single_whole_video_call_and_exact_prompt_and_report(self):
        result = self.analyze()
        self.assertEqual(result["status"], "SUCCESS")
        request = self.client.multimodal.chat.create
        request.assert_called_once_with(model="qwen3.8-max", messages=[{
            "role": "user", "content": [
                {"video": "file://" + self.video.resolve().as_posix(), "fps": 1.0},
                {"text": PROMPT.read_bytes().decode("utf-8")},
            ],
        }])
        self.assertEqual((self.run_path() / "video_facts.md").read_bytes(), self.report.encode("utf-8"))
        self.assertEqual(result["video"]["sha256"], hashlib.sha256(self.video.read_bytes()).hexdigest())
        self.assertEqual(result["prompt_sha256"], hashlib.sha256(PROMPT.read_bytes()).hexdigest())
        self.assertEqual((self.run_path() / "prompt.md").read_bytes(), PROMPT.read_bytes())
        self.assertEqual(result["usage"], {"input_tokens": 12, "output_tokens": 8})
        self.assertEqual(result["review_status"], "PENDING")
        self.assertEqual(result["fact_verification"], "NOT_PERFORMED")
        self.assertIsNone(result["billed_cost_cny"])
        self.assertIsNotNone(result["call_started_at"])
        self.assertIsNotNone(result["call_finished_at"])
        self.assertNotIn("synthetic-secret", (self.run_path() / "manifest.json").read_text(encoding="utf-8"))
        self.sdk.Client.assert_called_once_with(
            api_key="synthetic-secret", base_url=self.config["base_url"],
            protocol="native", timeout=300, max_retries=0,
        )

    def test_fps_override_and_invalid_values_do_not_call(self):
        self.assertEqual(self.analyze(fps=2.5)["fps"], 2.5)
        for value in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.analyze(run_id="bad", fps=value)
        self.assertEqual(self.client.multimodal.chat.create.call_count, 1)

    def test_missing_empty_non_mp4_fail_without_api(self):
        for index, action in enumerate(("missing", "empty", "non_mp4")):
            with self.subTest(action=action):
                if action == "missing":
                    self.video.unlink()
                elif action == "empty":
                    self.video.write_bytes(b"")
                else:
                    self.video = self.root / "wrong.txt"
                    self.video.write_text("synthetic")
                result = self.analyze(run_id=f"bad{index}")
                self.assertEqual(result["status"], "FAILED")
                self.assertEqual(result["api_attempts"], 0)
                self.assertFalse((self.run_path(f"bad{index}") / "video_facts.md").exists())
        self.sdk.Client.assert_not_called()

    def test_oversize_file_is_rejected_without_probe_or_upload(self):
        with patch.object(pipeline, "MAX_LOCAL_VIDEO_BYTES", 3):
            result = self.analyze()
        self.assertIn("100 MB", result["error"]["message"])
        self.assertEqual(result["status"], "FAILED")
        self.probe.assert_not_called()
        self.sdk.Client.assert_not_called()
        self.assertTrue((self.run_path() / "manifest.json").is_file())

    def test_preflight_failure_including_missing_ffprobe_blocks_upload(self):
        self.probe.return_value = {"status": "ERROR", "errors": ["ffprobe executable not found"]}
        result = self.analyze()
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("ffprobe", result["error"]["message"])
        self.sdk.Client.assert_not_called()

    def test_missing_key_blocks_upload(self):
        with patch.dict(os.environ, {}, clear=True):
            result = self.analyze()
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["api_attempts"], 0)
        self.sdk.Client.assert_not_called()

    def test_upload_or_request_failure_is_recorded_redacted_and_never_retried(self):
        self.client.multimodal.chat.create.side_effect = TimeoutError("upload failed synthetic-secret")
        result = self.analyze()
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("[REDACTED]", result["error"]["message"])
        self.assertNotIn("synthetic-secret", json.dumps(result))
        self.assertFalse((self.run_path() / "video_facts.md").exists())
        before = (self.run_path() / "manifest.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.analyze()
        self.assertEqual((self.run_path() / "manifest.json").read_bytes(), before)
        self.client.multimodal.chat.create.assert_called_once()

    def test_empty_response_keeps_failure_without_fabricated_report(self):
        for index, value in enumerate(("", " \r\n ", None)):
            self.response.output_text = value
            result = self.analyze(run_id=f"empty{index}")
            self.assertEqual(result["status"], "FAILED")
            self.assertEqual(result["usage"], {"input_tokens": 12, "output_tokens": 8})
            self.assertFalse((self.run_path(f"empty{index}") / "video_facts.md").exists())

    def test_truncated_response_preserved_but_not_exported(self):
        self.response.choices[0].finish_reason = "length"
        self.assertEqual(self.analyze()["status"], "FAILED")
        self.assertEqual((self.run_path() / "video_facts.md").read_bytes(), self.report.encode("utf-8"))
        with self.assertRaises(ValueError):
            pipeline.prepare_tasks(self.config, "test")

    def test_success_and_existing_manual_directory_are_never_overwritten(self):
        self.analyze()
        before = (self.run_path() / "video_facts.md").read_bytes()
        with self.assertRaises(FileExistsError):
            self.analyze()
        self.assertEqual((self.run_path() / "video_facts.md").read_bytes(), before)
        self.run_path("manual").mkdir()
        (self.run_path("manual") / "notes.md").write_text("manual notes")
        with self.assertRaises(FileExistsError):
            self.analyze(run_id="manual")
        self.client.multimodal.chat.create.assert_called_once()

    def test_prepare_exports_full_report_metadata_and_pending_contract_without_model(self):
        self.analyze()
        self.sdk.Client.reset_mock()
        result = pipeline.prepare_tasks(self.config, "test")
        contents = Path(result["codex_input"]).read_bytes()
        self.assertTrue(contents.endswith(self.report.encode("utf-8")))
        text = contents.decode("utf-8")
        for expected in ("RULES_PENDING", "CANDIDATE/PENDING", "query_time", "dependency_reason",
                         TASK_RULES.resolve().as_posix(), "synthetic-video", "sha256"):
            self.assertIn(expected, text)
        self.assertFalse((self.run_path() / "task_candidates.jsonl").exists())
        self.sdk.Client.assert_not_called()
        with self.assertRaises(FileExistsError):
            pipeline.prepare_tasks(self.config, "test")

    def test_prepare_rejects_changed_or_missing_report_and_failed_run(self):
        self.analyze()
        report = self.run_path() / "video_facts.md"
        report.write_text("changed")
        with self.assertRaises(ValueError):
            pipeline.prepare_tasks(self.config, "test")
        report.unlink()
        with self.assertRaises(FileNotFoundError):
            pipeline.prepare_tasks(self.config, "test")
        self.client.multimodal.chat.create.side_effect = RuntimeError("synthetic")
        self.analyze(run_id="failed")
        with self.assertRaises(ValueError):
            pipeline.prepare_tasks(self.config, "failed")

    def test_path_escape_and_legacy_manifest_rejected(self):
        for run_id in ("../old", "..", "/absolute", "bad/name", "bad\\name", ""):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                self.analyze(run_id=run_id)
        self.run_path().mkdir(parents=True)
        (self.run_path() / "manifest.json").write_text('{"status":"SUCCESS"}')
        with self.assertRaises(ValueError):
            pipeline.prepare_tasks(self.config, "test")
        self.sdk.Client.assert_not_called()

    def test_configuration_validation_and_relative_output_resolution(self):
        self.assertEqual(self.config["output_dir"], str((self.root / "runs").resolve()))
        for invalid in ({"api_key": "literal"}, {"discovery_fps": 0.5}, {"fps": 0},
                        {"fps": float("nan")}, {"base_url": "https://user:secret@example.org/api/v1"},
                        {"base_url": "https://example.org/compatible-mode/v1"}, {"model": "old-model"}):
            with self.subTest(invalid=invalid):
                self.config_path.write_text(json.dumps(invalid), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_config(self.config_path)

    def test_cli_analyze_prepare_and_failure_exit_codes(self):
        common = ["--run-id", "cli", "--config", str(self.config_path)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["analyze", "--video", str(self.video),
                                       "--video-id", "synthetic", *common]), 0)
            self.assertEqual(cli.main(["prepare-tasks", *common]), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["analyze", "--video", str(self.video),
                                       "--video-id", "synthetic", *common]), 1)
        self.video.unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["analyze", "--video", str(self.video), "--video-id",
                                       "synthetic", "--run-id", "missing", "--config", str(self.config_path)]), 1)

    def test_ffprobe_missing_is_error_and_no_audio_is_preserved(self):
        with patch("annotation_pipeline.scripts.media.subprocess.run", side_effect=FileNotFoundError):
            metadata = inspect_video("synthetic", self.video)
        self.assertEqual(metadata["status"], "ERROR")
        with patch("annotation_pipeline.scripts.media._probe", side_effect=[
            {"format": {"duration": "120"}, "streams": [
                {"index": 0, "codec_type": "video", "avg_frame_rate": "30/1"}]},
            {"packets": [{"size": "8"}]},
        ]):
            metadata = inspect_video("synthetic", self.video)
        self.assertEqual(metadata["status"], "READY")
        self.assertEqual(metadata["audio_streams"], [])

    def test_missing_or_legacy_sdk_fails_locally(self):
        with patch.object(backend.importlib, "import_module", side_effect=ImportError):
            with self.assertRaisesRegex(RuntimeError, "2.0.1"):
                backend.create_client(self.config, "synthetic-secret")
        with patch.object(backend.importlib, "import_module", return_value=SimpleNamespace()):
            with self.assertRaisesRegex(RuntimeError, "2.0.1"):
                backend.create_client(self.config, "synthetic-secret")


class ShippedFilesTests(unittest.TestCase):
    def test_prompt_is_byte_identical_to_instruction_package(self):
        supplied = PACKAGE.parent / "qwen_pipeline_refactor_files/annotation_pipeline/prompts/video_facts.md"
        # Keep standalone copies testable when only annotation_pipeline is copied.
        if supplied.is_file():
            self.assertEqual(PROMPT.read_bytes(), supplied.read_bytes())
        self.assertIn("RULES_PENDING", TASK_RULES.read_text(encoding="utf-8"))
        self.assertEqual(load_config(DEFAULT_CONFIG)["fps"], 1.0)


if __name__ == "__main__":
    unittest.main()
