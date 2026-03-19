#!/usr/bin/env python3
"""
Performance testing script for optimized endpoints.
Tests both cache miss and cache hit scenarios.
"""
import time
import requests
import sys

BASE_URL = "http://localhost:8080"

def test_endpoint(name, url, iterations=3):
    """Test an endpoint multiple times to measure cache performance."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")

    times = []
    for i in range(iterations):
        start = time.time()
        try:
            response = requests.get(url, timeout=30)
            elapsed = time.time() - start
            times.append(elapsed)

            status = "✅" if response.status_code == 200 else "❌"
            cache_status = "CACHE HIT" if i > 0 and elapsed < 0.2 else "CACHE MISS"

            print(f"  Request {i+1}: {status} {elapsed:.3f}s ({cache_status})")

            if response.status_code != 200:
                print(f"    Error: {response.status_code} - {response.text[:100]}")
        except Exception as e:
            print(f"  Request {i+1}: ❌ Error - {e}")
            times.append(None)

    # Calculate improvements
    valid_times = [t for t in times if t is not None]
    if len(valid_times) >= 2:
        first = valid_times[0]
        subsequent = sum(valid_times[1:]) / len(valid_times[1:])
        improvement = (first / subsequent) if subsequent > 0 else 0

        print(f"\n  📊 Results:")
        print(f"     First request (cache miss): {first:.3f}s")
        print(f"     Avg subsequent (cache hit):  {subsequent:.3f}s")
        print(f"     Improvement: {improvement:.1f}x faster")

        return first, subsequent

    return None, None

def main():
    print("🚀 Performance Testing Suite")
    print("=" * 60)

    # Wait for server to be ready
    print("\nWaiting for server to be ready...")
    for _ in range(10):
        try:
            requests.get(f"{BASE_URL}/health", timeout=2)
            print("✅ Server is ready!")
            break
        except:
            time.sleep(1)
    else:
        print("❌ Server not responding. Please start the server first:")
        print("   python -m src.main")
        sys.exit(1)

    # Test Hot Papers endpoint
    hot_miss, hot_hit = test_endpoint(
        "Hot Papers (/api/analytics/hot-papers)",
        f"{BASE_URL}/api/analytics/hot-papers?limit=10",
        iterations=3
    )

    # Test Recommendations endpoint
    rec_miss, rec_hit = test_endpoint(
        "Recommendations (/api/users/1/recommendations)",
        f"{BASE_URL}/api/users/1/recommendations?limit=10",
        iterations=3
    )

    # Summary
    print("\n" + "="*60)
    print("📈 PERFORMANCE SUMMARY")
    print("="*60)

    if hot_miss and hot_hit:
        print(f"\nHot Papers:")
        print(f"  Cache Miss: {hot_miss:.3f}s → Cache Hit: {hot_hit:.3f}s")
        print(f"  ✅ Success: {hot_hit < 0.2 and hot_miss < 1.0}")

    if rec_miss and rec_hit:
        print(f"\nRecommendations:")
        print(f"  Cache Miss: {rec_miss:.3f}s → Cache Hit: {rec_hit:.3f}s")
        print(f"  ✅ Success: {rec_hit < 0.5 and rec_miss < 10.0}")

    print("\n" + "="*60)

if __name__ == "__main__":
    main()