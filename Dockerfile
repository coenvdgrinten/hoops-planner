FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock manage.py ./
COPY src/ src/

# Install dependencies
RUN uv sync --frozen

# Set Python path
ENV PYTHONPATH=/app/src

# Create media directory
RUN mkdir -p /app/media

EXPOSE 8000

CMD ["uv", "run", "manage.py", "runserver", "0.0.0.0:8000"]
