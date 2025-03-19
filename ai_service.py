import openai
import logging
import asyncio
from openai.types.chat import ChatCompletionChunk
from typing import Generator, AsyncGenerator
from config import settings

# Configure OpenAI with the API key
openai.api_key = settings.openai_api_key

# Set up logging
logger = logging.getLogger(__name__)

async def generate_ai_response(message: str) -> AsyncGenerator[str, None]:
    """
    Generate a streaming response from OpenAI based on the user's message.
    
    Args:
        message: The user's message text
        
    Yields:
        Chunks of the AI response as they become available
    """
    max_retries = 3
    retry_count = 0
    retry_delay = 1  # Initial delay in seconds
    
    while retry_count <= max_retries:
        try:
            # Create a streaming chat completion
            logger.debug(f"Sending request to OpenAI (model: {settings.openai_model})")
            
            # Fix: Create the OpenAI client properly first
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            
            # Fix: Use the client to create the streaming response
            stream = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": message}
                ],
                stream=True,
                timeout=30  # Timeout in seconds
            )
            
            # Process and yield chunks as they arrive
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield content
            
            # If we get here, we've successfully processed the stream
            return
                
        except openai.APITimeoutError as e:
            retry_count += 1
            if retry_count <= max_retries:
                logger.warning(f"OpenAI request timed out. Retrying ({retry_count}/{max_retries})...")
                yield f"\n[Connection timeout. Retrying...]\n"
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"OpenAI API timeout after {max_retries} retries: {e}")
                yield f"\nSorry, I'm having trouble connecting to my AI services right now. Please try again in a moment."
                
        except openai.APIConnectionError as e:
            retry_count += 1
            if retry_count <= max_retries:
                logger.warning(f"OpenAI connection error. Retrying ({retry_count}/{max_retries})...")
                yield f"\n[Connection issue. Retrying...]\n"
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error(f"OpenAI API connection error after {max_retries} retries: {e}")
                yield f"\nSorry, I'm having trouble connecting to my AI services right now. Please try again in a moment."
                
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            yield f"\nSorry, there was an error with the AI service: {str(e)}"
            break
                
        except Exception as e:
            logger.error(f"Unexpected error generating AI response: {e}")
            yield f"\nSorry, an unexpected error occurred: {str(e)}"
            break 