#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys

# Automatically find the GDAL DLL in Conda environment
conda_prefix = os.environ.get("CONDA_PREFIX", "")
gdal_bin = os.path.join(conda_prefix, "Library", "bin")
os.environ["PATH"] = gdal_bin + ";" + os.environ.get("PATH", "")

# Set the versioned GDAL DLL explicitly (3.11 → gdal311.dll)
gdal_dll = os.path.join(gdal_bin, "gdal.dll")
if not os.path.exists(gdal_dll):
    raise RuntimeError(f"GDAL DLL not found at {gdal_dll}")

os.environ["GDAL_LIBRARY_PATH"] = gdal_dll
print("GDAL_LIBRARY_PATH set to:", gdal_dll)

# Continue with Django imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gisproject.settings")
try:
    from django.core.management import execute_from_command_line
except ImportError as exc:
    raise ImportError(
        "Couldn't import Django. Are you sure it's installed and available on your PYTHONPATH?"
    ) from exc

execute_from_command_line(sys.argv)


# -----------------------------
# Standard Django bootstrap
# -----------------------------
def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gisproject.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
