from datetime import datetime


def create_notification(event_type: str, message: str, severity: str = "info"):
    """
    Create a notification object.
    """

    return {
        "event": event_type,
        "message": message,
        "severity": severity,
        "timestamp": datetime.now().isoformat(timespec="seconds")
    }


# --------------------------------------------------
# Production
# --------------------------------------------------

def production_order_created(order_id: int):
    return create_notification(
        "production_order_created",
        f"Production Order #{order_id} has been created."
    )


# --------------------------------------------------
# Batch
# --------------------------------------------------

def batch_status_changed(batch_id: int, status: str):

    severity = "info"

    if status == "Rejected":
        severity = "warning"

    return create_notification(
        "batch_status_changed",
        f"Batch {batch_id} status changed to '{status}'.",
        severity
    )


# --------------------------------------------------
# Quality
# --------------------------------------------------

def quality_test_recorded(batch_id: int, result: str):

    severity = "info"

    if result == "Fail":
        severity = "warning"

    return create_notification(
        "quality_test_recorded",
        f"Quality test for Batch {batch_id}: {result}.",
        severity
    )


# --------------------------------------------------
# Recall
# --------------------------------------------------

def recall_created(recall_id: int, batch_id: int):

    return create_notification(
        "product_recall",
        f"Product Recall #{recall_id} initiated for Batch {batch_id}.",
        "critical"
    )