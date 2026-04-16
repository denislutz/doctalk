from fastapi import APIRouter, UploadFile, File, Form

router = APIRouter(prefix="/collections", tags=["upload"])


@router.post("/{topic}/upload")
async def upload_document(topic: str, file: UploadFile = File(...), description: str = Form(None)):
    # TODO: implement ingestion pipeline
    return {"filename": file.filename, "topic": topic, "status": "pending"}
