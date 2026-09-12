# -*- coding: utf-8 -*-
"""
Script tự động đóng gói và triển khai AI Telegram Bot lên Azure Container Apps (ACA).
Cách hoạt động:
1. Đóng gói thư mục app_ai_telegram thành tar.gz base64
2. Tạo/Cập nhật Container App 'ai-telegram-agent' trên Azure Container Apps Environment
3. Cấu hình Ingress External cổng 80, cấp HTTPS SSL tự động và gán biến môi trường mặc định
"""

import os
import sys
import io
import tarfile
import base64
import yaml
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Đảm bảo UTF-8 console Windows
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

CURRENT_DIR = Path(__file__).resolve().parent
load_dotenv(CURRENT_DIR / ".env")

DEFAULT_RG = "rg-devops-aca"
DEFAULT_ENV = "urlshortener-app-env"
DEFAULT_APP_NAME = "ai-telegram-agent"
DEFAULT_LOCATION = "eastasia"

def run_az(args: list, timeout: int = 500):
    is_win = sys.platform.startswith("win")
    az_bin = "az.cmd" if is_win else "az"
    cmd = [az_bin] + args
    print(f"👉 Đang thực thi: {' '.join(cmd[:4])} ...")
    res = subprocess.run(cmd, shell=is_win, capture_output=True, text=True, timeout=timeout)
    if res.returncode == 0:
        return True, res.stdout.strip()
    return False, res.stderr.strip() or res.stdout.strip()

def deploy():
    print("="*65)
    print("🚀 BẮT ĐẦU ĐÓNG GÓI & TRIỂN KHAI AI TELEGRAM BOT LÊN AZURE ACA")
    print("="*65)

    # 1. Đóng gói mã nguồn app_ai_telegram thành tar.gz b64
    print("📦 [1/4] Đang đóng gói mã nguồn AI Telegram...")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for root, dirs, files in os.walk(CURRENT_DIR):
            # Bỏ qua các file rác
            dirs[:] = [d for d in dirs if d not in ["__pycache__", ".git", "venv", ".venv"]]
            for file in files:
                if file.endswith((".pyc", ".db")):
                    continue
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, CURRENT_DIR)
                tar.add(full_p, arcname=rel_p)

    archive_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    print(f"✅ Đã nén mã nguồn ({len(archive_b64)} chars base64).")

    # 2. Lấy Managed Environment ID
    print(f"🔍 [2/4] Kiểm tra môi trường ACA '{DEFAULT_ENV}'...")
    ok, env_id = run_az(["containerapp", "env", "show", "-n", DEFAULT_ENV, "-g", DEFAULT_RG, "--query", "id", "-o", "tsv"])
    if not ok or not env_id:
        print(f"❌ Không tìm thấy Container Apps Environment '{DEFAULT_ENV}'. Vui lòng kiểm tra Resource Group '{DEFAULT_RG}'.")
        return

    env_id = env_id.strip()

    # 3. Tạo cấu hình YAML
    print("📝 [3/4] Tạo cấu hình YAML Serverless Container...")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    tavily_key = os.getenv("TAVILY_API_KEY", "")

    container_env = [
        {"name": "APP_ARCHIVE_B64", "value": archive_b64},
        {"name": "TELEGRAM_BOT_TOKEN", "value": token},
        {"name": "OPENROUTER_API_KEY", "value": openrouter_key},
        {"name": "OPENROUTER_MODEL", "value": "openrouter/free"},
        {"name": "TAVILY_API_KEY", "value": tavily_key},
        {"name": "PORT", "value": "80"},
        {"name": "HOST", "value": "0.0.0.0"}
    ]

    yaml_data = {
        "location": DEFAULT_LOCATION,
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
                        "name": "ai-telegram-bot",
                        "env": container_env,
                        "command": ["/bin/sh", "-c"],
                        "args": [
                            "mkdir -p /app && echo \"$APP_ARCHIVE_B64\" | base64 -d | tar -xz -C /app && pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r /app/requirements.txt && cd /app && python bot/telegram_runner.py"
                        ],
                        "resources": {"cpu": 0.5, "memory": "1.0Gi"}
                    }
                ],
                # Replicas = 1 cố định để Telegram Bot Polling không bị duplicate tin nhắn
                "scale": {"minReplicas": 1, "maxReplicas": 1}
            }
        }
    }

    yaml_file = CURRENT_DIR / "deploy_aca_generated.yaml"
    with open(yaml_file, "w", encoding="utf-8") as f:
        yaml.dump(yaml_data, f, sort_keys=False)

    # 4. Triển khai lên Azure Container Apps
    print(f"🚀 [4/4] Đang triển khai '{DEFAULT_APP_NAME}' lên Azure ACA...")
    deploy_ok, out = run_az(["containerapp", "create", "-g", DEFAULT_RG, "-n", DEFAULT_APP_NAME, "--yaml", str(yaml_file)])
    if not deploy_ok:
        print(f"⚠️ App có thể đã tồn tại, đang thử cập nhật...")
        deploy_ok, out = run_az(["containerapp", "update", "-g", DEFAULT_RG, "-n", DEFAULT_APP_NAME, "--yaml", str(yaml_file)])
        if not deploy_ok:
            print(f"❌ Lỗi Deploy: {out}")
            return

    if yaml_file.exists():
        os.remove(yaml_file)

    # Lấy URL FQDN HTTPS
    _, fqdn = run_az(["containerapp", "show", "-g", DEFAULT_RG, "-n", DEFAULT_APP_NAME, "--query", "properties.configuration.ingress.fqdn", "-o", "tsv"])
    fqdn_clean = fqdn.strip() if fqdn else ""
    url = f"https://{fqdn_clean}" if fqdn_clean else "N/A"

    print("\n" + "="*65)
    print("🎉 TRIỂN KHAI THÀNH CÔNG AI TELEGRAM BOT LÊN AZURE!")
    print("="*65)
    print(f"• Container App: `{DEFAULT_APP_NAME}`")
    print(f"• Resource Group: `{DEFAULT_RG}`")
    print(f"• Ingress FQDN HTTPS: {url}")
    print(f"• Health Probe: {url}/health")
    print(f"• Bot Telegram: Đang Polling trực tiếp từ Azure Cloud")
    print("="*65 + "\n")

if __name__ == "__main__":
    deploy()
