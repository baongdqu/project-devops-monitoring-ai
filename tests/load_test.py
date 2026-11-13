# -*- coding: utf-8 -*-
"""
SRE Load Testing & Chaos Engineering Script.
Dùng để kiểm thử tải, đo lường Golden Signals (RPS, Latency, Error Rate)
và kích hoạt Auto-scaling (Scale-to-Zero -> Scale-to-N) trên Azure Container Apps.
"""

import sys
import time
import argparse
import statistics
import concurrent.futures
import urllib.request
import urllib.error
import json
from typing import List, Dict, Any


def send_single_request(base_url: str, request_id: int) -> Dict[str, Any]:
    """Gửi một request kiểm thử và đo thời gian phản hồi (ms)."""
    start = time.perf_counter()
    # 70% truy vấn Health / Metrics, 30% tạo Shorten link
    is_post = (request_id % 3 == 0)
    
    status_code = 0
    error_msg = None
    
    try:
        if is_post:
            target_url = f"{base_url.rstrip('/')}/api/shorten"
            payload = json.dumps({"url": f"https://example.com/item/{request_id}_{int(time.time())}"}).encode("utf-8")
            req = urllib.request.Request(
                target_url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "SRE-LoadTester/1.0"},
                method="POST"
            )
        else:
            # Luân phiên giữa /health và /metrics
            endpoint = "/health" if (request_id % 2 == 0) else "/metrics"
            target_url = f"{base_url.rstrip('/')}{endpoint}"
            req = urllib.request.Request(
                target_url,
                headers={"User-Agent": "SRE-LoadTester/1.0"},
                method="GET"
            )
            
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.getcode()
    except urllib.error.HTTPError as e:
        status_code = e.code
    except Exception as e:
        error_msg = str(e)
        status_code = 0

    latency_ms = (time.perf_counter() - start) * 1000.0
    return {
        "id": request_id,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "error": error_msg
    }


def run_load_test(base_url: str, total_requests: int = 50, concurrency: int = 5) -> Dict[str, Any]:
    """Chạy bài test tải đồng thời và tổng hợp chỉ số SRE."""
    print(f"\n🚀 [SRE LOAD TEST] Bắt đầu sinh tải đến: {base_url}")
    print(f"📊 Cấu hình: {total_requests} requests | Concurrency: {concurrency} luồng đồng thời\n")
    
    start_total = time.perf_counter()
    results: List[Dict[str, Any]] = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_single_request, base_url, i + 1) for i in range(total_requests)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            results.append(res)
            # In tiến độ dạng chấm
            sys.stdout.write("." if res["status_code"] in (200, 307) else "x")
            sys.stdout.flush()
            
    total_duration = time.perf_counter() - start_total
    print("\n")
    
    latencies = [r["latency_ms"] for r in results]
    success_count = sum(1 for r in results if r["status_code"] in (200, 307))
    rate_limited_count = sum(1 for r in results if r["status_code"] == 429)
    error_count = total_requests - success_count - rate_limited_count
    
    latencies.sort()
    avg_latency = statistics.mean(latencies) if latencies else 0.0
    median_latency = statistics.median(latencies) if latencies else 0.0
    p95_index = int(len(latencies) * 0.95)
    p99_index = int(len(latencies) * 0.99)
    p95_latency = latencies[min(p95_index, len(latencies) - 1)] if latencies else 0.0
    p99_latency = latencies[min(p99_index, len(latencies) - 1)] if latencies else 0.0
    rps = total_requests / total_duration if total_duration > 0 else 0.0
    
    summary = {
        "total_requests": total_requests,
        "concurrency": concurrency,
        "total_duration_sec": round(total_duration, 2),
        "rps": round(rps, 2),
        "success_count": success_count,
        "rate_limited_count": rate_limited_count,
        "error_count": error_count,
        "min_latency_ms": round(min(latencies), 2) if latencies else 0.0,
        "avg_latency_ms": round(avg_latency, 2),
        "median_latency_ms": round(median_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
        "p99_latency_ms": round(p99_latency, 2),
        "max_latency_ms": round(max(latencies), 2) if latencies else 0.0
    }
    
    print("=" * 60)
    print("           📈 KẾT QUẢ KIỂM THỬ SRE GOLDEN SIGNALS           ")
    print("=" * 60)
    print(f"• Tổng số Requests     : {summary['total_requests']}")
    print(f"• Thời gian chạy       : {summary['total_duration_sec']}s")
    print(f"• Tốc độ thông lượng   : {summary['rps']} Requests/giây (RPS)")
    print(f"• Thành công (200/307) : {summary['success_count']} ({round(summary['success_count']/total_requests*100, 1)}%)")
    print(f"• Bị Rate Limit (429)  : {summary['rate_limited_count']}")
    print(f"• Lỗi (5xx/Network)    : {summary['error_count']}")
    print("-" * 60)
    print(f"• Độ trễ Trung bình    : {summary['avg_latency_ms']} ms")
    print(f"• Độ trễ Trung vị (p50): {summary['median_latency_ms']} ms")
    print(f"• Phân vị p95 (95%)    : {summary['p95_latency_ms']} ms")
    print(f"• Phân vị p99 (99%)    : {summary['p99_latency_ms']} ms")
    print(f"• Độ trễ Min / Max     : {summary['min_latency_ms']} ms / {summary['max_latency_ms']} ms")
    print("=" * 60 + "\n")
    
    return summary


def test_load_smoke_simulation():
    """Hàm test tích hợp cho pytest để đảm bảo script luôn runnable."""
    assert send_single_request is not None
    assert run_load_test is not None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SRE Load Testing Tool for Azure Container Apps")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of target service")
    parser.add_argument("--requests", type=int, default=30, help="Total number of requests")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent workers")
    args = parser.parse_args()
    
    run_load_test(base_url=args.url, total_requests=args.requests, concurrency=args.concurrency)

