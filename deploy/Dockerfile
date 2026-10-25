# 上岸计划 ASCENT · 生产镜像
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY run.py .
ENV DX_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8321
HEALTHCHECK --interval=60s --timeout=5s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8321/api/health',timeout=4)"
CMD ["python", "run.py"]
