import os
import requests
import logging
import boto3
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import SessionLocal
from app.models.image import Image

# ✅ 환경 변수 로드
load_dotenv()

# ✅ 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ 환경 변수
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")

# ✅ 필수 환경 변수 체크
if not OPENAI_API_KEY or not AWS_S3_BUCKET:
    raise ValueError("❌ 필수 환경 변수가 누락되었습니다.")

# ✅ S3 클라이언트 (EC2 Role 기반 인증)
s3_client = boto3.client("s3", region_name=AWS_REGION)

# ✅ FastAPI 라우터
router = APIRouter()

# ✅ 요청 모델
class PromptRequest(BaseModel):
    prompt: str
    user_id: Optional[int] = None  # 로그인 사용자 ID (선택)


# ✅ 이미지 다운로드 함수
def download_image(url: str, save_path: str):
    response = requests.get(url)
    if response.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(response.content)
        logger.info(f"✅ 이미지 다운로드 완료: {save_path}")
    else:
        logger.error("❌ 이미지 다운로드 실패")
        raise HTTPException(status_code=500, detail="이미지 다운로드 실패")


# ✅ S3 업로드 함수
def upload_to_s3(file_path: str, s3_key: str) -> Optional[str]:
    try:
        s3_client.upload_file(file_path, AWS_S3_BUCKET, s3_key)
        s3_url = f"https://{AWS_S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        logger.info(f"✅ S3 업로드 완료: {s3_url}")
        return s3_url
    except Exception as e:
        logger.error(f"❌ S3 업로드 에러: {str(e)}")
        return None


# ✅ RDS 저장 함수
def save_image_to_db(db: Session, prompt: str, openai_url: str, s3_url: Optional[str], user_id: Optional[int]):
    image = Image(
        prompt=prompt,
        openai_url=openai_url,
        s3_url=s3_url,
        user_id=user_id
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    logger.info(f"✅ RDS 저장 완료 (Image ID: {image.id})")


# ✅ 백그라운드 통합 작업
def handle_image_background(image_url: str, filename: str, prompt: str, user_id: Optional[int]):
    temp_path = f"/tmp/{filename}"
    try:
        # ✅ 이미지 다운로드
        download_image(image_url, temp_path)
        # ✅ S3 업로드
        s3_key = f"generated_images/{filename}"
        s3_url = upload_to_s3(temp_path, s3_key)
        # ✅ RDS 저장 (세션 독립)
        db = SessionLocal()
        save_image_to_db(db, prompt, image_url, s3_url, user_id)
    except Exception as e:
        logger.error(f"❌ 백그라운드 작업 에러: {str(e)}")
    finally:
        db.close()  # ✅ 세션 닫기


# ✅ 메인 API (이미지 URL만 반환, 백그라운드 작업)
@router.post("/generate-image")
def generate_image(request: PromptRequest, background_tasks: BackgroundTasks):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    payload = {
        "model": "dall-e-3",
        "prompt": request.prompt,
        "n": 1,
        "size": "1024x1024"
    }

    try:
        # ✅ OpenAI 호출
        logger.info(f"📡 OpenAI 호출: {payload}")
        response = requests.post("https://api.openai.com/v1/images/generations", headers=headers, json=payload)
        response_data = response.json()
        logger.info(f"✅ OpenAI 응답: {response_data}")

        # ✅ 응답 검증
        if "data" not in response_data or len(response_data["data"]) == 0:
            raise HTTPException(status_code=500, detail="OpenAI에서 이미지 생성 실패")

        # ✅ 이미지 URL 및 파일명
        image_url = response_data["data"][0]["url"]
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"generated_image_{timestamp}.png"

        # ✅ 백그라운드로 S3 + RDS 작업
        background_tasks.add_task(handle_image_background, image_url, filename, request.prompt, request.user_id)

        # ✅ 사용자에게 즉시 OpenAI 이미지 URL 반환
        return {"image_url": image_url}

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ OpenAI 요청 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="OpenAI API 요청 실패")
    except Exception as e:
        logger.error(f"❌ 서버 에러: {str(e)}")
        raise HTTPException(status_code=500, detail="서버 내부 에러")
