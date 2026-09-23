FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir ".[api]" \
    && useradd --system --uid 10001 --create-home nexo \
    && chown -R nexo:nexo /app
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "deploy.server"]
