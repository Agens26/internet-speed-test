#!/usr/bin/env python3
"""Measure average HTTP download speed over ten sequential requests."""

import argparse
import time
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

REQUEST_COUNT = 10
CHUNK_SIZE = 64 * 1024
TIMEOUT_SECONDS = 30


def download_once(url: str) -> tuple[int, float]:
    """Return downloaded body bytes and elapsed seconds for one request."""
    request = Request(url, headers={"Accept-Encoding": "identity"})
    started = time.perf_counter()
    downloaded = 0

    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        while chunk := response.read(CHUNK_SIZE):
            downloaded += len(chunk)

    return downloaded, time.perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure download speed using 10 sequential HTTP requests."
    )
    parser.add_argument("url", help="Full URL of a file or page (http:// or https://)")
    args = parser.parse_args()

    parsed = urlparse(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        parser.error("provide a full HTTP or HTTPS URL")

    total_bytes = 0
    total_seconds = 0.0

    try:
        for number in range(1, REQUEST_COUNT + 1):
            size, elapsed = download_once(args.url)
            total_bytes += size
            total_seconds += elapsed
            print(f"Request {number:2}/{REQUEST_COUNT}: {size:,} bytes, {elapsed:.3f} s")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, HTTPException) as exc:
        print(f"Error on request {number}: {exc}")
        return 1

    if total_seconds <= 0:
        print("Could not measure request duration.")
        return 1

    average_seconds = total_seconds / REQUEST_COUNT
    speed_mbps = total_bytes * 8 / total_seconds / 1_000_000
    print(f"\nAverage request time: {average_seconds:.3f} s")
    print(f"Total downloaded: {total_bytes:,} bytes")
    print(f"Average download speed: {speed_mbps:.2f} Mbit/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
