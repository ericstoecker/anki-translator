import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.ocr import OCRResponse
from app.services.llm_service import extract_words

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("", response_model=OCRResponse)
async def ocr_image(
    file: UploadFile = File(...),
):
    image_bytes = await file.read()
    media_type = file.content_type or "image/jpeg"
    try:
        result = await extract_words(image_bytes, media_type)
    except Exception as e:
        logger.exception("OCR failed")
        raise HTTPException(status_code=502, detail=f"OCR service error: {e}")
    return OCRResponse(
        words=result.get("words", []),
        raw_text=result.get("raw_text", ""),
    )
