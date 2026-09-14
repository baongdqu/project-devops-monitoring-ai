# -*- coding: utf-8 -*-
import os
import sys
import time
import asyncio
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pathlib import Path

# Thêm đường dẫn project vào sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.agent.memory import init_chat_db, create_thread, get_messages, save_message
from backend.agent.graph import create_agent_graph
from langchain_core.messages import HumanMessage, AIMessage

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("AITelegramServer")

# Cache Graph và User Threads
_graph = None
user_threads = {}

def get_graph():
    global _graph
    if _graph is None:
        _graph = create_agent_graph()
    return _graph

async def get_or_create_thread(user_id: str, name: str) -> str:
    if user_id in user_threads:
        return user_threads[user_id]
    th_id = f"tele_{user_id}"
    await create_thread(th_id, f"Telegram: {name}")
    user_threads[user_id] = th_id
    return th_id

# ── Telegram Handlers ──
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome = (
        f"👋 Xin chào *{user.first_name}*!\n\n"
        "Tôi là **AI Agent & DevOps Assistant** chạy trực tiếp trên **Microsoft Azure Container Apps**.\n\n"
        "🛡️ *Bảo mật Guardrail:* Hệ thống tích hợp cơ chế **Human-in-the-loop** phê duyệt xác nhận trước mọi tác vụ hạ tầng nhạy cảm.\n\n"
        "💡 *Bạn có thể:*\n"
        "• Hỏi đáp kiến thức hoặc tra cứu Web\n"
        "• Kiểm tra tình trạng sức khỏe ứng dụng trên Azure: `/status`\n"
        "• Scale ứng dụng Container: `/scale 2` (có nút phê duyệt)\n"
        "• Reset luồng trò chuyện: `/new`\n"
        "• Trợ giúp: `/help`\n\n"
        "Hãy nhắn tin trực tiếp để bắt đầu!"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)

async def new_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    import uuid
    th_id = f"tele_{user.id}_{uuid.uuid4().hex[:4]}"
    await create_thread(th_id, f"Telegram: {user.first_name}")
    user_threads[str(user.id)] = th_id
    await update.message.reply_text("🔄 Đã khởi tạo luồng trò chuyện mới!")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *Hướng dẫn ChatOps & AI Agent:*\n\n"
        "- Gửi câu hỏi bất kỳ bằng tiếng Việt hoặc tiếng Anh.\n"
        "- Ra lệnh tự nhiên: *'Kiểm tra tình trạng urlshortener trên Azure'*, *'Scale app lên 2 replicas'*, *'Tra cứu thời tiết Hà Nội hôm nay'*.\n"
        "- Lệnh tắt: `/status`, `/scale <số_replicas>`, `/new`.\n"
        "- **Human-in-the-loop Guardrail**: Mọi lệnh thay đổi hạ tầng đều yêu cầu Admin bấm xác nhận qua nút bấm tương tác."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from backend.tools.azure_tools import aca_get_service_status
    sent = await update.message.reply_text("⏳ Đang truy vấn Azure Container Apps...")
    res = await aca_get_service_status.ainvoke({})
    await sent.edit_text(res, parse_mode=ParseMode.MARKDOWN)

