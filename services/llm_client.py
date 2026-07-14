"""
services/llm_client.py — LLM abstraction layer.

Supports: Gemini, OpenAI, Anthropic, DeepSeek, Groq, OpenRouter.
Primary: Google Gemini 2.0 Flash (free, fast, high quality).

All calls are synchronous to match FastAPI's default thread model.
Includes retry logic with exponential backoff.
"""

import json
import time
import re
import urllib.request
import urllib.error
from typing import Optional

import config


# ── Default model names per provider ─────────────────────────────────────────

DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash-exp",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "deepseek": "deepseek-chat",
    "groq": "llama-3.1-70b-versatile",
    "openrouter": "google/gemini-2.0-flash-exp:free",
}


class LLMClient:
    """
    Unified LLM client that abstracts provider differences.
    
    Usage:
        client = LLMClient()
        response = client.complete(system="...", user="...")
    """

    def __init__(self):
        self.provider = config.LLM_PROVIDER
        self.api_key = config.LLM_API_KEY
        self.model = config.LLM_MODEL or DEFAULT_MODELS.get(self.provider, "")
        self.timeout = config.LLM_TIMEOUT
        self.temperature = config.LLM_TEMPERATURE
        self.max_tokens = config.LLM_MAX_TOKENS

    def complete(self, system: str, user: str, retries: int = 2) -> str:
        """
        Call the LLM and return the text response.
        
        Args:
            system: System prompt (persona + scoring criteria)
            user: User prompt (the specific composition task)
            retries: Number of retry attempts on failure
            
        Returns:
            LLM response text
            
        Raises:
            RuntimeError: If all retries fail
        """
        last_error = None
        for attempt in range(retries + 1):
            try:
                if self.provider == "gemini":
                    return self._call_gemini(system, user)
                elif self.provider == "openai":
                    return self._call_openai(system, user)
                elif self.provider == "anthropic":
                    return self._call_anthropic(system, user)
                elif self.provider == "deepseek":
                    return self._call_openai_compatible(
                        system, user,
                        "https://api.deepseek.com/v1/chat/completions",
                    )
                elif self.provider == "groq":
                    return self._call_openai_compatible(
                        system, user,
                        "https://api.groq.com/openai/v1/chat/completions",
                    )
                elif self.provider == "openrouter":
                    return self._call_openai_compatible(
                        system, user,
                        "https://openrouter.ai/api/v1/chat/completions",
                        extra_headers={"HTTP-Referer": "https://magicpin.com"},
                    )
                else:
                    raise ValueError(f"Unknown LLM provider: {self.provider}")

            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))  # backoff: 1.5s, 3s
                    continue
                break

        raise RuntimeError(f"LLM call failed after {retries + 1} attempts: {last_error}")

    # ── Provider implementations ──────────────────────────────────────────────

    def _call_gemini(self, system: str, user: str) -> str:
        """Call Google Gemini API using httpx."""
        import httpx
        # Combine system + user as Gemini handles them differently
        full_prompt = f"{system}\n\n{user}"
        
        body = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        }

        model = self.model or "gemini-2.0-flash-exp"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        
        headers = {
            "Content-Type": "application/json", 
            "x-goog-api-key": self.api_key
        }
        
        with httpx.Client(timeout=httpx.Timeout(self.timeout)) as client:
            resp = client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def _call_openai(self, system: str, user: str) -> str:
        """Call OpenAI API."""
        return self._call_openai_compatible(
            system, user,
            "https://api.openai.com/v1/chat/completions",
        )

    def _call_openai_compatible(
        self,
        system: str,
        user: str,
        endpoint: str,
        extra_headers: Optional[dict] = None,
    ) -> str:
        """Call any OpenAI-compatible API."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }).encode("utf-8")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        req = urllib.request.Request(endpoint, data=body, headers=headers)
        resp = urllib.request.urlopen(req, timeout=self.timeout)
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]

    def _call_anthropic(self, system: str, user: str) -> str:
        """Call Anthropic API."""
        model = self.model or "claude-3-5-haiku-20241022"
        body = json.dumps({
            "model": model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
        )
        resp = urllib.request.urlopen(req, timeout=self.timeout)
        data = json.loads(resp.read().decode("utf-8"))
        return data["content"][0]["text"]

    def available(self) -> bool:
        """Check if LLM is configured and available."""
        if self.provider == "gemini" and self.api_key:
            return True
        if self.provider in ("openai", "anthropic", "deepseek", "groq", "openrouter") and self.api_key:
            return True
        return False


def parse_json_response(text: str) -> dict:
    """
    Extract JSON from LLM response text.
    Handles cases where the model wraps JSON in markdown code blocks.
    """
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding any JSON object in the text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")


# Global singleton
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
