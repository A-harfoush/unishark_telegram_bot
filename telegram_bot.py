import os
import logging
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, Dispatcher, ContextTypes

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    force=True
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# FastAPI app
app = FastAPI()

# Pydantic model for Telegram webhook data (validates incoming JSON)
class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[Dict[str, Any]] = None
    edited_message: Optional[Dict[str, Any]] = None
    # Add other fields as needed from Telegram's Update object

# Your handlers (adapted for async)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
   
    logger.info(f"User {user.full_name} (ID: {user.id}) started the bot. Chat ID: {chat_id}")
   
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
   
    keyboard = [
        [InlineKeyboardButton("Go to UniShark Website", url="https://unishark.site")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
   
    await update.message.reply_html(
        message,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message_text = update.message.text
   
    if message_text == "كسمك":
        await update.message.reply_text("الله يسامحك")
    elif "حرفوش" in message_text:
        await update.message.reply_text("حرفوش عمك")

# Webhook endpoint
@app.post("/{token}")
async def telegram_webhook(token: str, request: Request):
    if token != TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        raise HTTPException(status_code=500, detail="Bot token not configured")
    
    try:
        data = await request.json()
        logger.info("Received webhook POST request")
        
        # Create bot and dispatcher per request (serverless)
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        await application.initialize()  # Required for async setup
        
        dispatcher = Dispatcher(application.bot, None)
        
        # Add handlers
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Process update
        update = Update.de_json(data, application.bot)
        await dispatcher.process_update(update)
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal error")

# Health check endpoints
@app.get("/")
@app.get("/health")
async def health_check():
    logger.debug("Health check pinged")
    return {"status": "OK"}

# No main() or polling—serverless handles invocation
