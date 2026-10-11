# -*- coding: utf-8 -*-
from fastapi.testclient import TestClient
from app_url_shortener.main import app

client = TestClient(app)


def test_api_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "azure-url-shortener"
    assert "uptime_seconds" in data
    assert "storage_backend" in data


def test_api_health_detailed():
    response = client.get("/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "total_links" in data
    assert "total_clicks" in data


def test_api_shorten_and_redirect():
    # 1. Rút gọn URL
    payload = {"url": "https://docs.microsoft.com/azure"}
    res = client.post("/api/shorten", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    short_code = data["short_code"]
    assert len(short_code) == 6

    # 2. Truy cập short_code để redirect
    redirect_res = client.get(f"/{short_code}", follow_redirects=False)
    assert redirect_res.status_code == 307
    assert redirect_res.headers["location"] == "https://docs.microsoft.com/azure"


def test_api_stats():
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_links" in data
    assert "total_clicks" in data
    assert isinstance(data["links"], list)


def test_api_not_found():
    res = client.get("/non_existent_code_999", follow_redirects=False)
    assert res.status_code == 404


def test_api_metrics():
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    text = res.text
    assert "urlshortener_uptime_seconds" in text
    assert "urlshortener_http_requests_total" in text
    assert "urlshortener_total_links" in text
    assert "urlshortener_total_clicks" in text
