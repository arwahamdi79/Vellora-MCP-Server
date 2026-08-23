"""
JSON schemas for MCP tools.
"""


CREATE_RECALL_SCHEMA = {

    "type": "object",

    "properties":

    {

        "employee_id":
        {
            "type": "integer"
        },

        "batch_id":
        {
            "type": "integer"
        },

        "recall_reason":
        {
            "type": "string"
        }

    },


    "required":

    [
        "employee_id",
        "batch_id",
        "recall_reason"
    ],


    "additionalProperties":
    False

}



CREATE_ORDER_SCHEMA = {

    "type": "object",

    "properties":

    {

        "employee_id":
        {
            "type": "integer"
        },

        "medicine_id":
        {
            "type": "integer"
        },

        "supplier_id":
        {
            "type": "integer"
        },

        "planned_quantity":
        {
            "type": "integer",
            "minimum": 1
        }

    },


    "required":

    [
        "employee_id",
        "medicine_id",
        "supplier_id",
        "planned_quantity"
    ],


    "additionalProperties":
    False

}