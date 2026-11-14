#!/usr/bin/env python3
"""Measure average HTTP download speed over ten sequential requests."""

# These are standard-library modules, so the script needs no extra packages.
# argparse reads the command-line URL; time measures request duration.
import argparse
import time
# urllib creates and sends requests, while these exceptions cover HTTP errors.
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# Make ten requests, reading responses in 64 KiB chunks with a 30-second
# timeout for blocking network operations. Chunks avoid storing the whole file.
REQUEST_COUNT = 10
CHUNK_SIZE = 64 * 1024
TIMEOUT_SECONDS = 30


def download_once(url: str) -> tuple[int, float]:
    """Return downloaded body bytes and elapsed seconds for one request."""
    # Ask the server for an uncompressed response. The server may ignore this.
    request = Request(url, headers={"Accept-Encoding": "identity"})
    # A monotonic, high-resolution timer measures elapsed time, including the
    # wait for the server and the time needed to read the whole response.
    started = time.perf_counter()
    downloaded = 0

    # Read until an empty chunk indicates the response is complete. The with
    # block closes the response even if an error occurs.
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        while chunk := response.read(CHUNK_SIZE):
            downloaded += len(chunk)

    # Return the response-body size and elapsed seconds to the caller.
    return downloaded, time.perf_counter() - started


def main() -> int:
    # Require a URL as a positional command-line argument.
    parser = argparse.ArgumentParser(
        description="Measure download speed using 10 sequential HTTP requests."
    )
    parser.add_argument("url", help="Full URL of a file or page (http:// or https://)")
    args = parser.parse_args()

    # Reject URLs without an HTTP(S) scheme or host before making requests.
    parsed = urlparse(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        parser.error("provide a full HTTP or HTTPS URL")

    # Keep totals across all completed downloads.
    total_bytes = 0
    total_seconds = 0.0

    # Each download finishes before the next one begins: there is no parallelism.
    try:
        for number in range(1, REQUEST_COUNT + 1):
            size, elapsed = download_once(args.url)
            total_bytes += size
            total_seconds += elapsed
            print(f"Request {number:2}/{REQUEST_COUNT}: {size:,} bytes, {elapsed:.3f} s")
    # Report a failure and stop instead of treating fewer than ten successful
    # requests as a completed measurement.
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, HTTPException) as exc:
        print(f"Error on request {number}: {exc}")
        return 1

    # Guard against division by zero if the timer reports no elapsed time.
    if total_seconds <= 0:
        print("Could not measure request duration.")
        return 1

    # Mean request time is total elapsed time divided by ten. For throughput,
    # multiply bytes by 8 to get bits, divide by seconds, then by one million
    # to express the result in decimal megabits per second (Mbit/s).
    average_seconds = total_seconds / REQUEST_COUNT
    speed_mbps = total_bytes * 8 / total_seconds / 1_000_000
    print(f"\nAverage request time: {average_seconds:.3f} s")
    print(f"Total downloaded: {total_bytes:,} bytes")
    print(f"Average download speed: {speed_mbps:.2f} Mbit/s")
    return 0


# Run main only when this file is executed directly. Its return value becomes
# the process exit code: zero for success, nonzero for an error.
if __name__ == "__main__":
    raise SystemExit(main())
