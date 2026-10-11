from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from db.base import Base

class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(Integer, ForeignKey("smart_devices.id"), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "device_id"),)

    user = relationship("User", back_populates="likes")
    device = relationship("SmartDevice", back_populates="likes")
