GET_BATCH_DETAILS_SCHEMA = {
    "type": "object",
    "properties": {
        "batch_id": {
            "type": "integer",
            "minimum": 1,
            "description": "Unique identifier of the manufacturing batch."
        }
    },
    "required": ["batch_id"],
    "additionalProperties": False
}

INITIATE_RECALL_SCHEMA = {
    "type": "object",
    "properties": {
        "batch_id": {
            "type": "integer",
            "minimum": 1,
            "description": "Unique identifier of the manufacturing batch to recall."
        },
        "recall_reason": {
            "type": "string",
            "minLength": 10,
            "maxLength": 500,
            "description": "Detailed justification for the product recall."
        },
        "authorized_manager_id": {
            "type": "integer",
            "minimum": 1,
            "description": "Employee ID of the authorizing QA/Operations Manager."
        }
    },
    "required": ["batch_id"],
    "additionalProperties": False
}