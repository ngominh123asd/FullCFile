# FileForge — Intelligent Document Converter

> Bản đặc tả kỹ thuật — Phiên bản 2.0

---

## 1. Tổng Quan Sản Phẩm

### 1.1 Mô tả

**FileForge** là nền tảng chuyển đổi định dạng tài liệu thông minh với khả năng OCR (Tiếng Anh + Tiếng Việt), hỗ trợ REST API mạnh mẽ và giao diện web hiện đại, phá cách.

### 1.2 Mục tiêu

- Cung cấp giải pháp chuyển đổi document toàn diện cho doanh nghiệp
- Hỗ trợ ngôn ngữ: **Tiếng Anh** (chính) + **Tiếng Việt**
- Kiến trúc scalable, đa tenant với REST API
- Giao diện web độc đáo, phá cách

### 1.3 Tính năng cốt lõi

| Category | Input Formats | Output Formats |
|----------|---------------|----------------|
| **Document** | Markdown, HTML, PDF, TXT, RTF | DOCX, PDF, HTML, Markdown |
| **Spreadsheet** | CSV, XLSX, ODS, JSON | XLSX, CSV, JSON, PDF |
| **Image (OCR)** | PNG, JPG, WEBP, TIFF, BMP | DOCX, PDF, TXT, XLSX |
| **Presentation** | PPTX | PPTX, PDF, PNG |

### 1.4 Core Conversion Features

**Document Conversion:**
```
Markdown ↔ DOCX      (Python python-docx + Pandoc)
DOCX → PDF          (Python docx2pdf / LibreOffice)
Markdown → PDF      (Pandoc + WeasyPrint)
HTML → PDF           (WeasyPrint)
```

**Spreadsheet Conversion:**
```
XLSX ↔ JSON ↔ CSV
ODS ↔ JSON ↔ CSV ↔ XLSX
```

---

## 2. Kiến Trúc Hệ Thống

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Web UI)                          │
│   React 18 + TypeScript + Vite + TailwindCSS                    │
│   Shadcn/UI Components + Framer Motion                         │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTPS
┌───────────────────────────────▼─────────────────────────────────┐
│                      API Gateway / Load Balancer                 │
│                     (Nginx / Traefik)                            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
┌───────▼───────┐     ┌─────────▼─────────┐    ┌──────▼──────┐
│  FastAPI      │     │   Worker Nodes     │    │  Redis      │
│  (Core API)   │     │   (Celery/Bull)    │    │  (Queue)    │
│  Python 3.11+ │     │   - OCR Engine     │    │             │
└───────┬───────┘     │   - PDF Generator  │    └─────────────┘
        │             │   - Spreadsheet    │           │
        │             │   - Document Conv │           │
        │             └───────────────────┘           │
        │                                           │
┌───────▼───────────────────────┐           ┌────────▼────────┐
│       PostgreSQL 16+          │           │  S3 / MinIO     │
│  (Users, Jobs, Metadata)      │           │  (File Storage) │
└───────────────────────────────┘           └─────────────────┘
```

### 2.2 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend** | Python 3.11+, FastAPI | High-performance API server |
| **Task Queue** | Celery + Redis | Async job processing |
| **Database** | PostgreSQL 16+ | Metadata, Users, Billing |
| **Cache** | Redis 7+ | Sessions, Rate limiting |
| **Storage** | S3-compatible (MinIO/AWS) | File storage |
| **Frontend** | React 18, TypeScript, Vite | SPA UI |
| **UI Components** | Shadcn/UI, TailwindCSS | Modern components |
| **Animations** | Framer Motion | Micro-interactions |
| **OCR Engine** | **PaddleOCR PP-Structure** | ML-based OCR với layout analysis |
| **Document** | Pandoc, python-docx, docx2pdf | Document conversion |
| **PDF** | WeasyPrint, Playwright | PDF generation |
| **Spreadsheet** | openpyxl, pandas, xlsxwriter | Excel operations |

### 2.3 Why Python for Backend?

- **PaddleOCR Integration**: Native support, no bridge needed
- **Document Processing**: python-docx, Pandoc, WeasyPrint are Python-native
- **ML Ecosystem**: Best support for PaddleOCR, Transformers, Torch
- **Existing Code**: Reuse and extend the existing `docx_smart_converter.py`
- **Async Processing**: FastAPI + Celery = excellent for I/O-bound tasks

---

## 3. Chức Năng Chi Tiết

### 3.1 REST API

**Base URL:** `https://api.fileforge.dev/v1`

#### Authentication
```bash
# Register
POST /auth/register
{
  "email": "user@example.com",
  "password": "securepassword",
  "name": "John Doe"
}

# Login (returns JWT)
POST /auth/login
{
  "email": "user@example.com",
  "password": "securepassword"
}

# Response
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 900
}
```

