"""Synthetic provider failures, retry pacing, cancellation and safe diagnostics."""

from unittest import TestCase
from unittest.mock import Mock, patch
import requests
import core


class ProviderRetryTests(TestCase):
    def api(self, responses):
        api = core.Cloud("synthetic-secret", core.DEFAULTS, on_retry=Mock())
        api.session.post = Mock(side_effect=responses)
        api.retry_wait = Mock()
        return api

    @staticmethod
    def response(status, headers=None):
        return Mock(
            status_code=status,
            ok=status == 200,
            headers=headers or {},
            json=Mock(return_value={"choices": [{"message": {"content": "Synthetic notes"}}]}),
        )

    def test_retry_after_and_transient_service_errors_recover(self):
        for response in [self.response(429, {"retry-after": "7"}), self.response(503), requests.Timeout()]:
            with self.subTest(response=type(response).__name__):
                api = self.api([response, self.response(200)])
                self.assertEqual(api.chat("model", "system", "synthetic input"), "Synthetic notes")
                self.assertEqual(api.session.post.call_count, 2)
                api.retry_wait.assert_called()
                api.on_retry.assert_called_once()
                if not isinstance(response, Exception) and response.status_code == 429:
                    self.assertGreaterEqual(api.retry_wait.call_args_list[0].args[0], 7)

    def test_permanent_errors_never_retry_or_echo_server_body(self):
        for status in [400, 401, 403, 404, 413, 422]:
            api = self.api([self.response(status)])
            with self.assertRaises(core.ApiError) as caught:
                api.chat("model", "system", "private synthetic input")
            self.assertIn(str(status), str(caught.exception))
            self.assertNotIn("synthetic-secret", str(caught.exception))
            self.assertNotIn("private synthetic input", str(caught.exception))
            self.assertEqual(api.session.post.call_count, 1)
            api.retry_wait.assert_not_called()

    def test_daily_limit_defers_instead_of_hammering_provider(self):
        api = self.api([self.response(429, {"retry-after": "3600"})])
        for _ in range(2):
            with self.assertRaises(core.ApiError) as caught:
                api.chat("model", "system", "content")
            self.assertTrue(caught.exception.retryable)
        self.assertEqual(api.session.post.call_count, 1)
        api.retry_wait.assert_not_called()

    def test_retries_are_bounded(self):
        api = self.api([requests.ConnectionError()] * 3)
        with self.assertRaises(core.ApiError) as caught:
            api.chat("model", "system", "content")
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(api.session.post.call_count, 3)
        self.assertEqual(api.retry_wait.call_count, 2)

    def test_cancelled_capture_never_uploads(self):
        api = core.Cloud("synthetic", core.DEFAULTS, should_continue=lambda path: False)
        api.session.post = Mock()
        with self.assertRaises(core.RequestCancelled):
            api.post("https://synthetic.invalid", "/audio/transcriptions")
        api.session.post.assert_not_called()

    def test_retry_wait_is_interruptible(self):
        api = core.Cloud("synthetic", core.DEFAULTS, should_continue=lambda path: False)
        with self.assertRaises(core.RequestCancelled):
            api.retry_wait(30, "/audio/transcriptions")

    def test_malformed_success_has_safe_diagnostic(self):
        response = self.response(200)
        response.json.return_value = ["private synthetic output"]
        api = self.api([response])
        with self.assertRaises(core.ApiError) as caught:
            api.chat("model", "system", "content")
        self.assertIn("格式异常", str(caught.exception))
        self.assertNotIn("private", str(caught.exception))

    def test_pause_then_resume_does_not_retry_old_audio_generation(self):
        epoch = [1]
        api = core.Cloud("synthetic", core.DEFAULTS, capture_epoch=lambda: epoch[0])
        api.session.post = Mock(side_effect=requests.Timeout())

        def pause_and_resume(*_):
            epoch[0] = 2

        api.retry_wait = pause_and_resume
        with self.assertRaises(core.RequestCancelled):
            api.post("https://synthetic.invalid", "/audio/transcriptions")
        self.assertEqual(api.session.post.call_count, 1)

    def test_capture_cancelled_at_end_of_cooldown_does_not_upload(self):
        epoch = [1]
        api = core.Cloud("synthetic", core.DEFAULTS, capture_epoch=lambda: epoch[0])
        api.cooldowns[("https://synthetic.invalid", "")] = core.time.monotonic() + 10
        api.session.post = Mock()

        def cancel_after_wait(*_):
            epoch[0] = 2

        api.retry_wait = cancel_after_wait
        with self.assertRaises(core.RequestCancelled):
            api.post("https://synthetic.invalid", "/audio/transcriptions")
        api.session.post.assert_not_called()
