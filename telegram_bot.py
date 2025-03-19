import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)
from telegram.error import TimedOut, NetworkError, RetryAfter
from config import settings
from ai_service import generate_ai_response

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.application = None
        self.max_retries = 5
        self.retry_delay = 3
        self._shutdown_lock = asyncio.Lock()

    async def start_command(self, update: Update, context: CallbackContext) -> None:
        """Send a message when the command /start is issued."""
        await update.message.reply_text(
            "Hi! I'm your AI assistant. Send me a message and I'll respond with AI-generated content!"
        )

    async def help_command(self, update: Update, context: CallbackContext) -> None:
        """Send a message when the command /help is issued."""
        await update.message.reply_text(
            "Just send me any text and I'll generate a response for you using AI."
        )

    async def handle_message(self, update: Update, context: CallbackContext) -> None:
        """Handle the user message and respond with AI-generated content."""
        if not update.message or not update.message.text:
            return
            
        user_message = update.message.text
        user_id = update.effective_user.id
        username = update.effective_user.username or str(user_id)
        
        logger.info(f"Received message from {username}: {user_message}")
        
        # Let the user know we're processing their request
        processing_message = await update.message.reply_text("Thinking...")
        
        # Initialize an empty response
        full_response = ""
        
        try:
            # Send initial message that will be updated
            async for response_chunk in generate_ai_response(user_message):
                full_response += response_chunk
                
                # Update the message periodically to show streaming effect
                # We don't want to hit Telegram's API rate limits
                if len(full_response) % 20 == 0:
                    try:
                        await processing_message.edit_text(full_response)
                        await asyncio.sleep(0.5)
                    except RetryAfter as e:
                        # Handle rate limiting
                        logger.warning(f"Rate limited. Waiting for {e.retry_after} seconds")
                        await asyncio.sleep(e.retry_after)
                        await processing_message.edit_text(full_response)
                    except (TimedOut, NetworkError) as e:
                        # Handle network errors
                        logger.warning(f"Network error when updating message: {e}")
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"Error updating message: {e}")
            
            # Send the final response if there's anything left
            if full_response:
                try:
                    await processing_message.edit_text(full_response)
                except Exception as e:
                    logger.error(f"Error sending final message: {e}")
                    # Try sending as a new message if editing fails
                    try:
                        await update.message.reply_text(full_response)
                    except Exception as e2:
                        logger.error(f"Also failed to send as new message: {e2}")
            else:
                await processing_message.edit_text("I couldn't generate a response. Please try again.")
                
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            await processing_message.edit_text(f"Sorry, an error occurred while processing your request.")

    async def error_handler(self, update: object, context: CallbackContext) -> None:
        """Log errors caused by updates."""
        logger.error(f"Exception while handling an update: {context.error}")
        
        # Add specific error handling based on error type
        error = context.error
        if isinstance(error, TimedOut):
            logger.warning("Request timed out")
        elif isinstance(error, NetworkError):
            logger.warning("Network error occurred")
        elif isinstance(error, RetryAfter):
            logger.warning(f"Rate limited. Retry after {error.retry_after} seconds")
            await asyncio.sleep(error.retry_after)

    async def setup_application(self) -> Application:
        """Set up the Telegram application."""
        if self.application:
            logger.warning("Application already exists, returning existing instance")
            return self.application
            
        # Build application with custom request parameters to improve reliability
        application_builder = Application.builder().token(settings.telegram_bot_token)
        
        # Customize connection pool parameters for better reliability
        application_builder.connection_pool_size(8)
        application_builder.connect_timeout(15.0)  # Increase from default
        application_builder.read_timeout(15.0)     # Increase from default
        application_builder.write_timeout(15.0)    # Increase from default
        
        application = application_builder.build()

        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Add error handler
        application.add_error_handler(self.error_handler)
        
        self.application = application
        return self.application

    async def shutdown(self):
        """Safely shutdown the application if it exists."""
        async with self._shutdown_lock:
            if self.application:
                logger.info("Shutting down bot application...")
                try:
                    if getattr(self.application, "updater", None) and self.application.updater.running:
                        await self.application.updater.stop()
                    await self.application.shutdown()
                    logger.info("Bot application shutdown completed")
                except Exception as e:
                    logger.error(f"Error during application shutdown: {e}")
                finally:
                    self.application = None

    async def run_polling_mode(self):
        """Run the bot in polling mode with automatic reconnection."""
        logger.info("Starting bot in polling mode")
        
        # Create a new application if needed
        if not self.application:
            self.application = await self.setup_application()

        max_retries = 5
        current_retry = 0
        base_delay = 5  # Starting delay in seconds

        while current_retry < max_retries:
            try:
                # Initialize the application
                logger.info(f"Initializing application (attempt {current_retry + 1}/{max_retries})")
                await self.application.initialize()
                
                # Start polling
                logger.info("Starting polling...")
                await self.application.start_polling(drop_pending_updates=True)
                logger.info("Polling started successfully")
                
                # Run the application - this blocks until the application is stopped
                await self.application.updater.start_polling()
                
                # If we get here, polling has stopped normally
                logger.info("Polling has stopped normally")
                break
                
            except (TimedOut, NetworkError) as e:
                current_retry += 1
                delay = base_delay * (2 ** (current_retry - 1))  # Exponential backoff
                delay = min(delay, 300)  # Cap at 5 minutes
                
                logger.warning(f"Network error in polling: {e}. Retrying in {delay} seconds...")
                
                # Clean up before retry
                try:
                    if self.application and hasattr(self.application, "updater"):
                        if self.application.updater.running:
                            await self.application.updater.stop()
                except Exception as shutdown_err:
                    logger.error(f"Error stopping updater before retry: {shutdown_err}")
                
                # Wait before retrying
                await asyncio.sleep(delay)
                
            except Exception as e:
                logger.error(f"Unexpected error in polling: {e}")
                break
                
        # Always clean up at the end
        await self.shutdown()

    async def setup_webhook(self) -> bool:
        """Set up webhook mode."""
        logger.info("Setting up webhook mode")
        
        # Create a new application if needed
        if not self.application:
            self.application = await self.setup_application()
            
        try:
            # Initialize the application
            await self.application.initialize()
            
            # Set the webhook
            webhook_url = settings.webhook_url
            secret_token = settings.webhook_secret
            
            if not webhook_url:
                logger.error("Webhook URL not configured")
                await self.shutdown()
                return False
                
            logger.info(f"Setting webhook to URL: {webhook_url}")
            await self.application.bot.set_webhook(
                url=webhook_url,
                secret_token=secret_token,
                drop_pending_updates=True
            )
            
            logger.info("Webhook setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up webhook: {e}")
            await self.shutdown()
            return False

    def get_application(self) -> Application:
        """Return the Telegram application instance."""
        return self.application 