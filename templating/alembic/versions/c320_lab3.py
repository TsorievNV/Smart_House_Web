"""ЛР3: ключи MinIO, завершение, хеш пароля; старые данные сохранены."""
from alembic import op
import sqlalchemy as sa
revision = "c320_lab3"
down_revision = "b219_lab2"
branch_labels = depends_on = None

def upgrade():
    op.add_column("users", sa.Column("password_hash", sa.String(256)))
    op.add_column("smart_devices", sa.Column("image_key", sa.String(500)))
    op.add_column("smart_devices", sa.Column("video_key", sa.String(500)))
    op.add_column("smart_devices", sa.Column("completed_at", sa.DateTime()))

def downgrade():
    for column in ("completed_at", "video_key", "image_key"):
        op.drop_column("smart_devices", column)
    op.drop_column("users", "password_hash")
