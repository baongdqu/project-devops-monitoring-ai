# -*- coding: utf-8 -*-
"""
Business Logic Layer cho URL Shortener Service.
Chuyên trách chuẩn hóa URL, thuật toán sinh mã ngẫu nhiên Base62 và các quy tắc nghiệp vụ.
"""

import string
import random
from typing import Optional, Dict, Any, List
try:
    from .storage import BaseLinkStorage
except (ImportError, ValueError):
    from storage import BaseLinkStorage

class URLShortenerService:
    """Service xử lý toàn bộ nghiệp vụ rút gọn và phân tích lượt click."""

    def __init__(self, storage: BaseLinkStorage, code_length: int = 6):
        self.storage = storage
        self.code_length = code_length
        self.chars = string.ascii_letters + string.digits

    def _generate_code(self) -> str:
        return "".join(random.choice(self.chars) for _ in range(self.code_length))

    def _normalize_url(self, url: str) -> str:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return "https://" + url
        return url

    def shorten_url(self, raw_url: str, base_url: str) -> Dict[str, Any]:
        """Chuẩn hóa URL và tạo hoặc lấy mã rút gọn có sẵn."""
        original_url = self._normalize_url(raw_url)

        # Kiểm tra xem URL này đã có trong database chưa (idempotent)
        existing = self.storage.get_by_url(original_url)
        if existing:
            short_code = existing["short_code"]
        else:
            # Sinh mã ngẫu nhiên và lưu vào storage (thử lại nếu trùng)
            while True:
                short_code = self._generate_code()
                if self.storage.save_link(short_code, original_url):
                    break

        base_url = base_url.rstrip("/")
        return {
            "success": True,
            "short_code": short_code,
            "short_url": f"{base_url}/{short_code}",
            "original_url": original_url
        }

    def resolve_and_record_click(self, short_code: str) -> Optional[str]:
        """Tìm URL gốc và tăng số lượt click."""
        link_info = self.storage.get_by_code(short_code)
        if not link_info:
            return None

        # Tăng lượt click trong storage
        self.storage.increment_click(short_code)
        return link_info["original_url"]

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Lấy số liệu thống kê danh sách link và tổng lượt click."""
        summary = self.storage.get_analytics_summary()
        recent_links = self.storage.list_recent_links(limit=50)

        return {
            "total_links": summary["total_links"],
            "total_clicks": summary["total_clicks"],
            "links": recent_links
        }

    def get_health_metrics(self, uptime_seconds: int) -> Dict[str, Any]:
        """Lấy thông số phục vụ Health Check & Observability."""
        summary = self.storage.get_analytics_summary()
        return {
            "status": "healthy",
            "service": "azure-url-shortener",
            "uptime_seconds": uptime_seconds,
            "total_links": summary["total_links"],
            "total_clicks": summary["total_clicks"]
        }
