# -*- coding: utf-8 -*-
"""
Storage Layer cho URL Shortener Service.
Triển khai theo Repository Pattern để tách biệt hoàn toàn cơ chế lưu trữ với logic nghiệp vụ.
"""

import sqlite3
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class BaseLinkStorage(ABC):
    """Giao diện trừu tượng (Interface) cho tầng lưu trữ liên kết."""

    @abstractmethod
    def save_link(self, short_code: str, original_url: str) -> bool:
        """Lưu một liên kết rút gọn mới."""
        pass

    @abstractmethod
    def get_by_code(self, short_code: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin liên kết theo mã rút gọn."""
        pass

    @abstractmethod
    def get_by_url(self, original_url: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin liên kết theo URL gốc."""
        pass

    @abstractmethod
    def increment_click(self, short_code: str) -> bool:
        """Tăng số lượt click của một liên kết và cập nhật thời gian."""
        pass

    @abstractmethod
    def list_recent_links(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy danh sách các liên kết mới nhất."""
        pass

    @abstractmethod
    def get_analytics_summary(self) -> Dict[str, int]:
        """Lấy số liệu tổng hợp (tổng link, tổng click)."""
        pass


class SQLiteLinkStorage(BaseLinkStorage):
    """Cài đặt Storage sử dụng SQLite (Hỗ trợ file đĩa hoặc in-memory)."""

    def __init__(self, db_path: str = "urls.db"):
        self.db_path = db_path
        self._mem_conn = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._init_db()

    def _get_connection(self):
        if self._mem_conn is not None:
            return self._mem_conn
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    short_code TEXT UNIQUE NOT NULL,
                    original_url TEXT NOT NULL,
                    clicks INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_clicked_at TIMESTAMP
                )
            """)
            conn.commit()

    def save_link(self, short_code: str, original_url: str) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO links (short_code, original_url, clicks) VALUES (?, ?, 0)",
                    (short_code, original_url)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def get_by_code(self, short_code: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT short_code, original_url, clicks, created_at, last_clicked_at FROM links WHERE short_code = ?",
                (short_code,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "short_code": row[0],
                "original_url": row[1],
                "clicks": row[2],
                "created_at": row[3],
                "last_clicked_at": row[4]
            }

    def get_by_url(self, original_url: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT short_code, original_url, clicks, created_at, last_clicked_at FROM links WHERE original_url = ?",
                (original_url,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "short_code": row[0],
                "original_url": row[1],
                "clicks": row[2],
                "created_at": row[3],
                "last_clicked_at": row[4]
            }

    def increment_click(self, short_code: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE links 
                SET clicks = clicks + 1, last_clicked_at = CURRENT_TIMESTAMP 
                WHERE short_code = ?
            """, (short_code,))
            conn.commit()
            return cursor.rowcount > 0

    def list_recent_links(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT short_code, original_url, clicks, created_at, last_clicked_at FROM links ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [
                {
                    "short_code": r[0],
                    "original_url": r[1],
                    "clicks": r[2],
                    "created_at": r[3],
                    "last_clicked_at": r[4]
                }
                for r in rows
            ]

    def get_analytics_summary(self) -> Dict[str, int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(clicks), 0) FROM links")
            count, clicks = cursor.fetchone()
            return {
                "total_links": count or 0,
                "total_clicks": clicks or 0
            }


class CosmosDBLinkStorage(BaseLinkStorage):
    """Cài đặt Storage sử dụng Azure Cosmos DB (NoSQL Serverless Database).
    
    Tách rời hoàn toàn database khỏi container ACA:
    - Partition Key: /short_code
    - Document Schema:
      {
        "id": "<short_code>",
        "short_code": "<short_code>",
        "original_url": "<original_url>",
        "clicks": 0,
        "created_at": "<ISO-8601>",
        "last_clicked_at": "<ISO-8601>"
      }
    """

    def __init__(self, endpoint: str, key: str, database_name: str = "urlshortener-db", container_name: str = "links"):
        import datetime
        self.endpoint = endpoint
        self.key = key
        self.database_name = database_name
        self.container_name = container_name
        self.datetime = datetime

        from azure.cosmos import CosmosClient, PartitionKey, exceptions
        self.exceptions = exceptions
        self.client = CosmosClient(
            url=self.endpoint,
            credential=self.key,
            connection_timeout=5,
            request_timeout=5
        )
        self.database = self.client.get_database_client(self.database_name)
        self.container = self.database.get_container_client(self.container_name)

    def save_link(self, short_code: str, original_url: str) -> bool:
        now_str = self.datetime.datetime.now(self.datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        item = {
            "id": short_code,
            "short_code": short_code,
            "original_url": original_url,
            "clicks": 0,
            "created_at": now_str,
            "last_clicked_at": None
        }
        try:
            self.container.create_item(body=item)
            return True
        except self.exceptions.CosmosResourceExistsError:
            return False
        except Exception as e:
            print(f"[CosmosDB Error] save_link failed: {e}")
            return False

    def get_by_code(self, short_code: str) -> Optional[Dict[str, Any]]:
        try:
            item = self.container.read_item(item=short_code, partition_key=short_code)
            return {
                "short_code": item.get("short_code"),
                "original_url": item.get("original_url"),
                "clicks": item.get("clicks", 0),
                "created_at": item.get("created_at"),
                "last_clicked_at": item.get("last_clicked_at")
            }
        except self.exceptions.CosmosResourceNotFoundError:
            return None
        except Exception as e:
            print(f"[CosmosDB Error] get_by_code failed: {e}")
            return None

    def get_by_url(self, original_url: str) -> Optional[Dict[str, Any]]:
        query = "SELECT TOP 1 * FROM c WHERE c.original_url = @original_url"
        parameters = [{"name": "@original_url", "value": original_url}]
        try:
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            if not items:
                return None
            item = items[0]
            return {
                "short_code": item.get("short_code"),
                "original_url": item.get("original_url"),
                "clicks": item.get("clicks", 0),
                "created_at": item.get("created_at"),
                "last_clicked_at": item.get("last_clicked_at")
            }
        except Exception as e:
            print(f"[CosmosDB Error] get_by_url failed: {e}")
            return None

    def increment_click(self, short_code: str) -> bool:
        now_str = self.datetime.datetime.now(self.datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        try:
            # Dùng Cosmos DB Patch API để tăng số clicks nguyên tử (atomic increment)
            patch_operations = [
                {"op": "incr", "path": "/clicks", "value": 1},
                {"op": "set", "path": "/last_clicked_at", "value": now_str}
            ]
            self.container.patch_item(
                item=short_code,
                partition_key=short_code,
                patch_operations=patch_operations
            )
            return True
        except self.exceptions.CosmosResourceNotFoundError:
            return False
        except Exception as e:
            # Fallback nếu patch không hỗ trợ hoặc lỗi: read - modify - replace
            try:
                item = self.container.read_item(item=short_code, partition_key=short_code)
                item["clicks"] = item.get("clicks", 0) + 1
                item["last_clicked_at"] = now_str
                self.container.replace_item(item=short_code, body=item)
                return True
            except Exception as e2:
                print(f"[CosmosDB Error] increment_click failed: {e2}")
                return False

    def list_recent_links(self, limit: int = 50) -> List[Dict[str, Any]]:
        query = f"SELECT TOP {limit} * FROM c ORDER BY c._ts DESC"
        try:
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            return [
                {
                    "short_code": item.get("short_code"),
                    "original_url": item.get("original_url"),
                    "clicks": item.get("clicks", 0),
                    "created_at": item.get("created_at"),
                    "last_clicked_at": item.get("last_clicked_at")
                }
                for item in items
            ]
        except Exception as e:
            print(f"[CosmosDB Error] list_recent_links failed: {e}")
            return []

    def get_analytics_summary(self) -> Dict[str, int]:
        query = "SELECT VALUE COUNT(1) FROM c"
        try:
            count_res = list(self.container.query_items(query=query, enable_cross_partition_query=True))
            total_links = count_res[0] if count_res else 0

            # Tính tổng số clicks
            clicks_query = "SELECT VALUE SUM(c.clicks) FROM c"
            clicks_res = list(self.container.query_items(query=clicks_query, enable_cross_partition_query=True))
            total_clicks = clicks_res[0] if clicks_res and clicks_res[0] is not None else 0

            return {
                "total_links": total_links,
                "total_clicks": total_clicks
            }
        except Exception as e:
            print(f"[CosmosDB Error] get_analytics_summary failed: {e}")
            return {"total_links": 0, "total_clicks": 0}
