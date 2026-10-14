# Backend Dockerfile - Full Stack with OCR + LibreOffice
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies (Torch CPU first for minimal image size)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y onnxruntime && \
    pip install --no-cache-dir --no-deps onnxruntime-gpu

# Both CPU and GPU wheels use the same ``onnxruntime`` package directory. The
# uninstall above removes those files after pip has already marked the GPU
# distribution as installed, so restore the files explicitly in a cached,
# separate layer.
RUN pip install --no-cache-dir --force-reinstall --no-deps onnxruntime-gpu==1.19.2

# ==================== Production Stage ====================
FROM python:3.11-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install all runtime dependencies and fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    poppler-utils \
    libmagic1 \
    pandoc \
    libreoffice-core \
    libreoffice-writer \
    libreoffice-impress \
    libreoffice-calc \
    tesseract-ocr \
    tesseract-ocr-vie \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    fontconfig \
    fonts-liberation \
    fonts-liberation2 \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    fonts-dejavu \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed Python packages
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Configure dynamic linker for NVIDIA CUDA/cuDNN libraries
RUN echo '/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib' > /etc/ld.so.conf.d/nvidia.conf && \
    echo '/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib' >> /etc/ld.so.conf.d/nvidia.conf && \
    echo '/usr/local/lib/python3.11/site-packages/nvidia/cuda_runtime/lib' >> /etc/ld.so.conf.d/nvidia.conf && \
    echo '/usr/local/lib/python3.11/site-packages/nvidia/cuda_nvrtc/lib' >> /etc/ld.so.conf.d/nvidia.conf && \
    echo '/usr/local/lib/python3.11/site-packages/nvidia/curand/lib' >> /etc/ld.so.conf.d/nvidia.conf && \
    echo '/usr/local/lib/python3.11/site-packages/nvidia/cufft/lib' >> /etc/ld.so.conf.d/nvidia.conf && \
    ldconfig

# Copy TrueType fonts and refresh font cache
COPY fonts/ /usr/share/fonts/truetype/windows/
RUN fc-cache -f

# Copy app code
COPY . .

# Create dirs
RUN mkdir -p /app/models /tmp/fileforge_uploads /tmp/celery

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
