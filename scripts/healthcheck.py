"""Container health check script."""

import sys
import urllib.request


def main() -> int:
    """Return zero when the app health endpoint responds successfully."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:5000/health", timeout=5) as response:
            return 0 if response.status == 200 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
