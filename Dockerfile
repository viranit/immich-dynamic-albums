# syntax=docker/dockerfile:1

# ---- build stage ----
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime stage ----
FROM python:3.12-slim
LABEL maintainer="viranit" \
      description="Immich Dynamic Albums \u2014 Web UI"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.12/site-packages"

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app
COPY --from=builder /install /install
COPY . .

# Compile translation catalogs (.po -> .mo) so Flask-Babel can serve them at runtime.
RUN pybabel compile -d translations --statistics 2>/dev/null || true

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 5000

# Run database migrations then start gunicorn
CMD ["sh", "-c", "flask db upgrade && gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 'run:app'"]
