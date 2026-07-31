from pathlib import Path
from .app import mcp
print("Loading resources.py")
POLICY_DIR = Path(__file__).resolve().parent.parent / "docs" / "policies"


def read_policy(filename):
    with open(POLICY_DIR / filename, "r", encoding="utf-8") as f:
        return f.read()


@mcp.resource("policy://batch_approval")
def batch_approval_policy():
    return read_policy("batch_approval_policy.md")


@mcp.resource("policy://manufacturing_sop")
def manufacturing_sop():
    return read_policy("manufacturing_sop.md")


@mcp.resource("policy://product_recall")
def product_recall_policy():
    return read_policy("product_recall_policy.md")


@mcp.resource("policy://storage_guidelines")
def storage_guidelines():
    return read_policy("storage_guidelines.md")