from pathlib import Path

from .server import mcp


POLICY_DIR = (
    Path(__file__).resolve()
    .parent.parent
    / "docs"
    / "policies"
)


def read_policy(filename: str):

    path = POLICY_DIR / filename

    if not path.exists():
        return "Policy document not found."

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return file.read()



@mcp.resource(
    "vellora://policies/batch-approval"
)
def batch_approval_policy():

    """
    Manufacturing batch approval policy.
    """

    return read_policy(
        "batch_approval_policy.md"
    )



@mcp.resource(
    "vellora://policies/manufacturing-sop"
)
def manufacturing_sop():

    """
    Standard manufacturing operating procedure.
    """

    return read_policy(
        "manufacturing_sop.md"
    )



@mcp.resource(
    "vellora://policies/product-recall"
)
def product_recall_policy():

    """
    Product recall policy.
    """

    return read_policy(
        "product_recall_policy.md"
    )



@mcp.resource(
    "vellora://policies/storage-guidelines"
)
def storage_guidelines():

    """
    Medicine storage guidelines.
    """

    return read_policy(
        "storage_guidelines.md"
    )