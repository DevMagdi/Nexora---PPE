"""baseline schema

Revision ID: bec6d3a1cd21
Revises: 
Create Date: 2026-10-10 14:41:54.565368

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bec6d3a1cd21'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('alert_log', 'violation_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_constraint(op.f('FK__alert_log__viola__52593CB8'), 'alert_log', type_='foreignkey')
    op.create_foreign_key(
        'fk_alert_log_violation_id_violations',
        'alert_log', 'violations', ['violation_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index(op.f('ix_violations_camera_id'), 'violations', ['camera_id'], unique=False)
    op.create_index(op.f('ix_violations_violation_type'), 'violations', ['violation_type'], unique=False)
    op.drop_constraint(op.f('FK__violation__camer__4E88ABD4'), 'violations', type_='foreignkey')
    op.create_foreign_key(
        'fk_violations_camera_id_cameras',
        'violations', 'cameras', ['camera_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_violations_camera_id_cameras', 'violations', type_='foreignkey')
    op.create_foreign_key(
        op.f('FK__violation__camer__4E88ABD4'), 'violations', 'cameras', ['camera_id'], ['id']
    )
    op.drop_index(op.f('ix_violations_violation_type'), table_name='violations')
    op.drop_index(op.f('ix_violations_camera_id'), table_name='violations')
    op.drop_constraint('fk_alert_log_violation_id_violations', 'alert_log', type_='foreignkey')
    op.create_foreign_key(
        op.f('FK__alert_log__viola__52593CB8'), 'alert_log', 'violations', ['violation_id'], ['id']
    )
    op.alter_column('alert_log', 'violation_id',
               existing_type=sa.INTEGER(),
               nullable=False)