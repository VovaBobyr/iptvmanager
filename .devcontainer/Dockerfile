FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg sqlite3 \
    && rm -rf /var/lib/apt/lists/*
