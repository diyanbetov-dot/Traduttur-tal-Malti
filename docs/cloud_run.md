# Cloud Run Deployment Guidance

The translator is CPU-heavy because hybrid mode loads spaCy, PyTorch, Transformers and OPUS-MT. The correct fix is controlled startup and readiness, not reducing translation quality or bypassing OPUS-MT.

## Required Environment

```text
TRANSLATOR_ENGINE=v2
TRANSLATION_BACKEND=hybrid
PRELOAD_SPACY=true
PRELOAD_OPUS=true
RULE_POSTPROCESSING_ENABLED=true
OPUS_MT_MODEL_DIR=/app/models/opus-mt-en-mt
TRANSLATION_LOCAL_FILES_ONLY=true
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

## Probes

Use:

- liveness: `/health`
- readiness/startup: `/ready`

`/ready` remains false if OPUS-MT or spaCy failed to load.

## Runtime Shape

Start with:

```text
WEB_CONCURRENCY=1
GUNICORN_THREADS=1
GUNICORN_TIMEOUT=120
GUNICORN_GRACEFUL_TIMEOUT=30
```

Multiple workers may duplicate the OPUS model in memory. Multiple threads do not improve model loading and can make CPU contention worse.

## Cold Starts

The Docker image stores the OPUS model locally, so runtime should not download model files. Cold starts still load the model into RAM. If first-request latency must be near-instant, configure minimum instances to 1. That setting costs money continuously, so keep it optional.

## Benchmark Before Raising Concurrency

Run `scripts/benchmark_runtime.py` locally or in a one-off cloud instance and compare:

- initialization time;
- first translation latency;
- second translation latency;
- memory before and after model load;
- whether backend is `hybrid` and OPUS output is present.
