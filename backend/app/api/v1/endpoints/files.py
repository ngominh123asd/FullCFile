"""
FileForge Backend - Files Endpoints
No auth required - uses guest user for storage
"""
import os
import uuid
import aiofiles
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.config import settings
from app.models.database import File as FileModel, User
from app.schemas.schemas import FileResponse, FileUploadResponse

router = APIRouter()

GUEST_USER_ID = "00000000-0000-0000-0000-000000000001"

FILE_TYPE_MAP = {
    ".md": "markdown",
    ".html": "html",
    ".htm": "html",
    ".pdf": "pdf",
    ".txt": "text",
    ".rtf": "rtf",
    ".docx": "docx",
    ".doc": "doc",
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".ods": "ods",
    ".json": "json",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".tiff": "image",
    ".bmp": "image",
    ".gif": "image",
    ".pptx": "presentation",
}


async def ensure_guest_user(db: AsyncSession) -> str:
    """Ensure guest user exists, return user_id"""
    result = await db.execute(select(User).where(User.id == GUEST_USER_ID))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=GUEST_USER_ID,
            email="guest@fileforge.local",
            name="Guest",
            tier="guest",
        )
        db.add(user)
        await db.flush()

    return GUEST_USER_ID


async def save_file_to_storage(file: UploadFile, user_id: str) -> tuple[str, int]:
    """Save uploaded file to local storage"""
    user_dir = os.path.join("/tmp", "fileforge_uploads", user_id)
    os.makedirs(user_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1].lower()
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(user_dir, unique_filename)

    size = 0
    async with aiofiles.open(file_path, "wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            await out_file.write(chunk)

    return file_path, size


def verify_file_magic_bytes(file_path: str, ext: str, original_filename: str) -> tuple[bool, str]:
    """Verify that the file's binary content matches its claimed extension (detect fake/spoofed extensions)."""
    import zipfile
    ext_clean = ext.lower().lstrip(".")

    try:
        with open(file_path, "rb") as f:
            header_bytes = f.read(2048)
    except Exception as e:
        return False, f"Không thể đọc nội dung tệp tin: {str(e)}"

    if len(header_bytes) == 0:
        return False, f"Tệp tin '{original_filename}' rỗng (0 bytes), vui lòng kiểm tra lại."

    # 1. PDF
    if ext_clean == "pdf":
        if not header_bytes.startswith(b"%PDF-") and b"%PDF-" not in header_bytes[:1024]:
            return False, f"Tệp tin '{original_filename}' không phải định dạng PDF hợp lệ (nội dung thực tế không khớp với phần mở rộng .pdf)."
        return True, ""

    # 2. Modern Office formats (DOCX, XLSX, PPTX, ODS) - must be valid Zip packages with proper internal structure
    if ext_clean in ["docx", "xlsx", "pptx", "ods"]:
        if not (header_bytes.startswith(b"PK\x03\x04") or header_bytes.startswith(b"PK\x05\x06")):
            return False, f"Tệp tin '{original_filename}' không phải tài liệu {ext_clean.upper()} hợp lệ (phát hiện tệp giả mạo hoặc bị đổi đuôi)."
        try:
            with zipfile.ZipFile(file_path, "r") as z:
                namelist = z.namelist()
                if ext_clean == "docx" and not any(n.startswith("word/") or n == "[Content_Types].xml" for n in namelist):
                    return False, f"Tệp tin '{original_filename}' không có cấu trúc tài liệu Word (.docx) hợp lệ."
                if ext_clean == "xlsx" and not any(n.startswith("xl/") or n == "[Content_Types].xml" for n in namelist):
                    return False, f"Tệp tin '{original_filename}' không có cấu trúc bảng tính Excel (.xlsx) hợp lệ."
                if ext_clean == "pptx" and not any(n.startswith("ppt/") or n == "[Content_Types].xml" for n in namelist):
                    return False, f"Tệp tin '{original_filename}' không có cấu trúc bản trình chiếu PowerPoint (.pptx) hợp lệ."
                if ext_clean == "ods" and not any(n == "content.xml" or n == "mimetype" for n in namelist):
                    return False, f"Tệp tin '{original_filename}' không có cấu trúc bảng tính ODS hợp lệ."
        except Exception:
            return False, f"Tệp tin '{original_filename}' bị hỏng hoặc đổi đuôi .{ext_clean} giả mạo."
        return True, ""

    # 3. Legacy Office formats (DOC, XLS) - support Binary OLE, HTML/MHTML Office export, Word/Excel 2003 XML, RTF, OpenXML
    if ext_clean in ["doc", "xls"]:
        ole_magic = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        is_ole = header_bytes.startswith(ole_magic)
        is_html_office = (
            header_bytes.startswith(b"<html")
            or b"<html" in header_bytes[:1024]
            or header_bytes.startswith(b"<!DOCTYPE")
            or b"<!DOCTYPE" in header_bytes[:512]
            or header_bytes.startswith(b"MIME-Version:")
        )
        is_xml_office = (
            header_bytes.startswith(b"<?xml")
            or b"<?xml" in header_bytes[:256]
        )
        is_rtf = header_bytes.startswith(b"{\\rtf")
        is_openxml = header_bytes.startswith(b"PK\x03\x04")

        # Executable binary check
        if header_bytes.startswith(b"MZ") or header_bytes.startswith(b"\x7fELF"):
            return False, f"Phát hiện tệp tin thực thi nguy hiểm giả mạo định dạng .{ext_clean}."

        if not (is_ole or is_html_office or is_xml_office or is_rtf or is_openxml):
            return False, f"Tệp tin '{original_filename}' không phải tài liệu Microsoft {ext_clean.upper()} hợp lệ."
        return True, ""

    # 4. Images
    if ext_clean == "png":
        if not header_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return False, f"Tệp tin '{original_filename}' không phải định dạng ảnh PNG hợp lệ."
        return True, ""
    if ext_clean in ["jpg", "jpeg"]:
        if not header_bytes.startswith(b"\xff\xd8\xff"):
            return False, f"Tệp tin '{original_filename}' không phải định dạng ảnh JPEG hợp lệ."
        return True, ""
    if ext_clean == "gif":
        if not (header_bytes.startswith(b"GIF87a") or header_bytes.startswith(b"GIF89a")):
            return False, f"Tệp tin '{original_filename}' không phải định dạng ảnh GIF hợp lệ."
        return True, ""
    if ext_clean == "webp":
        if not (header_bytes.startswith(b"RIFF") and header_bytes[8:12] == b"WEBP"):
            return False, f"Tệp tin '{original_filename}' không phải định dạng ảnh WEBP hợp lệ."
        return True, ""
    if ext_clean == "bmp":
        if not header_bytes.startswith(b"BM"):
            return False, f"Tệp tin '{original_filename}' không phải định dạng ảnh BMP hợp lệ."
        return True, ""
    if ext_clean in ["tiff", "tif"]:
        if not (header_bytes.startswith(b"II*\x00") or header_bytes.startswith(b"MM\x00*")):
            return False, f"Tệp tin '{original_filename}' không phải định dạng ảnh TIFF hợp lệ."
        return True, ""

    # 5. RTF
    if ext_clean == "rtf":
        if not header_bytes.startswith(b"{\\rtf"):
            return False, f"Tệp tin '{original_filename}' không phải định dạng RTF hợp lệ."
        return True, ""

    # 6. Text / CSV / MD / JSON / HTML
    if ext_clean in ["csv", "txt", "md", "json", "html", "htm"]:
        # Binary null bytes or executable magic bytes in text indicate spoofing
        if b"\x00" in header_bytes[:512]:
            return False, f"Tệp tin '{original_filename}' chứa mã nhị phân không hợp lệ cho định dạng văn bản .{ext_clean}."
        if header_bytes.startswith(b"MZ") or header_bytes.startswith(b"\x7fELF"):
            return False, f"Phát hiện tệp tin thực thi nguy hiểm giả mạo định dạng .{ext_clean}."
        if header_bytes.startswith(b"%PDF-") and ext_clean in ["csv", "txt", "json"]:
            return False, f"Tệp tin '{original_filename}' thực chất là tài liệu PDF nhưng bị đổi đuôi sang .{ext_clean}."
        if header_bytes.startswith(b"PK\x03\x04") and ext_clean in ["csv", "txt", "md"]:
            return False, f"Tệp tin '{original_filename}' thực chất là tệp nén/Office nhưng bị đổi đuôi sang .{ext_clean}."
        return True, ""

    return True, ""


@router.post("/upload", response_model=FileUploadResponse)
async def upload_files(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload files - no auth required"""
    user_id = await ensure_guest_user(db)

    uploaded_files = []

    for file in files:
        # Validate file extension
        ext = os.path.splitext(file.filename)[1].lower()
        if ext.lstrip(".") not in [e.lstrip(".") for e in settings.ALLOWED_EXTENSIONS]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Định dạng tệp '{ext}' không được hỗ trợ. Vui lòng tải lên các định dạng: PDF, Word, Excel, CSV, PPTX, Ảnh, Markdown...",
            )

        # Save to storage
        file_path, file_size = await save_file_to_storage(file, user_id)

        # Validate magic bytes / genuine file structure
        is_valid, error_msg = verify_file_magic_bytes(file_path, ext, file.filename)
        if not is_valid:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )

        file_type = FILE_TYPE_MAP.get(ext, "unknown")

        # Create database record
        file_record = FileModel(
            user_id=user_id,
            filename=f"{uuid.uuid4()}{ext}",
            original_filename=file.filename,
            file_type=file_type,
            file_size=file_size,
            storage_path=file_path,
            content_type=file.content_type,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.add(file_record)
        await db.flush()
        await db.refresh(file_record)

        uploaded_files.append(
            FileResponse(
                id=file_record.id,
                filename=file_record.original_filename,
                original_filename=file_record.original_filename,
                file_type=file_record.file_type,
                file_size=file_record.file_size,
                content_type=file_record.content_type,
                created_at=file_record.created_at,
                expires_at=file_record.expires_at,
                url=f"/api/v1/files/{file_record.id}/download",
            )
        )

    return FileUploadResponse(files=uploaded_files)


@router.get("", response_model=list[FileResponse])
async def list_files(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List uploaded files"""
    user_id = await ensure_guest_user(db)

    offset = (page - 1) * limit
    result = await db.execute(
        select(FileModel)
        .where(FileModel.user_id == user_id)
        .order_by(FileModel.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    files = result.scalars().all()

    return [
        FileResponse(
            id=f.id,
            filename=f.original_filename,
            original_filename=f.original_filename,
            file_type=f.file_type,
            file_size=f.file_size,
            content_type=f.content_type,
            created_at=f.created_at,
            expires_at=f.expires_at,
            url=f"/api/v1/files/{f.id}/download",
        )
        for f in files
    ]


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get file metadata"""
    user_id = await ensure_guest_user(db)

    result = await db.execute(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.user_id == user_id,
        )
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return FileResponse(
        id=file_record.id,
        filename=file_record.original_filename,
        original_filename=file_record.original_filename,
        file_type=file_record.file_type,
        file_size=file_record.file_size,
        content_type=file_record.content_type,
        created_at=file_record.created_at,
        expires_at=file_record.expires_at,
        url=f"/api/v1/files/{file_record.id}/download",
    )


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download file"""
    from fastapi.responses import FileResponse as FastAPIFileResponse

    user_id = await ensure_guest_user(db)

    result = await db.execute(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.user_id == user_id,
        )
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    if not os.path.exists(file_record.storage_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on storage",
        )

    return FastAPIFileResponse(
        path=file_record.storage_path,
        filename=file_record.original_filename,
        media_type=file_record.content_type or "application/octet-stream",
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a file"""
    user_id = await ensure_guest_user(db)

    result = await db.execute(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.user_id == user_id,
        )
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Delete from storage
    if os.path.exists(file_record.storage_path):
        os.remove(file_record.storage_path)

    await db.delete(file_record)

    return {"message": "File deleted successfully"}