FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app:/app/tests
ENV CEECEE_ENV=synthetic PMI_RESEARCH_ENABLED=0 PMI_REVIEW_ACCESS_KEY=synthetic-review-key-at-least-24
CMD ["gunicorn","--workers","2","--threads","4","--timeout","60","--bind","0.0.0.0:8080","resource_app:app"]
