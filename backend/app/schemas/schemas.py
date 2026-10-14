"""
FileForge Backend - Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, Union, List
from pydantic import BaseModel, EmailStr, Field
from enum import Enum


# ============== Enums ==============
class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, Enum):
    CONVERT = "convert"
    OCR = "ocr"
    SPREADSHEET = "spreadsheet"


class UserTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# ============== Auth Schemas ==============
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    tier: UserTier
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ============== File Schemas ==============
class FileResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    content_type: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    url: Optional[str] = None

    class Config:
        from_attributes = True


class FileUploadResponse(BaseModel):
    files: list[FileResponse]


# ============== Job Schemas ==============
class ConversionOptions(BaseModel):
    preserve_formatting: bool = True
    table_style: str = "grid"
    image_quality: str = "high"


class OcrOptions(BaseModel):
    engine: Optional[str] = "fast_native"  # "fast_native" or "vietocr"
    language: str = "auto"  # auto, en, vi
    output_format: str = "docx"  # docx, xlsx, pdf, txt, html
    preserve_layout: bool = True
    preserve_tables: bool = True
    enhance: bool = False
    use_gpu: bool = False
    det_thresh: Optional[float] = None
    det_box_thresh: Optional[float] = None
    det_unclip_ratio: Optional[float] = None
    rec_score_thresh: Optional[float] = None
    cls_thresh: Optional[float] = None
    max_side_len: Optional[int] = None
    det_model_path: Optional[str] = None
    rec_model_path: Optional[str] = None
    cls_model_path: Optional[str] = None
    rec_keys_path: Optional[str] = None
    pages: Optional[Union[str, List[int]]] = None
    page_indices: Optional[List[int]] = None


class SpreadsheetOptions(BaseModel):
    header_row: int | str = "auto"
    sheet_name: Optional[str] = None
    cell_range: Optional[str] = None  # e.g. "A1:H50" or "B2:E20"
    start_row: Optional[int] = None
    end_row: Optional[int] = None
    start_col: Optional[str] = None
    end_col: Optional[str] = None
    include_header: bool = True
    date_format: str = "YYYY-MM-DD"
    flatten_nested: bool = True
    null_value: str = ""
    delimiter: str = ","
    indent: int = 2


class ConvertRequest(BaseModel):
    input_file_id: str
    output_format: str
    options: Optional[ConversionOptions] = None


class OcrRequest(BaseModel):
    input_file_id: str
    engine: Optional[str] = "fast_native"
    language: str = "auto"
    output_format: str = "docx"
    preserve_layout: bool = True
    preserve_tables: bool = True
    enhance: bool = False
    use_gpu: bool = False
    det_thresh: Optional[float] = None
    det_box_thresh: Optional[float] = None
    det_unclip_ratio: Optional[float] = None
    rec_score_thresh: Optional[float] = None
    cls_thresh: Optional[float] = None
    max_side_len: Optional[int] = None
    det_model_path: Optional[str] = None
    rec_model_path: Optional[str] = None
    cls_model_path: Optional[str] = None
    rec_keys_path: Optional[str] = None
    pages: Optional[Union[str, List[int]]] = None
    page_indices: Optional[List[int]] = None
    options: Optional[OcrOptions] = None


class SpreadsheetRequest(BaseModel):
    input_file_id: str
    output_format: str = "xlsx"
    options: Optional[SpreadsheetOptions] = None


class SpreadsheetPreviewRequest(BaseModel):
    input_file_id: str
    options: Optional[SpreadsheetOptions] = None


class JobResponse(BaseModel):
    id: str
    user_id: str
    input_file_id: Optional[str]
    job_type: JobType
    status: JobStatus
    output_format: str
    progress: int
    stage: Optional[str]
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class JobDetailResponse(JobResponse):
    result: Optional[dict] = None
    output_files: list["OutputFileResponse"] = []


class OutputFileResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    url: str

    class Config:
        from_attributes = True


# Update forward reference
JobDetailResponse.model_rebuild()


# ============== OCR Schemas ==============
class OcrAnalyzeResponse(BaseModel):
    language: str
    confidence: float
    has_text: bool
    has_tables: bool
    has_images: bool
    layout: list[str]
    estimated_processing_time: int


# ============== API Key Schemas ==============
class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key: Optional[str] = None  # Only shown once on creation
    created_at: datetime
    last_used_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============== Webhook Schemas ==============
class WebhookCreate(BaseModel):
    url: str
    events: list[str]


class WebhookResponse(BaseModel):
    id: str
    url: str
    events: list[str]
    is_active: bool

    class Config:
        from_attributes = True


# ============== Pagination ==============
class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int


# ============== Health ==============
class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    redis: str
