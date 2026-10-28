"""add media_files to incident

Revision ID: b2c8f1a4e901
Revises: 9574de33ec76
Create Date: 2026-06-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c8f1a4e901'
down_revision = '9574de33ec76'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('media_files', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.drop_column('media_files')
