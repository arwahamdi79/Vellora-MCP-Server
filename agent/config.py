"""
Project Configuration
Vellora Therapeutics AI Agent
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# ==========================
# Gemini
# ==========================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODEL_NAME = "gemini-2.0-flash-lite"


# ==========================
# MCP Server
# ==========================

BASE_DIR = Path(__file__).resolve().parent.parent

SERVER_PATH = "mcp_server/server.py"


# ==========================
# Agent
# ==========================

SYSTEM_PROMPT = """
You are Vellora Therapeutics AI Assistant.

You are an internal enterprise assistant.

Rules:

- Never invent company information.
- Use MCP tools when database information is required.
- Use MCP resources for company policies.
- Use MCP prompts for standardized reports.
- Be professional and concise.
"""