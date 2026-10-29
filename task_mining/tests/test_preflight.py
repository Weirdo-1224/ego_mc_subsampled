import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from task_mining.preflight import DEFAULT_CONFIG, discover_videos, inspect_video, main


def fake_ffprobe(command, **kwargs):
    """Small ffprobe response fixture; never claims to inspect real media."""
    if "-show_packets" in command:
        payload = {"packets": [{"size": "256"}]}
    else:
        payload = {"format": {"duration": "12.5"}, "streams": [
            {"index": 0, "codec_type": "video", "avg_frame_rate": "30000/1001"},
            {"index": 1, "codec_type": "audio", "codec_name": "aac",
             "sample_rate": "48000", "channels": 2},
        ]}
    return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")


class PreflightTests(unittest.TestCase):
    def test_default_pipeline_never_reads_legacy_inputs(self):
        expected_ids = ["GX010021", "GX010029", "GX010033", "GX010037",
                        "GX010049", "GX010053", "GX010063"]
        original_open = Path.open
        reads = []

        def guarded_open(path, mode="r", *args, **kwargs):
            if "r" in mode:
                reads.append(path.resolve())
                # Only configuration is an allowed Python-level input. ffprobe handles MP4s.
                if path.resolve() != DEFAULT_CONFIG.resolve():
                    raise AssertionError(f"Unexpected input read: {path}")
            return original_open(path, mode, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for vid in expected_ids:
                (root / f"{vid}.MP4").write_bytes(b"synthetic test fixture")
            output = root / "registry.json"
            with patch.object(Path, "open", guarded_open), patch(
                "task_mining.preflight.subprocess.run", side_effect=fake_ffprobe,
            ) as probe, contextlib.redirect_stdout(io.StringIO()):
                code = main(["--video-root", str(root), "--output", str(output)])
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(reads, [DEFAULT_CONFIG.resolve()])
        self.assertEqual([v["video_id"] for v in report["videos"]], expected_ids)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(probe.call_count, 14)
        for call in probe.call_args_list:
            self.assertEqual(Path(call.args[0][-1]).suffix, ".MP4")
        config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))["ego_mc"]
        self.assertIsNone(config["adapter"])
        self.assertEqual(config["status"], "VIDEO_MINING_NOT_STARTED")

    def test_configured_video_root_is_relative_to_config(self):
        videos = discover_videos()
        self.assertEqual(len(videos), 7)
        self.assertEqual(videos[0][1], DEFAULT_CONFIG.parent.parent / "videos/GX010021.MP4")

    def test_missing_videos_produce_failed_registry_and_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "missing.json"
            with patch("task_mining.preflight.subprocess.run") as probe, contextlib.redirect_stdout(io.StringIO()):
                code = main(["--video-root", tmp, "--output", str(output)])
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        probe.assert_not_called()
        self.assertEqual(report["status"], "ERROR")
        self.assertEqual(len(report["videos"]), 7)
        for video in report["videos"]:
            self.assertFalse(video["exists"])
            self.assertFalse(video["basic_readable"])
            self.assertIsNone(video["duration_seconds"])
            self.assertIsNone(video["audio_streams"])
            self.assertIn("Missing video", video["errors"][0])

    def test_probe_metadata_and_no_audio_are_reported(self):
        def no_audio(command, **kwargs):
            result = fake_ffprobe(command, **kwargs)
            payload = json.loads(result.stdout)
            if "streams" in payload:
                payload["streams"] = payload["streams"][:1]
            result.stdout = json.dumps(payload)
            return result

        with tempfile.NamedTemporaryFile(suffix=".MP4") as video, patch(
            "task_mining.preflight.subprocess.run", side_effect=no_audio,
        ):
            video.write(b"fixture")
            video.flush()
            entry = inspect_video("test", video.name)
        self.assertEqual(entry["status"], "READY")
        self.assertEqual(entry["duration_seconds"], 12.5)
        self.assertAlmostEqual(entry["fps"], 30000 / 1001)
        self.assertEqual(entry["frame_rate"], "30000/1001")
        self.assertEqual(entry["audio_streams"], [])

    def test_ffprobe_failures_do_not_become_ready(self):
        cases = [
            FileNotFoundError("ffprobe not found"),
            subprocess.TimeoutExpired("ffprobe", 30),
            subprocess.CompletedProcess([], 1, "", "invalid media"),
            subprocess.CompletedProcess([], 0, "not json", ""),
            subprocess.CompletedProcess([], 0, '{"streams": []}', ""),
        ]
        with tempfile.NamedTemporaryFile(suffix=".MP4") as video:
            video.write(b"fixture")
            video.flush()
            for case in cases:
                with self.subTest(case=case), patch(
                    "task_mining.preflight.subprocess.run",
                    side_effect=case if isinstance(case, Exception) else None,
                    return_value=case,
                ):
                    entry = inspect_video("test", video.name)
                self.assertEqual(entry["status"], "ERROR")
                self.assertFalse(entry["basic_readable"])
                self.assertTrue(entry["errors"])

    def test_empty_packet_sample_and_invalid_metadata_fail(self):
        for invalid in ("packets", "duration", "frame_rate"):
            def invalid_probe(command, **kwargs):
                result = fake_ffprobe(command, **kwargs)
                payload = json.loads(result.stdout)
                if "-show_packets" in command and invalid == "packets":
                    payload = {"packets": []}
                elif "streams" in payload:
                    if invalid == "duration":
                        payload["format"]["duration"] = "nan"
                    elif invalid == "frame_rate":
                        payload["streams"][0]["avg_frame_rate"] = "0/0"
                result.stdout = json.dumps(payload)
                return result

            with self.subTest(invalid=invalid), tempfile.NamedTemporaryFile(suffix=".MP4") as video, patch(
                "task_mining.preflight.subprocess.run", side_effect=invalid_probe,
            ):
                video.write(b"fixture")
                video.flush()
                entry = inspect_video("test", video.name)
            self.assertEqual(entry["status"], "ERROR")
            self.assertFalse(entry["basic_readable"])

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "registry.json"
            output.write_text("preserve review work", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                code = main(["--video-root", tmp, "--output", str(output)])
            self.assertEqual(code, 1)
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve review work")


if __name__ == "__main__":
    unittest.main()
