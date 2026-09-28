"""Lab 2: domain fields and database invariants, preserving existing rows."""
from alembic import op
import sqlalchemy as sa
revision = "b219_lab2"
down_revision = "0ce199bf6641"
branch_labels = depends_on = None

def upgrade():
    op.add_column("smart_devices", sa.Column("type_label", sa.String(100), nullable=False, server_default="УМНОЕ УСТРОЙСТВО"))
    op.add_column("smart_devices", sa.Column("model", sa.String(100)))
    op.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    op.execute("UPDATE smart_devices SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    op.alter_column("users", "created_at", nullable=False)
    op.alter_column("smart_devices", "created_at", nullable=False)
    op.alter_column("smart_devices", "creator_id", nullable=False)
    op.alter_column("likes", "user_id", nullable=False)
    op.alter_column("likes", "device_id", nullable=False)
    op.create_check_constraint("ck_device_status", "smart_devices", "status IN ('draft', 'published', 'deleted')")
    op.create_check_constraint("ck_device_traffic", "smart_devices", "traffic_mean >= 0 AND traffic_variance >= 0")
    op.create_index("uq_device_creator_draft", "smart_devices", ["creator_id"], unique=True, postgresql_where=sa.text("status = 'draft'"))

def downgrade():
    op.drop_index("uq_device_creator_draft", table_name="smart_devices")
    op.drop_constraint("ck_device_traffic", "smart_devices")
    op.drop_constraint("ck_device_status", "smart_devices")
    for table, col in [("users", "created_at"), ("smart_devices", "created_at"), ("smart_devices", "creator_id"), ("likes", "user_id"), ("likes", "device_id")]:
        op.alter_column(table, col, nullable=True)
    op.drop_column("smart_devices", "model")
    op.drop_column("smart_devices", "type_label")
