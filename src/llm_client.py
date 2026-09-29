"""
src/llm_client.py — Secure, configurable OpenRouter / OpenAI API client.

SECURITY:
- Reads OPENROUTER_API_KEY from .env only.
- Never prints, logs, or exposes the API key in exceptions or messages.
- Request headers containing the key are never logged or leaked.
- Configurable model via environment variable.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from openai import OpenAI, APIError, RateLimitError, APITimeoutError

from src.config import OPENROUTER_BASE_URL, DEFAULT_MODEL, ROOT

# Ensure local .env is loaded
load_dotenv(ROOT / ".env", override=False)


class LLMClientError(Exception):
    """Base exception for LLM client that never exposes secret credentials."""
    pass


class LLMClient:
    """Configurable client for LLM API calls via OpenRouter."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        timeout: float = 30.0,
    ) -> None:
        raw_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not raw_key or not raw_key.strip():
            raise LLMClientError(
                "OPENROUTER_API_KEY is not set. Please provide it in the local .env file."
            )

        self._api_key = raw_key.strip()
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL)
        self.model = (
            model
            or os.getenv("OPENROUTER_MODEL")
            or os.getenv("OPENAI_MODEL")
            or DEFAULT_MODEL
        )
        self.max_retries = max_retries
        self.timeout = timeout

        # Initialize OpenAI client pointing to OpenRouter
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self._api_key,
            timeout=self.timeout,
            max_retries=0,  # We handle retries explicitly with backoff
        )

    def __repr__(self) -> str:
        # Never expose api_key in string representation
        return f"<LLMClient model='{self.model}' base_url='{self.base_url}'>"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 400,
    ) -> Dict[str, Any]:
        """
        Execute completion with exponential backoff on transient errors.

        Returns a dictionary with:
        - raw_text: string response
        - model: model identifier used
        - extracted_at: UTC timestamp ISO string
        - prompt_tokens: count or None
        - completion_tokens: count or None
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        attempt = 0
        backoff_delay = 1.0

        while attempt < self.max_retries:
            attempt += 1
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                choice = response.choices[0]
                raw_content = choice.message.content or ""

                usage = getattr(response, "usage", None)
                prompt_tokens = usage.prompt_tokens if usage else None
                completion_tokens = usage.completion_tokens if usage else None

                return {
                    "raw_text": raw_content,
                    "model": self.model,
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "attempts": attempt,
                }

            except (RateLimitError, APITimeoutError, APIError) as e:
                # Sanitize error message to ensure no key leakage
                err_msg = str(e)
                if self._api_key in err_msg:
                    err_msg = err_msg.replace(self._api_key, "[REDACTED_API_KEY]")

                if attempt >= self.max_retries:
                    raise LLMClientError(
                        f"LLM API request failed after {attempt} attempts: {type(e).__name__} - {err_msg}"
                    ) from None

                time.sleep(backoff_delay)
                backoff_delay *= 2.0

            except Exception as e:
                err_msg = str(e)
                if self._api_key in err_msg:
                    err_msg = err_msg.replace(self._api_key, "[REDACTED_API_KEY]")
                raise LLMClientError(f"Unexpected error in LLMClient: {type(e).__name__} - {err_msg}") from None

        raise LLMClientError(f"LLM API request failed after {self.max_retries} attempts.")
