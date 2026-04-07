# scripts/prefetch_imdb.py
"""Download IMDB datasets into the build directory. Run once at build time."""
import os
import sys

# Point imdb module at the build-time data dir before importing
os.environ.setdefault("IMDB_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data", "imdb"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.imdb import _download_tsv

for filename in ("title.basics.tsv.gz", "title.episode.tsv.gz", "title.ratings.tsv.gz"):
    print(f"Downloading {filename}…")
    _download_tsv(filename)
    print(f"  done.")
