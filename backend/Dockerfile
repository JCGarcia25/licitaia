# LicitaIA — Backend (FastAPI + Celery)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt constraints-release-candidate.txt ./
RUN pip install --no-cache-dir -c constraints-release-candidate.txt -r requirements.txt psycopg2-binary

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
