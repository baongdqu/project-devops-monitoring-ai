# -*- coding: utf-8 -*-
"""
Bộ công cụ Azure Container Apps (ACA - Serverless Kubernetes) cho ChatOps AI Agent.
Sử dụng Azure CLI (az containerapp) để quản lý container serverless, scale-to-zero, và giám sát live.
"""

import os
import sys
import json
import time
import urllib.request
import subprocess
from typing import Dict, Any

# Đảm bảo encoding utf-8 trên Windows
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_RESOURCE_GROUP = "rg-devops-aca"
DEFAULT_APP_NAME = "urlshortener-app"
DEFAULT_LOCATION = "eastasia" # Hong Kong - Thuộc danh sách Allowed Locations của SV

def run_az_command(args: list, timeout: int = 400) -> Dict[str, Any]:
    """Hàm bổ trợ chạy lệnh Azure CLI."""
    is_win = sys.platform.startswith("win")
    az_bin = "az.cmd" if is_win else "az"
    cmd = [az_bin] + args
    try:
        res = subprocess.run(cmd, shell=is_win, capture_output=True, text=True, timeout=timeout)
        if res.returncode == 0:
            output = res.stdout.strip()
            try:
                return {"success": True, "data": json.loads(output) if output else {}}
            except json.JSONDecodeError:
                return {"success": True, "data": output}
        else:
            return {"success": False, "error": res.stderr.strip() or res.stdout.strip()}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Lệnh Azure CLI bị timeout (vượt quá {timeout}s)."}
    except Exception as e:
        return {"success": False, "error": f"Lỗi thực thi Azure CLI: {str(e)}"}

