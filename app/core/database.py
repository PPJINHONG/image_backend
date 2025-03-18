import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# .env 파일에서 환경 변수로 설정 (보안 및 편의)
DATABASE_URL = os.getenv("DATABASE_URL")  # 예: postgresql://admin:password123@host:5432/mydatabase

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# DB 세션 가져오는 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
