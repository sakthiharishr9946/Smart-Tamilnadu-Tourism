"""Shared HTTP client for every scraper.

Centralises the behaviour each source needs to be collected reliably and
politely:

* retries with exponential backoff on connection errors, 429 and 5xx,
  honouring ``Retry-After``;
* a per-host minimum interval between requests (thread safe), so parallel
  collection never hammers one server;
* certificate verification against the operating-system trust store when
  ``truststore`` is installed. Several Tamil Nadu government sites serve an
  incomplete certificate chain that certifi alone rejects, while the OS store
  completes it - verification stays on;
* one identifying User-Agent for the project.
"""

import logging
import ssl
import threading
import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

USER_AGENT = (
    "SmartTamilnaduTourism/5.0 (tourism data collection; "
    "https://github.com/smart-tamilnadu-tourism)"
)
DEFAULT_TIMEOUT = (10, 60)  # (connect, read) seconds
RETRY_STATUSES = (429, 500, 502, 503, 504)


class SourceUnavailable(Exception):
    """Raised when a source's entry point cannot be fetched or parsed at all."""


def _ssl_context():
    try:
        import truststore
    except ImportError:
        return None

    base = truststore.SSLContext

    class _SharedTrustStoreContext(base):
        """truststore context that reports the checks it actually enforces.

        During each handshake truststore sets the wrapped context to
        CERT_NONE/check_hostname=False and afterwards verifies the chain and
        hostname itself against the OS store. Another thread reading those
        attributes mid-handshake on this shared context would see the
        temporary values: urllib3 then wrongly warns "unverified request" or
        attempts its own hostname match on an empty certificate.
        """

        _enforced_mode = ssl.CERT_REQUIRED
        _enforced_check_hostname = True

        @property
        def verify_mode(self):
            return self._enforced_mode

        @verify_mode.setter
        def verify_mode(self, value):
            base.verify_mode.fset(self, value)
            self._enforced_mode = value

        @property
        def check_hostname(self):
            return self._enforced_check_hostname

        @check_hostname.setter
        def check_hostname(self, value):
            base.check_hostname.fset(self, value)
            self._enforced_check_hostname = value

    return _SharedTrustStoreContext(ssl.PROTOCOL_TLS_CLIENT)


class _TrustStoreAdapter(HTTPAdapter):
    def __init__(self, *args, ssl_context=None, **kwargs):
        self._ssl_context = ssl_context
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        if self._ssl_context is not None:
            kwargs["ssl_context"] = self._ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        if self._ssl_context is not None:
            kwargs["ssl_context"] = self._ssl_context
        return super().proxy_manager_for(*args, **kwargs)


class HttpClient:
    """A requests session with retries and per-host throttling."""

    def __init__(self, min_interval=0.5, retries=3, backoff=1.5,
                 timeout=DEFAULT_TIMEOUT, host_intervals=None, user_agent=USER_AGENT):
        self.timeout = timeout
        self.min_interval = float(min_interval)
        self.host_intervals = dict(host_intervals or {})
        self._last_request = {}
        self._host_locks = {}
        self._lock = threading.Lock()

        retry = Retry(
            total=retries, connect=retries, read=retries, status=retries,
            backoff_factor=backoff, status_forcelist=RETRY_STATUSES,
            allowed_methods=frozenset({"GET", "POST", "HEAD"}),
            respect_retry_after_header=True, raise_on_status=False,
        )
        adapter = _TrustStoreAdapter(max_retries=retry, pool_maxsize=16, ssl_context=_ssl_context())
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({"User-Agent": user_agent, "Accept-Language": "en"})

    def _throttle(self, url):
        host = urlparse(url).netloc.lower()
        interval = self.host_intervals.get(host, self.min_interval)
        with self._lock:
            host_lock = self._host_locks.setdefault(host, threading.Lock())
        with host_lock:
            wait = self._last_request.get(host, 0.0) + interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request[host] = time.monotonic()

    def request(self, method, url, **kwargs):
        """Perform a request; raise ``requests.RequestException`` on failure."""
        kwargs.setdefault("timeout", self.timeout)
        self._throttle(url)
        started = time.monotonic()
        response = self.session.request(method, url, **kwargs)
        logger.debug("%s %s -> %s in %.1fs", method, url, response.status_code, time.monotonic() - started)
        response.raise_for_status()
        return response

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def get_text(self, url, **kwargs):
        response = self.get(url, **kwargs)
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    def try_get_text(self, url, **kwargs):
        """Like ``get_text`` but return None (and log) instead of raising."""
        try:
            return self.get_text(url, **kwargs)
        except requests.RequestException as error:
            logger.info("Could not fetch %s: %s", url, _short_error(error))
            return None


def _short_error(error):
    text = str(error)
    return text if len(text) <= 160 else text[:157] + "..."


def short_error(error):
    return f"{type(error).__name__}: {_short_error(error)}"
