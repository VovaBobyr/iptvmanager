FROM python:3.13-slim AS runtime

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 iptv \
    && mkdir -p /app/data \
    && chown -R iptv:iptv /app
USER iptv

ENV IPTV_DATABASE_URL=sqlite:////app/data/iptv.db
EXPOSE 8000
VOLUME ["/app/data"]

CMD ["uvicorn", "iptv_manager.app:app", "--host", "0.0.0.0", "--port", "8000"]
