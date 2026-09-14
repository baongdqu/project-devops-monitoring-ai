import os
import sys
import json
import urllib.request
import subprocess
from typing import Dict, Any
from langchain_core.tools import tool

DEFAULT_RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP", "rg-devops-aca")
DEFAULT_APP_NAME = os.getenv("AZURE_APP_NAME", "urlshortener-app")
DEFAULT_LOCATION = os.getenv("AZURE_LOCATION", "eastasia")

def _run_az(args: list) -> Dict[str, Any]:
    is_win = sys.platform.startswith("win")
    az_bin = "az.cmd" if is_win else "az"
    try:
        res = subprocess.run([az_bin] + args, shell=is_win, capture_output=True, text=True, timeout=120)
        if res.returncode == 0:
            out = res.stdout.strip()
            try:
                return {"success": True, "data": json.loads(out) if out else {}}
            except Exception:
                return {"success": True, "data": out}
        return {"success": False, "error": res.stderr.strip() or res.stdout.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def aca_get_service_status(resource_group: str = DEFAULT_RESOURCE_GROUP, app_name: str = DEFAULT_APP_NAME) -> str:
    """
    Kiểm tra trạng thái Azure Container App: ProvisioningState, FQDN HTTPS, số lượng replicas đang chạy và Healthcheck.
    """
    res = _run_az(["containerapp", "show", "-g", resource_group, "-n", app_name, "-o", "json"])
    if not res["success"]:
        return f"❌ Lỗi truy vấn Container App '{app_name}': {res['error']}"

    data = res.get("data", {})
    props = data.get("properties", {})
    state = props.get("provisioningState", "Unknown")
    fqdn = props.get("configuration", {}).get("ingress", {}).get("fqdn", "")
    url = f"https://{fqdn}" if fqdn else "N/A"

    rep_res = _run_az(["containerapp", "replica", "list", "-g", resource_group, "-n", app_name, "-o", "json"])
    replicas = rep_res.get("data", []) if rep_res["success"] and isinstance(rep_res.get("data"), list) else []

    health_status = "Chưa kiểm tra"
    if url and url != "N/A":
        try:
            req = urllib.request.Request(f"{url}/health", headers={"User-Agent": "AzureAI-HealthCheck/1.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                health_status = f"✅ HTTP {r.status} OK (Live & Healthy)"
        except Exception as e:
            health_status = f"⚠️ Không phản hồi (có thể đang scale 0 replicas): {e}"

    return f"""📊 **BÁO CÁO SỨC KHỎE AZURE CONTAINER APP:**
- **Ứng dụng**: `{app_name}` (RG: `{resource_group}`)
- **Trạng thái**: `{state}`
- **Số Replicas Active**: `{len(replicas)}`
- **Domain HTTPS**: {url}
- **Healthcheck Live**: {health_status}
"""

@tool
def aca_scale_app(min_replicas: int, max_replicas: int, confirmed: bool = False, resource_group: str = DEFAULT_RESOURCE_GROUP, app_name: str = DEFAULT_APP_NAME) -> str:
    """
    Điều chỉnh số lượng bản sao Container (Scale-to-Zero hoặc tăng tải replicas).
    Cần confirmed=True để thực thi; nếu confirmed=False thì trả về yêu cầu phê duyệt Human-in-the-loop.
    """
    if not confirmed:
        return (
            f"⚠️ **YÊU CẦU PHÊ DUYỆT HUMAN-IN-THE-LOOP (GUARDRAIL)** ⚠️\n\n"
            f"Bạn đang yêu cầu thay đổi cấu hình hạ tầng Azure Container Apps:\n"
            f"• **Ứng dụng**: `{app_name}` (RG: `{resource_group}`)\n"
            f"• **Min Replicas**: `{min_replicas}`\n"
            f"• **Max Replicas**: `{max_replicas}`\n\n"
            f"👉 Vui lòng xác nhận thực thi bằng nút bên dưới hoặc gửi: `Xác nhận scale {min_replicas} đến {max_replicas}`"
        )

    res = _run_az([
        "containerapp", "update",
        "-g", resource_group,
        "-n", app_name,
        "--min-replicas", str(min_replicas),
        "--max-replicas", str(max_replicas)
    ])
    if not res["success"]:
        return f"❌ Lỗi scale ứng dụng: {res['error']}"
    return f"✅ **ĐÃ PHÊ DUYỆT & THỰC THI THÀNH CÔNG** `{app_name}`: Min={min_replicas}, Max={max_replicas}."

def execute_approved_scale(min_replicas: int, max_replicas: int, resource_group: str = DEFAULT_RESOURCE_GROUP, app_name: str = DEFAULT_APP_NAME) -> str:
    """Hàm chạy trực tiếp khi người dùng bấm nút [Xác nhận thực thi] trên Telegram."""
    res = _run_az([
        "containerapp", "update",
        "-g", resource_group,
        "-n", app_name,
        "--min-replicas", str(min_replicas),
        "--max-replicas", str(max_replicas)
    ])
    if not res["success"]:
        return f"❌ Lỗi thực thi scale ứng dụng: {res['error']}"
    return f"✅ **[HUMAN-IN-THE-LOOP APPROVED]** Đã scale thành công `{app_name}` lên Min={min_replicas}, Max={max_replicas}."
