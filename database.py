# database.py
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# Создаем базовый класс
Base = declarative_base()


class UserRequest(Base):
    __tablename__ = 'requests'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)  # Очищенный вопрос
    original_question = Column(Text)  # ← ДОБАВЬТЕ ЭТО ПОЛЕ (опционально)
    status = Column(String(50), default='waiting')
    created_at = Column(DateTime, default=datetime.now)

    drafts = relationship("DraftAnswer", back_populates="request", cascade="all, delete-orphan")


class DraftAnswer(Base):
    __tablename__ = 'drafts'

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey('requests.id', ondelete="CASCADE"), nullable=False)  # ВАЖНО: ForeignKey!
    llm_response = Column(Text)
    expert_edited_response = Column(Text)
    expert_id = Column(Integer)
    decision_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)

    # Связь с запросом
    request = relationship("UserRequest", back_populates="drafts")


class Expert(Base):
    __tablename__ = 'experts'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True)
    name = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)


# Создаем движок и сессию
engine = create_engine('sqlite:///chatbot.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()