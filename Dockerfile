FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt requirements_module.txt ./

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt -r requirements_module.txt

# Install additional dependencies from git
RUN pip3 install git+https://github.com/m-bain/whisperx.git \
    && pip3 install git+https://github.com/facebookresearch/demucs#egg=demucs

# Copy application code
COPY . .

# Create directory for model downloads
RUN mkdir -p /root/.cache/huggingface

# Download models during build
COPY scripts/ /app/scripts/

# Create directory and download wav2vec2 model
RUN mkdir -p models/ASR/whisper && wget -nc https://download.pytorch.org/torchaudio/models/wav2vec2_fairseq_base_ls960_asr_ls960.pth \
    -O models/ASR/whisper/wav2vec2_fairseq_base_ls960_asr_ls960.pth

# Download additional models from Hugging Face
RUN python3 scripts/huggingface_download.py

CMD ["python3", "main.py"]