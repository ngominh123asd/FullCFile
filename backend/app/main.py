"""
FileForge Backend - Main FastAPI Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api.v1.endpoints import auth, files, convert, ocr, spreadsheet, jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    await init_db()

    # Warmup OCR engines (load models into memory before first request)
    # This eliminates the ~1-2s delay on the first OCR call
    try:
        from app.services.ocr_service import _get_rapid_engine, _get_vietocr_onnx_predictor
        print("🔄 Warming up OCR engines...")
        _get_rapid_engine()  # Pre-load RapidOCR DBNet
        _get_vietocr_onnx_predictor()  # Pre-load VietOCR ONNX
        print("✅ OCR engines ready!")
    except Exception as warmup_err:
        # Non-fatal: engines will load lazily on first use
        import logging
        logging.getLogger(__name__).warning(f"OCR warmup skipped: {warmup_err}")

    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} started!")
    print(f"📦 Environment: {settings.ENVIRONMENT}")

    yield
    # Shutdown
    await close_db()
    print(f"👋 {settings.APP_NAME} shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Intelligent Document Converter - Convert documents, OCR, Spreadsheets",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Type", "Content-Length"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": exc.body,
        },
    )


# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
app.include_router(convert.router, prefix="/api/v1/convert", tags=["Conversion"])
app.include_router(ocr.router, prefix="/api/v1/ocr", tags=["OCR"])
app.include_router(spreadsheet.router, prefix="/api/v1/spreadsheet", tags=["Spreadsheet"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])


# Health check
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "name": settings.APP_NAME,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "version": settings.APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
