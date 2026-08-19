#!/bin/sh
set -e

# Run migrations before starting the server
uv run manage.py migrate --noinput

# In development, bootstrap an admin user. The registration flow requires
# admin approval, and the e2e suite uses this account to approve the test
# users it registers (credentials: admin / adminpass123).
case "${DEBUG:-false}" in
  true|True|TRUE)
    uv run python - <<'EOF'
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hoops_planner.settings")
import django

django.setup()
from django.contrib.auth.models import User

admin = User.objects.filter(username="admin").first()
if admin is None:
    User.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="adminpass123",
        is_staff=True,
        is_superuser=True,
    )
else:
    admin.is_staff = True
    admin.is_superuser = True
    admin.is_active = True
    admin.set_password("adminpass123")
    admin.save()
EOF
    ;;
esac

# Execute the CMD
exec "$@"
