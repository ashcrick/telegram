import os
import logging
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
numeric_level = getattr(logging, log_level, logging.INFO)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=numeric_level
)

class Settings(BaseSettings):
    # Telegram settings
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    webhook_url: str = os.getenv("WEBHOOK_URL", "")
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")
    telegram_api_url: str = os.getenv("TELEGRAM_API_URL", "https://api.telegram.org")
    
    # Network settings
    http_proxy: str = os.getenv("HTTP_PROXY", "")
    https_proxy: str = os.getenv("HTTPS_PROXY", "")
    max_connection_retries: int = int(os.getenv("MAX_CONNECTION_RETRIES", "5"))
    
    # OpenAI settings
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # App settings
    environment: str = os.getenv("ENVIRONMENT", "development")
    log_level: str = log_level
    
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"
    
    @property
    def using_proxy(self) -> bool:
        return bool(self.http_proxy or self.https_proxy)
    
    def configure_proxies(self):
        """Configure proxies for the application."""
        if self.http_proxy or self.https_proxy:
            proxies = {}
            if self.http_proxy:
                proxies["http"] = self.http_proxy
            if self.https_proxy:
                proxies["https"] = self.https_proxy
                
            # Set environment variables for libraries that use them
            os.environ["HTTP_PROXY"] = self.http_proxy if self.http_proxy else ""
            os.environ["HTTPS_PROXY"] = self.https_proxy if self.https_proxy else ""
            
            return proxies
        return None

settings = Settings()

# Apply proxy configuration if available
if settings.using_proxy:
    proxies = settings.configure_proxies()
    logging.info(f"Using proxy configuration: {proxies}")

# Log the current configuration (without sensitive data)
logging.debug(f"Environment: {settings.environment}")
logging.debug(f"Log level: {settings.log_level}")
logging.debug(f"Using Telegram API URL: {settings.telegram_api_url}")
logging.debug(f"Using OpenAI model: {settings.openai_model}")
logging.debug(f"Max connection retries: {settings.max_connection_retries}")
logging.debug(f"Using proxies: {settings.using_proxy}")
logging.debug(f"Webhook enabled: {settings.is_production}")

# Check for required configuration
if not settings.telegram_bot_token:
    logging.warning("Telegram bot token is not set!")

if settings.is_production and not (settings.webhook_url and settings.webhook_secret):
    logging.warning("Production mode requires webhook URL and secret to be set!") 