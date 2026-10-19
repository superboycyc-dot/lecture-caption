# Third-party notices

## Application

Lecture Caption application code is MIT; see `LICENSE`. The blue/white project icon is AI-generated and distributed under the same project terms, without an exclusivity or trademark-registration claim.

## Vendored modules

`vendor/audio.py`, `vendor/quota.py`, `vendor/config.py` come from [AwesomeMi/realtime-transcribe](https://github.com/AwesomeMi/realtime-transcribe), commit `8b3639490068b327eb85aaf9daab60d58aa82709`, MIT, Copyright (c) 2026 AwesomeMi. Its full license is preserved in `vendor/LICENSE`; provenance also appears in `vendor/UPSTREAM_COMMIT`. These modules provide voice-activity detection, chunking, WAV encoding and quota accounting. This is an independent adaptation, not an official upstream release.

## Bundled runtime

Python, PySide6/Qt, Shiboken, NumPy, SciPy, python-sounddevice/PortAudio, Requests and their transitive dependencies retain their respective licenses and notices. Exact runtime versions are pinned in `requirements-lock.txt`. Distribution metadata license files are copied into `licenses/` by `scripts/collect_licenses.py`; they ship inside the application and source releases.

Qt/PySide/Shiboken are used under the LGPLv3 alternative. Copyright belongs to The Qt Company Ltd. and its contributors. Complete LGPLv3 and GPLv3 texts accompany the distribution in `licenses/`. They are dynamically bundled, and users may replace compatible libraries or rebuild the open application; see `docs/RELEASING.md`. Official matching-version source: [PySide/Shiboken](https://code.qt.io/pyside/pyside-setup.git/) and [Qt base](https://code.qt.io/qt/qtbase.git/).

The PyInstaller bootloader uses its GPL license with a distribution exception; its notice is retained. Native Apple frameworks are system dependencies, not redistributed copies. No AI model weights are bundled; use of cloud services and models is governed by the selected provider's terms. No affiliation with Apple, Groq or the upstream authors is implied.