def aca_deploy_url_shortener(
    resource_group: str = DEFAULT_RESOURCE_GROUP,
    app_name: str = DEFAULT_APP_NAME,
    location: str = DEFAULT_LOCATION
) -> str:
    """
    Tự động hóa hoàn toàn quy trình Deploy lên Azure Container Apps (Serverless):
    1. Tạo Resource Group (nếu chưa có)
    2. Build Docker Container từ thư mục app_url_shortener và đẩy lên ACA
    3. Cấu hình Ingress External cổng 80 (Tự động cấp phát HTTPS SSL)
    4. Bật chế độ Scale-to-Zero (min-replicas=0, max-replicas=3)
    """
    # 1. Tạo Resource Group
    rg_res = run_az_command(["group", "create", "--name", resource_group, "--location", location, "--output", "json"])
    if not rg_res["success"]:
        return f"[Lỗi Tạo Resource Group] {rg_res['error']}"

    import base64
    import yaml

    # 2. Đảm bảo ContainerApp Environment tồn tại
    env_name = f"{app_name}-env"
    env_res = run_az_command(["containerapp", "env", "show", "-n", env_name, "-g", resource_group, "--query", "id", "-o", "tsv"])
    env_id = env_res.get("data", "").strip()
    if not env_id or "error" in env_id.lower():
        run_az_command(["containerapp", "env", "create", "-n", env_name, "-g", resource_group, "-l", location, "--output", "json"])
        env_res = run_az_command(["containerapp", "env", "show", "-n", env_name, "-g", resource_group, "--query", "id", "-o", "tsv"])
        env_id = env_res.get("data", "").strip()

    import io
    import tarfile

    # 3. Đóng gói mã nguồn (main.py, service.py, storage.py) vào tar.gz base64
    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app_url_shortener"))
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for fname in ["main.py", "service.py", "storage.py", "__init__.py"]:
            fpath = os.path.join(app_dir, fname)
            if os.path.exists(fpath):
                tar.add(fpath, arcname=fname)
    archive_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    # 3.1. Kiểm tra và lấy thông tin kết nối Azure Cosmos DB (nếu có)
    cosmos_endpoint = ""
    cosmos_key = ""
    cosmos_name = "cosmos-devops-uit-east"
    cosmos_res = run_az_command(["cosmosdb", "show", "--name", cosmos_name, "--resource-group", resource_group, "--query", "documentEndpoint", "-o", "tsv"])
    if cosmos_res["success"] and cosmos_res.get("data"):
        cosmos_endpoint = cosmos_res["data"].strip()
        key_res = run_az_command(["cosmosdb", "keys", "list", "--name", cosmos_name, "--resource-group", resource_group, "--query", "primaryMasterKey", "-o", "tsv"])
        if key_res["success"] and key_res.get("data"):
            cosmos_key = key_res["data"].strip()

    container_env = [
        {"name": "APP_ARCHIVE_B64", "value": archive_b64},
        {"name": "DB_FILE", "value": "/app/urls.db"}
    ]
    if cosmos_endpoint and cosmos_key:
        container_env.extend([
            {"name": "COSMOS_ENDPOINT", "value": cosmos_endpoint},
            {"name": "COSMOS_KEY", "value": cosmos_key},
            {"name": "COSMOS_DATABASE", "value": "urlshortener-db"},
            {"name": "COSMOS_CONTAINER", "value": "links"}
        ])

    yaml_data = {
        "location": location,
        "type": "Microsoft.App/containerApps",
        "properties": {
            "managedEnvironmentId": env_id,
            "configuration": {
                "activeRevisionsMode": "Single",
                "ingress": {
                    "external": True,
                    "targetPort": 80,
                    "transport": "auto",
                    "allowInsecure": False
                }
            },
            "template": {
                "containers": [
                    {
                        "image": "python:3.11-slim",
                        "name": "urlshortener",
                        "env": container_env,
                        "command": ["/bin/sh", "-c"],
                        "args": [
                            "mkdir -p /app && echo \"$APP_ARCHIVE_B64\" | base64 -d | tar -xz -C /app && pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org fastapi uvicorn pydantic azure-cosmos && python -m uvicorn main:app --app-dir /app --host 0.0.0.0 --port 80"
                        ],
                        "resources": {"cpu": 0.25, "memory": "0.5Gi"}
                    }
                ],
                "scale": {"minReplicas": 0, "maxReplicas": 3}
            }
        }
    }

    yaml_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "deploy_aca_generated.yaml"))
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(yaml_data, f, sort_keys=False)

    # 4. Triển khai cấu hình qua Azure CLI
    deploy_res = run_az_command(["containerapp", "create", "--resource-group", resource_group, "--name", app_name, "--yaml", yaml_path], timeout=500)
    if not deploy_res["success"]:
        # Nếu app đã tồn tại, dùng lệnh update
        deploy_res = run_az_command(["containerapp", "update", "--resource-group", resource_group, "--name", app_name, "--yaml", yaml_path], timeout=500)
        if not deploy_res["success"]:
            return f"[Lỗi Deploy Azure Container App] {deploy_res['error']}"

    if os.path.exists(yaml_path):
        os.remove(yaml_path)

    # 4. Lấy URL FQDN HTTPS chính thức
    show_res = run_az_command([
        "containerapp", "show",
        "--name", app_name,
        "--resource-group", resource_group,
        "--query", "properties.configuration.ingress.fqdn",
        "--output", "tsv"
    ])

    fqdn = show_res.get("data", "").strip() if show_res["success"] else ""
    https_url = f"https://{fqdn}" if fqdn else "Đang cập nhật FQDN"

    return f"""🎉 **TRIỂN KHAI THÀNH CÔNG LÊN AZURE CONTAINER APPS (SERVERLESS)!**
----------------------------------------------------------------------
- **Loại hình**: Serverless Kubernetes (Azure Container Apps)
- **Tên ứng dụng**: `{app_name}`
- **Resource Group**: `{resource_group}`
- **Khu vực**: `{location}` (Hong Kong)
- **Cơ chế Tiết kiệm**: **Scale-to-Zero (0đ khi không có truy cập)**
- **Giới hạn Replicas**: 0 -> 3 (Tự động scale khi có traffic)
- **Đường dẫn HTTPS Bảo Mật**: {https_url}
- **Endpoint Healthcheck**: {https_url}/health

💡 *Lưu ý: Ứng dụng đã sẵn sàng nhận truy cập với chứng chỉ SSL chính thức từ Microsoft.*
"""

