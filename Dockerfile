FROM python:3.13.9-slim-bookworm@sha256:b685a4fa58bb19d1814d78a1ec0f0208f351452724f78b20212c984d6e124a34

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN groupadd --gid 10001 momenria && useradd --uid 10001 --gid momenria --no-create-home momenria
COPY requirements.txt ./
RUN pip install --requirement requirements.txt
COPY . .
RUN mkdir -p /data/private/sources /data/private/results /data/private/characters /app/staticfiles && chown -R momenria:momenria /data/private /app/staticfiles

USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "momenria.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-"]
