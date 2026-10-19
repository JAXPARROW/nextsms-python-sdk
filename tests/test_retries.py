"""
Tests for the v0.2.0 retry policy.

Most tests run the real requests -> urllib3 -> SafeRetry stack against a
throwaway local HTTP server (stdlib only), so urllib3's own retry loop is
exercised and we can count exactly how many requests reached the "server".
Sleeps are recorded instead of slept.
"""

import json
import socket
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import urllib3.connection
import urllib3.util.retry as retry_module
from urllib3.exceptions import NewConnectionError, ProtocolError, ReadTimeoutError
from urllib3.response import HTTPResponse

from nextsms import (
    NextSMS,
    NextSMSAmbiguousResponseError,
    NextSMSConnectionError,
    NextSMSRateLimitError,
    NextSMSServerError,
)
from nextsms.utils.http_client import SafeRetry, build_retry

SEND = dict(sender_id="NANOTECH", recipient="255712345678", message="Hello")


# ----------------------------------------------------------------------
# Fixtures: scripted local server + recorded sleeps
# ----------------------------------------------------------------------

class _ScriptedServer:
    """Replies with queued (status, headers, delay) tuples, then 200 OK."""

    def __init__(self):
        self.script = []
        self.requests = []  # (method, path, client_port)
        self.release = threading.Event()
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"  # keep-alive, so pooling is observable

            def log_message(self, *args):
                pass

            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    self.rfile.read(length)
                server.requests.append((self.command, self.path, self.client_address[1]))
                status, headers, delay = (server.script.pop(0) if server.script
                                          else (200, {}, 0))
                if delay:
                    server.release.wait(delay)  # longer than the client timeout
                body = json.dumps({"message": "OK" if status == 200 else "error"}).encode()
                try:
                    self.send_response(status)
                    for k, v in headers.items():
                        self.send_header(k, v)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:
                    pass  # client already gave up

            do_GET = do_POST = _handle

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.release.set()
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    s = _ScriptedServer()
    yield s
    s.close()


@pytest.fixture
def sleeps(monkeypatch):
    """Record urllib3 retry sleeps instead of sleeping."""
    recorded = []
    import time as real_time
    fake_time = types.SimpleNamespace(sleep=recorded.append, time=real_time.time)
    monkeypatch.setattr(retry_module, "time", fake_time)
    return recorded


def _client(base_url, **kwargs):
    c = NextSMS(username="u", password="p", **kwargs)
    c.http.base_url = base_url
    return c


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def count_connects(monkeypatch):
    """Count TCP connection attempts; optionally fail the first N."""
    state = {"calls": 0, "fail_first": 0}
    original = urllib3.connection.HTTPConnection._new_conn

    def spy(self):
        state["calls"] += 1
        if state["calls"] <= state["fail_first"]:
            raise NewConnectionError(self, "simulated: connection refused")
        return original(self)

    monkeypatch.setattr(urllib3.connection.HTTPConnection, "_new_conn", spy)
    return state


# ----------------------------------------------------------------------
# POST (send SMS): never resend something that may have been processed
# ----------------------------------------------------------------------

