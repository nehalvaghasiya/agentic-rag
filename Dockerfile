FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN adduser --disabled-password --gecos '' rag
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
COPY infra ./infra
RUN pip install --no-cache-dir .
USER rag
EXPOSE 8001
CMD ["agentic-rag", "serve", "--host", "0.0.0.0", "--port", "8001", "--config", "/app/configs/demo.yaml"]
