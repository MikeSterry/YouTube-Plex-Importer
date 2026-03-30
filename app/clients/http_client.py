"""Simple HTTP client wrapper."""

import requests


class HttpClient:
    """Small wrapper around requests for easier testing and reuse."""

    def __init__(self, timeout: int = 60) -> None:
        """Initialize the client with a default timeout."""
        self._timeout = timeout

    def get_bytes(self, url: str) -> bytes:
        """Download raw bytes from the given URL."""
        response = requests.get(url, timeout=self._timeout)
        response.raise_for_status()
        return response.content