class TestPostRetries:
    def test_post_503_is_not_retried(self, server, sleeps):
        server.script = [(503, {}, 0)]
        with _client(server.url) as c, pytest.raises(NextSMSServerError):
            c.send_sms(**SEND)
        assert len(server.requests) == 1
        assert sleeps == []

    @pytest.mark.parametrize("status", [500, 502, 504])
    def test_post_other_5xx_not_retried(self, server, sleeps, status):
        server.script = [(status, {}, 0)]
        with _client(server.url) as c, pytest.raises(NextSMSServerError):
            c.send_sms(**SEND)
        assert len(server.requests) == 1

    def test_post_503_with_retry_after_still_not_retried(self, server, sleeps):
        server.script = [(503, {"Retry-After": "1"}, 0)]
        with _client(server.url) as c, pytest.raises(NextSMSServerError):
            c.send_sms(**SEND)
        assert len(server.requests) == 1

    def test_post_read_timeout_not_retried_and_ambiguous(self, server, sleeps):
        server.script = [(200, {}, 5)]
        with _client(server.url, timeout=0.3) as c:
            with pytest.raises(NextSMSAmbiguousResponseError) as exc_info:
                c.send_sms(**SEND)
        assert len(server.requests) == 1
        # Backwards compatible: still a NextSMSConnectionError
        assert isinstance(exc_info.value, NextSMSConnectionError)

    def test_post_connect_error_is_retried(self, server, sleeps, count_connects):
        count_connects["fail_first"] = 2
        with _client(server.url) as c:
            resp = c.send_sms(**SEND)
        assert resp.success
        assert count_connects["calls"] == 3
        assert len(server.requests) == 1  # delivered exactly once
        assert sleeps == [2.0, 4.0]

    def test_post_connection_refused_exhausts_as_connection_error(self, sleeps, count_connects):
        with _client(f"http://127.0.0.1:{_free_port()}") as c:
            with pytest.raises(NextSMSConnectionError) as exc_info:
                c.send_sms(**SEND)
        # Never sent, so not "ambiguous"
        assert not isinstance(exc_info.value, NextSMSAmbiguousResponseError)
        assert count_connects["calls"] == 4  # 1 + max_retries(3)

    def test_post_429_is_retried_with_backoff(self, server, sleeps):
        server.script = [(429, {}, 0), (429, {}, 0)]
        with _client(server.url) as c:
            assert c.send_sms(**SEND).success
        assert len(server.requests) == 3
        assert sleeps == [2.0, 4.0]

    def test_post_429_honours_retry_after(self, server, sleeps):
        server.script = [(429, {"Retry-After": "7"}, 0)]
        with _client(server.url) as c:
            assert c.send_sms(**SEND).success
        assert len(server.requests) == 2
        assert sleeps == [7.0]

    def test_retry_after_is_capped(self, server, sleeps):
        server.script = [(429, {"Retry-After": "3600"}, 0)]
        with _client(server.url) as c:
            assert c.send_sms(**SEND).success
        assert sleeps == [60.0]

    def test_post_429_exhausted_raises_rate_limit(self, server, sleeps):
        server.script = [(429, {}, 0)] * 4
        with _client(server.url) as c, pytest.raises(NextSMSRateLimitError):
            c.send_sms(**SEND)
        assert len(server.requests) == 4
        assert sleeps == [2.0, 4.0, 8.0]


# ----------------------------------------------------------------------
# GET (balance, logs, status): idempotent, retried on transient failures
# ----------------------------------------------------------------------

class TestGetRetries:
    def test_get_503_is_retried(self, server, sleeps):
        server.script = [(503, {}, 0)] * 3
        with _client(server.url) as c:
            assert c.get_balance().success
        assert len(server.requests) == 4
        assert sleeps == [2.0, 4.0, 8.0]

    def test_get_429_is_retried(self, server, sleeps):
        server.script = [(429, {"Retry-After": "3"}, 0)]
        with _client(server.url) as c:
            assert c.get_balance().success
        assert len(server.requests) == 2
        assert sleeps == [3.0]

    def test_get_503_exhausted_raises_server_error(self, server, sleeps):
        server.script = [(503, {}, 0)] * 4
        with _client(server.url) as c, pytest.raises(NextSMSServerError):
            c.get_balance()
        assert len(server.requests) == 4

    def test_get_read_timeout_is_retried(self, server, sleeps):
        server.script = [(200, {}, 5)]
        with _client(server.url, timeout=0.3) as c:
            assert c.get_balance().success
        assert len(server.requests) == 2

    def test_custom_backoff_factor(self, server, sleeps):
        server.script = [(503, {}, 0)] * 2
        with _client(server.url, backoff_factor=0.5) as c:
            assert c.get_balance().success
        assert sleeps == [0.5, 1.0]

    def test_connection_pool_is_reused(self, server, sleeps):
        with _client(server.url) as c:
            c.get_balance()
            c.get_balance()
            c.send_sms(**SEND)
        ports = {port for _, _, port in server.requests}
        assert len(server.requests) == 3
        assert len(ports) == 1  # same keep-alive connection


# ----------------------------------------------------------------------
# max_retries=0 disables everything
# ----------------------------------------------------------------------

