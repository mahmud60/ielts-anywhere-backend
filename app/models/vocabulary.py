from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class VocabularyWord(Base):
    __tablename__ = "vocabulary_words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(100), unique=True, nullable=False, index=True)
    module = Column(String(20), nullable=False, index=True)
    topic = Column(String(100), nullable=False, index=True)
    band = Column(String(10), nullable=False)
    part_of_speech = Column(String(30))
    definition = Column(Text)
    example = Column(Text)
    mnemonic = Column(Text)
    collocations = Column(JSONB, default=list)
