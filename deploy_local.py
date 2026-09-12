# -*- coding: utf-8 -*-
"""
Script tự động đóng gói và triển khai cả Web App và AI Telegram Bot từ LOCAL lên Azure ACA.
Target:
- Resource Group: rg-devops-aca-local
- Environment: urlshortener-env-local
- Web App: urlshortener-app-local
- AI Bot: ai-telegram-agent-local
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

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

RESOURCE_GROUP = "rg-devops-aca-local"
ENVIRONMENT = "urlshortener-env-local"
LOCATION = "eastasia"

def run_az(args: list, timeout: int = 500):
    is_win = sys.platform.startswith("win")
    az_bin = "az.cmd" if is_win else "az"
    cmd = [az_bin] + args
    print(f"👉 Đang thực thi: {' '.join(cmd[:4])} ...")
    res = subprocess.run(cmd, shell=is_win, capture_output=True, text=True, timeout=timeout)
    if res.returncode == 0:
        return True, res.stdout.strip()
    return False, res.stderr.strip() or res.stdout.strip()

def deploy_web_local():
    print("\n" + "="*60)
    print("🌐 BẮT ĐẦU TRIỂN KHAI WEB APP: urlshortener-app-local")
    print("="*60)

    web_dir = ROOT_DIR / "app_url_shortener"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for f in ["main.py", "service.py", "storage.py", "__init__.py"]:
            p = web_dir / f
            if p.exists():
                tar.add(str(p), arcname=f)

    archive_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    print(f"📦 Đã đóng gói Web App ({len(archive_b64)} chars b64)")

    ok, env_id = run_az(["containerapp", "env", "show", "-n", ENVIRONMENT, "-g", RESOURCE_GROUP, "--query", "id", "-o", "tsv"])
    if not ok or not env_id:
        print(f"❌ Không tìm thấy Container Apps Environment '{ENVIRONMENT}' trong '{RESOURCE_GROUP}'.")
        return

    cosmos_endpoint = os.getenv("COSMOS_ENDPOINT", "")
    cosmos_key = os.getenv("COSMOS_KEY", "")

    yaml_data = {
        "location": LOCATION,
        "type": "Microsoft.App/containerApps",
        "properties": {
            "managedEnvironmentId": env_id.strip(),
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
                        "env": [
                            {"name": "APP_ARCHIVE_B64", "value": archive_b64},
                            {"name": "DB_FILE", "value": "/app/urls.db"},
                            {"name": "COSMOS_ENDPOINT", "value": cosmos_endpoint},
                            {"name": "COSMOS_KEY", "value": cosmos_key},
                            {"name": "COSMOS_DATABASE", "value": "urlshortener-db"},
                            {"name": "COSMOS_CONTAINER", "value": "links"}
                        ],
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

    yaml_path = ROOT_DIR / "deploy_web_local.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(yaml_data, f, sort_keys=False)

    app_name = "urlshortener-app-local"
    ok, out = run_az(["containerapp", "create", "-g", RESOURCE_GROUP, "-n", app_name, "--yaml", str(yaml_path)])
    if not ok:
        print("⚠️ App đã tồn tại, tiến hành update...")
        ok, out = run_az(["containerapp", "update", "-g", RESOURCE_GROUP, "-n", app_name, "--yaml", str(yaml_path)])

    if yaml_path.exists():
        os.remove(yaml_path)

    _, fqdn = run_az(["containerapp", "show", "-g", RESOURCE_GROUP, "-n", app_name, "--query", "properties.configuration.ingress.fqdn", "-o", "tsv"])
    print(f"✅ Triển khai Web App thành công! URL: https://{fqdn.strip() if fqdn else 'N/A'}")

def deploy_ai_local():
    print("\n" + "="*60)
    print("🤖 BẮT ĐẦU TRIỂN KHAI AI BOT: ai-telegram-agent-local")
    print("="*60)

    ai_dir = ROOT_DIR / "app_ai_telegram"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for root, dirs, files in os.walk(ai_dir):
            dirs[:] = [d for d in dirs if d not in ["__pycache__", ".git", "venv", ".venv"]]
            for file in files:
                if file.endswith((".pyc", ".db")):
                    continue
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, ai_dir)
                tar.add(full_p, arcname=rel_p)

    archive_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    print(f"📦 Đã đóng gói AI Bot ({len(archive_b64)} chars b64)")

    ok, env_id = run_az(["containerapp", "env", "show", "-n", ENVIRONMENT, "-g", RESOURCE_GROUP, "--query", "id", "-o", "tsv"])
    if not ok or not env_id:
        print(f"❌ Không tìm thấy Container Apps Environment '{ENVIRONMENT}' trong '{RESOURCE_GROUP}'.")
        return

    yaml_data = {
        "location": LOCATION,
        "type": "Microsoft.App/containerApps",
        "properties": {
            "managedEnvironmentId": env_id.strip(),
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
                        "env": [
                            {"name": "APP_ARCHIVE_B64", "value": archive_b64},
                            {"name": "TELEGRAM_BOT_TOKEN", "value": os.getenv("TELEGRAM_BOT_TOKEN", "")},
                            {"name": "OPENROUTER_API_KEY", "value": os.getenv("OPENROUTER_API_KEY", "")},
                            {"name": "OPENROUTER_MODEL", "value": "openrouter/free"},
                            {"name": "TAVILY_API_KEY", "value": os.getenv("TAVILY_API_KEY", "")},
                            {"name": "PORT", "value": "80"},
                            {"name": "HOST", "value": "0.0.0.0"}
                        ],
                        "command": ["/bin/sh", "-c"],
                        "args": [
                            "mkdir -p /app && echo \"$APP_ARCHIVE_B64\" | base64 -d | tar -xz -C /app && pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r /app/requirements.txt && cd /app && python bot/telegram_runner.py"
                        ],
                        "resources": {"cpu": 0.5, "memory": "1.0Gi"}
                    }
                ],
                "scale": {"minReplicas": 1, "maxReplicas": 1}
            }
        }
    }

    yaml_path = ROOT_DIR / "deploy_ai_local.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(yaml_data, f, sort_keys=False)

    app_name = "ai-telegram-agent-local"
    ok, out = run_az(["containerapp", "create", "-g", RESOURCE_GROUP, "-n", app_name, "--yaml", str(yaml_path)])
    if not ok:
        print("⚠️ App đã tồn tại, tiến hành update...")
        ok, out = run_az(["containerapp", "update", "-g", RESOURCE_GROUP, "-n", app_name, "--yaml", str(yaml_path)])

    if yaml_path.exists():
        os.remove(yaml_path)

    _, fqdn = run_az(["containerapp", "show", "-g", RESOURCE_GROUP, "-n", app_name, "--query", "properties.configuration.ingress.fqdn", "-o", "tsv"])
    print(f"✅ Triển khai AI Bot thành công! URL: https://{fqdn.strip() if fqdn else 'N/A'}")

if __name__ == "__main__":
    deploy_web_local()
    deploy_ai_local()