#### File Operations
```bash
# Upload file(s)
POST /files/upload
Content-Type: multipart/form-data
Authorization: Bearer {token}

files: [binary]

# Response
{
  "files": [
    {
      "id": "uuid",
      "filename": "document.md",
      "file_type": "markdown",
      "size": 1024,
      "url": "/files/uuid/download"
    }
  ]
}

# List user's files
GET /files
Query: ?page=1&limit=20

# Download file
GET /files/{file_id}/download

# Delete file
DELETE /files/{file_id}
```

#### Document Conversion
```bash
# Convert document
POST /convert
{
  "input_file_id": "uuid",
  "output_format": "docx",
  "options": {
    "preserve_formatting": true,
    "table_style": "grid"
  }
}

# Response
{
  "job_id": "uuid",
  "status": "queued",
  "estimated_time": 5
}
```

#### OCR Processing (ML-Powered)
```bash
# Analyze image (detect layout, language, quality)
POST /ocr/analyze
{
  "input_file_id": "uuid"
}

# Response
{
  "language": "en",
  "confidence": 0.99,
  "has_text": true,
  "has_tables": true,
  "has_images": false,
  "layout": ["paragraph", "table", "paragraph"],
  "estimated_processing_time": 5
}

# Full OCR process
POST /ocr/process
{
  "input_file_id": "uuid",
  "language": "auto",
  "output_format": "docx",
  "preserve_layout": true,
  "preserve_tables": true
}

# Get OCR result
GET /ocr/{job_id}/result

# Response includes full layout info
{
  "job_id": "uuid",
  "status": "completed",
  "result": {
    "format": "docx",
    "pages": [
      {
        "width": 210,
        "height": 297,
        "blocks": [
          { "type": "paragraph", "text": "...", "bbox": [...] },
          { "type": "table", "rows": 5, "cols": 3, "cells": [...] }
        ]
      }
    ]
  }
}
```

#### Spreadsheet Conversion
```bash
# Convert spreadsheet
POST /spreadsheet/convert
{
  "input_file_id": "uuid",
  "output_format": "json",
  "options": {
    "header_row": 1,
    "date_format": "YYYY-MM-DD",
    "flatten_nested": true
  }
}

# Preview data structure
POST /spreadsheet/preview
{
  "input_file_id": "uuid",
  "max_rows": 10
}
```

#### Job Management
```bash
# Get job status
GET /jobs/{job_id}

# Response
{
  "id": "uuid",
  "status": "processing",  // pending | processing | completed | failed
  "progress": 65,
  "stage": "ocr_text_recognition",
  "result": null,
  "created_at": "2024-01-15T10:30:00Z"
}

# Download result
GET /jobs/{job_id}/download

# List jobs
GET /jobs
Query: ?status=completed&page=1&limit=20
```

### 3.2 Webhook Events
```bash
# Register webhook
POST /webhooks
{
  "url": "https://your-app.com/webhook",
  "events": ["job.completed", "job.failed"]
}

# Event payload
POST https://your-app.com/webhook
{
  "event": "job.completed",
  "job_id": "uuid",
  "data": {
    "output_files": [...]
  },
  "timestamp": "2024-01-15T10:35:00Z"
}
```

### 3.3 Rate Limits

| Tier | Requests/min | Upload Size | Concurrent Jobs |
|------|-------------|-------------|----------------|
| Free | 30 | 50MB | 2 |
| Pro | 100 | 500MB | 10 |
| Enterprise | 500 | 5GB | 50 |

---

## 4. Document Conversion Matrix

### 4.1 Full Matrix

```
FROM \ TO │ DOCX   PDF    HTML   MD     XLSX   CSV    JSON   TXT
───────────┼────────────────────────────────────────────────────────
Markdown  │   ✓      ✓      ✓      —       —      —      —      ✓
HTML      │   ✓      ✓      —       ✓       —      —      —      ✓
PDF       │   ✓      —       ✓       ✓       —      —      —      ✓
DOCX      │   —       ✓      ✓       ✓       —      —      —      ✓
TXT       │   ✓       ✓      ✓       ✓       —      —      —      —
RTF       │   ✓       ✓      ✓       ✓       —      —      —      ✓
CSV       │   ✓       ✓      ✓       ✓       ✓      —       ✓      ✓
XLSX      │   ✓       ✓      ✓       ✓       —       ✓       ✓      ✓
JSON      │   —       —      —       —       ✓       ✓      —       ✓
ODS       │   ✓       ✓      ✓       ✓       ✓       ✓       ✓      ✓
PNG/JPG   │   ✓       ✓      ✓       ✓       ✓      —       ✓      ✓
PPTX      │   ✓       ✓      —       ✓       —      —       —       ✓
```

### 4.2 Conversion Details

