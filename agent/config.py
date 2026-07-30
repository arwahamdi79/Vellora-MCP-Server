"""
Project Configuration
Vellora Therapeutics AI Agent
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ==========================
# Gemini
# ==========================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODEL_NAME = "gemini-2.5-flash"

# ==========================
# MCP Server
# ==========================

SERVER_PATH = "../mcp_server/server.py"

# ==========================
# Agent
# ==========================

SYSTEM_PROMPT = """
You are Vellora Therapeutics AI Assistant.

You are an internal enterprise assistant.

Rules:

- Never invent company information.
- Prefer MCP Tools whenever data is needed.
- Prefer MCP Resources for company policies.
- Use MCP Prompts when generating standardized reports.
- Be concise and professional.
"""
