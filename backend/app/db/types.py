from enum import StrEnum

from sqlalchemy import JSON, Enum
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on PostgreSQL (indexable, compact), plain JSON elsewhere (SQLite tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")


def str_enum(enum_cls: type[StrEnum], length: int = 32, name: str | None = None) -> Enum:
    """Store a StrEnum as VARCHAR + CHECK constraint (portable, no native PG enum migrations).

    Pass ``name`` when a table has two columns of the same enum: the CHECK constraint is
    named ``ck_<table>_<name>`` and PostgreSQL rejects duplicates within a table.
    """
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
        create_constraint=True,
        name=name or enum_cls.__name__.lower(),
    )
