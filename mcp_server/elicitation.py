"""
Human-in-the-loop elicitation helpers.

Used for risky operations like product recall.
"""


def create_elicitation_request(
    action: str,
    details: dict
):

    return {

        "method": "elicitation/create",

        "params": {

            "message":
            f"Human approval required before {action}",


            "requestedAction":
            action,


            "details":
            details,


            "requestedSchema":

            {

                "type": "object",

                "properties":

                {

                    "approved":

                    {

                        "type": "boolean",

                        "description":
                        "Approve or reject operation"

                    }

                },


                "required":
                [
                    "approved"
                ],


                "additionalProperties":
                False

            }

        }

    }



def input_required(
    message,
    missing_fields
):

    return {

        "status":
        "input_required",

        "message":
        message,

        "missing_fields":
        missing_fields

    }