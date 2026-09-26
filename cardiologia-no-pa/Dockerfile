FROM python:3.12-slim
WORKDIR /app
COPY gateway.py test_gateway.py ./
RUN python -m unittest -v test_gateway
ENV PORT=8080 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 65534:65534
EXPOSE 8080
CMD ["python", "-u", "gateway.py"]
