import queue
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np
import core
import local_services
from utterances import Utterance, UtteranceSegmenter, offer_utterance
from test_pipeline import Signals


class UtteranceTests(unittest.TestCase):
    def test_previews_keep_id_and_prefix_until_pause(self):
        outputs = []
        ids = iter(range(1, 10))
        segmenter = UtteranceSegmenter(lambda: next(ids), outputs.append, preview_seconds=1)
        for i in range(130):
            segmenter.feed(np.full(320, i / 1000, dtype=np.float32), i < 100, 1000 + i * 0.02)
        self.assertEqual([u.ident for u in outputs], [1, 1, 1])
        self.assertEqual([u.final for u in outputs], [False, False, True])
        self.assertEqual(len({u.started for u in outputs}), 1)
        np.testing.assert_array_equal(outputs[-1].audio[: len(outputs[0].audio)], outputs[0].audio)
        self.assertGreater(outputs[-1].ended, outputs[0].ended)
        for i in range(100):
            segmenter.feed(np.ones(320, dtype=np.float32), True, 1003 + i * 0.02)
        self.assertEqual(outputs[-1].ident, 2)

    def test_silence_does_not_produce_recognition(self):
        outputs = []
        segmenter = UtteranceSegmenter(lambda: 1, outputs.append)
        for i in range(1000):
            segmenter.feed(np.zeros(320, dtype=np.float32), False, i * 0.02)
        self.assertEqual(outputs, [])

    def test_queue_coalesces_revisions_without_losing_final(self):
        q = queue.Queue(maxsize=2)
        audio = np.zeros(16000, dtype=np.float32)
        for revision in range(1, 4):
            self.assertTrue(offer_utterance(q, 1, Utterance(1, revision, audio, 1, 2, revision == 3)))
        self.assertEqual(q.qsize(), 1)
        self.assertTrue(q.queue[0][1].final)
        offer_utterance(q, 1, Utterance(2, 1, audio, 3, 4, True))
        offer_utterance(q, 1, Utterance(3, 1, audio, 5, 6, False))
        self.assertEqual([item.ident for _, item in q.queue], [1, 2])

    def test_both_backends_retranslate_complete_revision_and_commit_notes_once(self):
        for backend in ("apple", "cloud"):
            with (
                self.subTest(backend=backend),
                tempfile.TemporaryDirectory() as tmp,
                patch.object(core, "DATA_ROOT", Path(tmp)),
            ):
                sig = Signals()
                engine = core.Engine(
                    sig, {"stt_backend": backend, "translation_backend": backend, "notes_interval": 3600}
                )
                api = Mock()
                engine.api = api
                phrases = ["Binary search requires", "Binary search requires a sorted array."]
                api.transcribe.side_effect = phrases
                api.chat.return_value = "完整译文"
                engine.last_request = -100
                engine.active, engine.gen = True, 1
                engine.ensure_session()
                with (
                    patch.object(local_services, "transcribe", side_effect=phrases),
                    patch.object(local_services, "translate", return_value="完整译文") as translate,
                ):
                    engine.chunks.put((1, Utterance(1, 1, np.ones(16000, dtype=np.float32), 100, 101, False)))
                    self.wait(lambda: len(sig.caption.items) >= 2)
                    self.assertEqual(engine.pending, [])
                    self.assertEqual(engine.live_utterances[1][1], phrases[0])
                    engine.last_request = -100
                    engine.chunks.put((1, Utterance(1, 2, np.ones(32000, dtype=np.float32), 100, 102, True)))
                    self.wait(lambda: len(sig.caption.items) >= 4)
                    self.assertEqual({item[0] for item in sig.caption.items}, {1})
                    self.assertEqual(sig.caption.items[-1][1], phrases[-1])
                    self.assertEqual(sig.caption.items[-1][3:], (100, 102))
                    if backend == "apple":
                        self.assertEqual(translate.call_args.args[0], phrases[-1])
                        api.transcribe.assert_not_called()
                        api.chat.assert_not_called()
                    else:
                        self.assertEqual(api.chat.call_args.args[2], phrases[-1])
                        self.assertEqual(api.transcribe.call_args.args[0].size, 32000)
                    self.assertEqual(len(engine.pending), 1)
                    self.assertEqual(engine.pending[0][1], phrases[-1])
                    self.assertEqual(engine.live_utterances, {})
                engine.active = False
                engine.shutdown = True
                engine.force_notes.set()

    def test_pause_preserves_latest_draft_for_notes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, "DATA_ROOT", Path(tmp)):
            engine = core.Engine(Signals(), {"notes_interval": 3600})
            engine.ensure_session()
            engine.live_utterances[1] = ("12:00:00", "Keep this unfinished sentence")
            engine.stop()
            self.assertEqual(engine.pending, [("12:00:00", "Keep this unfinished sentence")])
            self.assertEqual(engine.live_utterances, {})
            self.assertIn("Keep this unfinished sentence", (engine.session_dir / "notes.md").read_text())
            engine.shutdown = True
            engine.force_notes.set()

    def wait(self, predicate):
        deadline = time.monotonic() + 4
        while not predicate() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(predicate())