def aca_get_service_status(
    resource_group: str = DEFAULT_RESOURCE_GROUP,
    app_name: str = DEFAULT_APP_NAME
) -> str:
    """Kiểm tra tình trạng Serverless Container, số lượng replicas và đo chỉ số Uptime/Health."""
    show_res = run_az_command([
        "containerapp", "show",
        "--name", app_name,
        "--resource-group", resource_group,
        "--output", "json"
    ])

    if not show_res["success"]:
        return f"[Lỗi Kiểm tra Container App] {show_res['error']}"

    app_data = show_res.get("data", {})
    provisioning_state = app_data.get("properties", {}).get("provisioningState", "Unknown")
    fqdn = app_data.get("properties", {}).get("configuration", {}).get("ingress", {}).get("fqdn", "")
    scale_rules = app_data.get("properties", {}).get("template", {}).get("scale", {})
    min_rep = scale_rules.get("minReplicas", 0)
    max_rep = scale_rules.get("maxReplicas", 1)

    # Đếm số replica đang chạy
    replica_res = run_az_command([
        "containerapp", "replica", "list",
        "--name", app_name,
        "--resource-group", resource_group,
        "--output", "json"
    ])
    active_replicas = 0
    if replica_res["success"] and isinstance(replica_res.get("data"), list):
        active_replicas = len(replica_res["data"])

    # Ping Healthcheck
    health_info = "Chưa kết nối được"
    latency_ms = 0
    if fqdn:
        url = f"https://{fqdn}/health"
        try:
            start_t = time.time()
            req = urllib.request.Request(url, headers={"User-Agent": "DevOps-ACA-Monitor"})
            with urllib.request.urlopen(req, timeout=10) as response:
                latency_ms = int((time.time() - start_t) * 1000)
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    backend = data.get('storage_backend', 'N/A')
                    health_info = f"✅ Healthy (Uptime: {data.get('uptime_seconds')}s, Backend: {backend})"
        except Exception as e:
            health_info = f"⚠️ Đang Scale-from-Zero hoặc khởi động container ({str(e)})"

    return f"""📊 **BÁO CÁO GIÁM SÁT AZURE CONTAINER APPS (SERVERLESS)**
----------------------------------------------------------------------
- **Ứng dụng**: `{app_name}` trong `{resource_group}`
- **Trạng thái Triển khai**: `{provisioning_state}`
- **Bản sao hoạt động (Replicas)**: `{active_replicas}` (Scale Cấu hình: {min_rep} -> {max_rep})
- **Tên miền HTTPS**: https://{fqdn}
- **Độ trễ phản hồi**: `{latency_ms} ms`
- **Sức khỏe Dịch vụ**: {health_info}
"""

def aca_scale_app(
    min_replicas: int,
    max_replicas: int,
    resource_group: str = DEFAULT_RESOURCE_GROUP,
    app_name: str = DEFAULT_APP_NAME
) -> str:
    """Điều chỉnh số lượng bản sao Container (Replicas) tối thiểu và tối đa."""
    res = run_az_command([
        "containerapp", "update",
        "--name", app_name,
        "--resource-group", resource_group,
        "--min-replicas", str(min_replicas),
        "--max-replicas", str(max_replicas)
    ])
    if res["success"]:
        return f"✅ Đã cấu hình Autoscaling thành công cho `{app_name}`: Min Replicas = `{min_replicas}`, Max Replicas = `{max_replicas}`."
    return f"[Lỗi Cấu hình Scale] {res['error']}"

def aca_destroy_infra(resource_group: str = DEFAULT_RESOURCE_GROUP) -> str:
    """Xóa sạch Resource Group ACA trên Azure."""
    res = run_az_command(["group", "delete", "--name", resource_group, "--yes", "--no-wait"])
    if res["success"]:
        return f"🗑️ Đã gửi lệnh xóa Resource Group `{resource_group}` trên Azure. Mọi tài nguyên Serverless đang được dọn dẹp an toàn trong nền."
    return f"[Lỗi Xóa ACA] {res['error']}"
