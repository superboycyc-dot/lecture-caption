"""Bounded, revisable utterances shared by Apple and cloud recognition."""

from dataclasses import dataclass
from collections import deque
import numpy as np


@dataclass
class Utterance:
    ident: int
    revision: int
    audio: np.ndarray
    started: float
    ended: float
    final: bool


class UtteranceSegmenter:
    """Preview cumulative audio; seal on a natural pause, not every preview tick.

    Keeping the prefix lets ASR revise words cut by an earlier preview. All
    translations use the complete current text, never stitched translations.
    """

    def __init__(self, identify, emit, preview_seconds=3, max_seconds=24, silence_seconds=0.4):
        self.identify, self.emit = identify, emit
        self.preview_frames = max(1, round(preview_seconds * 50))
        self.max_frames = round(max_seconds * 50)
        self.silence_frames = round(silence_seconds * 50)
        self.preroll = deque(maxlen=10)
        self.frames = []
        self.ident = None
        self.revision = 0
        self.started = 0
        self.silence = 0
        self.voiced = 0
        self.last_preview = 0

    def feed(self, frame, speaking, started):
        if self.ident is None:
            self.preroll.append((frame, started))
            if not speaking:
                return
            self.ident = self.identify()
            self.started = self.preroll[0][1]
            self.frames = [a for a, _ in self.preroll]
            self.preroll.clear()
            self.revision = self.last_preview = self.silence = 0
            self.voiced = 1
        else:
            self.frames.append(frame)
            self.voiced += bool(speaking)
            self.silence = 0 if speaking else self.silence + 1
        if self.silence >= self.silence_frames or len(self.frames) >= self.max_frames:
            self.snapshot(final=True)
            self.ident = None
            self.frames = []
        elif len(self.frames) - self.last_preview >= self.preview_frames:
            self.snapshot(final=False)

    def snapshot(self, final):
        if self.voiced < 20:
            return
        self.revision += 1
        audio = np.concatenate(self.frames).astype(np.float32)
        self.emit(Utterance(self.ident, self.revision, audio, self.started, self.started + len(audio) / 16000, final))
        self.last_preview = len(self.frames)


def offer_utterance(q, generation, utterance):
    """Coalesce superseded previews; never evict a final for another preview.

    A false return means a completed utterance was dropped, requiring a gap mark.
    """
    with q.mutex:
        items = q.queue
        for i in range(len(items) - 1, -1, -1):
            old_generation, old = items[i]
            if old_generation == generation and old.ident == utterance.ident:
                items[i] = (generation, utterance)
                q.not_empty.notify()
                return True
        retained = True
        if len(items) >= q.maxsize:
            preview = next((i for i, (_, item) in enumerate(items) if not item.final), None)
            if preview is not None:
                del items[preview]
                retained = False  # even a preview can be the last retained speech for its paragraph
            elif not utterance.final:
                return True  # its eventual final will be queued; keep completed speech
            else:
                items.popleft()
                retained = False
        items.append((generation, utterance))
        q.not_empty.notify()
        return retained
