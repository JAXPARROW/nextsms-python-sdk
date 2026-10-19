"""
HTTP client with connection pooling and retry logic for NextSMS API.

Retry policy (see ``SafeRetry``)
--------------------------------
Sending an SMS is a POST and is *not* idempotent: if NextSMS accepted the
message but the reply was lost or was a 5xx, sending it again delivers a
duplicate SMS to the customer and is billed twice.  So the SDK only retries
a request automatically when it is certain the first attempt was not
processed:

=================================  ====================  ======================
Outcome                            GET / HEAD / OPTIONS  POST (and other verbs)
=================================  ====================  ======================
Connect error / DNS / refused      retry                 retry (never sent)
HTTP 429 Too Many Requests         retry                 retry (was rejected)
HTTP 500 / 502 / 503 / 504         retry                 NO retry -> exception
Read timeout / read error /        retry                 NO retry -> exception
protocol error after sending                             (ambiguous)
=================================  ====================  ======================

Waits between attempts honour the server's ``Retry-After`` header (capped at
``retry_after_max``), otherwise ``backoff_factor * 2 ** (n - 1)`` seconds for
the n-th retry (2 s, 4 s, 8 s with the default factor), capped at
``backoff_max``.
"""

import logging
import ssl
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.exceptions import ConnectTimeoutError, ProxyError
from urllib3.util.retry import Retry

from ..exceptions import NextSMSAmbiguousResponseError, NextSMSConnectionError

logger = logging.getLogger(__name__)

BASE_URL = "https://messaging-service.co.tz"
TEST_BASE_URL = "https://messaging-service.co.tz/test"
SDK_VERSION = "0.2.0"

#: Methods that are safe to repeat: the SDK only uses them for reads
#: (balance, logs, delivery status).
IDEMPOTENT_METHODS = frozenset(["GET", "HEAD", "OPTIONS"])

#: Statuses retried for idempotent methods.
RETRY_STATUSES = frozenset([429, 500, 502, 503, 504])

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 2.0    # waits of 2 s, 4 s, 8 s
DEFAULT_BACKOFF_MAX = 30.0      # never back off longer than this per attempt
DEFAULT_RETRY_AFTER_MAX = 60.0  # cap on a server-supplied Retry-After


def _is_connect_error(err: BaseException) -> bool:
    """True if ``err`` happened while opening the connection, i.e. before
    any byte of the request reached the server.

    ``NewConnectionError`` (refused, unreachable) and ``NameResolutionError``
    (DNS) both subclass ``ConnectTimeoutError`` in urllib3 1.26 and 2.x.
    """
    if isinstance(err, ProxyError) and getattr(err, "original_error", None) is not None:
        err = err.original_error
    return isinstance(err, ConnectTimeoutError)


class SafeRetry(Retry):
    """urllib3 ``Retry`` that never repeats a request that may already have
    been processed by the server.

    * Idempotent methods (``IDEMPOTENT_METHODS``) behave like a normal
      ``Retry``: connect/read errors and ``status_forcelist`` are retried.
    * Every other method (POST) is retried only on connection errors
      (request never sent) and on HTTP 429 (request rejected, not processed).

    The backoff formula and the Retry-After cap are implemented here instead
    of inherited because they differ between urllib3 1.26 and 2.x (both skip
    the wait before the *first* retry, and ``backoff_max`` /
    ``retry_after_max`` are not constructor arguments in every version).
    """

    def __init__(
        self,
        *args,
        backoff_max: float = DEFAULT_BACKOFF_MAX,
        retry_after_max: float = DEFAULT_RETRY_AFTER_MAX,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        # Set after super().__init__ so they win over urllib3's own defaults.
        self.backoff_max = backoff_max
        self.retry_after_max = retry_after_max

    def new(self, **kw):
        # urllib3 1.26's new() does not forward these; 2.x does. Make both work.
        kw.setdefault("backoff_max", self.backoff_max)
        kw.setdefault("retry_after_max", self.retry_after_max)
        return super().new(**kw)

    @staticmethod
    def _is_idempotent(method: Optional[str]) -> bool:
        return method is not None and method.upper() in IDEMPOTENT_METHODS

    # -- decisions ----------------------------------------------------------

    def is_retry(self, method, status_code, has_retry_after=False):
        """Should a request that got ``status_code`` be retried?"""
        if self._is_idempotent(method):
            return super().is_retry(method, status_code, has_retry_after)
        # Non-idempotent (POST): a 429 means the rate limiter rejected the
        # request before it was processed, so sending it again is safe. Any
        # other status (notably 5xx) may mean the SMS was already accepted.
        return status_code == 429

    def increment(self, method=None, url=None, response=None, error=None,
                  _pool=None, _stacktrace=None):
        """Called by urllib3 after a failed attempt; raising here stops retrying."""
        if (error is not None
                and not self._is_idempotent(method)
                and not _is_connect_error(error)):
            # The request may have reached the server (read timeout, reset
            # while reading, TLS error mid-response, ...). Do not resend;
            # re-raise so the caller sees the original error.
            raise error.with_traceback(_stacktrace)
        return super().increment(method=method, url=url, response=response, error=error,
                                 _pool=_pool, _stacktrace=_stacktrace)

    # -- timing -------------------------------------------------------------

    def get_backoff_time(self) -> float:
        """``backoff_factor * 2 ** (n - 1)`` for the n-th consecutive retry,
        capped at ``backoff_max``. Unlike urllib3, the first retry waits too."""
        consecutive = 0
        for attempt in reversed(self.history):
            if attempt.redirect_location is not None:
                break
            consecutive += 1
        if consecutive == 0 or self.backoff_factor <= 0:
            return 0.0
        return float(min(self.backoff_max, self.backoff_factor * (2 ** (consecutive - 1))))

    def get_retry_after(self, response):
        """Seconds from the ``Retry-After`` header, capped at ``retry_after_max``.

        An unparseable header falls back to the exponential backoff instead of
        raising ``InvalidHeader`` as urllib3 would.
        """
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            seconds = float(self.parse_retry_after(value))
        except Exception:
            return None
        return min(max(seconds, 0.0), self.retry_after_max)


def build_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    backoff_max: float = DEFAULT_BACKOFF_MAX,
    retry_after_max: float = DEFAULT_RETRY_AFTER_MAX,
) -> SafeRetry:
    """Build the SDK's retry policy. ``max_retries=0`` disables all retries."""
    if max_retries is None or max_retries < 0:
        raise ValueError("max_retries must be an integer >= 0")
    if backoff_factor < 0:
        raise ValueError("backoff_factor must be >= 0")
    return SafeRetry(
        total=max_retries,
        backoff_factor=backoff_factor,
        backoff_max=backoff_max,
        retry_after_max=retry_after_max,
        status_forcelist=sorted(RETRY_STATUSES),
        allowed_methods=sorted(IDEMPOTENT_METHODS),
        respect_retry_after_header=True,
        # Hand the final 429/5xx response back so _handle_response can raise
        # the matching SDK exception instead of a generic retry error.
        raise_on_status=False,
    )


