from .database import (
    get_connection,
)


def validate_positive_integer(value, field_name):
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")


def validate_choice(value, allowed_values, field_name):
    if value not in allowed_values:
        raise ValueError(
            f"{field_name} must be one of: {', '.join(allowed_values)}"
        )


def record_exists(table, id_column, value):
    conn = get_connection()

    cursor = conn.execute(
        f"""
        SELECT 1
        FROM {table}
        WHERE {id_column} = ?
        """,
        (value,)
    )

    exists = cursor.fetchone() is not None

    conn.close()

    return exists


def validate_exists(table, id_column, value):

    if not record_exists(table, id_column, value):
        raise ValueError(
            f"{table} record with {id_column}={value} does not exist."
        )