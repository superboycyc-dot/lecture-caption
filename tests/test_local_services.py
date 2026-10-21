import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import core
import local_services
from test_pipeline import Signals


class LocalTests(unittest.TestCase):
    def test_regular_recognition_does_not_implicitly_download_assets(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(local_services, "NATIVE_ROOT", Path(tmp)),
            patch.object(local_services.platform, "system", return_value="Darwin"),
        ):
            (Path(tmp) / "LocalSpeech").touch()
            with patch.object(
                local_services.subprocess, "run", return_value=Mock(returncode=0, stdout=b'{"text":"synthetic words"}')
            ) as run:
                audio = np.ones(16000, dtype=np.float32)
                self.assertEqual(local_services.transcribe(audio), "synthetic words")
                args, kwargs = run.call_args
                self.assertNotIn("--prepare", args[0])
                self.assertEqual(kwargs["input"], audio.astype("<f4").tobytes())
                self.assertEqual(kwargs["timeout"], 45)

    def test_explicit_resource_preparation_uses_dedicated_command(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(local_services, "NATIVE_ROOT", Path(tmp)),
            patch.object(local_services.platform, "system", return_value="Darwin"),
            patch.object(local_services.platform, "mac_ver", return_value=("26.6", (), "arm64")),
        ):
            (Path(tmp) / "LocalSpeech").touch()
            with patch.object(
                local_services.subprocess, "run", return_value=Mock(returncode=0, stdout=b'{"text":"ready"}')
            ) as run:
                self.assertEqual(local_services.prepare_speech(), "ready")
                args, kwargs = run.call_args
                self.assertIn("--prepare", args[0])
                self.assertEqual(kwargs["input"], b"")
                self.assertEqual(kwargs["timeout"], 600)

    def test_helper_errors_never_echo_stderr_or_audio(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(local_services, "NATIVE_ROOT", Path(tmp)),
            patch.object(local_services.platform, "system", return_value="Darwin"),
        ):
            (Path(tmp) / "LocalSpeech").touch()
            with patch.object(
                local_services.subprocess,
                "run",
                return_value=Mock(returncode=1, stdout=b"invalid", stderr=b"private-audio"),
            ):
                with self.assertRaises(core.ApiError) as caught:
                    local_services.transcribe(np.ones(16000, dtype=np.float32))
                self.assertNotIn("private-audio", str(caught.exception))

    def test_local_pipeline_never_calls_cloud_or_counts_audio_quota(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(core, "DATA_ROOT", Path(tmp)),
            patch.object(local_services, "transcribe", return_value="An invariant is preserved."),
            patch.object(local_services, "translate", return_value="不变量得以保持。"),
        ):
            sig = Signals()
            engine = core.Engine(sig, {"stt_backend": "apple", "translation_backend": "apple", "notes_interval": 3600})
            engine.notes_enabled = False
            engine.api = Mock()
            engine.active, engine.gen = True, 1
            engine.ensure_session()
            engine.chunks.put((1, 1, np.ones(48000, dtype=np.float32) * 0.1, time.monotonic()))
            deadline = time.monotonic() + 2
            while len(sig.caption.items) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(sig.caption.items[-1], (1, "An invariant is preserved.", "不变量得以保持。"))
            engine.api.transcribe.assert_not_called()
            engine.api.chat.assert_not_called()
            self.assertEqual(engine.usage.stats()["req_day"], 0)
            self.assertEqual(engine.pending, [])
            events = [json.loads(line) for line in (engine.session_dir / "transcript.jsonl").read_text().splitlines()]
            self.assertEqual(events[-1]["translation"], "不变量得以保持。")
            engine.shutdown = True
            engine.active = False
            engine.force_notes.set()

    def test_missing_local_resources_never_fall_back(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(core, "DATA_ROOT", Path(tmp)),
            patch.object(local_services, "transcribe", side_effect=core.ApiError("missing-resource")),
        ):
            sig = Signals()
            engine = core.Engine(sig, {"stt_backend": "apple", "notes_interval": 3600})
            engine.api = Mock()
            engine.active, engine.gen = True, 1
            engine.ensure_session()
            engine.chunks.put((1, 1, np.ones(16000, dtype=np.float32), time.monotonic()))
            deadline = time.monotonic() + 2
            while not sig.capture_failed.items and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(sig.capture_failed.items)
            engine.api.transcribe.assert_not_called()
            self.assertEqual(engine.usage.stats()["req_day"], 0)
            engine.shutdown = True
            engine.active = False
            engine.force_notes.set()