async def scale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Cú pháp: `/scale <số_replicas>` (ví dụ: `/scale 2`)", parse_mode=ParseMode.MARKDOWN)
        return
    reps = int(args[0])
    
    # Human-in-the-loop: Gửi Inline Keyboard phê duyệt
    keyboard = [
        [
            InlineKeyboardButton("✅ Xác Nhận Phê Duyệt", callback_data=f"approve_scale:{reps}"),
            InlineKeyboardButton("❌ Hủy Bỏ Lệnh", callback_data="cancel_scale")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    confirm_text = (
        f"🛡️ **[HUMAN-IN-THE-LOOP GUARDRAIL] YÊU CẦU PHÊ DUYỆT**\n\n"
        f"Bạn đang yêu cầu thay đổi tài nguyên trên Microsoft Azure:\n"
        f"• **Hành động**: Scale Azure Container App\n"
        f"• **Số Replicas Mục Tiêu**: `{reps}` (Min: {reps}, Max: {max(reps, 3)})\n"
        f"• **Người yêu cầu**: {update.effective_user.first_name} (ID: `{update.effective_user.id}`)\n\n"
        f"⚠️ *Hệ thống sẽ không thực thi lệnh nếu chưa có sự phê duyệt thủ công của bạn.*"
    )
    await update.message.reply_text(confirm_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý nút bấm Human-in-the-loop xác nhận thực thi."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("approve_scale:"):
        reps = int(data.split(":")[1])
        await query.edit_message_text(f"⏳ **[ĐÃ PHÊ DUYỆT]** Đang tiến hành scale Azure Container Apps lên {reps} replicas...")
        
        from backend.tools.azure_tools import execute_approved_scale
        res = execute_approved_scale(min_replicas=reps, max_replicas=max(reps, 3))
        await query.message.reply_text(res)
    elif data == "cancel_scale":
        await query.edit_message_text("❌ **[ĐÃ HỦY BỎ]** Lệnh thay đổi hạ tầng đã bị người vận hành hủy an toàn.")

async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return
    user = update.effective_user
    chat_id = str(update.effective_chat.id)
    th_id = await get_or_create_thread(str(user.id), user.first_name)

    # Kiểm tra intent scale bằng ngôn ngữ tự nhiên để kích hoạt Human-in-the-loop Guardrail
    import re
    scale_match = re.search(r"(?:scale|tăng|giảm|chỉnh|điều chỉnh).+?(\d+)\s*(?:pod|replica|bản)", text, re.IGNORECASE)
    if scale_match:
        reps = int(scale_match.group(1))
        keyboard = [
            [
                InlineKeyboardButton("✅ Xác Nhận Phê Duyệt", callback_data=f"approve_scale:{reps}"),
                InlineKeyboardButton("❌ Hủy Bỏ Lệnh", callback_data="cancel_scale")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        confirm_text = (
            f"🛡️ **[HUMAN-IN-THE-LOOP GUARDRAIL] YÊU CẦU PHÊ DUYỆT**\n\n"
            f"AI nhận diện yêu cầu thay đổi tài nguyên hạ tầng Azure Container Apps:\n"
            f"• **Ứng dụng**: `urlshortener-app` (Resource Group: `rg-devops-aca`)\n"
            f"• **Số Replicas Mục Tiêu**: `{reps}` (Min: {reps}, Max: {max(reps, 3)})\n"
            f"• **Người yêu cầu**: {user.first_name} (ID: `{user.id}`)\n\n"
            f"⚠️ *Theo chính sách DevSecOps Guardrail, thao tác nhạy cảm này bị chặn tự động và yêu cầu sự phê duyệt thủ công của bạn để tiếp tục.*"
        )
        await update.message.reply_text(confirm_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        return

    # Hiệu ứng typing
    typing = True
    async def keep_typing():
        while typing:
            try:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            except Exception:
                pass
            await asyncio.sleep(4)
    task = asyncio.create_task(keep_typing())

    sent_msg = await update.message.reply_text("⏳ *AI đang suy nghĩ và điều phối...*", parse_mode=ParseMode.MARKDOWN)

    try:
        await save_message(th_id, "user", text)
        history = await get_messages(th_id)
        messages = []
        for h in history[-8:]:
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            elif h["role"] == "assistant":
                messages.append(AIMessage(content=h["content"]))

        state = {
            "messages": messages,
            "step_count": 0,
            "is_complete": False,
            "system_prompt": None,
            "user_id": f"tele_{user.id}",
            "model": settings.OPENROUTER_MODEL,
            "disabled_tools": []
        }

        full_response = ""
        async for event in get_graph().astream_events(state, version="v2"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and isinstance(chunk.content, str):
                    full_response += chunk.content

        if not full_response:
            full_response = "Đã thực hiện xong yêu cầu của bạn."

        await save_message(th_id, "assistant", full_response)
        
        # Gửi phản hồi kèm Human-in-the-loop button nếu phát hiện yêu cầu Guardrail
        reply_markup = None
        if "HUMAN-IN-THE-LOOP" in full_response.upper():
            # Tự động parse số replicas nếu có để tạo nút phê duyệt nhanh
            import re
            m = re.search(r"Min\s*Replicas[\*`:\s]*(\d+)", full_response, re.IGNORECASE)
            target_reps = int(m.group(1)) if m else 2
            keyboard = [
                [
                    InlineKeyboardButton("✅ Xác Nhận Phê Duyệt", callback_data=f"approve_scale:{target_reps}"),
                    InlineKeyboardButton("❌ Hủy Bỏ Lệnh", callback_data="cancel_scale")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

        if len(full_response) <= 4000:
            try:
                await sent_msg.edit_text(full_response, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
            except Exception:
                await sent_msg.edit_text(full_response, reply_markup=reply_markup)
        else:
            await sent_msg.edit_text(full_response[:4000])
            for i in range(4000, len(full_response), 4000):
                await update.message.reply_text(full_response[i:i+4000])

    except Exception as e:
        logger.error(f"Lỗi chat: {e}", exc_info=True)
        await sent_msg.edit_text(f"❌ Lỗi: {str(e)}")
    finally:
        typing = False
        task.cancel()

# ── FastAPI Application (Health Check + Telegram Runner) ──
tele_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global tele_app
    await init_chat_db()
    token = settings.TELEGRAM_BOT_TOKEN
    if token:
        logger.info("Khởi động Telegram Bot Polling...")
        tele_app = ApplicationBuilder().token(token).build()
        tele_app.add_handler(CommandHandler("start", start_cmd))
        tele_app.add_handler(CommandHandler("new", new_cmd))
        tele_app.add_handler(CommandHandler("help", help_cmd))
        tele_app.add_handler(CommandHandler("status", status_cmd))
        tele_app.add_handler(CommandHandler("scale", scale_cmd))
        tele_app.add_handler(CallbackQueryHandler(handle_approval_callback))
        tele_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message))

        await tele_app.initialize()
        await tele_app.start()
        await tele_app.updater.start_polling()
        logger.info("✅ Telegram Bot Polling đang hoạt động!")
    yield
    if tele_app and tele_app.updater:
        logger.info("Đang dừng Telegram Bot Polling...")
        await tele_app.updater.stop()
        await tele_app.stop()
        await tele_app.shutdown()

api_server = FastAPI(
    title="AI Agent Telegram Bot Server",
    description="Container chạy Telegram Bot tích hợp LangGraph AI & HTTP Healthcheck cho Azure Container Apps",
    version="1.0.0",
    lifespan=lifespan
)

@api_server.get("/health")
async def health_check():
    return JSONResponse({
        "status": "healthy",
        "service": "ai-telegram-agent",
        "platform": "Azure Container Apps (ACA)",
        "telegram_active": tele_app is not None and tele_app.updater.running if tele_app else False
    })

@api_server.get("/")
async def root():
    return JSONResponse({
        "message": "AI Agent Telegram Bot is Running on Azure Container Apps.",
        "health_endpoint": "/health"
    })

def main():
    port = settings.PORT
    host = settings.HOST
    logger.info(f"Khởi động Web Server tại {host}:{port}...")
    uvicorn.run(api_server, host=host, port=port)

if __name__ == "__main__":
    main()
