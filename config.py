"""
config.py — Central configuration for Vera Bot.
All settings are read from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# LLM Configuration
# ──────────────────────────────────────────────

# Which LLM provider to use: "gemini" | "openai" | "anthropic" | "deepseek" | "groq" | "openrouter"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")

# API key for the chosen provider
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")

# Model name (leave empty for provider default)
LLM_MODEL: str = os.getenv("LLM_MODEL", "")

# Timeout for LLM calls in seconds (judge allows 30s per endpoint)
LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "25"))

# Temperature — 0 for deterministic output (required by challenge)
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0"))

# Max tokens in LLM response
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "800"))

# ──────────────────────────────────────────────
# Bot Identity
# ──────────────────────────────────────────────

TEAM_NAME: str = os.getenv("TEAM_NAME", "Vera Elite Bot")
TEAM_MEMBERS: list[str] = os.getenv("TEAM_MEMBERS", "Utkarsh").split(",")
CONTACT_EMAIL: str = os.getenv("CONTACT_EMAIL", "team@example.com")
BOT_VERSION: str = "2.0.0"
SUBMITTED_AT: str = os.getenv("SUBMITTED_AT", "2026-07-14T00:00:00Z")

# ──────────────────────────────────────────────
# Server Configuration
# ──────────────────────────────────────────────

PORT: int = int(os.getenv("PORT", "8080"))
HOST: str = os.getenv("HOST", "0.0.0.0")

# ──────────────────────────────────────────────
# Composition Limits
# ──────────────────────────────────────────────

# Max actions per tick (to stay within 30s budget)
MAX_ACTIONS_PER_TICK: int = int(os.getenv("MAX_ACTIONS_PER_TICK", "5"))

# Max turns per conversation before forcing exit
MAX_TURNS_PER_CONV: int = int(os.getenv("MAX_TURNS_PER_CONV", "5"))

# Auto-reply threshold before ending conversation
AUTO_REPLY_END_THRESHOLD: int = 3

# Soft cap on message body length (no hard limit in spec)
MAX_BODY_LENGTH: int = int(os.getenv("MAX_BODY_LENGTH", "600"))
