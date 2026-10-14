"""Install pinned optional OCR models into the persistent model volume.

Run: docker compose exec backend python scripts/setup_ocr_models.py
No document data is sent to the model hosts.
"""
import hashlib
import os
from pathlib import Path
import requests

MODELS = [
    ('tessdata_best/vie.traineddata',
     'https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/vie.traineddata',
     'b6b49293d95d0b6dbd8780174627e82c75be957b6f4ed9862155540d6b00bb45'),
    ('handwriting/transformerocr.pth',
     'https://huggingface.co/DungHugging/vietocr-handwritten-finetune/resolve/0827b42e17cb0e1c1bbda5aac11f7cc5c816e0ca/transformerocr.pth',
     'd5357730c328e40dd1aeae7288994d8ad85979f8334c03c9bfad53c320114fa7'),
]


def install():
    root = Path(os.environ.get('OCR_MODEL_DIR','/app/models'))
    for name,url,digest in MODELS:
        target = root/name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            print(name, 'verified')
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix+'.part')
        checksum = hashlib.sha256()
        with requests.get(url,stream=True,timeout=120) as response:
            response.raise_for_status()
            with temporary.open('wb') as output:
                for chunk in response.iter_content(1024*1024):
                    checksum.update(chunk)
                    output.write(chunk)
        if checksum.hexdigest() != digest:
            raise RuntimeError('Checksum mismatch: '+name)
        temporary.replace(target)
        print(name,'installed and verified')


if __name__ == '__main__':
    install()
