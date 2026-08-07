#!/bin/sh
set -e

# Run migrations before starting the server
python manage.py migrate --noinput

# Execute the CMD
exec "$@"
