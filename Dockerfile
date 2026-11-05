FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SPARK_LOCAL_IP=127.0.0.1 FLEET_HOME=/data
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN python -m pip install --no-cache-dir -r requirements.lock
COPY fleet ./fleet
COPY dbt ./dbt
RUN useradd --uid 10001 --create-home fleet && mkdir -p /data && chown fleet:fleet /data
USER fleet
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "fleet.api:app", "--host", "0.0.0.0", "--port", "8000"]
