import asyncio
import logging
import uvicorn
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from config import settings
from telegram_bot import TelegramBot
from pydantic import BaseModel
from telegram import Update
from telegram.error import TelegramError, TimedOut, NetworkError
import json

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Telegram AI Bot API")

# Initialize Telegram bot as a global object
bot = TelegramBot()

class BotStatus(BaseModel):
    """Model for the bot status response."""
    status: str
    environment: str
    webhook_enabled: bool
    connected: bool = False

# Global status for bot connection
bot_connected = False

@app.on_event("startup")
async def startup_event():
    """Initialize the bot when the FastAPI app starts."""
    global bot_connected
    
    logger.info("Initializing Telegram bot")
    
    # Set up the application
    try:
        await bot.setup_application()
        
        # Always use webhook mode for both production and development
        webhook_success = await bot.setup_webhook()
        if webhook_success:
            bot_connected = True
            logger.info(f"Bot ready for webhook mode (environment: {settings.environment})")
        else:
            logger.error("Failed to set up webhook")
        
        logger.info("Bot initialization complete")
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
        # We don't want to crash the API server if the bot fails to start
        # The status endpoint will show that the bot is not connected

@app.post("/webhook")
async def webhook(request: Request):
    """
    Handle incoming webhook updates from Telegram.
    This endpoint should be set as the webhook URL in Telegram.
    """
    try:
        # Verify secret token for security
        telegram_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if settings.is_production and telegram_secret != settings.webhook_secret:
            logger.warning("Unauthorized webhook attempt")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        
        # Parse the update
        update_data = await request.json()
        application = bot.get_application()
        
        if not application:
            logger.error("No telegram application available")
            return JSONResponse(content={"status": "error", "message": "Bot not initialized"}, status_code=500)
        
        # Convert the JSON data to a Telegram Update object
        update = Update.de_json(data=update_data, bot=application.bot)
        
        # Process the update with the application
        await application.process_update(update)
        
        # Return a 200 OK response to acknowledge receipt
        return JSONResponse(content={"status": "ok"})
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook request")
        return JSONResponse(
            content={"status": "error", "message": "Invalid JSON"}, 
            status_code=400
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/webhook/info")
async def webhook_info():
    """Get information about the current webhook setup."""
    try:
        application = bot.get_application()
        if not application or not application.bot:
            return JSONResponse(
                content={"status": "error", "message": "Bot not initialized"}, 
                status_code=500
            )
            
        # Get webhook info from Telegram
        webhook_info = await application.bot.get_webhook_info()
        
        return {
            "url": webhook_info.url,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "max_connections": webhook_info.max_connections,
            "ip_address": webhook_info.ip_address,
            "last_error_date": webhook_info.last_error_date,
            "last_error_message": webhook_info.last_error_message,
            "last_synchronization_error_date": webhook_info.last_synchronization_error_date,
        }
    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)}, 
            status_code=500
        )

@app.get("/status")
async def get_status() -> BotStatus:
    """
    Get the current status of the bot.
    """
    global bot_connected
    
    # Check if the application is available
    application = bot.get_application()
    bot_connected = application is not None
    
    return BotStatus(
        status="running",
        environment=settings.environment,
        webhook_enabled=True,  # Always using webhook mode now
        connected=bot_connected
    )

@app.post("/set-webhook")
async def set_webhook_post():
    """
    Manually set the webhook for the bot (POST method).
    """
    if not settings.webhook_url:
        raise HTTPException(status_code=400, detail="Webhook URL not configured")
    
    try:
        # Initialize webhook
        success = await bot.setup_webhook()
        if success:
            return {"status": "webhook set successfully", "webhook_url": settings.webhook_url}
        else:
            return JSONResponse(
                content={"status": "error", "message": "Failed to set webhook"}, 
                status_code=500
            )
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)}, 
            status_code=500
        )

@app.get("/set-webhook")
async def set_webhook_get():
    """
    Manually set the webhook for the bot (GET method).
    """
    if not settings.webhook_url:
        raise HTTPException(status_code=400, detail="Webhook URL not configured")
    
    try:
        # Initialize webhook
        success = await bot.setup_webhook()
        if success:
            return {"status": "webhook set successfully", "webhook_url": settings.webhook_url}
        else:
            return JSONResponse(
                content={"status": "error", "message": "Failed to set webhook"}, 
                status_code=500
            )
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)}, 
            status_code=500
        )

@app.post("/remove-webhook")
async def remove_webhook():
    """
    Remove the webhook for the bot.
    """
    try:
        application = bot.get_application()
        if application and application.bot:
            await application.bot.delete_webhook()
            return {"status": "webhook removed"}
        else:
            return JSONResponse(
                content={"status": "error", "message": "Bot not initialized"}, 
                status_code=500
            )
    except Exception as e:
        logger.error(f"Error removing webhook: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)}, 
            status_code=500
        )

@app.post("/restart")
async def restart_bot(background_tasks: BackgroundTasks):
    """
    Restart the Telegram bot.
    """
    global bot_connected
    bot_connected = False
    
    try:
        # Stop current application if it exists
        await bot.shutdown()
        
        # Re-initialize the bot
        bot.__init__()
        await bot.setup_application()
        
        # Always use webhook mode
        success = await bot.setup_webhook()
        if success:
            bot_connected = True
            return {"status": "bot restarted in webhook mode"}
        else:
            return JSONResponse(
                content={"status": "error", "message": "Failed to set up webhook"}, 
                status_code=500
            )
            
    except Exception as e:
        logger.error(f"Error restarting bot: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)}, 
            status_code=500
        )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 