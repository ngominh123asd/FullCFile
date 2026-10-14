"""
FileForge Backend - Celery Tasks
Async tasks for heavy processing (OCR, large file conversions)
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="process_ocr")
def process_ocr(self, file_id: str, output_format: str, options: dict):
    """Process OCR job in background with three-tier fallback"""
    try:
        from app.services.ocr_service import ocr_service
        from app.core.database import AsyncSessionLocal
        from app.models.database import File, Job
        from sqlalchemy import select
        import asyncio

        async def run_ocr():
            async with AsyncSessionLocal() as db:
                # Get file
                result = await db.execute(select(File).where(File.id == file_id))
                file_record = result.scalar_one_or_none()

                if not file_record:
                    raise ValueError(f"File not found: {file_id}")

                # Run OCR
                result = await ocr_service.process_image(
                    image_path=file_record.storage_path,
                    output_format=output_format,
                    **options,
                )

                # Update job
                job_result = await db.execute(
                    select(Job).where(Job.input_file_id == file_id).order_by(Job.created_at.desc())
                )
                job = job_result.scalar_one_or_none()

                if job:
                    job.status = "completed"
                    job.progress = 100
                    job.result = result

                return result

        result = asyncio.run(run_ocr())
        return {"status": "success", "result": result}

    except Exception as e:
        logger.error(f"OCR task failed: {e}")
        # Mark job as failed before propagating
        try:
            import asyncio
            from app.core.database import AsyncSessionLocal
            from app.models.database import Job
            from sqlalchemy import select

            async def mark_failed():
                async with AsyncSessionLocal() as db:
                    job_result = await db.execute(
                        select(Job).where(Job.input_file_id == file_id).order_by(Job.created_at.desc())
                    )
                    job = job_result.scalar_one_or_none()
                    if job:
                        job.status = "failed"
                        job.error = str(e)
            asyncio.run(mark_failed())
        except Exception:
            pass
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@shared_task(bind=True, name="process_document_conversion")
def process_document_conversion(self, file_id: str, output_format: str, options: dict):
    """Process document conversion in background"""
    try:
        from app.services.document_service import document_service
        from app.core.database import AsyncSessionLocal
        from app.models.database import File, Job
        from sqlalchemy import select
        import asyncio

        async def run_conversion():
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(File).where(File.id == file_id))
                file_record = result.scalar_one_or_none()

                if not file_record:
                    raise ValueError(f"File not found: {file_id}")

                result = await document_service.convert(
                    input_path=file_record.storage_path,
                    output_format=output_format,
                    options=options,
                )

                # Update job status
                job_result = await db.execute(
                    select(Job).where(Job.input_file_id == file_id).order_by(Job.created_at.desc())
                )
                job = job_result.scalar_one_or_none()

                if job:
                    job.status = "completed"
                    job.progress = 100
                    job.result = result

                return result

        result = asyncio.run(run_conversion())
        return {"status": "success", "result": result}

    except Exception as e:
        logger.error(f"Conversion task failed: {e}")
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@shared_task(bind=True, name="process_spreadsheet_conversion")
def process_spreadsheet_conversion(self, file_id: str, output_format: str, options: dict):
    """Process spreadsheet conversion in background"""
    try:
        from app.services.spreadsheet_service import spreadsheet_service
        from app.core.database import AsyncSessionLocal
        from app.models.database import File, Job
        from sqlalchemy import select
        import asyncio

        async def run_conversion():
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(File).where(File.id == file_id))
                file_record = result.scalar_one_or_none()

                if not file_record:
                    raise ValueError(f"File not found: {file_id}")

                result = await spreadsheet_service.convert(
                    input_path=file_record.storage_path,
                    output_format=output_format,
                    options=options,
                )

                # Update job status
                job_result = await db.execute(
                    select(Job).where(Job.input_file_id == file_id).order_by(Job.created_at.desc())
                )
                job = job_result.scalar_one_or_none()

                if job:
                    job.status = "completed"
                    job.progress = 100
                    job.result = result

                return result

        result = asyncio.run(run_conversion())
        return {"status": "success", "result": result}

    except Exception as e:
        logger.error(f"Spreadsheet task failed: {e}")
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise