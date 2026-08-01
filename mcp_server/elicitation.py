def input_required(message, missing_fields):
    """
    Return a standardized response when required information is missing.
    """

    return {
        "status": "input_required",
        "message": message,
        "missing_fields": missing_fields
    }