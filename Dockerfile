# Hidden Hand arena. Bots run as an unprivileged user inside this container.
FROM python:3.12-slim
RUN useradd --create-home arena && mkdir /data && chown arena /data
WORKDIR /app
COPY --chown=root:root . .
USER arena
ENV ARENA_DATA=/data PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "arena.py"]
