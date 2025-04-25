from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    Table,
    Text,
    func,
)

metadata = MetaData()

fights = Table(
    "fights",
    metadata,
    Column("id", Text, primary_key=True),
    Column("fight_json", JSON, nullable=False),
    Column("date", DateTime, nullable=False),
    Column("created_at", DateTime, server_default=func.now()),
)

participants = Table(
    "fight_participants",
    metadata,
    Column("fight_id", Text, ForeignKey("fights.id")),
    Column("class_name", Text, nullable=False),
    Column("win", Boolean, nullable=False),
)
