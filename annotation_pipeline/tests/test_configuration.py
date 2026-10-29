"""Synthetic local configuration tests; no real API requests."""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from annotation_pipeline.scripts import cli, mine
from annotation_pipeline.scripts.backend import VideoBackend
from annotation_pipeline.scripts.common import DEFAULT_CONFIG, PACKAGE, load_api_key, load_config, prompt_snapshot


class ConfigurationTests(unittest.TestCase):
    def test_model_endpoint_and_request_options_are_user_selectable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.local.json"
            path.write_text(json.dumps({"provider": "my-compatible-provider", "model": "my-video-model",
                                        "base_url": "https://example.org/v1", "api_key_env": "MY_VIDEO_KEY",
                                        "request_options": {}, "video_fps_parameter": False}), encoding="utf-8")
            config = load_config(path)
            self.assertEqual(config["model"], "my-video-model")
            self.assertEqual(config["base_url"], "https://example.org/v1")
            self.assertEqual(config["request_options"], {})
            self.assertFalse(config["video_fps_parameter"])
            path.write_text('{"api_key":"literal-secret-not-allowed"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)

    def test_local_credentials_and_environment_precedence_do_not_enter_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "config.local.json"
            path.write_text('{"api_key_env":"SYNTHETIC_VIDEO_KEY"}', encoding="utf-8")
            (root / "credentials.local.json").write_text('{"SYNTHETIC_VIDEO_KEY":"synthetic-local-secret"}', encoding="utf-8")
            config = load_config(path)
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(load_api_key(config), "synthetic-local-secret")
            with patch.dict(os.environ, {"SYNTHETIC_VIDEO_KEY": "synthetic-env-secret"}):
                self.assertEqual(load_api_key(config), "synthetic-env-secret")
            self.assertNotIn("synthetic-local-secret", json.dumps(config))
            self.assertNotIn("synthetic-env-secret", json.dumps(config))

    def test_changed_prompt_cannot_resume_old_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(PACKAGE / "prompts", root / "prompts")
            path = root / "config.local.json"
            path.write_text('{"output_dir":"runs","prompts_dir":"prompts"}', encoding="utf-8")
            config = load_config(path)
            run = root / "runs/test"
            run.mkdir(parents=True)
            report = {"run_id": "test", "config": config, "prompt_snapshot": prompt_snapshot(config)}
            (run / "run_report.json").write_text(json.dumps(report), encoding="utf-8")
            prompt = root / "prompts/tasks.md"
            prompt.write_text(prompt.read_text(encoding="utf-8") + "\nSynthetic replacement instruction.\n", encoding="utf-8")
            with patch("annotation_pipeline.scripts.backend.urllib.request.urlopen") as request:
                with self.assertRaises(ValueError):
                    mine.run(path, "test", resume=True)
            request.assert_not_called()

    def test_dry_run_never_calls_api(self):
        with patch("annotation_pipeline.scripts.cli.inspect_video", return_value={"status": "READY"}), patch(
            "annotation_pipeline.scripts.backend.urllib.request.urlopen",
        ) as request, contextlib.redirect_stdout(io.StringIO()) as output:
            code = cli.main(["mine", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["api_calls"], 0)
        request.assert_not_called()

    def test_previous_unknown_request_cannot_be_reissued(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(DEFAULT_CONFIG)
            root = Path(tmp)
            (root / "raw").mkdir()
            report = {"calls": [], "api_attempts": 0, "reserved_cost_cny": 0}
            backend = VideoBackend(config, root, {"sha256": "synthetic"}, report, lambda: None)
            with patch.dict(os.environ, {config["api_key_env"]: "synthetic-only"}), patch(
                "annotation_pipeline.scripts.backend.urllib.request.urlopen", side_effect=TimeoutError("synthetic timeout"),
            ) as request:
                with self.assertRaises(TimeoutError):
                    backend.request("synthetic", "JSON test", [])
                with self.assertRaisesRegex(PermissionError, "unknown"):
                    backend.request("synthetic", "JSON test", [])
            self.assertEqual(request.call_count, 1)
            self.assertEqual(report["api_attempts"], 1)


if __name__ == "__main__":
    unittest.main()
