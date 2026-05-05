"""Ping backend and frontend to verify both services are up."""

import argparse
import sys

import httpx

API_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:8501"


def ping_api() -> bool:
    try:
        r = httpx.get(f"{API_URL}/health", timeout=5)
        data = r.json()
        status = data.get("status", "unknown")
        ok = status == "ok"
        icon = "✓" if ok else "✗"
        print(f"{icon} API        {API_URL}/health  →  {status}")
        for key, val in data.items():
            if key in ("status", "service"):
                continue
            sub_icon = "✓" if val == "ok" else "✗"
            print(f"  {sub_icon} {key}: {val}")
        return ok
    except Exception as e:
        print(f"✗ API        {API_URL}/health  →  unreachable ({e})")
        return False


def ping_frontend() -> bool:
    try:
        r = httpx.get(FRONTEND_URL, timeout=5)
        ok = r.status_code == 200
        icon = "✓" if ok else "✗"
        print(f"{icon} Frontend   {FRONTEND_URL}  →  HTTP {r.status_code}")
        return ok
    except Exception as e:
        print(f"✗ Frontend   {FRONTEND_URL}  →  unreachable ({e})")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--api-only", action="store_true")
    group.add_argument("--frontend-only", action="store_true")
    args = parser.parse_args()

    results = []
    if not args.frontend_only:
        results.append(ping_api())
    if not args.api_only:
        results.append(ping_frontend())

    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
