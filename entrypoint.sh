#!/bin/sh
set -e

# Run migrations before starting the server
uv run manage.py migrate --noinput

# Execute the CMD
exec "$@"
