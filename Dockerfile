FROM python:3.12-slim
# Calibre aporta ebook-convert para pasar a EPUB los formatos que Kindle ya no acepta
# (MOBI, AZW3, FB2…). Sin recommends se queda en lo imprescindible.
RUN apt-get update && \
    apt-get install -y --no-install-recommends calibre && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--timeout", "300", "app:app"]
