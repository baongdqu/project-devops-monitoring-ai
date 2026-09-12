#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DevOps MCP Server cho Azure Container Apps (ACA - Serverless Kubernetes).
Cung cấp các Tool:
- aca_deploy_url_shortener: Tự động hóa build & deploy container lên ACA Serverless.
- aca_get_service_status: Kiểm tra trạng thái container, replicas, FQDN HTTPS và Uptime.
- aca_scale_app: Điều chỉnh cấu hình autoscaling (min/max replicas).
- aca_destroy_infra: Xóa sạch tài nguyên ACA trên Azure.
"""

import os
import sys
import json
from typing import Dict, Any, List
from pathlib import Path

# Thiết lập encoding utf-8 cho Windows console/pipe
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Đảm bảo đường dẫn module
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR.parent))

from mcp_server.azure_tools import (
    aca_deploy_url_shortener,
    aca_get_service_status,
    aca_scale_app,
    aca_destroy_infra,
    DEFAULT_RESOURCE_GROUP,
    DEFAULT_APP_NAME,
    DEFAULT_LOCATION
)

def list_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "aca_deploy_url_shortener",
            "description": "Tự động hóa build container từ mã nguồn và triển khai lên Azure Container Apps (Serverless Kubernetes) với chứng chỉ HTTPS bảo mật và cơ chế Scale-to-Zero tiết kiệm 100% chi phí.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "resource_group": {
                        "type": "string",
                        "description": f"Tên Resource Group (mặc định: '{DEFAULT_RESOURCE_GROUP}')."
                    },
                    "app_name": {
                        "type": "string",
                        "description": f"Tên ứng dụng Container App (mặc định: '{DEFAULT_APP_NAME}')."
                    },
                    "location": {
                        "type": "string",
                        "description": f"Khu vực triển khai (mặc định: '{DEFAULT_LOCATION}' - Hong Kong)."
                    }
                }
            }
        },
        {
            "name": "aca_get_service_status",
            "description": "Kiểm tra tình trạng ứng dụng Serverless ACA: Tên miền HTTPS, số bản sao (Replicas) đang chạy, độ trễ và Uptime thời gian thực.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "resource_group": {
                        "type": "string",
                        "description": f"Tên Resource Group (mặc định: '{DEFAULT_RESOURCE_GROUP}')."
                    },
                    "app_name": {
                        "type": "string",
                        "description": f"Tên ứng dụng Container App (mặc định: '{DEFAULT_APP_NAME}')."
                    }
                }
            }
        },
        {
            "name": "aca_scale_app",
            "description": "Điều chỉnh số lượng bản sao Container (Replicas) tối thiểu (min) và tối đa (max) của ứng dụng trên Azure Container Apps.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "min_replicas": {
                        "type": "integer",
                        "description": "Số bản sao tối thiểu (đặt 0 để bật Scale-to-Zero tiết kiệm tiền khi không có ai truy cập)."
                    },
                    "max_replicas": {
                        "type": "integer",
                        "description": "Số bản sao tối đa khi có lượng truy cập cao (ví dụ: 3 hoặc 5)."
                    },
                    "resource_group": {
                        "type": "string",
                        "description": f"Tên Resource Group (mặc định: '{DEFAULT_RESOURCE_GROUP}')."
                    },
                    "app_name": {
                        "type": "string",
                        "description": f"Tên ứng dụng Container App (mặc định: '{DEFAULT_APP_NAME}')."
                    }
                },
                "required": ["min_replicas", "max_replicas"]
            }
        },
        {
            "name": "aca_destroy_infra",
            "description": "Hủy bỏ và xóa sạch Resource Group ACA trên Azure để dọn dẹp khi không sử dụng.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "resource_group": {
                        "type": "string",
                        "description": f"Tên Resource Group cần xóa (mặc định: '{DEFAULT_RESOURCE_GROUP}')."
                    }
                }
            }
        }
    ]

def call_tool(name: str, arguments: Dict[str, Any]) -> str:
    rg = arguments.get("resource_group", DEFAULT_RESOURCE_GROUP)
    app = arguments.get("app_name", DEFAULT_APP_NAME)

    if name == "aca_deploy_url_shortener":
        loc = arguments.get("location", DEFAULT_LOCATION)
        return aca_deploy_url_shortener(resource_group=rg, app_name=app, location=loc)

    elif name == "aca_get_service_status":
        return aca_get_service_status(resource_group=rg, app_name=app)

    elif name == "aca_scale_app":
        min_r = int(arguments.get("min_replicas", 0))
        max_r = int(arguments.get("max_replicas", 3))
        return aca_scale_app(min_replicas=min_r, max_replicas=max_r, resource_group=rg, app_name=app)

    elif name == "aca_destroy_infra":
        return aca_destroy_infra(resource_group=rg)

    else:
        return f"[Error] Không tìm thấy Tool '{name}' trong DevOps ACA MCP Server."

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"JSON parse error: {e}\n")
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": list_tools()}
            }
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            result_text = call_tool(tool_name, tool_args)

            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}]
                }
            }
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()

        elif method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "azure-container-apps-mcp-server",
                        "version": "3.0.0"
                    },
                    "capabilities": {"tools": {}}
                }
            }
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()

        else:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found"}
            }
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
