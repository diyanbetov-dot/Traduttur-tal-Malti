# Build stage: install Python dependencies and prepare the OPUS model locally.
FROM python:3.11-slim AS build

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements-core.txt requirements-neural.txt ./
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-core.txt -r requirements-neural.txt

# Download OPUS-MT model weights (Helsinki-NLP/opus-mt-en-mt) at build time
RUN python -c "from transformers import MarianMTModel, MarianTokenizer; model='Helsinki-NLP/opus-mt-en-mt'; out='/models/opus-mt-en-mt'; tok=MarianTokenizer.from_pretrained(model); mt=MarianMTModel.from_pretrained(model); tok.save_pretrained(out); mt.save_pretrained(out)"

# Download spaCy English model at build time so there is zero network I/O at runtime
RUN python -m spacy download en_core_web_sm

# Pre-generate the lexicon binary cache (lexicon_db.pkl) at build time.
# This cuts cold-start database load from ~1.5s to ~230ms.
COPY Essentials/ /build/Essentials/
COPY translator_v2/ /build/translator_v2/
ENV PYTHONPATH=/build
RUN python -c "from translator_v2.maltese.lexicon.database import get_lexicon_db; get_lexicon_db()"

# Runtime stage: no build tools, no runtime model downloads.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8080 \
    TRANSLATOR_ENGINE=v2 \
    TRANSLATION_BACKEND=hybrid \
    PRELOAD_SPACY=true \
    PRELOAD_OPUS=true \
    RULE_POSTPROCESSING_ENABLED=true \
    OPUS_MT_MODEL_DIR=/app/models/opus-mt-en-mt \
    TRANSLATION_LOCAL_FILES_ONLY=true \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

WORKDIR /app
COPY --from=build /usr/local /usr/local
COPY --from=build /models /app/models
COPY app.py gunicorn.conf.py requirements*.txt README.md ./
COPY Essentials/ /app/Essentials/
# Overwrite with pre-built binary cache from the build stage (faster than text-parse at runtime)
COPY --from=build /build/Essentials/finaldics/lexicon_db.pkl /app/Essentials/finaldics/lexicon_db.pkl
COPY translator_v2/ /app/translator_v2/
COPY data/ /app/data/
COPY docs/ /app/docs/

EXPOSE 8080
CMD ["gunicorn", "-c", "gunicorn.conf.py", "Essentials.app:app"]
