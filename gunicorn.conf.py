import os


bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "1"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
preload_app = os.getenv("GUNICORN_PRELOAD", "").strip().casefold() in {"1", "true", "yes", "on"}
accesslog = "-"
errorlog = "-"
capture_output = True
