"""
FileForge Backend - Spreadsheet Endpoints - No auth required
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.v1.endpoints.files import ensure_guest_user
from app.models.database import File, Job
from app.schemas.schemas import SpreadsheetRequest, SpreadsheetPreviewRequest, JobResponse
from app.services.spreadsheet_service import spreadsheet_service

router = APIRouter()


@router.post("/convert", response_model=JobResponse)
async def convert_spreadsheet(
    request: SpreadsheetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Convert spreadsheet"""
    user_id = await ensure_guest_user(db)

    result = await db.execute(
        select(File).where(File.id == request.input_file_id)
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    spreadsheet_types = ["csv", "xlsx", "ods", "json"]
    if file_record.file_type not in spreadsheet_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file_record.file_type}' is not a spreadsheet",
        )

    valid_outputs = {
        "csv": ["xlsx", "json", "csv"],
        "xlsx": ["csv", "json", "xlsx"],
        "json": ["xlsx", "csv"],
        "ods": ["xlsx", "csv", "json"],
    }

    allowed_formats = valid_outputs.get(file_record.file_type, [])
    if request.output_format not in allowed_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot convert {file_record.file_type} to {request.output_format}",
        )

    job = Job(
        user_id=user_id,
        input_file_id=file_record.id,
        job_type="spreadsheet",
        output_format=request.output_format,
        config=request.options.model_dump() if request.options else {},
        status="pending",
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    try:
        result = await spreadsheet_service.convert(
            input_path=file_record.storage_path,
            output_format=request.output_format,
            options=request.options.model_dump() if request.options else None,
        )

        job.status = "completed"
        job.progress = 100
        job.stage = "completed"
        job.result = result
        await db.flush()

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        await db.flush()

    return job


@router.post("/preview")
async def preview_spreadsheet(
    request: SpreadsheetPreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """Preview spreadsheet data"""
    result = await db.execute(
        select(File).where(File.id == request.input_file_id)
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        preview = await spreadsheet_service.preview(
            input_path=file_record.storage_path,
            max_rows=1000000,
            options=request.options.model_dump() if request.options else None,
        )
        return preview
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")