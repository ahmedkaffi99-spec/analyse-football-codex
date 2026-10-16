import unittest
from unittest.mock import patch

from football_analysis.telegram_publisher import send_message


class TelegramPublisherTests(unittest.TestCase):
    def test_requires_token_and_chat_id(self):
        with self.assertRaises(ValueError):
            send_message("hello", token="", chat_id="123")
        with self.assertRaises(ValueError):
            send_message("hello", token="token", chat_id="")

    @patch("football_analysis.telegram_publisher.urlopen")
    def test_sends_telegram_message_and_returns_result(self, mocked_urlopen):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b'{"ok": true, "result": {"message_id": 42}}'
        mocked_urlopen.return_value = Response()
        result = send_message("preview", token="test-token", chat_id="-100123")
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["message_id"], 42)
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.telegram.org/bottest-token/sendMessage")
        self.assertIn(b'"text": "preview"', request.data)
        self.assertIn(b'"chat_id": "-100123"', request.data)

    @patch("football_analysis.telegram_publisher.urlopen")
    def test_rejects_telegram_api_failure(self, mocked_urlopen):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b'{"ok": false, "description": "chat not found"}'
        mocked_urlopen.return_value = Response()
        with self.assertRaises(RuntimeError):
            send_message("preview", token="test-token", chat_id="bad-chat")


if __name__ == "__main__":
    unittest.main()
