import asyncio
import django
from django.conf import settings
settings.configure()
django.setup()
from django.db.models.query import ModelIterable
print("has aiter:", hasattr(ModelIterable, "__aiter__"))
