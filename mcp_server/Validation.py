from jsonschema import validate, ValidationError

def validate_tool_args(arguments: dict, schema: dict) -> tuple[bool, str]:
    
    try:
        validate(instance=arguments, schema=schema)
        return True, "Valid"
    except ValidationError as e:
        return False, f"Schema Validation Error: {e.message}"
    except Exception as e:
        return False, f"Unexpected Validation Error: {str(e)}"