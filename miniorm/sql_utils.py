import uuid

def sql_escape(value: str) -> str:
    """Escapes single quotes for safe SQL usage."""
    return value.replace("'", "''")

def sql_value(v):
    """
    Escapes and formats a Python value for direct use in SQL statements.

    - Wraps UUIDs and strings in single quotes (escaping internal quotes).
    - Converts bool/int/float directly.
    - Returns 'null' for None values.

    Args:
        v: The value to convert.

    Returns:
        str: A SQL-safe representation of the value.
    """
    if v is None:
        return 'null'
    if isinstance(v, uuid.UUID):
        return f"'{str(v)}'"
    if isinstance(v, str):
        escaped = v.replace("'", "''")
        return f"'{escaped}'"
    if isinstance(v, (int, float, bool)):
        return str(v)
    return f"'{str(v)}'"  # fallback to string

def normalize_query_params(params: dict) -> dict:
    """
    Converts UUID values to strings to make them safe for SQL execution.
    """
    return {
        key: str(value) if isinstance(value, uuid.UUID) else value
        for key, value in params.items()
    }