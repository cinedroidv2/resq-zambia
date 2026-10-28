"""remove media files and add incident tracking fields

Revision ID: f31ab68cff36
Revises: b2c8f1a4e901
Create Date: 2026-06-14 20:14:46.702468
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers used by Alembic.
revision = "f31ab68cff36"
down_revision = "b2c8f1a4e901"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "incidents",
        schema=None
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "language",
                sa.String(length=5),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                "assigned_departments",
                sa.Text(),
                nullable=True
            )
        )

        # Must remain nullable because existing incidents
        # do not have an updated_at value yet.
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                "dispatched_at",
                sa.DateTime(),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                "resolved_at",
                sa.DateTime(),
                nullable=True
            )
        )

        # Increase the available length safely.
        batch_op.alter_column(
            "classification_status",
            existing_type=sa.VARCHAR(length=20),
            type_=sa.String(length=30),
            existing_nullable=True
        )

        # Permanently remove the unused media column.
        batch_op.drop_column(
            "media_files"
        )


def downgrade():
    with op.batch_alter_table(
        "incidents",
        schema=None
    ) as batch_op:
        batch_op.alter_column(
            "classification_status",
            existing_type=sa.String(length=30),
            type_=sa.VARCHAR(length=20),
            existing_nullable=True
        )

        batch_op.drop_column(
            "resolved_at"
        )

        batch_op.drop_column(
            "dispatched_at"
        )

        batch_op.drop_column(
            "updated_at"
        )

        batch_op.drop_column(
            "assigned_departments"
        )

        batch_op.drop_column(
            "language"
        )

    # media_files is deliberately not restored.
    # It has been permanently removed from the active system.
