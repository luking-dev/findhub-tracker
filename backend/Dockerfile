FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app:/app/GoogleFindMyTools

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Librería no oficial para consultar Google Find Hub (Nova API + descifrado E2EE)
RUN git clone --depth 1 https://github.com/leonboe1/GoogleFindMyTools.git /app/GoogleFindMyTools

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r /app/GoogleFindMyTools/requirements.txt

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]