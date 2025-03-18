from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from typing import List
import boto3
import io
import os
import logging

from app.core.database import get_db
from app.models.image import Image

# ✅ 라우터 설정
router = APIRouter()

# ✅ 로거 설정
logger = logging.getLogger(__name__)

# ✅ S3 설정 (Role 기반)
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")

# ✅ S3 클라이언트
s3_client = boto3.client("s3", region_name=AWS_REGION)


# ✅ 1. 내 이미지 목록 조회 API (프론트 연동용)
@router.get("/my-images", response_model=List[dict])
def get_my_images(user_id: int = Query(...), db: Session = Depends(get_db)):
    """
    사용자의 모든 이미지 리스트 반환
    """
    logger.info(f"📦 사용자 {user_id}의 이미지 조회 시도")
    images = db.query(Image).filter(Image.user_id == user_id).order_by(Image.created_at.desc()).all()
    if not images:
        logger.info("❗️ 이미지 없음")
        return []  # 빈 리스트 반환

    # ✅ 리스트 반환
    return [
        {
            "id": image.id,
            "prompt": image.prompt,
            "openai_url": image.openai_url,
            "s3_url": image.s3_url,
            "created_at": image.created_at.isoformat()  # 직렬화
        }
        for image in images
    ]


# ✅ 2. 이미지 다운로드 API (FastAPI 프록시, 보안 유지)
@router.get("/get-image/{image_id}")
def get_image(image_id: int, user_id: int, db: Session = Depends(get_db)):
    """
    사용자 본인이 생성한 이미지인지 확인하고 S3에서 다운로드해서 반환
    """
    logger.info(f"🖼️ 이미지 다운로드 시도: image_id={image_id}, user_id={user_id}")

    # ✅ 사용자 소유 이미지 확인
    image = db.query(Image).filter(Image.id == image_id, Image.user_id == user_id).first()
    if not image:
        logger.error("❌ 이미지 없음 또는 접근 거부")
        raise HTTPException(status_code=404, detail="Image not found or access denied")

    if not image.s3_url:
        logger.error("❌ 이미지 S3 URL 없음")
        raise HTTPException(status_code=404, detail="S3 URL not found")

    # ✅ S3 키 파싱
    s3_key = image.s3_url.split(f".amazonaws.com/")[-1]  # 경로 추출
    logger.info(f"✅ S3 접근 키: {s3_key}")

    # ✅ S3 파일 다운로드 (Stream)
    file_obj = io.BytesIO()
    try:
        s3_client.download_fileobj(AWS_S3_BUCKET, s3_key, file_obj)
        file_obj.seek(0)
        logger.info(f"✅ 이미지 다운로드 성공: {image_id}")
        return StreamingResponse(file_obj, media_type="image/png")
    except Exception as e:
        logger.error(f"❌ S3 다운로드 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download image: {str(e)}")
