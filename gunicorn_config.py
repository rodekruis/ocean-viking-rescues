"""
Gunicorn configuration file for production deployment.

When using Infomaniak Port Redirection:
- Bind to 0.0.0.0:8000
- Configure Infomaniak to redirect 80->8000 and 443->8000
- No Nginx needed!

When using Nginx:
- Can bind to 127.0.0.1:8000 (localhost only)
- Nginx proxies to this
"""

import multiprocessing
import os

# Bind to all interfaces on port 8000
# For Infomaniak Port Redirection: use 0.0.0.0:8000
# For Nginx reverse proxy: can use 127.0.0.1:8000
bind = "0.0.0.0:8000"

# Number of worker processes
# Use 2-4 workers per core for I/O bound applications
workers = multiprocessing.cpu_count() * 2 + 1
# Alternative: Use environment variable or fixed number
# workers = int(os.getenv("WORKERS", "4"))

# Worker class
worker_class = "sync"

# Timeout for graceful workers restart
timeout = 120

# Maximum requests a worker will process before restarting
# Helps prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"  # Log to stderr
loglevel = "info"

# Process naming
proc_name = "ocean-viking-rescues"

# Preload app for better memory usage
preload_app = True

# Keep alive
keepalive = 5
