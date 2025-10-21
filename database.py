from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Создаем базовый класс для моделей
Base = declarative_base()


class UserRequest(Base):
    __tablename__ = 'requests'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    status = Column(String(20), default='waiting')  # waiting, approved, rejected


class DraftAnswer(Base):
    __tablename__ = 'drafts'

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, nullable=False)
    llm_response = Column(Text)
    expert_edited_response = Column(Text)
    expert_id = Column(Integer)
    decision_time = Column(DateTime)


class Expert(Base):
    __tablename__ = 'experts'

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    telegram_id = Column(Integer, unique=True)
    is_active = Column(Boolean, default=True)


# Создаем базу данных
engine = create_engine('sqlite:///chatbot.db', echo=True)
Base.metadata.create_all(engine)

# Создаем сессию для работы с БД
Session = sessionmaker(bind=engine)
session = Session()