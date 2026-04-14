"""SQL input sanitization helpers.

All user input that reaches the database must be either:
  1. Bound as a parameter via DuckDB's `?` placeholders, OR
  2. Validated against a fixed allowlist before being interpolated.

These helpers centralize that discipline so route handlers can't accidentally
build a query out of raw request data.
"""

from typing import Iterable


class InvalidParameter(ValueError):
    """Raised when a query parameter fails validation."""


def safe_sort_field(value: str | None, allowed: Iterable[str], default: str) -> str:
    """Return `value` only if it is in `allowed`; otherwise return `default`.

    Use this for any column name that gets interpolated into an ORDER BY
    clause. Never trust user-supplied column names directly.
    """
    if value is None:
        return default
    return value if value in allowed else default


def safe_sort_order(value: str | None, default: str = "DESC") -> str:
    """Return 'ASC' or 'DESC'. Anything else falls back to `default`."""
    if value is None:
        return default
    upper = value.upper()
    return upper if upper in ("ASC", "DESC") else default


def safe_int(
    value: str | int | None,
    *,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Parse `value` as int and clamp to [minimum, maximum].

    Raises InvalidParameter if `value` is non-numeric. This converts
    junk input into a 400 instead of a 500 from int()/duckdb.
    """
    if value is None or value == "":
        result = default
    else:
        try:
            result = int(value)
        except (TypeError, ValueError):
            raise InvalidParameter(f"expected integer, got {value!r}")
    if minimum is not None and result < minimum:
        result = minimum
    if maximum is not None and result > maximum:
        result = maximum
    return result


def escape_like(value: str) -> str:
    """Escape LIKE/ILIKE wildcards in user input.

    Without this, a user searching for "100%" would match every row, and
    a search for "a_b" would match "axb". We escape the wildcards and
    declare the escape character with `ESCAPE '\\'` in the query.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
