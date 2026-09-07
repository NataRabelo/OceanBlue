FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

WORKDIR /app
LABEL org.opencontainers.image.title="OceanBlue" org.opencontainers.image.version="2.1.0-rc.1"

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.txt

COPY . .
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh \
    && cp /app/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh \
    && adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/instance/storage \
    && chown -R appuser:appuser /app/instance \
    && chmod 700 /app/instance /app/instance/storage

ENV FLASK_APP=wsgi.py
ENV FLASK_ENV=production

HEALTHCHECK --interval=5s --timeout=5s --retries=6 CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:5000/api/ready', timeout=4)"

USER appuser

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:5000", "--timeout", "60", "--forwarded-allow-ips", "", "wsgi:app"]
