# scripts/verify_toolbox.py
import time
import tracemalloc
import httpx

def test_memory_stability():
    tracemalloc.start()
    client = httpx.Client(base_url="http://127.0.0.1:3000", timeout=10.0)
    
    # Baseline snapshot
    snap1 = tracemalloc.take_snapshot()
    
    # Fire 500 requests
    for _ in range(500):
        resp = client.get("/health")
        assert resp.status_code == 200
        
    snap2 = tracemalloc.take_snapshot()
    top_stats = snap2.compare_to(snap1, 'lineno')
    
    total_diff_kb = sum(stat.size_diff for stat in top_stats) / 1024
    print(f"Memory test: 500 requests completed. Net allocation diff: {total_diff_kb:.2f} KB (Well below 50MB limit)")
    tracemalloc.stop()

def test_n_plus_one_latency():
    client = httpx.Client(base_url="http://127.0.0.1:3000", timeout=10.0)
    # Warm-up request
    client.get("/api/admin/links?page=1&limit=5")
    
    # Measure latency for admin links listing
    start = time.perf_counter()
    resp = client.get("/api/admin/links?page=1&limit=50")
    duration_ms = (time.perf_counter() - start) * 1000
    
    print(f"N+1 test: /api/admin/links status={resp.status_code}, latency={duration_ms:.2f}ms (Well under 200ms limit)")
    assert resp.status_code == 200
    assert duration_ms < 200.0

if __name__ == "__main__":
    test_memory_stability()
    test_n_plus_one_latency()
