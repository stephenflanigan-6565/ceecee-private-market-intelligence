FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV CEECEE_ENV=production
ENV CEECEE_DRY_RUN=1
ENV CEECEE_OUTREACH_ENABLED=0
CMD ["sh","-c","gunicorn --workers 2 --threads 4 --bind 0.0.0.0:${PORT:-8080} web_app:app"]
