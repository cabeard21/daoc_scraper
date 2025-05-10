"""add uix_fight_name

Revision ID: b720bf29d7f9
Revises: bdc6e0586c71
Create Date: 2025-05-09 19:24:06.025363

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b720bf29d7f9"
down_revision: Union[str, None] = "bdc6e0586c71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # SQLite needs batch mode to add/drop constraints
    with op.batch_alter_table("fight_participants") as batch_op:
        batch_op.create_unique_constraint("uix_fight_name", ["fight_id", "name"])


def downgrade():
    with op.batch_alter_table("fight_participants") as batch_op:
        batch_op.drop_constraint("uix_fight_name", type_="unique")
