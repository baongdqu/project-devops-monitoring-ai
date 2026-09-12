# 🚀 Azure Container Apps (ACA) Serverless ChatOps & SRE Platform

Hệ thống cho phép kỹ sư DevOps và người dùng vận hành, tự động triển khai ứng dụng web (**URL Shortener & Live Analytics**) lên nền tảng **Serverless Kubernetes (Azure Container Apps - ACA)** trên **Microsoft Azure**, tích hợp cơ chế **Scale-to-Zero (0đ khi không có truy cập)**, chứng chỉ **HTTPS SSL tự động** và giám sát sức khỏe hoàn toàn bằng **ngôn ngữ tự nhiên** qua **Telegram ChatOps Bot** hoặc **CLI**, kết nối trực tiếp với **AI Agent** qua giao thức **Model Context Protocol (MCP)**.

---

## 🌟 Kiến Trúc Hoạt Động

```
[Người dùng trên Telegram / CLI] 
       │ 
       ▼ (Ngôn ngữ tự nhiên: "Deploy app lên ACA", "Check tình trạng replicas", "Scale app lên 2 pods")
[ChatOps Gateway / Telegram Bot]
       │ (Phê duyệt Human-in-the-loop nếu là thao tác nhạy cảm: Deploy / Scale / Destroy)
       ▼
[AI Agent Core (`project my agent`)]
       │ (LLM Function Calling qua chuẩn MCP)
       ▼
[Azure Container Apps MCP Server (`devops_mcp_server.py`)]
       ├─► [aca_deploy_url_shortener]: Tự động hóa build YAML & deploy container lên ACA
       ├─► [aca_get_service_status]: Đọc trạng thái live, số replicas, Uptime, lượt click
       ├─► [aca_scale_app]: Điều chỉnh cấu hình autoscaling (min/max replicas)
       └─► [aca_destroy_infra]: Xóa dọn dẹp toàn bộ Resource Group khi không dùng
```

---

## 🌐 Ứng Dụng Đang Hoạt Động Trực Tuyến

* 🔗 **Website Serverless HTTPS**: **[https://urlshortener-app.redmoss-b81863cc.eastasia.azurecontainerapps.io](https://urlshortener-app.redmoss-b81863cc.eastasia.azurecontainerapps.io)**
* 🩺 **Endpoint Health Check**: **[https://urlshortener-app.redmoss-b81863cc.eastasia.azurecontainerapps.io/health](https://urlshortener-app.redmoss-b81863cc.eastasia.azurecontainerapps.io/health)**
* ☁️ **Resource Group**: `rg-devops-aca` (Khu vực `eastasia` - Hong Kong)
* ⚡ **Workload Profile**: `Consumption` (Tự động scale về 0 khi không có truy cập - **0.00$ khi nhàn rỗi**)

---

## 🛠️ Bộ Công Cụ MCP Đã Tích Hợp
1. **`aca_deploy_url_shortener`**: Tự động hóa đóng gói và triển khai ứng dụng lên Azure Container Apps qua cấu hình YAML tự động (không phụ thuộc ACR Tasks).
2. **`aca_get_service_status`**: Kiểm tra trạng thái Container App (ProvisioningState), FQDN HTTPS, số lượng replicas đang active, và độ trễ phản hồi.
3. **`aca_scale_app`**: Điều chỉnh số lượng bản sao Container (`min_replicas` và `max_replicas`).
4. **`aca_destroy_infra`**: Xóa sạch toàn bộ Resource Group ACA trên Azure chỉ bằng một lệnh.

---

## 🚀 Hướng Dẫn Vận Hành & Khởi Chạy
 
### 1. Khởi chạy AI Agent & ChatOps:
AI Agent Core và Telegram Bot được quản lý tập trung tại dự án **`( ) project my agent`**:
```powershell
# Chạy Telegram Bot chính của AI Agent (đã tích hợp MCP Azure DevOps)
cd "..\..\zzz kỹ năng tech - ai (separator)\( ) project my agent"
.\telegram.bat
```

### 2. Thử nghiệm và Triển khai:
```powershell
.\run_chatops.bat mcp         # Kiểm tra Azure DevOps MCP Server
.\run_chatops.bat app         # Chạy thử nghiệm URL Shortener tại localhost:8000
.\run_chatops.bat ai-local    # Chạy thử nghiệm AI Telegram Bot Server tại Local
.\run_chatops.bat ai-deploy   # Đóng gói và Deploy AI Telegram Bot lên Azure ACA
```

---

## 📦 Module Mới: `app_ai_telegram` (Đóng Gói Lên Azure Container Apps)
Dự án đã được tích hợp gói mã nguồn AI độc lập tại thư mục `app_ai_telegram/`:
* **Core Agent**: LangGraph ReAct Agent tích hợp OpenAI/OpenRouter + Tavily Web Search.
* **DevOps Tools**: Azure Status Check (`aca_get_service_status`), Scale App (`aca_scale_app`), File Tools.
* **Dual-Runner Architecture**: Vừa duy trì Telegram Bot Polling thời gian thực, vừa cung cấp endpoint HTTP `/health` trên cổng 80 cho Ingress Health Check của Azure Container Apps.
* **Tự động hóa Deploy**: Chỉ cần chạy `run_chatops.bat ai-deploy` để đóng gói mã nguồn và phát hành trực tiếp lên Azure Container Apps.

