from enum import Enum

from sqlalchemy.dialects.postgresql import ENUM


def pg_str_enum(enum_class: type[Enum], name: str) -> ENUM:
    """PostgreSQL ENUM that stores Python enum values (e.g. 'operator'), not names."""
    return ENUM(
        enum_class,
        name=name,
        create_type=False,
        values_callable=lambda members: [member.value for member in members],
    )
