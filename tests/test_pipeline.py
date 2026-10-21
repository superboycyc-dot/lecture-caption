import io
import json
import os
import queue
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

_temp = tempfile.TemporaryDirectory()
os.environ["LECTURE_CAPTION_DATA_DIR"] = _temp.name
import core
from audio import Chunker, Vad, to_wav
from credentials import CredentialStore
import numpy as np


class Event:
    def __init__(self):
        self.items = []

    def emit(self, *args):
        self.items.append(args)


class Signals:
    def __init__(self):
        for name in ("status", "error", "capture_failed", "level", "caption", "notes", "note_status"):
            setattr(self, name, Event())


class AudioTests(unittest.TestCase):
    def test_silence_never_produces_upload(self):
        output = []
        vad = Vad(fixed=0.004)
        chunker = Chunker("test", 4, 8, 0.6, lambda _, a: output.append(a))
        for _ in range(1000):
            frame = np.zeros(320, dtype=np.float32)
            chunker.feed(frame, vad.push(frame))
        self.assertEqual(output, [])

    def test_continuous_speech_chunks_are_bounded(self):
        output = []
        vad = Vad(fixed=0.004)
        chunker = Chunker("test", 4, 8, 0.6, lambda _, a: output.append(a))
        for _ in range(850):
            frame = np.full(320, 0.03, dtype=np.float32)
            chunker.feed(frame, vad.push(frame))
        self.assertGreaterEqual(len(output), 2)
        self.assertTrue(all(len(a) <= 128000 for a in output))

    def test_wav_format(self):
        with wave.open(io.BytesIO(to_wav(np.zeros(16000, dtype=np.float32)))) as wav:
            self.assertEqual(
                (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()), (16000, 1, 2, 16000)
            )

    def test_queue_retains_recent_audio(self):
        q = queue.Queue(maxsize=2)
        for item in (1, 2, 3):
            core.bounded_offer(q, item)
        self.assertEqual([q.get(), q.get()], [2, 3])


class ApiTests(unittest.TestCase):
    def test_quota_uses_numeric_provider_headers_only(self):
        self.assertEqual(core.groq_quota_message({"x-ratelimit-remaining-requests": "private-key"}, "model"), "")
        message = core.groq_quota_message(
            {
                "x-ratelimit-remaining-requests": "125",
                "x-ratelimit-limit-requests": "1000",
                "x-ratelimit-remaining-tokens": "500",
            },
            "synthetic-model",
        )
        self.assertIn("当日请求剩余 125 / 1000", message)
        self.assertIn("本分钟 token 剩余 500", message)
        self.assertIn("synthetic-model", message)

    def test_credentials_and_server_body_not_echoed_on_errors(self):
        api = core.Cloud("synthetic-secret", core.DEFAULTS)
        for status in (401, 403, 429, 500):
            with self.subTest(status=status):
                api.session.post = Mock(return_value=Mock(status_code=status, ok=False, text="synthetic-secret"))
                with self.assertRaises(core.ApiError) as caught:
                    api.chat("model", "system", "content")
                self.assertNotIn("synthetic-secret", str(caught.exception))
                self.assertEqual(api.session.post.call_count, 1)

    def test_no_speech_segments_filtered(self):
        api = core.Cloud("synthetic", core.DEFAULTS)
        api.post = Mock(
            return_value={
                "segments": [
                    {"text": "real words", "no_speech_prob": 0.1, "avg_logprob": -0.2},
                    {"text": "hallucination", "no_speech_prob": 0.9},
                ]
            }
        )
        self.assertEqual(api.transcribe(np.zeros(16000, dtype=np.float32), "context"), "real words")

    def test_empty_chat_response_is_error(self):
        api = core.Cloud("synthetic", core.DEFAULTS)
        api.post = Mock(return_value={"choices": [{"message": {"content": None}}]})
        with self.assertRaises(core.ApiError):
            api.chat("model", "system", "content")

    def test_clipped_output_marked(self):
        api = core.Cloud("synthetic", core.DEFAULTS)
        api.post = Mock(return_value={"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]})
        self.assertIn("不完整", api.chat("model", "system", "content"))


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.store = CredentialStore(Path("/synthetic"), core.DEFAULTS)

    def test_endpoints_have_separate_records(self):
        other = CredentialStore(Path("/synthetic"), {**core.DEFAULTS, "text_base_url": "http://home-server:8000/v1"})
        self.assertNotEqual(self.store.account, other.account)
        self.assertEqual(len(self.store.account), 64)

    def test_secret_passes_only_via_stdin(self):
        with patch("credentials.subprocess.run", return_value=Mock(returncode=0, stdout='{"status":"ok"}')) as run:
            self.store.save("synthetic-not-real")
            args, kwargs = run.call_args
            self.assertNotIn("synthetic-not-real", str(args))
            self.assertEqual(json.loads(kwargs["input"])["secret"], "synthetic-not-real")

    def test_missing_key_does_not_fallback_to_plaintext(self):
        with patch("credentials.subprocess.run", return_value=Mock(returncode=0, stdout='{"status":"missing"}')):
            self.assertEqual(self.store.load(), "")

    def test_helper_failure_does_not_echo_output(self):
        with patch("credentials.subprocess.run", return_value=Mock(returncode=1, stdout="synthetic-secret")):
            with self.assertRaises(RuntimeError) as caught:
                self.store.load()
            self.assertNotIn("synthetic-secret", str(caught.exception))


class NotesTests(unittest.TestCase):
    def test_pending_source_saved_then_replaced_with_organized_notes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, "DATA_ROOT", Path(tmp)):
            sig = Signals()
            engine = core.Engine(sig, {"notes_interval": 3600})
            api = Mock()
            api.transcribe.return_value = "Binary search requires a sorted array."
            api.chat.side_effect = lambda model, system, text, limit: (
                "二分查找要求数组有序。" if limit == 1100 else "- 前提：数组有序。"
            )
            engine.api = api
            engine.active = True
            engine.gen = 1
            engine.ensure_session()
            engine.chunks.put((1, 1, np.ones(16000, dtype=np.float32) * 0.1, time.monotonic()))
            path = engine.session_dir / "notes.md"
            until = time.monotonic() + 3
            while "Binary search" not in path.read_text() and time.monotonic() < until:
                time.sleep(0.01)
            self.assertIn("Binary search", path.read_text())
            engine.force_notes.set()
            until = time.monotonic() + 3
            while "前提" not in path.read_text() and time.monotonic() < until:
                time.sleep(0.01)
            self.assertIn("前提", path.read_text())
            self.assertNotIn("尚待整理", path.read_text())
            self.assertTrue((engine.session_dir / "transcript.jsonl").exists())
            engine.shutdown = True
            engine.force_notes.set()


if __name__ == "__main__":
    unittest.main()
