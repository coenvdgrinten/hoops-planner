FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install system dependencies for WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock manage.py ./
COPY src/ src/

# Create media directory (assets are copied separately if needed)
RUN mkdir -p /app/media

# Install dependencies
RUN uv sync --frozen

# Set Python path
ENV PYTHONPATH=/app/src

# Copy and make entrypoint executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uv", "run", "manage.py", "runserver", "0.0.0.0:8000"]

# Create media directory and copy assets
RUN mkdir -p /app/media/assets
COPY media/assets/ /app/media/assets/

EXPOSE 8000

CMD ["uv", "run", "manage.py", "runserver", "0.0.0.0:8000"]
