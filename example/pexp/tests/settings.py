import os
import sys

example_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if example_dir not in sys.path:
    sys.path.insert(0, example_dir)

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

DEBUG = False

rdbms = os.environ.get("RDBMS", "sqlite")

if rdbms == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("PYTEST_DB_NAME", ":memory:"),
        },
    }
elif rdbms == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("PYTEST_DB_NAME", "test_pexp"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", ""),
            "PORT": os.environ.get("POSTGRES_PORT", ""),
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

INSTALLED_APPS = [
    "pexp",
    "polymorphic",
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

SECRET_KEY = "test-secret-key-for-pexp"

USE_TZ = False