def _never_sent(exc: BaseException) -> bool:
    """True if a requests exception proves the request never reached the
    server (connect failure, DNS, refused, TLS certificate rejected)."""
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return True
    seen = set()
    stack = [exc]
    while stack:
        err = stack.pop()
        if err is None or id(err) in seen:
            continue
        seen.add(id(err))
        if _is_connect_error(err) or isinstance(err, ssl.SSLCertVerificationError):
            return True
        stack.extend(a for a in getattr(err, "args", ()) if isinstance(a, BaseException))
        stack.append(getattr(err, "reason", None))          # MaxRetryError
        stack.append(getattr(err, "original_error", None))  # ProxyError
        stack.append(err.__cause__)
        stack.append(err.__context__)
    return False


# requests errors that can happen after the request was (possibly) delivered.
_POSSIBLY_DELIVERED = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ContentDecodingError,
)


class PooledHTTPClient:
    """
    HTTP client with connection pooling, Basic Auth, and safe retry logic.
    Reuse a single instance across requests for best performance.
    """

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str = BASE_URL,
        timeout: int = 30,
        max_retries: int = DEFAULT_MAX_RETRIES,
        pool_connections: int = 10,
        pool_maxsize: int = 100,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        logger: Optional[logging.Logger] = None,
        backoff_max: float = DEFAULT_BACKOFF_MAX,
        retry_after_max: float = DEFAULT_RETRY_AFTER_MAX,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.logger = logger or logging.getLogger(__name__)

        self.retry = build_retry(
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            backoff_max=backoff_max,
            retry_after_max=retry_after_max,
        )

        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"nextsms-python-sdk/{SDK_VERSION}",
        })

        adapter = HTTPAdapter(
            max_retries=self.retry,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            pool_block=False,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.logger.debug(
            "NextSMS HTTP client ready — base_url=%s pool=%d/%d retries=%d backoff=%s",
            self.base_url, pool_connections, pool_maxsize, max_retries, backoff_factor,
        )

    def request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        kwargs.setdefault("timeout", self.timeout)
        self.logger.debug("%s %s", method, url)
        try:
            response = self.session.request(method, url, **kwargs)
            self.logger.debug("← %s", response.status_code)
            return response
        except requests.exceptions.RequestException as exc:
            idempotent = method.upper() in IDEMPOTENT_METHODS
            if not idempotent and isinstance(exc, _POSSIBLY_DELIVERED) and not _never_sent(exc):
                if isinstance(exc, requests.exceptions.Timeout):
                    what = "timed out waiting for the response"
                else:
                    what = "lost the connection"
                raise NextSMSAmbiguousResponseError(
                    f"{method.upper()} {endpoint} {what} after the request was sent "
                    f"({exc}). NextSMS may have processed it; it was NOT retried to "
                    "avoid a duplicate. Check delivery logs before resending."
                ) from exc
            if isinstance(exc, requests.exceptions.Timeout):
                raise NextSMSConnectionError(
                    f"Request timed out after {kwargs['timeout']}s"
                ) from exc
            if isinstance(exc, requests.exceptions.ConnectionError):
                raise NextSMSConnectionError(
                    f"Failed to connect to NextSMS API: {exc}"
                ) from exc
            raise NextSMSConnectionError(f"Request failed: {exc}") from exc

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
