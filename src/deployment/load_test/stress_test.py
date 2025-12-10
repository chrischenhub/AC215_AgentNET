#!/usr/bin/env python3
"""
Simple HTTP stress tester.

Examples:
python stress_test.py --url http://34.16.91.173.sslip.io/api/search --concurrency 50 --duration 120
python stress_test.py --url http://localhost:8000/api/search --method POST --body '{"query": "test"}'
"""
import argparse
import asyncio
import json
import signal
import sys
import time
from collections import Counter
from typing import Any, Dict, List

try:
    import aiohttp
except ImportError:
    sys.stderr.write("aiohttp is required. Install with: pip install aiohttp\n")
    sys.exit(1)


async def _worker(
    name: int,
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    payload: Any,
    headers: Dict[str, str],
    deadline: float,
    results: Dict[str, Any],
    lock: asyncio.Lock,
) -> None:
    while time.time() < deadline:
        started = time.perf_counter()
        try:
            async with session.request(method, url, json=payload, headers=headers) as resp:
                await resp.read()  # consume body
                status = resp.status
                ok = 200 <= status < 400
        except Exception:
            status = "error"
            ok = False

        elapsed_ms = (time.perf_counter() - started) * 1000
        async with lock:
            results["total"] += 1
            results["latencies"].append(elapsed_ms)
            results["status_counts"][status] += 1
            if ok:
                results["success"] += 1
            else:
                results["errors"] += 1


def _percentile(data: List[float], pct: float) -> float:
    if not data:
        return 0.0
    data = sorted(data)
    k = (len(data) - 1) * pct
    f = int(k)
    c = min(f + 1, len(data) - 1)
    if f == c:
        return data[int(k)]
    d0 = data[f] * (c - k)
    d1 = data[c] * (k - f)
    return d0 + d1


async def main() -> None:
    parser = argparse.ArgumentParser(description="Simple HTTP Stress Test")
    parser.add_argument("--url", required=True, help="Target URL (e.g., http://host/api/)")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent requests")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")
    parser.add_argument("--method", choices=["GET", "POST"], default="GET", help="HTTP method")
    parser.add_argument("--body", help="JSON string for POST body")
    parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout seconds")
    args = parser.parse_args()

    payload = None
    headers: Dict[str, str] = {}
    if args.method == "POST":
        if args.body:
            payload = json.loads(args.body)
        headers["Content-Type"] = "application/json"

    deadline = time.time() + args.duration
    results: Dict[str, Any] = {
        "total": 0,
        "success": 0,
        "errors": 0,
        "latencies": [],
        "status_counts": Counter(),
    }
    lock = asyncio.Lock()

    stop = asyncio.Event()

    def _handle_sigint(*_):
        stop.set()

    signal.signal(signal.SIGINT, _handle_sigint)

    timeout = aiohttp.ClientTimeout(total=args.timeout)
    connector = aiohttp.TCPConnector(limit=args.concurrency)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [
            asyncio.create_task(
                _worker(
                    i,
                    session,
                    args.method,
                    args.url,
                    payload,
                    headers,
                    deadline,
                    results,
                    lock,
                )
            )
            for i in range(args.concurrency)
        ]
        await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Wait until deadline or stop event
        while time.time() < deadline and not stop.is_set():
            await asyncio.sleep(0.1)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    duration_used = max(1e-9, args.duration)
    latencies = results["latencies"]
    print("=== Stress Test Summary ===")
    print(f"Target:       {args.url}")
    print(f"Method:       {args.method}")
    print(f"Concurrency:  {args.concurrency}")
    print(f"Duration:     {args.duration}s")
    print(f"Total reqs:   {results['total']}")
    print(f"Success:      {results['success']}")
    print(f"Errors:       {results['errors']}")
    print("Status codes:", dict(results["status_counts"]))
    if latencies:
        print(f"Avg latency:  {sum(latencies)/len(latencies):.2f} ms")
        print(f"P50 latency:  {_percentile(latencies, 0.50):.2f} ms")
        print(f"P95 latency:  {_percentile(latencies, 0.95):.2f} ms")
        print(f"P99 latency:  {_percentile(latencies, 0.99):.2f} ms")
        print(f"Throughput:   {results['total']/duration_used:.2f} req/s")


if __name__ == "__main__":
    asyncio.run(main())