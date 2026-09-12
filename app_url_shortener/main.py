# -*- coding: utf-8 -*-
"""
URL Shortener & Live Analytics Service.
Phục vụ cho dự án DevOps Cloud Automation trên Microsoft Azure.
"""

import os
import sys
import time
import string
import random
import sqlite3
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel

try:
    from .storage import SQLiteLinkStorage, CosmosDBLinkStorage
    from .service import URLShortenerService
except (ImportError, ValueError):
    from storage import SQLiteLinkStorage, CosmosDBLinkStorage
    from service import URLShortenerService

app = FastAPI(
    title="Cloud DevOps URL Shortener",
    description="Dịch vụ Rút gọn Link & Phân tích Click theo thời gian thực trên Microsoft Azure",
    version="1.0.0"
)

START_TIME = time.time()
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DB_FILE = os.getenv("DB_FILE", "urls.db")

# Khởi tạo Dependency Injection:
# Nếu có cấu hình Cosmos DB (Remote Cloud Database) -> dùng CosmosDBLinkStorage
# Nếu không -> dùng SQLiteLinkStorage (Local / InMemory)
if COSMOS_ENDPOINT and COSMOS_KEY:
    try:
        storage = CosmosDBLinkStorage(
            endpoint=COSMOS_ENDPOINT,
            key=COSMOS_KEY,
            database_name=os.getenv("COSMOS_DATABASE", "urlshortener-db"),
            container_name=os.getenv("COSMOS_CONTAINER", "links")
        )
        storage_type = "Azure Cosmos DB (Serverless NoSQL)"
        print("Connected to Azure Cosmos DB successfully.")
    except Exception as e:
        print(f"Error connecting to Azure Cosmos DB: {e}, falling back to SQLite.")
        storage = SQLiteLinkStorage(DB_FILE)
        storage_type = f"SQLite (Fallback: {e})"
else:
    storage = SQLiteLinkStorage(DB_FILE)
    storage_type = "SQLite (Local/File)"

service = URLShortenerService(storage)

class ShortenRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    """Giao diện người dùng Web Hiện Đại (Dark Mode + Glassmorphism)."""
    return HTMLResponse(content=HTML_CONTENT)

@app.post("/api/shorten")
async def shorten_url(payload: ShortenRequest, request: Request):
    base_url = str(request.base_url).rstrip("/")
    # Nếu chạy qua Ingress SSL của Azure, đảm bảo tiền tố HTTPS
    if "azurecontainerapps.io" in base_url and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://")
    return service.shorten_url(raw_url=payload.url, base_url=base_url)

@app.get("/health")
async def health_check():
    """Endpoint Health Check nhanh cho DevOps Monitoring & Liveness probe."""
    uptime = int(time.time() - START_TIME)
    return {
        "status": "healthy",
        "service": "azure-url-shortener",
        "uptime_seconds": uptime,
        "storage_backend": storage_type,
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    }

