FROM python:3.11-slim

LABEL maintainer="your.email@example.com"
LABEL description="ProdGuardian - Production readiness auditor"

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

ENTRYPOINT ["prodguardian"]
CMD ["--help"]
