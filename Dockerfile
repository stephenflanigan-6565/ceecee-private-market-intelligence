FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV CEECEE_ENV=production
ENV CEECEE_DRY_RUN=1
ENV CEECEE_OUTREACH_ENABLED=0
CMD ["python","operator_report.py"]
