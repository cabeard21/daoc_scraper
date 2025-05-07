from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    func,
)
from pydantic import BaseModel

metadata = MetaData()

fights = Table(
    "fights",
    metadata,
    Column("id", Text, primary_key=True),
    Column("fight_json", JSON, nullable=False),
    Column("date", DateTime, nullable=False, index=True),
    Column("created_at", DateTime, server_default=func.now()),
    Column("min_size", Integer, nullable=False, index=True),
    Column("max_size", Integer, nullable=False, index=True),
)

participants = Table(
    "fight_participants",
    metadata,
    Column("fight_id", Text, ForeignKey("fights.id")),
    Column("class_name", Text, nullable=False),
    Column("win", Boolean, nullable=False),
)


class BulkQuery(BaseModel):
    ids: list[str]
