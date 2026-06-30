"""Wraps the Anthropic client with retry logic and clear error handling."""
import time

import anthropic
from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, MAX_RETRIES, MAX_TOKENS, MODEL_NAME, RETRY_BACKOFF_SECONDS
from logger import get_logger

logger = get_logger("claude_client")

_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Errors worth retrying (transient/server-side). Credit/auth/billing errors
# are NOT retried since retrying won't fix them.
_RETRYABLE_EXCEPTIONS = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


def ask(question: str, system_blocks: list) -> str:
    """
    Sends a question to the model with the given cached system context.
    Retries on transient failures; raises immediately on billing/auth errors
    so the caller can surface a clear, actionable message.
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = _client.messages.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                system=system_blocks,
                messages=[{"role": "user", "content": question}],
            )
            logger.info(
                "Query OK | input_tokens=%s output_tokens=%s cache_read=%s",
                response.usage.input_tokens,
                response.usage.output_tokens,
                getattr(response.usage, "cache_read_input_tokens", "n/a"),
            )
            return response.content[0].text

        except anthropic.BadRequestError as e:
            # e.g. low credit balance — won't be fixed by retrying
            logger.error("Bad request (likely billing/credits): %s", e)
            raise RuntimeError(
                "Your Anthropic API credit balance is too low or the request was "
                "invalid. Check https://console.anthropic.com/settings/billing"
            ) from e

        except anthropic.AuthenticationError as e:
            logger.error("Authentication failed: %s", e)
            raise RuntimeError(
                "Invalid API key. Check ANTHROPIC_API_KEY in your .env file."
            ) from e

        except _RETRYABLE_EXCEPTIONS as e:
            last_error = e
            wait = RETRY_BACKOFF_SECONDS * attempt
            logger.warning(
                "Transient error on attempt %d/%d (%s). Retrying in %.1fs...",
                attempt, MAX_RETRIES, type(e).__name__, wait,
            )
            time.sleep(wait)

        except anthropic.APIStatusError as e:
            logger.error("API error: %s", e)
            raise RuntimeError(f"Anthropic API error: {e}") from e

    raise RuntimeError(
        f"Failed after {MAX_RETRIES} attempts due to repeated transient errors: {last_error}"
    )
