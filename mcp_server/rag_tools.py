from .app import mcp
from .knowledge_base import KnowledgeBase
from mcp_server.knowledge_base import KnowledgeBase


kb = KnowledgeBase()


# Company knowledge documents

kb.add_document(
    """
    Manufacturing SOP:
    All pharmaceutical batches must pass quality testing
    before release to market.
    """
)


kb.add_document(
    """
    Storage Policy:
    Medicines must be stored between 2 and 8 degrees Celsius
    when required by product specifications.
    """
)


kb.add_document(
    """
    Recall Policy:
    Any defective medicine batch must be quarantined
    and reviewed by the quality department.
    """
)



@mcp.tool()
def search_knowledge_base(
    query: str,
    top_k: int = 3
):

    """
    Search company documents and policies.
    """

    results = kb.search(
        query,
        top_k
    )


    if not results:
        return "No information found."


    return "\n\n".join(results)