class ContinuityTests(unittest.TestCase):
    def wait(self, predicate):
        deadline = time.monotonic() + 4
        while not predicate() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(predicate())

    def test_old_recognition_response_is_discarded_after_handoff(self):
        import threading

        entered, release = threading.Event(), threading.Event()
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, "DATA_ROOT", Path(tmp)):
            sig = Signals()
            engine = core.Engine(sig, {"notes_interval": 3600})

            def delayed(*_):
                entered.set()
                release.wait(2)
                return "Stale words from old input"

            api = Mock()
            api.transcribe.side_effect = delayed
            engine.api = api
            engine.active, engine.gen = True, 1
            engine.ensure_session()
            engine.chunks.put((1, Utterance(1, 1, np.ones(16000, dtype=np.float32), 100, 101, True)))
            self.wait(entered.is_set)
            engine.gen = 2
            release.set()
            time.sleep(0.1)
            self.assertEqual(sig.caption.items, [])
            self.assertEqual(engine.pending, [])
            api.chat.assert_not_called()
            engine.active = False
            engine.shutdown = True
            engine.force_notes.set()

    def test_continuous_note_document_carries_previous_context(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, "DATA_ROOT", Path(tmp)):
            engine = core.Engine(Signals(), {"notes_interval": 3600})
            engine.ensure_session()
            engine.sections = ["## 定义\n- An invariant remains true."]
            engine.source_paragraphs = {
                1: ("10:00:00", "Define an invariant."),
                2: ("10:00:12", "It must hold after each iteration."),
            }
            engine.pending = [engine.source_paragraphs[2]]
            api = Mock()
            api.chat.return_value = "## 定义与用途\n- Invariant must hold after each iteration."
            engine.api = api
            engine.force_notes.set()
            self.wait(lambda: len(engine.sections) == 2)
            self.assertTrue(engine.sections[1].startswith("## 定义与用途"))
            self.assertIn("An invariant remains true", engine.sections[0])
            payload = api.chat.call_args.args[2]
            self.assertIn("An invariant remains true", payload)
            self.assertNotIn("Define an invariant", payload)
            self.assertIn("It must hold after each iteration", payload)
            self.assertEqual(len(engine.sections), 2)
            engine.save_notes()
            source = (engine.session_dir / "transcript.md").read_text()
            self.assertIn("Define an invariant", source)
            self.assertIn("It must hold after each iteration", source)
            self.assertNotIn("10:00:00 —", engine.sections[0])
            engine.shutdown = True
            engine.force_notes.set()

    def test_translation_handoff_discards_old_translation_without_duplicate_notes(self):
        import threading

        entered, release = threading.Event(), threading.Event()
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(core, "DATA_ROOT", Path(tmp)),
            patch.object(local_services, "translate", return_value="新模型译文"),
        ):
            sig = Signals()
            engine = core.Engine(sig, {"notes_interval": 3600})

            def delayed(*_):
                entered.set()
                release.wait(3)
                return "stale translation"

            api = Mock()
            api.transcribe.return_value = "An invariant holds."
            api.chat.side_effect = delayed
            engine.api = api
            engine.active, engine.gen = True, 1
            engine.ensure_session()
            engine.chunks.put((1, Utterance(1, 1, np.ones(16000, dtype=np.float32), 100, 101, True)))
            self.wait(entered.is_set)
            engine.change_translation("apple", "unused", "synthetic")
            release.set()
            self.wait(lambda: any(c[2] == "新模型译文" for c in sig.caption.items))
            self.assertFalse(any(c[2] == "stale translation" for c in sig.caption.items))
            self.assertEqual(engine.gen, 1)
            self.assertEqual(len(engine.pending), 1)
            self.assertEqual(engine.pending[0][1], "An invariant holds.")
            engine.active = False
            engine.shutdown = True
            engine.force_notes.set()
