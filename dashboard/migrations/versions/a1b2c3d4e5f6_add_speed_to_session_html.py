"""Add speed column to session_html

Revision ID: a1b2c3d4e5f6
Revises: 5c40381ea62d
Create Date: 2024-12-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '5c40381ea62d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('session_html', schema=None) as batch_op:
        batch_op.add_column(sa.Column('speed', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('session_html', schema=None) as batch_op:
        batch_op.drop_column('speed')
