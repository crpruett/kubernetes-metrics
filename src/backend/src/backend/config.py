import os

APP_NAME = os.getenv("APP_NAME", "Kubernetes Metrics Board")

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "22112"))
