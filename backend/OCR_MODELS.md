# Optional local OCR models

Install into the persistent `ocr-models` Docker volume:

```sh
docker compose exec backend python scripts/setup_ocr_models.py
docker compose restart backend celery-worker
```

Downloads are pinned to revisions and verified with SHA-256. Inference does not
make external OCR requests. A missing optional model falls back to installed OCR.

| Model | Source and license | Use |
| --- | --- | --- |
| Tesseract Vietnamese best | [tesseract-ocr/tessdata_best](https://github.com/tesseract-ocr/tessdata_best), Apache-2.0 | Scanned PDF text; the installed fast model remains on the photograph path |
| VietOCR handwriting | [DungHugging/vietocr-handwritten-finetune](https://huggingface.co/DungHugging/vietocr-handwritten-finetune), MIT per model card | Selected colored handwritten table cells |

Handwriting remains uncertain, particularly Vietnamese accents and telephone
digits. Refined handwritten cells carry `needs_review` metadata, a yellow fill
and a comment in XLSX, and a corresponding preview highlight. No document-specific
names, phone numbers or sequential row values are substituted into OCR output.

Private sample images and diagnostic output live under `diagnostics/`, excluded
from Docker images by `.dockerignore`.