**Markdown ↔ DOCX:**
- Preserve headers, bold, italic, code blocks
- Convert tables to Word tables with styling
- Support callout blocks (![NOTE], ![WARNING], etc.)
- Convert lists (ordered/unordered/nested)

**DOCX/HTML/Markdown → PDF:**
- High-quality rendering via WeasyPrint/Pandoc
- Preserve fonts, colors, images
- Table formatting with borders
- Code syntax highlighting

**XLSX ↔ JSON:**
```python
# Input JSON structure
[
  {"name": "Alice", "age": 30, "city": "Hanoi"},
  {"name": "Bob", "age": 25, "city": "HCMC"}
]

# Options
{
  "header_row": "auto",      // or 1, 2, 3...
  "sheet_name": "Data",      // for XLSX output
  "date_format": "YYYY-MM-DD",
  "flatten_nested": true,
  "null_value": "",
  "include_empty_rows": false
}
```

---

## 5. OCR Processing (Image to Text) — ML-Powered

### 5.1 Why PaddleOCR (PP-Structure)?

| Engine | Layout Detection | Table Recovery | Multi-column | Preservation |
|--------|----------------|----------------|--------------|-------------|
| **Tesseract** | ❌ Basic | ❌ Manual | ❌ Poor | 60-70% |
| **PaddleOCR (PP-Structure)** | ✅ SOTA | ✅ Built-in | ✅ Excellent | **95%+** |
| **EasyOCR** | ⚠️ Moderate | ❌ Manual | ⚠️ Moderate | 75-85% |
| **Google Cloud Vision** | ✅ Excellent | ✅ Excellent | ✅ Excellent | **95%+** |

**PaddleOCR PP-Structure** được chọn vì:
- **Layout Analysis tích hợp**: Table, image,公式, separator detection
- **Table Recognition**: Khôi phục cấu trúc bảng 1:1
- **Multi-language**: Hỗ trợ tiếng Anh, Tiếng Việt (và có thể mở rộng)
- **Open-source**: Tự host, không phụ thuộc cloud pricing
- **Production-ready**: Được train trên massive dataset

### 5.2 Supported Languages

| Language | Code | Status |
|----------|------|--------|
| English | `en` | Primary — 99%+ accuracy |
| Vietnamese | `vi` | Supported — 95%+ accuracy |

### 5.3 Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    OCR Processing Pipeline                        │
└─────────────────────────────────────────────────────────────────┘

Image Input
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  Pre-processing (ML-enhanced)                                 │
│  • Auto deskew & rotation                                    │
│  • Contrast enhancement (adaptive)                           │
│  • Noise reduction (retinex-based)                          │
│  • Resolution optimization                                    │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  Layout Analysis (PP-Structure)  ←── Key differentiator!    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Detects:                                               │    │
│  │ • Text blocks (paragraphs)     → Preserved positions   │    │
│  │ • Tables (with cells)         → Exact structure        │    │
│  │ • Images/Figures               → Embedded              │    │
│  │ • Headers/Footers              → Page positioning       │    │
│  │ • Equations/Formulas           → LaTeX or MathML        │    │
│  │ • Separators                   → Page breaks            │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  Text Recognition (PaddleOCR DB++)

│  ┌──────────────┐    ┌──────────────┐                      │
│  │    English    │    │   Vietnamese  │                      │
│  │  (PP-OCRv4)   │    │  (Custom Vi)  │                      │
│  │   99.5%+ acc  │    │   95%+ acc    │                      │
│  └──────────────┘    └──────────────┘                      │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  Table Recognition (SLANet)  ←── Preserves 100% structure  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Cell detection → Row/Col mapping → HTML/Markdown    │    │
│  │ Merged cells → Spanning rows/cols preserved          │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  Document Reconstruction (DOCX/PDF with positions)          │
│  • Font inference (Times/Calibri/Arial detection)           │
│  • Size estimation (headers vs body)                        │
│  • Bold/Italic detection                                    │
│  • Color preservation (if detectable)                       │
│  • Spacing & alignment (left/center/right/justify)         │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
Output (DOCX/PDF/HTML with exact formatting)
```

### 5.4 Output Formats

| Format | Formatting Preservation | Use Case |
|--------|----------------------|----------|
| **DOCX** | ✅ Near-perfect | Editable, print-ready |
| **PDF** | ✅ Near-perfect | Archival, sharing |
| **HTML** | ✅ Best (CSS-based) | Web, exact positioning |
| **TXT** | ⚠️ Text only | Plain text extraction |
| **XLSX** | ✅ For tables | Data tables only |
| **Markdown** | ⚠️ Structure only | Git-friendly docs |

### 5.5 Table Recovery (Critical Feature)

```python
# Input: Scanned invoice with table
# ┌─────────────────────────────┐
# │  Invoice #12345             │
# │  ─────────────────────────  │
# │  Item       Qty    Price    │
# │  ─────────────────────────  │
# │  Apple       5     $10.00   │
# │  Banana      3      $6.00   │
# └─────────────────────────────┘

