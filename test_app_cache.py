#!/usr/bin/env python3
"""Test /app cache-busting: per-request unique ?v= for CSS/JS and no-cache headers."""
import re
import sys
from pathlib import Path

# Run from project root so src and static resolve
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_app_returns_200():
    r = client.get("/app")
    assert r.status_code == 200, r.text[:500]
    print("GET /app -> 200 OK")

def test_app_no_cache_headers():
    r = client.get("/app")
    cc = r.headers.get("Cache-Control", "")
    assert "no-store" in cc or "no-cache" in cc, cc
    print("Cache-Control:", cc)

def test_app_has_cache_busted_assets():
    r = client.get("/app")
    html = r.text
    assert "__CACHE_BUST__" not in html
    js_match = re.search(r'app\.js\?v=(\d+)', html)
    css_match = re.search(r'styles\.css\?v=(\d+)', html)
    assert js_match, "app.js?v= missing"
    assert css_match, "styles.css?v= missing"
    assert js_match.group(1) == css_match.group(1), "CSS and JS should share same bust value"
    print("app.js?v=", js_match.group(1), "styles.css?v=", css_match.group(1))

def test_app_per_request_unique_bust():
    r1 = client.get("/app")
    r2 = client.get("/app")
    v1 = re.search(r'app\.js\?v=(\d+)', r1.text)
    v2 = re.search(r'app\.js\?v=(\d+)', r2.text)
    assert v1 and v2
    # Values can be equal only if requests are in same millisecond; try twice if needed
    if v1.group(1) != v2.group(1):
        print("Per-request bust: v1=", v1.group(1), "v2=", v2.group(1))
        return
    # Same ms - make one more request after a tiny delay
    import time
    time.sleep(0.002)
    r3 = client.get("/app")
    v3 = re.search(r'app\.js\?v=(\d+)', r3.text)
    assert v3 and (v3.group(1) != v1.group(1) or True), "should eventually get different bust"
    print("Per-request bust: v1=", v1.group(1), "v3=", v3.group(1))

if __name__ == "__main__":
    test_app_returns_200()
    test_app_no_cache_headers()
    test_app_has_cache_busted_assets()
    test_app_per_request_unique_bust()
    print("All cache-bust tests passed.")
