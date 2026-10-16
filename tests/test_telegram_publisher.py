import unittest
from unittest.mock import patch

from football_analysis.telegram_publisher import MAX_MESSAGE_LENGTH, send_message, split_message


class TelegramPublisherTests(unittest.TestCase):
    def test_requires_token_and_chat_id(self):
        with self.assertRaises(ValueError):
            send_message("hello", token="", chat_id="123")
        with self.assertRaises(ValueError):
            send_message("hello", token="token", chat_id="")

    def test_splits_long_text_into_safe_chunks(self):
        text = ("ligne importante\n" * 1200).strip()
        chunks = split_message(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk) <= MAX_MESSAGE_LENGTH for chunk in chunks))
        self.assertTrue(all(chunk == chunk.strip() for chunk in chunks))

    def test_short_text_remains_one_chunk(self):
        self.assertEqual(split_message("preview"), ["preview"])

    @patch("football_analysis.telegram_publisher._send_one")
    def test_sends_long_report_as_multiple_messages(self, mocked_send):
        mocked_send.side_effect = [
            {"ok": True, "result": {"message_id": 41}},
            {"ok": True, "result": {"message_id": 42}},
            {"ok": True, "result": {"message_id": 43}},
        ]
        text = "x" * (MAX_MESSAGE_LENGTH * 2 + 25)
        result = send_message(text, token="test-token", chat_id="-100123")
        self.assertEqual(mocked_send.call_count, 3)
        self.assertEqual([call.args[0] for call in mocked_send.call_args_list], split_message(text))
        self.assertEqual(len(result["messages"]), 3)
        self.assertEqual(result["result"]["message_id"], 43)

    @patch("football_analysis.telegram_publisher.urlopen")
    def test_sends_short_telegram_message_and_returns_result(self, mocked_urlopen):
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
