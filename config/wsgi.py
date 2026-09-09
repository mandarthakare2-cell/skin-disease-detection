import os

# Limit TensorFlow memory consumption for Render free tier (512MB RAM)
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from django.core.wsgi import get_wsgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

application = get_wsgi_application()

# Startup migration safety net for Render deployments
try:
    from django.core.management import call_command
    call_command("migrate", interactive=False)
except Exception as e:
    import logging
    logging.getLogger("django").warning(f"Startup migration check: {e}")