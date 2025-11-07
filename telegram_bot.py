import os
import logging
from fastapi import FastAPI, Request, HTTPException, Response

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Token
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set")
    raise ValueError("TELEGRAM_BOT_TOKEN is missing")

# Build application (global, with updater disabled for webhook-only)
application = (
    Application.builder()
    .token(TOKEN)
    .updater(None)  # Critical for serverless webhook
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

# Add handlers globally (safe at module level)
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Your handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"User {user.full_name} (ID: {user.id}) started bot. Chat ID: {chat_id}")

    message = (
        f"<b>👋 Welcome to UniShark Bot, {user.first_name}!</b> 🦈\n\n"
        "I'm here to help you stay on top of your university tasks. Here is your unique ID to connect me to your account:\n\n"
        f"🔑 <b>Your Personal Chat ID is:</b> <code>{chat_id}</code>\n\n"
        "<b>Action Required:</b>\n"
        "1️⃣ Copy the Chat ID above.\n"
        "2️⃣ Go to your UniShark settings page.\n"
        "3️⃣ Paste the ID into the 'Telegram Chat ID' field.\n\n"
        "Once connected, I'll send you instant notifications for:\n"
        "- 📝 New Assignments\n"
        "- ❓ New Quizzes\n"
        "- ⏰ Approaching Deadlines\n\n"
        "Good luck with your studies! 🎓"
    )

    keyboard = [[InlineKeyboardButton("Go to UniShark Website", url="https://unishark.site")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(message, reply_markup=reply_markup, disable_web_page_preview=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "كسمك":
        await update.message.reply_text("الله يسامحك")
    elif "حرفوش" in text:
        await update.message.reply_text("حرفوش عمك")

# FastAPI app
app = FastAPI()

# Health check
@app.get("/")
@app.get("/health")
async def health():
    return {"status": "OK"}

# Webhook endpoint (secure with token in path)
@app.post("/{token}")
async def webhook(token: str, request: Request):
    if token != TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)

        # Per-request context (safe for serverless cold starts)
        async with application:
            await application.process_update(update)

        return Response(content="OK", status_code=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Processing failed")
