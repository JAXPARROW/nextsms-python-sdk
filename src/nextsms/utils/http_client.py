"""
HTTP client with connection pooling and retry logic for NextSMS API.
"""

import logging
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..exceptions import NextSMSConnectionError

logger = logging.getLogger(__name__)

BASE_URL = "https://messaging-service.co.tz"
TEST_BASE_URL = "https://messaging-service.co.tz/test"
SDK_VERSION = "0.1.0"


class PooledHTTPClient:
    """
    HTTP client with connection pooling, Basic Auth, and retry logic.
    Reuse a single instance across requests for best performance.
    """

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str = BASE_URL,
        timeout: int = 30,
        max_retries: int = 3,
        pool_connections: int = 10,
        pool_maxsize: int = 100,
        backoff_factor: float = 0.5,
        logger: Optional[logging.Logger] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.logger = logger or logging.getLogger(__name__)

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
            raise_on_status=False,
        )

        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"nextsms-python-sdk/{SDK_VERSION}",
        })

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            pool_block=False,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.logger.debug(
            "NextSMS HTTP client ready — base_url=%s pool=%d/%d",
            self.base_url, pool_connections, pool_maxsize,
        )

    def request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        kwargs.setdefault("timeout", self.timeout)
        self.logger.debug("%s %s", method, url)
        try:
            response = self.session.request(method, url, **kwargs)
            self.logger.debug("← %s", response.status_code)
            return response
        except requests.exceptions.Timeout:
            raise NextSMSConnectionError(f"Request timed out after {self.timeout}s")
        except requests.exceptions.ConnectionError as exc:
            raise NextSMSConnectionError(f"Failed to connect to NextSMS API: {exc}")
        except requests.exceptions.RequestException as exc:
            raise NextSMSConnectionError(f"Request failed: {exc}")

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
