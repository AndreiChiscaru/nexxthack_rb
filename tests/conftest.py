"""Tests never call Claude: force the mock agents even if .env has a real ANTHROPIC_API_KEY."""
import os

os.environ["MOCK_LLM"] = "true"
