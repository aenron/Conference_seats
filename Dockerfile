FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# CairoSVG 渲染 PNG/PDF 所需的动态库与常用中文字体。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY README.md ./

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/generated_files \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8100

CMD ["python", "-m", "app.mcp_sse_server"]
