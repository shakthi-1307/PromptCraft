import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text
from app.database import Base


class User(Base):
    __tablename__ = "users"

    email      = Column(String, primary_key=True, index=True)
    name       = Column(String, nullable=False)
    password   = Column(String, nullable=False)  # bcrypt hash
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Prompt(Base):
    __tablename__ = "prompts"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_email = Column(String, nullable=False, index=True)
    user_input = Column(Text, nullable=False)
    generated  = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))