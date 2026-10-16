import io
import json
import unittest
import urllib.error
from email.message import Message

from football_analysis.api_football_client import (
    ApiFootballAuthError,
    ApiFootballClient,
    ApiFootballRateLimitError,
    ApiFootballResponseError,
)


class FakeResponse:
    def __init__(self, body, headers=None, status=200):
        self._body = body.encode("utf-8") if isinstance(body, str) else body
        self.headers = headers or {}
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body


class ApiFootballClientTests(unittest.TestCase):
    def test_requires_key_without_making_request(self):
        with self.assertRaises(ApiFootballAuthError):
            ApiFootballClient(api_key="")

    def test_sends_key_and_parses_quota_headers(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["key"] = request.get_header("X-apisports-key")
            seen["timeout"] = timeout
            return FakeResponse(
                json.dumps({"response": [{"id": 7}], "errors": []}),
                headers={
                    "x-ratelimit-requests-limit": "7500",
                    "x-ratelimit-requests-remaining": "7490",
                    "X-RateLimit-Limit": "300",
                    "X-RateLimit-Remaining": "290",
                },
            )

        client = ApiFootballClient("not-a-real-key", opener=opener, sleep=lambda _delay: None)
        result = client.get("fixtures", {"league": 39, "season": 2026, "unused": None})
        self.assertEqual(result["response"][0]["id"], 7)
        self.assertIn("league=39", seen["url"])
        self.assertNotIn("unused", seen["url"])
        self.assertEqual(seen["key"], "not-a-real-key")
        self.assertEqual(client.last_quota.daily_remaining, 7490)
        self.assertEqual(client.last_quota.minute_limit, 300)

    def test_retries_429_using_retry_after(self):
        calls, sleeps = [], []

        def opener(_request, timeout):
            calls.append(timeout)
            if len(calls) == 1:
                headers = Message()
                headers["Retry-After"] = "2"
                raise urllib.error.HTTPError("https://example.test", 429, "rate limited", headers, io.BytesIO(b""))
            return FakeResponse('{"response":[],"errors":[]}')

        client = ApiFootballClient("test", max_retries=1, opener=opener, sleep=sleeps.append)
        self.assertEqual(client.get("fixtures")["response"], [])
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [2.0])

    def test_stops_after_bounded_rate_limit_retries(self):
        def opener(_request, timeout=None):
            headers = Message()
            raise urllib.error.HTTPError("https://example.test", 429, "rate limited", headers, io.BytesIO(b""))

        client = ApiFootballClient("test", max_retries=2, opener=opener, sleep=lambda _delay: None)
        with self.assertRaises(ApiFootballRateLimitError):
            client.get("odds")

    def test_does_not_retry_authentication_failure(self):
        calls = []

        def opener(_request, _timeout):
            calls.append(1)
            headers = Message()
            raise urllib.error.HTTPError("https://example.test", 401, "unauthorized", headers, io.BytesIO(b""))

        client = ApiFootballClient("test", max_retries=3, opener=opener, sleep=lambda _delay: None)
        with self.assertRaises(ApiFootballAuthError):
            client.get("fixtures")
        self.assertEqual(len(calls), 1)

    def test_provider_validation_error_is_safe(self):
        client = ApiFootballClient(
            "test",
            opener=lambda *_args, **_kwargs: FakeResponse(
                '{"response":[],"errors":{"token":"sensitive detail"}}'
            ),
        )
        with self.assertRaises(ApiFootballResponseError) as caught:
            client.get("fixtures")
        self.assertIn("token", str(caught.exception))
        self.assertNotIn("sensitive detail", str(caught.exception))
        self.assertNotIn("test", str(caught.exception))

    def test_rejects_absolute_endpoint(self):
        client = ApiFootballClient("test", opener=lambda *_a, **_k: self.fail("network should not be called"))
        with self.assertRaises(ValueError):
            client.get("https://example.com")


if __name__ == "__main__":
    unittest.main()
