FROM python:3.12-slim
WORKDIR /srv/sunny
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend backend
COPY scripts scripts
COPY frontend/dist frontend/dist
RUN mkdir -p runtime/database runtime/uploads
EXPOSE 8000
CMD ["uvicorn","backend.app.main:app","--host","0.0.0.0","--port","8000","--workers","1"]
