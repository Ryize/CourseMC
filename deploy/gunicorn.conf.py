import multiprocessing
import os


bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
worker_class = "gthread"
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
capture_output = True

# The web container is not published directly; only Nginx can reach it.
forwarded_allow_ips = "*"

# Kept as documentation for sizing larger servers.
recommended_sync_workers = multiprocessing.cpu_count() * 2 + 1
