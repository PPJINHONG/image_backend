from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base




class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    prompt = Column(String, nullable=False)
    openai_url = Column(String, nullable=False)
    s3_url = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 연동된 사용자 ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