class TestMaxRetriesZero:
    def test_get_503_single_attempt(self, server, sleeps):
        server.script = [(503, {}, 0)]
        with _client(server.url, max_retries=0) as c, pytest.raises(NextSMSServerError):
            c.get_balance()
        assert len(server.requests) == 1
        assert sleeps == []

    def test_post_429_single_attempt(self, server, sleeps):
        server.script = [(429, {}, 0)]
        with _client(server.url, max_retries=0) as c, pytest.raises(NextSMSRateLimitError):
            c.send_sms(**SEND)
        assert len(server.requests) == 1

    def test_get_read_timeout_single_attempt(self, server, sleeps):
        server.script = [(200, {}, 5)]
        with _client(server.url, timeout=0.3, max_retries=0) as c:
            with pytest.raises(NextSMSConnectionError) as exc_info:
                c.get_balance()
        assert not isinstance(exc_info.value, NextSMSAmbiguousResponseError)
        assert len(server.requests) == 1

    def test_post_connect_error_single_attempt(self, sleeps, count_connects):
        with _client(f"http://127.0.0.1:{_free_port()}", max_retries=0) as c:
            with pytest.raises(NextSMSConnectionError):
                c.send_sms(**SEND)
        assert count_connects["calls"] == 1

    def test_negative_max_retries_rejected(self):
        with pytest.raises(ValueError):
            NextSMS(username="u", password="p", max_retries=-1)


# ----------------------------------------------------------------------
# The policy object on its own
# ----------------------------------------------------------------------

class TestSafeRetryPolicy:
    def setup_method(self):
        self.retry = build_retry()

    @pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
    def test_get_retries_transient_statuses(self, status):
        assert self.retry.is_retry("GET", status) is True

    def test_post_retries_only_429(self):
        assert self.retry.is_retry("POST", 429) is True
        for status in (500, 502, 503, 504, 400, 401):
            assert self.retry.is_retry("POST", status) is False
        assert self.retry.is_retry("POST", 503, has_retry_after=True) is False

    def test_post_read_timeout_reraised(self):
        err = ReadTimeoutError(None, "/x", "read timed out")
        with pytest.raises(ReadTimeoutError):
            self.retry.increment(method="POST", url="/x", error=err)

    def test_post_protocol_error_reraised(self):
        err = ProtocolError("Connection aborted.", ConnectionResetError())
        with pytest.raises(ProtocolError):
            self.retry.increment(method="POST", url="/x", error=err)

    def test_post_connect_error_counts_as_retry(self):
        err = NewConnectionError(None, "refused")
        new = self.retry.increment(method="POST", url="/x", error=err)
        assert new.total == 2

    def test_get_read_timeout_counts_as_retry(self):
        err = ReadTimeoutError(None, "/x", "read timed out")
        new = self.retry.increment(method="GET", url="/x", error=err)
        assert new.total == 2

    def test_backoff_sequence_and_cap(self):
        r = build_retry(max_retries=10)
        waits = []
        for _ in range(6):
            r = r.increment(method="GET", url="/x",
                            response=HTTPResponse(status=503, preload_content=False))
            waits.append(r.get_backoff_time())
        assert waits == [2.0, 4.0, 8.0, 16.0, 30.0, 30.0]

    def test_settings_survive_increment(self):
        r = build_retry(backoff_factor=1.5, backoff_max=9, retry_after_max=11)
        r2 = r.increment(method="GET", url="/x",
                         response=HTTPResponse(status=503, preload_content=False))
        assert isinstance(r2, SafeRetry)
        assert (r2.backoff_factor, r2.backoff_max, r2.retry_after_max) == (1.5, 9, 11)

    def test_invalid_retry_after_falls_back_to_backoff(self):
        resp = HTTPResponse(status=429, headers={"Retry-After": "soon"}, preload_content=False)
        assert self.retry.get_retry_after(resp) is None


# ----------------------------------------------------------------------
# Backwards-compatible constructor
# ----------------------------------------------------------------------

class TestConstructorCompat:
    def test_old_positional_signature_still_works(self):
        import logging
        c = NextSMS("u", "p", False, 30, 3, 10, 100, logging.getLogger("x"))
        assert c.http.retry.total == 3
        assert c.http.retry.backoff_factor == 2.0
        c.close()

    def test_backoff_factor_passed_through(self):
        c = NextSMS(username="u", password="p", backoff_factor=0.25, max_retries=5)
        assert c.http.retry.backoff_factor == 0.25
        assert c.http.retry.total == 5
        c.close()
