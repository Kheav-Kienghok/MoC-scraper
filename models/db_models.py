from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()  # take environment variables

os.makedirs('databases', exist_ok=True)

DATABASE_ENGINE = os.getenv('DATABASE_ENGINE', 'sqlite:///databases/scraped_content.db')

Base = declarative_base()

class ScrapedContent(Base):
    __tablename__ = 'scraped_content'
    id = Column(Integer, primary_key=True, autoincrement=True)
    english_text = Column(String)
    khmer_text = Column(String)

# Setup the database (SQLite example)
engine = create_engine(DATABASE_ENGINE)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)