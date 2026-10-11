# -*- coding: utf-8 -*-
import pytest
from app_url_shortener.storage import SQLiteLinkStorage
from app_url_shortener.service import URLShortenerService


@pytest.fixture
def memory_storage():
    """Tạo storage SQLite in-memory dùng riêng cho mỗi test case."""
    return SQLiteLinkStorage(db_path=":memory:")


@pytest.fixture
def url_service(memory_storage):
    """Khởi tạo service với in-memory storage."""
    return URLShortenerService(storage=memory_storage, code_length=6)


def test_sqlite_storage_crud(memory_storage):
    # 1. Lưu link mới
    saved = memory_storage.save_link("abc123", "https://example.com/long-url")
    assert saved is True

    # Lưu trùng mã code sẽ trả về False
    duplicate = memory_storage.save_link("abc123", "https://other.com")
    assert duplicate is False

    # 2. Lấy link theo mã
    item = memory_storage.get_by_code("abc123")
    assert item is not None
    assert item["short_code"] == "abc123"
    assert item["original_url"] == "https://example.com/long-url"
    assert item["clicks"] == 0

    # 3. Lấy link theo URL gốc
    item_by_url = memory_storage.get_by_url("https://example.com/long-url")
    assert item_by_url is not None
    assert item_by_url["short_code"] == "abc123"

    # 4. Tăng số lượt click
    inc_ok = memory_storage.increment_click("abc123")
    assert inc_ok is True
    updated = memory_storage.get_by_code("abc123")
    assert updated["clicks"] == 1

    # 5. Thống kê analytics
    summary = memory_storage.get_analytics_summary()
    assert summary["total_links"] == 1
    assert summary["total_clicks"] == 1


def test_service_normalize_url(url_service):
    assert url_service._normalize_url("example.com") == "https://example.com"
    assert url_service._normalize_url("  http://my-site.org  ") == "http://my-site.org"
    assert url_service._normalize_url("https://secure.net/page") == "https://secure.net/page"


def test_service_shorten_url_idempotent(url_service):
    base_url = "https://short.ly"
    res1 = url_service.shorten_url("github.com/microsoft", base_url)
    assert res1["success"] is True
    assert len(res1["short_code"]) == 6
    assert res1["short_url"] == f"{base_url}/{res1['short_code']}"
    assert res1["original_url"] == "https://github.com/microsoft"

    # Gọi lại cùng URL phải trả về cùng short_code (Idempotent)
    res2 = url_service.shorten_url("github.com/microsoft", base_url)
    assert res2["short_code"] == res1["short_code"]
    assert res2["short_url"] == res1["short_url"]


def test_service_resolve_and_record_click(url_service):
    base_url = "https://short.ly"
    created = url_service.shorten_url("https://azure.microsoft.com", base_url)
    code = created["short_code"]

    # Click lần 1
    target = url_service.resolve_and_record_click(code)
    assert target == "https://azure.microsoft.com"

    # Click lần 2
    target2 = url_service.resolve_and_record_click(code)
    assert target2 == "https://azure.microsoft.com"

    stats = url_service.get_dashboard_stats()
    assert stats["total_links"] == 1
    assert stats["total_clicks"] == 2


def test_service_resolve_non_existent(url_service):
    result = url_service.resolve_and_record_click("nonexist")
    assert result is None


def test_service_health_metrics(url_service):
    url_service.shorten_url("https://google.com", "https://sho.rt")
    metrics = url_service.get_health_metrics(uptime_seconds=120)
    assert metrics["status"] == "healthy"
    assert metrics["service"] == "azure-url-shortener"
    assert metrics["uptime_seconds"] == 120
    assert metrics["total_links"] == 1
    assert metrics["total_clicks"] == 0
