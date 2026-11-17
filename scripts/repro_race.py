# scripts/repro_race.py
# Minimal reproduction: concurrent redirects on a single short link
import asyncio
import sys
import httpx

SHORT_CODE = "test01"
CONCURRENCY = 10
BASE_URL = f"http://127.0.0.1:3000/r/{SHORT_CODE}"


async def make_request(client: httpx.AsyncClient):
    try:
        resp = await client.get(BASE_URL, follow_redirects=False, timeout=10.0)
        return resp.status_code
    except Exception as exc:
        return exc


async def main():
    concurrency = int(sys.argv[1]) if len(sys.argv) > 1 else CONCURRENCY
    async with httpx.AsyncClient() as client:
        tasks = [make_request(client) for _ in range(concurrency)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = [r for r in results if isinstance(r, int) and r in (301, 302)]
    errors = [r for r in results if isinstance(r, int) and r == 500]
    exceptions = [r for r in results if isinstance(r, Exception)]

    print(f"Results: {len(successes)} redirects, {len(errors)} errors, {len(exceptions)} exceptions")

    if errors:
        print("BUG REPRODUCED: 500 errors under concurrent load")
        return 1
    else:
        print("No errors this run. Try again or increase CONCURRENCY.")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
