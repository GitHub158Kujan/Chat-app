from database import Base
from sqlalchemy import String, Integer, Column, TIMESTAMP, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    password = Column(String(100), nullable=False)

    sent_messages = relationship("Message", back_populates="sender", foreign_keys='Message.sender_id')
    received_messages = relationship("Message", back_populates="receiver", foreign_keys='Message.receiver_id')


class Message(Base):
    __tablename__ = "message"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("user.id"))
    receiver_id = Column(Integer, ForeignKey("user.id"))
    message = Column(String(400), nullable=False)
    time = Column(TIMESTAMP(timezone=True), server_default=func.now())

    sender = relationship("User", back_populates="sent_messages", foreign_keys=[sender_id])
    receiver = relationship("User", back_populates="received_messages", foreign_keys=[receiver_id])
