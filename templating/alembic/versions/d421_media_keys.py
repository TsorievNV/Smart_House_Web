"""Store media keys only; convert legacy MinIO URLs without moving objects."""
from urllib.parse import urlsplit, unquote, quote
from alembic import op
import sqlalchemy as sa
from core.config import settings

revision = "d421_media_keys"
down_revision = "c320_lab3"
branch_labels = depends_on = None

def media_key(value):
    if not value:
        return None
    parsed = urlsplit(value)
    prefix = "/" + settings.MINIO_BUCKET + "/"
    if parsed.scheme not in ("http", "https") or not parsed.netloc or not parsed.path.startswith(prefix):
        raise ValueError("Legacy media URL does not point to the configured MinIO bucket")
    key = unquote(parsed.path[len(prefix):])
    if not key:
        raise ValueError("Empty legacy media key")
    return key

def upgrade():
    connection = op.get_bind()
    table = sa.table("smart_devices", sa.column("id"), sa.column("image_key"),
                     sa.column("video_key"), sa.column("image_url"), sa.column("video_url"))
    for row in connection.execute(sa.select(table)).mappings().all():
        values = {}
        for kind in ("image", "video"):
            if not row[kind + "_key"] and row[kind + "_url"]:
                values[kind + "_key"] = media_key(row[kind + "_url"])
        if values:
            connection.execute(table.update().where(table.c.id == row["id"]).values(**values))
    op.drop_column("smart_devices", "image_url")
    op.drop_column("smart_devices", "video_url")

def downgrade():
    op.add_column("smart_devices", sa.Column("image_url", sa.String(500)))
    op.add_column("smart_devices", sa.Column("video_url", sa.String(500)))
    connection = op.get_bind()
    table = sa.table("smart_devices", sa.column("id"), sa.column("image_key"),
                     sa.column("video_key"), sa.column("image_url"), sa.column("video_url"))
    base = ("https" if settings.MINIO_SECURE else "http") + "://" + settings.MINIO_ENDPOINT + "/" + settings.MINIO_BUCKET + "/"
    for row in connection.execute(sa.select(table)).mappings().all():
        values = {kind + "_url": base + quote(row[kind + "_key"], safe="/")
                  for kind in ("image", "video") if row[kind + "_key"]}
        if values:
            connection.execute(table.update().where(table.c.id == row["id"]).values(**values))
