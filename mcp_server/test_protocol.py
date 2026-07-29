from .capabilities import SERVER_CAPABILITIES
from .notifications import get_available_tools


def test_capabilities():

    assert "tools" in SERVER_CAPABILITIES
    assert "resources" in SERVER_CAPABILITIES
    assert "elicitation" in SERVER_CAPABILITIES
    assert "sampling" in SERVER_CAPABILITIES


def test_dynamic_tools():

    normal_user = get_available_tools("Researcher")

    manager_user = get_available_tools(
        "QA Manager"
    )

    assert "get_batch_details" in normal_user

    assert (
        "initiate_product_recall"
        in manager_user
    )
    