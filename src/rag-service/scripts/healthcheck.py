#!/usr/bin/env python3
"""Health check script for Docker container."""

import sys
import urllib.request
import urllib.error


def check_health() -> bool:
    """Check if the service is healthy."""
    try:
        url = "http://localhost:8000/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return True
    except urllib.error.URLError:
        pass
    except Exception:
        pass
    return False


if __name__ == "__main__":
    if check_health():
        sys.exit(0)
    else:
        sys.exit(1)
