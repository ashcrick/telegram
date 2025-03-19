# Telegram AI Bot

A Telegram bot integrated with OpenAI's API and FastAPI framework. This bot responds to user messages with AI-generated content, supports both development (polling) and production (webhook) environments, and includes robust error handling and retry mechanisms.

## Features

- Telegram bot integration with message handling
- OpenAI API integration with streaming responses
- FastAPI backend for configuration and webhook handling
- Development mode with polling (automatic reconnection)
- Production mode with webhook support
- Configuration endpoints for bot management
- Robust error handling and retry mechanisms
- Proxy support for restricted networks
- Flexible configuration through environment variables

## Setup

### Prerequisites

- Python 3.8+ 
- A Telegram bot token (obtain from BotFather)
- An OpenAI API key

### Installation

1. Clone the repository
```
git clone <repository-url>
cd telegram-ai-bot
```

2. Create a virtual environment
```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```
pip install -r requirements.txt
```

4. Create a `.env` file based on `.env.example`
```
cp .env.example .env
```

5. Edit the `.env` file and add your credentials:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
ENVIRONMENT=development  # or production
```

## Running the Bot

### Development Mode

In development mode, the bot uses polling to receive updates from Telegram:

```
python main.py
```

The bot includes automatic reconnection logic if the Telegram API is temporarily unreachable.

### Production Mode

1. Set `ENVIRONMENT=production` in your `.env` file
2. Set your webhook URL: `WEBHOOK_URL=https://your-domain.com/webhook`
3. Set a webhook secret: `WEBHOOK_SECRET=your_secret_here`
4. Run the application with a production ASGI server:
```
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /status`: Check the bot's status and connection state
- `POST /set-webhook`: Manually set the webhook
- `POST /remove-webhook`: Remove the webhook
- `POST /webhook`: Endpoint for Telegram to send updates (used in production)
- `POST /restart`: Restart the bot (useful for recovery after errors)

## Usage

1. Start a chat with your bot on Telegram
2. Send any message
3. The bot will respond with AI-generated content from OpenAI

## Troubleshooting

### Connection Issues

If you're experiencing connection issues:

1. Check that your Telegram bot token is valid
2. Ensure you have internet connectivity
3. If behind a firewall or proxy, set the HTTP_PROXY and HTTPS_PROXY environment variables
4. Check the logs for detailed error information
5. Try restarting the bot using the `/restart` API endpoint

### Webhook Issues

For webhook deployment:

1. Ensure your server is publicly accessible
2. SSL/TLS is required by Telegram (HTTPS only)
3. The webhook URL must be properly configured in the `.env` file
4. Set a strong webhook secret to secure your endpoint

## Advanced Configuration

Configure additional settings in your `.env` file:

```
# OpenAI model to use
OPENAI_MODEL=gpt-3.5-turbo

# Network settings for proxies
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=http://proxy.example.com:8080

# Logging level
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Development

The application structure:

- `main.py`: The main FastAPI application
- `telegram_bot.py`: Telegram bot implementation with retry logic
- `ai_service.py`: OpenAI integration with error handling
- `config.py`: Configuration management 