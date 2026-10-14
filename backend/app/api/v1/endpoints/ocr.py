from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from app.core.database import get_db, AsyncSessionLocal
from app.api.v1.endpoints.files import ensure_guest_user
from app.models.database import File, Job
from app.schemas.schemas import OcrRequest, OcrAnalyzeResponse, JobResponse
from app.services.ocr_service import ocr_service

router = APIRouter()


async def get_file_for_user(db: AsyncSession, file_id: str) -> File:
    """Get file for guest user"""
    user_id = await ensure_guest_user(db)

    result = await db.execute(
        select(File).where(
            File.id == file_id,
            File.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


@router.post("/analyze", response_model=OcrAnalyzeResponse)
async def analyze_image(
    request: OcrRequest,
    db: AsyncSession = Depends(get_db),
):
    """Analyze image"""
    file_record = await get_file_for_user(db, request.input_file_id)

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    if file_record.file_type not in ("image", "pdf"):
        raise HTTPException(status_code=400, detail="File is not an image or PDF")

    try:
        analysis = await ocr_service.analyze_image(file_record.storage_path)
        return OcrAnalyzeResponse(**analysis)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR analysis failed: {str(e)}")


@router.post("/process", response_model=JobResponse)
async def process_ocr(
    request: OcrRequest,
    db: AsyncSession = Depends(get_db),
):
    """Start OCR processing"""
    file_record = await get_file_for_user(db, request.input_file_id)

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    if file_record.file_type not in ("image", "pdf"):
        raise HTTPException(status_code=400, detail="File is not an image or PDF")

    allowed_formats = ["docx", "xlsx", "pdf", "txt", "html"]
    if request.output_format not in allowed_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid output format. Allowed: {', '.join(allowed_formats)}",
        )

    user_id = await ensure_guest_user(db)

    # Collect OCR and fine-tuning options
    opt_dict = request.options.model_dump(exclude_none=True) if request.options else {}
    req_dict = request.model_dump(exclude={"input_file_id", "options"}, exclude_none=True)
    merged_options = {**req_dict, **opt_dict}

    job = Job(
        user_id=user_id,
        input_file_id=file_record.id,
        job_type="ocr",
        output_format=request.output_format,
        config=merged_options,
        status="pending",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    try:
        result = await ocr_service.process_image(
            image_path=file_record.storage_path,
            output_format=request.output_format,
            language=merged_options.get("language", "auto"),
            preserve_layout=merged_options.get("preserve_layout", True),
            preserve_tables=merged_options.get("preserve_tables", True),
            options=merged_options,
        )

        job.status = "completed"
        job.progress = 100
        job.stage = "completed"
        job.result = result
        await db.commit()

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        await db.commit()

    return job


@router.post("/process-stream")
async def process_ocr_stream(
    request: OcrRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Real-Time Server-Sent Events (SSE) Streaming OCR.
    Streams 100% genuine stage and percentage progress directly from the Deep Learning pipeline.
    """
    file_record = await get_file_for_user(db, request.input_file_id)

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    if file_record.file_type not in ("image", "pdf"):
        raise HTTPException(status_code=400, detail="File is not an image or PDF")

    allowed_formats = ["docx", "xlsx", "pdf", "txt", "html"]
    if request.output_format not in allowed_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid output format. Allowed: {', '.join(allowed_formats)}",
        )

    user_id = await ensure_guest_user(db)
    opt_dict = request.options.model_dump(exclude_none=True) if request.options else {}
    req_dict = request.model_dump(exclude={"input_file_id", "options"}, exclude_none=True)
    merged_options = {**req_dict, **opt_dict}

    job = Job(
        user_id=user_id,
        input_file_id=file_record.id,
        job_type="ocr",
        output_format=request.output_format,
        config=merged_options,
        status="processing",
        progress=5,
        stage="Đang khởi tạo tài nguyên OCR...",
        started_at=datetime.utcnow(),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    job_id = job.id
    merged_options["job_id"] = job_id
    storage_path = file_record.storage_path
    output_format = request.output_format

    async def event_generator():
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()

        # Send initial job_id immediately so frontend can track and persist it
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "init", "job_id": job_id, "progress": 5, "stage": "Đang khởi tạo tài nguyên OCR..."}
        )

        async def _async_update_db_progress(p: int, s: str):
            try:
                async with AsyncSessionLocal() as db_session:
                    j = await db_session.get(Job, job_id)
                    if j and j.status == "processing":
                        j.progress = p
                        j.stage = s
                        await db_session.commit()
            except Exception:
                pass

        def sync_progress_cb(pct: int, msg: str):
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "progress", "progress": pct, "stage": msg, "job_id": job_id}
            )
            asyncio.run_coroutine_threadsafe(_async_update_db_progress(pct, msg), loop)

        async def run_worker():
            try:
                sync_progress_cb(1, "Đang nạp dữ liệu và kiểm tra cấu trúc...")
                result = await ocr_service.process_image(
                    image_path=storage_path,
                    output_format=output_format,
                    language=merged_options.get("language", "auto"),
                    preserve_layout=merged_options.get("preserve_layout", True),
                    preserve_tables=merged_options.get("preserve_tables", True),
                    options=merged_options,
                    progress_callback=sync_progress_cb,
                )

                from app.services.ocr_service import is_ocr_job_cancelled
                if is_ocr_job_cancelled(job_id) or result is None:
                    logger.info(f"Job {job_id} was cancelled, skipping completion handling.")
                    return

                # Persist completed status and result in database so preview & download work instantly
                now_utc = datetime.utcnow()
                async with AsyncSessionLocal() as db_session:
                    db_job = await db_session.get(Job, job_id)
                    if db_job:
                        db_job.status = "completed"
                        db_job.progress = 100
                        db_job.stage = "Hoàn tất!"
                        db_job.completed_at = now_utc
                        if db_job.started_at:
                            dur_sec = round((db_job.completed_at - db_job.started_at).total_seconds(), 1)
                            if isinstance(result, dict):
                                result["duration_seconds"] = dur_sec
                        db_job.result = result
                        await db_session.commit()

                job_dict = {
                    "id": job_id,
                    "status": "completed",
                    "progress": 100,
                    "stage": "Hoàn tất!",
                    "output_format": output_format,
                    "result": result,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": now_utc.isoformat(),
                }
                sync_progress_cb(100, "Hoàn tất!")
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "completed", "progress": 100, "stage": "Hoàn tất!", "job": job_dict}
                )
            except Exception as exc:
                logger.error(f"OCR Stream worker error: {exc}", exc_info=True)
                async with AsyncSessionLocal() as db_session:
                    db_job = await db_session.get(Job, job_id)
                    if db_job:
                        db_job.status = "failed"
                        db_job.progress = 100
                        db_job.stage = "Lỗi xử lý"
                        db_job.error = str(exc)
                        await db_session.commit()
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "error", "error": str(exc)}
                )

        worker_task = asyncio.create_task(run_worker())

        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=3.0)
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                if item.get("type") in ("completed", "error"):
                    break
            except asyncio.TimeoutError:
                # SSE heartbeat keepalive to prevent browser/proxy connection drop
                yield ": keepalive\n\n"

        await worker_task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/{job_id}/result")
async def get_ocr_result(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get OCR result"""
    user_id = await ensure_guest_user(db)

    result = await db.execute(
        select(Job).where(
            Job.id == job_id,
            Job.user_id == user_id,
            Job.job_type == "ocr",
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="OCR job not found")

    if job.status != "completed":
        return {
            "job_id": job.id,
            "status": job.status,
            "progress": job.progress,
            "stage": job.stage,
        }

    return {
        "job_id": job.id,
        "status": job.status,
        "result": job.result,
    }


@router.post("/{job_id}/cancel")
async def cancel_ocr(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancel in-flight OCR job immediately"""
    from app.services.ocr_service import cancel_ocr_job
    cancel_ocr_job(job_id)

    async with AsyncSessionLocal() as db_session:
        db_job = await db_session.get(Job, job_id)
        if db_job and db_job.status in ("pending", "processing"):
            db_job.status = "failed"
            db_job.error = "Đã hủy tác vụ theo yêu cầu người dùng"
            await db_session.commit()

    return {"message": "Đã hủy tác vụ OCR thành công", "job_id": job_id}