"""Synthetic continuation/edit/revise/finalization regression tests."""

import os
import tempfile
import threading
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

os.environ["LECTURE_CAPTION_NO_UPDATE"] = "1"
import core
from test_pipeline import Signals


class DocumentTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = patch.object(core, "DATA_ROOT", self.root)
        self.patch.start()
        self.engine = core.Engine(Signals(), {"notes_interval": 3600})

    def tearDown(self):
        self.engine.shutdown = True
        self.engine.force_notes.set()
        time.sleep(0.02)
        self.patch.stop()
        self.temp.cleanup()

    def test_import_is_baseline_and_edit_is_backed_up(self):
        self.engine.replace_document("# 二叉搜索树\n\n## 上一课\n- 左子树更小。")
        self.engine.pending = [("10:00", "Today we prove the invariant.")]
        self.engine.api = Mock()
        self.engine.api.chat.return_value = "# 二叉搜索树\n\n- 左子树更小。\n- 不变量证明。"
        self.engine.process_notes()
        payload = self.engine.api.chat.call_args.args[2]
        self.assertIn("上一课", payload)
        self.assertIn("Today we prove", payload)
        self.engine.replace_document("# 手动修正\n\n- 左右子树有序。")
        self.assertTrue(list(self.engine.session_dir.glob("notes-before-edit-*.md")))
        self.assertIn("手动修正", (self.engine.session_dir / "notes.md").read_text())

    def test_edit_wins_over_inflight_response_and_new_source_is_requeued(self):
        self.engine.replace_document("# 原笔记\n- 原定义")
        self.engine.pending = [("10:00", "New material")]
        api = Mock()

        def response(*_):
            self.engine.replace_document("# 人工改正\n- 人工定义")
            return "# 过时模型结果"

        api.chat.side_effect = response
        self.engine.api = api
        self.engine.process_notes()
        self.assertIn("人工改正", self.engine.sections[0])
        self.assertEqual(self.engine.pending, [("10:00", "New material")])

    def test_revise_reorganizes_whole_document_and_sets_specific_title(self):
        self.engine.replace_document("## 定义\n- 不变量\n## 例子\n- 二分搜索")
        self.engine.api = Mock()
        self.engine.api.chat.return_value = "# 二分搜索与循环不变量\n\n## 定义与证明\n- 不变量\n- 二分搜索"
        self.engine.revise_notes()
        self.assertEqual(self.engine.note_title, "二分搜索与循环不变量")
        self.assertFalse(self.engine.revise_dirty)
        self.assertTrue((self.engine.session_dir / "notes.md").read_text().startswith("# 二分搜索与循环不变量"))
        self.engine.revise_notes()
        self.engine.api.chat.assert_called_once()

    def test_failed_revise_preserves_document(self):
        self.engine.replace_document("# 已保存的原笔记\n- 保留事实")
        self.engine.api = Mock()
        self.engine.api.chat.return_value = "# 缺失内容\n【输出达到上限，本段可能不完整】"
        with self.assertRaises(core.ApiError):
            self.engine.revise_notes()
        self.assertIn("保留事实", self.engine.sections[0])

    def test_finish_waits_for_final_revise_and_preserves_backup(self):
        self.engine.replace_document("# 原笔记\n- 定义")
        entered, release = threading.Event(), threading.Event()
        api = Mock()

        def response(*_):
            entered.set()
            release.wait(2)
            return "# 最终课程主题\n- 定义与推导"

        api.chat.side_effect = response
        self.engine.api = api
        self.engine.finish()
        self.assertTrue(entered.wait(2))
        self.assertFalse(self.engine.finished.is_set())
        release.set()
        self.assertTrue(self.engine.finished.wait(3))
        self.assertEqual(self.engine.note_title, "最终课程主题")
        self.assertIn("定义与推导", (self.engine.session_dir / "notes.md").read_text())

    def test_auto_revise_runs_without_new_pending_fragments(self):
        self.engine.replace_document("# 已有笔记\n- 前文概念")
        self.engine.api = Mock()
        self.engine.api.chat.return_value = "# 概念与依赖\n- 前文概念"
        self.engine.last_revise = time.monotonic() - 301
        self.engine.force_notes.set()
        deadline = time.monotonic() + 3
        while self.engine.revise_dirty and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(self.engine.revise_dirty)
        self.assertEqual(self.engine.note_title, "概念与依赖")

    def test_end_during_inflight_revise_runs_a_fresh_final_pass(self):
        self.engine.replace_document("# 原主题\n- 定义")
        entered, release = threading.Event(), threading.Event()
        api = Mock()

        def response(*_):
            if not entered.is_set():
                entered.set()
                release.wait(2)
                return "# 过时主题\n- 定义"
            return "# 最终二次整理主题\n- 定义与总结"

        api.chat.side_effect = response
        self.engine.api = api
        self.engine.last_revise = time.monotonic() - 301
        self.engine.force_notes.set()
        self.assertTrue(entered.wait(2))
        self.engine.active = True
        self.engine.finish()
        release.set()
        self.assertTrue(self.engine.finished.wait(3))
        self.assertEqual(self.engine.note_title, "最终二次整理主题")
        self.assertEqual(api.chat.call_count, 2)
        self.assertIn("【缺失片段】", "\n".join(self.engine.sections))

    def test_empty_key_never_creates_cloud_client_for_note_only_save(self):
        self.engine.configure("")
        self.assertIsNone(self.engine.api)
        self.engine.replace_document("# 离线手写笔记\n\n定义")
        self.engine.finish()
        self.assertTrue(self.engine.finished.wait(3))
        self.assertIn("离线手写笔记", (self.engine.session_dir / "notes.md").read_text())

    def test_explicit_summary_can_run_once_after_editor_focus_returns(self):
        self.engine.replace_document("# 已有笔记\n\n定义")
        self.engine.notes_editing = True
        self.engine.pending = [("12:00", "New source")]
        from unittest.mock import Mock

        self.engine.api = Mock()
        self.engine.api.chat.return_value = "# 已整理内容\n\n定义与新内容"
        self.engine.manual_summary.set()
        self.engine.process_notes()
        self.engine.api.chat.assert_called_once()
        self.assertFalse(self.engine.manual_summary.is_set())
