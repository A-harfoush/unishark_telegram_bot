import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from aiohttp import web

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    force=True
)
# Force output to stdout/stderr immediately (no buffering)
logging.getLogger().handlers[0].flush = lambda: None
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 8000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message when the command /start is issued."""
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
    """Handle regular text messages."""
    message_text = update.message.text
    
    if message_text == "كسمك":
        await update.message.reply_text("الله يسامحك")
    elif "حرفوش" in message_text:
        await update.message.reply_text("حرفوش عمك")

async def health_check(request):
    """Health check endpoint for Choreo"""
    logger.debug("Health check pinged")
    return web.Response(text='OK\n', status=200)

async def run_bot_with_health_check():
    """Run bot with webhook and health check on single port"""
    logger.info(f"Initializing bot on port {PORT}...")
    logger.info(f"Token configured: {TELEGRAM_BOT_TOKEN[:10]}...")
    logger.info(f"Webhook URL: {WEBHOOK_URL}")
    
    # Create application
    try:
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    except Exception as e:
        logger.error(f"Failed to create application: {e}", exc_info=True)
        raise
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Initialize the application
    try:
        await application.initialize()
        await application.start()
        logger.info("Application initialized and started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}", exc_info=True)
        raise
    
    # Set up webhook
    webhook_path = f"/{TELEGRAM_BOT_TOKEN}"
    webhook_url = WEBHOOK_URL + TELEGRAM_BOT_TOKEN
    
    logger.info(f"Setting webhook to: {webhook_url}")
    try:
        await application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        logger.info("Webhook set successfully")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}", exc_info=True)
        raise
    
    # Create web app with routes
    web_app = web.Application()
    
    # Health check endpoints
    web_app.router.add_get('/', health_check)
    web_app.router.add_get('/health', health_check)
    
    # Webhook endpoint - handle Telegram updates
    async def telegram_webhook(request):
        """Handle Telegram webhook POST requests"""
        try:
            logger.info("Received webhook POST request")
            data = await request.json()
            update = Update.de_json(data, application.bot)
            await application.update_queue.put(update)
            logger.info(f"Update queued successfully: {update.update_id}")
            return web.Response(status=200)
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            return web.Response(status=500)
    
    web_app.router.add_post(webhook_path, telegram_webhook)
    
    # Start web server
    try:
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        logger.info(f"Web server started on 0.0.0.0:{PORT}")
    except Exception as e:
        logger.error(f"Failed to start web server: {e}", exc_info=True)
        raise
    
    logger.info(f"✅ Bot is running!")
    logger.info(f"   - Webhook: {webhook_url}")
    logger.info(f"   - Health check: http://0.0.0.0:{PORT}/health")
    logger.info(f"   - Listening on: 0.0.0.0:{PORT}")
    logger.info("Bot will stay alive indefinitely. Press Ctrl+C to stop.")
    
    # Log a heartbeat every 5 minutes to confirm bot is still alive
    async def heartbeat():
        while True:
            await asyncio.sleep(300)  # 5 minutes
            logger.info("💓 Heartbeat: Bot is still running")
            # Ping ourselves to prevent idle timeout
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(f'http://localhost:{PORT}/health', timeout=5) as resp:
                        if resp.status == 200:
                            logger.debug("Self-ping successful")
            except Exception as e:
                logger.warning(f"Self-ping failed: {e}")
    
    heartbeat_task = asyncio.create_task(heartbeat())
    
    # Keep the application running to process updates from the queue
    try:
        await asyncio.Event().wait()
    finally:
        heartbeat_task.cancel()
        await application.stop()
        await application.shutdown()
        await runner.cleanup()

async def run_bot_polling():
    """Run bot with polling for local testing"""
    logger.info("Starting bot in polling mode (local testing)...")
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Delete webhook to enable polling
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook deleted, starting polling...")
    
    # Start polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    logger.info("✅ Bot is running in polling mode!")
    
    try:
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

def main() -> None:
    """Start the bot."""
    logger.info("=== UniShark Telegram Bot Starting ===")
    logger.info(f"Python version: {os.sys.version}")
    logger.info(f"PORT: {PORT}")
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. The bot cannot start.")
        return
    
    logger.info(f"Token present: {TELEGRAM_BOT_TOKEN[:10]}...{TELEGRAM_BOT_TOKEN[-4:]}")
    
    # Check if running locally (no valid webhook URL or localhost)
    is_local = not WEBHOOK_URL or "localhost" in WEBHOOK_URL or "127.0.0.1" in WEBHOOK_URL
    
    if is_local:
        logger.info("Local environment detected - using polling mode")
    else:
        logger.info(f"Production environment detected - using webhook mode")
        logger.info(f"WEBHOOK_URL: {WEBHOOK_URL}")
    
    try:
        if is_local:
            asyncio.run(run_bot_polling())
        else:
            asyncio.run(run_bot_with_health_check())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise  # Re-raise to show full error in logs

if __name__ == "__main__":
    main()
