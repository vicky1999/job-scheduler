# app/core/model_registry.py

import importlib
from pathlib import Path

import app
from app.core.models import Base


def import_all_models():
    app_dir = Path(app.__file__).parent

    for path in app_dir.rglob("models.py"):
        if path == app_dir / "core" / "models.py":
            continue

        relative = path.relative_to(app_dir.parent)
        module_name = ".".join(relative.with_suffix("").parts)

        importlib.import_module(module_name)
