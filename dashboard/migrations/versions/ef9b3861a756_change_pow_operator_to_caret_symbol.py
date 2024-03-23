"""Change pow operator to caret symbol

Revision ID: ef9b3861a756
Revises: 1ecf18307d08
Create Date: 2024-03-23 20:58:37.877649

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ef9b3861a756'
down_revision = '1ecf18307d08'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE calibration_method SET data=REPLACE(data, '**', '^')"))
    conn.execute(sa.text("UPDATE calibration_method SET updated=unixepoch('now')"))


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE calibration_method SET data=REPLACE(data, '^', '**')"))
    conn.execute(sa.text("UPDATE calibration_method SET updated=unixepoch('now')"))
