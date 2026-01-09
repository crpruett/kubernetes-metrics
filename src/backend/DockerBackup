FROM python:3.13-alpine

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn kubernetes

COPY src/backend/main.py /app/main.py

EXPOSE 22112
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "22112"]

