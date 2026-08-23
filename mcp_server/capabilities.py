"""
MCP Server capability declaration.

This file contains what the server supports.
The client is responsible for checking these
during initialize/initialized exchange.
"""


SERVER_CAPABILITIES = {

    "tools": {
        "listChanged": True
    },

    "resources": {
        "listChanged": False,
        "subscribe": False
    },

    "prompts": {
        "listChanged": False
    },

    # Server can request human input
    "elicitation": True,

    # Sampling is handled by client side
    # Member 3 responsibility
    "sampling": False

}



SERVER_DESCRIPTION = """
Vellora Therapeutics MCP Server

Purpose:
Provide safe and controlled LLM access to
Vellora pharmaceutical manufacturing data.

The LLM never accesses the database directly.
All access goes through validated MCP tools.

Supported MCP Features:

- Tools
- Resources
- Prompts
- Authorization
- Server-side Validation
- Notifications
- Elicitation
- Progress Tracking


Available Tools:

Read Operations:
- get_medicines
- get_medicine
- get_batches
- get_quality_tests
- get_recalls
- employee


Write Operations:
- create_order
- change_batch_status
- add_quality_test
- create_recall


Available Resources:

- batch_approval_policy
- manufacturing_sop
- product_recall_policy
- storage_guidelines


Available Prompts:

- batch_analysis_prompt
- recall_explanation_prompt


Safety Features:

- Role based authorization
- Input validation
- Human approval for risky operations
- Runtime tool updates
"""