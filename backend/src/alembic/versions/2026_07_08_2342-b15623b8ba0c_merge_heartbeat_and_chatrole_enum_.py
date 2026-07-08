"""merge heartbeat and chatrole enum branches

Revision ID: b15623b8ba0c
Revises: f550c1c17fde, a1b2c3d4e5f6
Create Date: 2026-07-08 23:42:45.115446

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b15623b8ba0c'
down_revision: Union[str, Sequence[str], None] = ('f550c1c17fde', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
