from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.api import auth, openai, image 
from app.models.user import User  # ✅ 명시적 모델 import
from app.models.image import Image  # ✅ 명시적 모델 import (추가했던 image 모델)

# ✅ FastAPI 앱 생성
app = FastAPI()

# ✅ CORS 설정 (배포시 특정 도메인으로 제한 권장)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 중 전체 허용, 배포 시 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ DB 테이블 자동 생성 (명시적 모델 포함)
Base.metadata.create_all(bind=engine)

# ✅ API 라우터 등록
app.include_router(auth.router, prefix="/api")   # 로그인/회원가입
app.include_router(openai.router, prefix="/api")  # 이미지 생성 등
app.include_router(image.router, prefix="/api")
# ✅ 루트 엔드포인트
@app.get("/")
def read_root():
    return {"message": "Hello FastAPI!"}
