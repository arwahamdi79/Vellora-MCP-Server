from pathlib import Path

POLICY_DIR = Path(__file__).resolve().parent.parent / "docs" / "policies"


def read_policy(filename):
    """Read a policy document from the policies folder."""
    with open(POLICY_DIR / filename, "r", encoding="utf-8") as f:
        return f.read()


# =====================================================
# Policy Resources
# =====================================================

def get_batch_approval_policy():
    """Return the Batch Approval Policy."""
    return read_policy("batch_approval_policy.md")


def get_manufacturing_sop():
    """Return the Manufacturing Standard Operating Procedure."""
    return read_policy("manufacturing_sop.md")


def get_product_recall_policy():
    """Return the Product Recall Policy."""
    return read_policy("product_recall_policy.md")


def get_storage_guidelines():
    """Return the Storage Guidelines."""
    return read_policy("storage_guidelines.md")