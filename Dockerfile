# Use a lightweight official Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TRANSLATOR_ENGINE=v2 \
    TRANSLATION_BACKEND=opus_mt \
    PORT=8080

# Set working directory
WORKDIR /app

# Install system dependencies needed for compiling some packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch (CPU-only version to reduce Docker image size significantly)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install other requirements
RUN pip install --no-cache-dir \
    transformers \
    sentencepiece \
    spacy \
    flask \
    gunicorn

# Pre-download the Hugging Face translation model during build phase
# This bakes the model weights directly into the container image so there is no startup download delay.
RUN python -c "from transformers import MarianMTModel, MarianTokenizer; \
    MarianTokenizer.from_pretrained('Helsinki-NLP/opus-mt-en-mt'); \
    MarianMTModel.from_pretrained('Helsinki-NLP/opus-mt-en-mt')"

# Pre-download the spaCy English grammar model
RUN python -m spacy download en_core_web_sm

# Copy the application code into the container
COPY Essentials/ /app/Essentials/
COPY translator_v2/ /app/translator_v2/

# Expose port
EXPOSE 8080

# Start the Flask app using Gunicorn for production-grade serving
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 Essentials.app:app