@app.get("/health/detailed")
async def health_detailed():
    """Endpoint Health Check chi tiết (bao gồm cả số liệu database)."""
    uptime = int(time.time() - START_TIME)
    data = service.get_health_metrics(uptime_seconds=uptime)
    data["server_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    data["storage_backend"] = storage_type
    return data

@app.get("/api/stats")
async def get_stats():
    """Lấy danh sách các liên kết và lượt click thời gian thực."""
    return service.get_dashboard_stats()

@app.get("/{short_code}")
async def redirect_link(short_code: str):
    if short_code in ("health", "metrics", "favicon.ico", "api"):
        raise HTTPException(status_code=404)

    original_url = service.resolve_and_record_click(short_code)
    if not original_url:
        raise HTTPException(status_code=404, detail="Mã rút gọn không tồn tại.")

    return RedirectResponse(url=original_url, status_code=307)

@app.post("/api/chaos/simulate-crash")
async def simulate_crash():
    """Cố tình tắt app để thử nghiệm AI ChatOps tự động phát hiện và phục hồi."""
    def crash():
        time.sleep(1)
        os._exit(1)
    import threading
    threading.Thread(target=crash).start()
    return {"message": "Simulating crash in 1 second. Container will exit."}


HTML_CONTENT = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cloud DevOps URL Shortener | Azure</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }
        body {
            min-height: 100vh;
            background: linear-gradient(135deg, #090d16 0%, #0d1527 50%, #08111e 100%);
            color: #f1f5f9;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px 20px;
        }
        .header { text-align: center; margin-bottom: 36px; max-width: 600px; }
        .badge {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 6px 14px; background: rgba(56, 189, 248, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 9999px;
            color: #38bdf8; font-size: 13px; font-weight: 600; margin-bottom: 16px;
        }
        .pulse { width: 8px; height: 8px; background: #38bdf8; border-radius: 50%; box-shadow: 0 0 10px #38bdf8; }
        h1 { font-size: 38px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 12px; background: linear-gradient(to right, #ffffff, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        p.subtitle { color: #94a3b8; font-size: 16px; line-height: 1.5; }
        .card {
            width: 100%; max-width: 680px;
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px; padding: 28px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
            backdrop-filter: blur(16px);
            margin-bottom: 30px;
        }
        .input-group { display: flex; gap: 12px; margin-bottom: 20px; }
        input[type="text"] {
            flex: 1; padding: 14px 18px; border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.12);
            background: rgba(30, 41, 59, 0.6); color: #fff;
            font-size: 15px; outline: none; transition: 0.2s;
        }
        input[type="text"]:focus { border-color: #38bdf8; box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2); }
        button.btn-primary {
            padding: 14px 26px; border-radius: 12px; border: none;
            background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
            color: #fff; font-weight: 700; font-size: 15px; cursor: pointer;
            transition: all 0.2s; display: flex; align-items: center; gap: 6px;
        }
        button.btn-primary:hover { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(2, 132, 199, 0.4); }
        .result-box {
            display: none; padding: 16px; border-radius: 12px;
            background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3);
            margin-top: 16px; align-items: center; justify-content: space-between;
        }
        .result-link { color: #34d399; font-weight: 700; font-size: 16px; text-decoration: none; word-break: break-all; }
        .btn-copy {
            padding: 8px 16px; border-radius: 8px; border: none;
            background: #10b981; color: #fff; font-weight: 600; cursor: pointer;
        }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
        .stat-card {
            background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 14px; padding: 18px; text-align: center;
        }
        .stat-value { font-size: 26px; font-weight: 800; color: #38bdf8; margin-bottom: 4px; }
        .stat-label { font-size: 13px; color: #64748b; text-transform: uppercase; font-weight: 600; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }
        th { text-align: left; padding: 10px 12px; color: #64748b; border-bottom: 1px solid rgba(255, 255, 255, 0.08); }
        td { padding: 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.04); }
        .short-code { color: #38bdf8; font-weight: 700; text-decoration: none; }
        .click-badge {
            display: inline-block; padding: 4px 10px; background: rgba(56, 189, 248, 0.15);
            color: #38bdf8; border-radius: 20px; font-weight: 700; font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="badge"><div class="pulse"></div> Cloud Live on Microsoft Azure</div>
        <h1>URL Shortener & Analytics</h1>
        <p class="subtitle">Dịch vụ rút gọn liên kết và giám sát lượt click thời gian thực được tự động hóa triển khai bởi AI ChatOps.</p>
    </div>

    <div class="card">
        <form id="shorten-form" class="input-group" onsubmit="handleShorten(event)">
            <input type="text" id="url-input" placeholder="Dán đường link dài của bạn vào đây (vd: https://github.com/...)" required autocomplete="off">
            <button type="submit" class="btn-primary">Rút Gọn 🚀</button>
        </form>

        <div id="result-box" class="result-box">
            <div>
                <div style="font-size: 12px; color: #a7f3d0; margin-bottom: 2px;">Link rút gọn của bạn:</div>
                <a id="short-link-anchor" href="#" target="_blank" class="result-link"></a>
            </div>
            <button class="btn-copy" onclick="copyResult()">Copy</button>
        </div>
    </div>

    <div class="card">
        <div class="stats-grid">
            <div class="stat-card">
                <div id="total-links" class="stat-value">0</div>
                <div class="stat-label">Tổng Liên Kết</div>
            </div>
            <div class="stat-card">
                <div id="total-clicks" class="stat-value" style="color: #34d399;">0</div>
                <div class="stat-label">Tổng Lượt Click</div>
            </div>
            <div class="stat-card">
                <div id="uptime-val" class="stat-value" style="color: #f59e0b;">Online</div>
                <div class="stat-label">Trạng Thái SRE</div>
            </div>
        </div>

        <h3 style="font-size: 17px; margin-bottom: 12px; color: #cbd5e1;">📊 Các Link Rút Gọn Gần Đây</h3>
        <div style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        <th>Mã Ngắn</th>
                        <th>URL Gốc</th>
                        <th>Số Click</th>
                        <th>Lần Click Cuối</th>
                    </tr>
                </thead>
                <tbody id="links-tbody">
                    <tr><td colspan="4" style="text-align: center; color: #64748b;">Đang tải dữ liệu...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('total-links').innerText = data.total_links;
                document.getElementById('total-clicks').innerText = data.total_clicks;

                const tbody = document.getElementById('links-tbody');
                if (data.links.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #64748b;">Chưa có liên kết nào được tạo.</td></tr>';
                    return;
                }

                tbody.innerHTML = data.links.map(l => `
                    <tr>
                        <td><a href="/${l.short_code}" target="_blank" class="short-code">/${l.short_code}</a></td>
                        <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            <a href="${l.original_url}" target="_blank" style="color: #94a3b8; text-decoration: none;">${l.original_url}</a>
                        </td>
                        <td><span class="click-badge">${l.clicks} clicks</span></td>
                        <td style="color: #64748b; font-size: 12px;">${l.last_clicked_at || 'Chưa click'}</td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error(e);
            }
        }

        async function handleShorten(e) {
            e.preventDefault();
            const input = document.getElementById('url-input');
            const btn = e.target.querySelector('button');
            btn.disabled = true;
            btn.innerText = 'Đang tạo...';

            try {
                const res = await fetch('/api/shorten', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: input.value })
                });
                const data = await res.json();
                if (data.success) {
                    document.getElementById('result-box').style.display = 'flex';
                    const anchor = document.getElementById('short-link-anchor');
                    anchor.href = data.short_url;
                    anchor.innerText = data.short_url;
                    input.value = '';
                    loadStats();
                }
            } catch (err) {
                alert('Có lỗi xảy ra: ' + err);
            } finally {
                btn.disabled = false;
                btn.innerText = 'Rút Gọn 🚀';
            }
        }

        function copyResult() {
            const anchor = document.getElementById('short-link-anchor');
            navigator.clipboard.writeText(anchor.innerText);
            const btn = document.querySelector('.btn-copy');
            btn.innerText = 'Đã Copy!';
            setTimeout(() => { btn.innerText = 'Copy'; }, 2000);
        }

        loadStats();
        setInterval(loadStats, 5000);
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