# Output: Exact table structure preserved
# - Cell positions maintained
# - Row/column count exact
# - Borders and shading (if detectable)
# - Merged cells (header spanning) preserved
```

### 5.6 Performance Targets

| Metric | Target |
|--------|--------|
| Text accuracy (EN) | ≥ 99.5% |
| Text accuracy (VI) | ≥ 95% |
| Table structure | 100% recovery |
| Layout preservation | ≥ 95% |
| Processing time (A4) | < 5 seconds |
| Processing time (A4 scan, 300 DPI) | < 10 seconds |

## 6. Database Schema

### 7.1 PostgreSQL Tables

```sql
-- Users
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255),
  name VARCHAR(255),
  avatar_url TEXT,
  tier VARCHAR(20) DEFAULT 'free',
  stripe_customer_id VARCHAR(255),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Files
CREATE TABLE files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  filename VARCHAR(255) NOT NULL,
  file_type VARCHAR(50) NOT NULL,
  file_size BIGINT NOT NULL,
  storage_path VARCHAR(500),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP
);

-- Jobs
CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  input_file_id UUID REFERENCES files(id),
  status VARCHAR(20) DEFAULT 'pending',
  job_type VARCHAR(50) NOT NULL,
  config JSONB NOT NULL DEFAULT '{}',
  progress INTEGER DEFAULT 0,
  stage VARCHAR(100),
  result JSONB,
  error TEXT,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

-- API Keys
CREATE TABLE api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  key_hash VARCHAR(255) NOT NULL,
  last_used_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_files_user ON files(user_id);
CREATE INDEX idx_jobs_user ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_api_keys_user ON api_keys(user_id);
```

---

## 7. Security

### 7.1 Authentication
- JWT tokens (15 min access, 7 days refresh)
- API Keys for programmatic access
- Rate limiting per user/key

### 7.2 File Security
- Magic bytes validation
- Max size enforcement
- Automatic expiration (24h for free tier)
- Encrypted storage (AES-256)

---

## 8. Development Roadmap

### Phase 1: Core (6-8 weeks)
- [ ] FastAPI backend setup
- [ ] User authentication (JWT)
- [ ] File upload/download
- [ ] MD ↔ DOCX conversion (extend existing Python code)
- [ ] DOCX/HTML → PDF conversion
- [ ] Basic web UI
- [ ] Unit tests

### Phase 2: Expansion (4-6 weeks)
- [ ] **OCR với PaddleOCR PP-Structure (ML)**
  - Layout analysis (tables, columns, images)
  - Table recognition (SLANet)
  - Format preservation ≥95%
  - Support EN + VI
- [ ] Spreadsheet conversions (XLSX ↔ JSON ↔ CSV)
- [ ] API keys & documentation
- [ ] Job queue with Celery
- [ ] Webhooks

### Phase 3: Polish (2-4 weeks)
- [ ] Full UI implementation
- [ ] Stripe billing
- [ ] Performance optimization
- [ ] Documentation

### Phase 4: Scale
- [ ] Multi-region deployment
- [ ] Advanced caching
- [ ] Mobile optimization

---

## 9. Success Metrics

| Metric | 3 months | 6 months | 12 months |
|--------|----------|----------|-----------|
| API Users | 500 | 2,000 | 10,000 |
| Conversions/month | 10K | 100K | 1M |
| Uptime | 99.5% | 99.9% | 99.95% |
| Avg Response Time | < 2s | < 1s | < 500ms |

---

## 10. Appendix

### 10.1 File Size Limits

| Tier | Max File | Daily Jobs | Monthly Jobs |
|------|----------|------------|--------------|
| Free | 50 MB | 50 | 500 |
| Pro | 500 MB | 500 | 10,000 |
| Enterprise | 5 GB | Unlimited | Unlimited |

### 10.2 Glossary

- **FastAPI**: Modern Python web framework, async support
- **Celery**: Distributed task queue cho background jobs
- **PaddleOCR (PP-Structure)**: ML-based OCR engine với layout analysis — **selected for this project**
- **PP-Structure**: PaddleOCR's document structure analysis system (table recognition, layout detection)
- **SLANet**: Table recognition model trong PaddleOCR
- **DB++**: New text detection model với better accuracy
- **Glassmorphism**: Frosted glass UI effect
- **WeasyPrint**: HTML/CSS to PDF converter
- **Layout Analysis**: Xác định cấu trúc tài liệu (paragraphs, tables, images, headers)

---

*Bản đặc tả này là tài liệu sống, cập nhật theo tiến độ phát triển.*
*Last updated: 2026-08-17 (v2.1 — PaddleOCR PP-Structure for 95%+ format preservation)*
