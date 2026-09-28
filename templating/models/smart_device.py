from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, CheckConstraint, Index, text
from sqlalchemy.orm import relationship
from datetime import datetime
from db.base import Base

class SmartDevice(Base):
    __tablename__ = "smart_devices"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    type_label = Column(String(100), nullable=False, default="УМНОЕ УСТРОЙСТВО", server_default="УМНОЕ УСТРОЙСТВО")
    model = Column(String(100))
    description = Column(Text)
    status = Column(String(20), nullable=False, default="draft")  # draft / published / deleted
    image_url = Column(String(500))
    video_url = Column(String(500))
    traffic_mean = Column(Float)
    traffic_variance = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    formed_at = Column(DateTime)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # без CASCADE

    creator = relationship("User", back_populates="devices")
    likes = relationship("Like", back_populates="device")

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'deleted')", name="ck_device_status"),
        CheckConstraint("traffic_mean >= 0 AND traffic_variance >= 0", name="ck_device_traffic"),
        Index("uq_device_creator_draft", "creator_id", unique=True,
              postgresql_where=text("status = 'draft'")),
    )
