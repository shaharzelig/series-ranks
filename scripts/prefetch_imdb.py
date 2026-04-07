# scripts/prefetch_imdb.py
"""Download IMDB datasets and pre-process to parquet at build time."""
import os
import sys

import pandas as pd

DATA_DIR = os.environ.get(
    "IMDB_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data", "imdb"),
)
os.makedirs(DATA_DIR, exist_ok=True)

IMDB_BASE = "https://datasets.imdbws.com"
USECOLS = {
    "title.basics.tsv.gz":  ["tconst", "titleType", "primaryTitle", "startYear"],
    "title.episode.tsv.gz": ["tconst", "parentTconst", "seasonNumber", "episodeNumber"],
    "title.ratings.tsv.gz": ["tconst", "averageRating", "numVotes"],
}


def download_tsv(filename: str) -> str:
    import gzip, urllib.request
    dest = os.path.join(DATA_DIR, filename.replace(".gz", ""))
    print(f"Downloading {filename}…")
    with urllib.request.urlopen(f"{IMDB_BASE}/{filename}") as r:
        data = gzip.decompress(r.read())
    with open(dest, "wb") as f:
        f.write(data)
    print(f"  saved {len(data) // 1024 // 1024}MB → {dest}")
    return dest


def load_tsv(filename: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, filename.replace(".gz", ""))
    if not os.path.exists(path):
        download_tsv(filename)
    return pd.read_csv(path, sep="\t", low_memory=False, na_values=["\\N"],
                       usecols=USECOLS[filename])


print("Loading raw IMDB datasets…")
basics   = load_tsv("title.basics.tsv.gz")
episodes = load_tsv("title.episode.tsv.gz")
ratings  = load_tsv("title.ratings.tsv.gz")

# ── series.parquet ──────────────────────────────────────────────────────────
print("Building series.parquet…")
tv = basics[basics["titleType"] == "tvSeries"][["tconst", "primaryTitle", "startYear"]].copy()
ep_counts = episodes.groupby("parentTconst").size().rename("episode_count")
tv = tv.join(ep_counts, on="tconst")
tv.to_parquet(os.path.join(DATA_DIR, "series.parquet"), index=False)
print(f"  {len(tv):,} series")

# ── episodes.parquet ────────────────────────────────────────────────────────
print("Building episodes.parquet…")
eps = episodes[["tconst", "parentTconst", "seasonNumber", "episodeNumber"]].copy()
for col in ("seasonNumber", "episodeNumber"):
    eps[col] = pd.to_numeric(eps[col], errors="coerce")
eps = eps.dropna(subset=["seasonNumber", "episodeNumber"])
eps = eps.merge(ratings[["tconst", "averageRating", "numVotes"]], on="tconst", how="left")
eps = eps.merge(basics[["tconst", "primaryTitle"]], on="tconst", how="left")
eps["seasonNumber"]  = eps["seasonNumber"].astype("int16")
eps["episodeNumber"] = eps["episodeNumber"].astype("int16")
eps["numVotes"]      = pd.to_numeric(eps["numVotes"], errors="coerce").fillna(0).astype("int32")
# Sort by parentTconst so pyarrow row-group min/max stats allow efficient per-series filtering
eps = eps.sort_values("parentTconst").reset_index(drop=True)
eps.to_parquet(os.path.join(DATA_DIR, "episodes.parquet"), index=False, row_group_size=50_000)
print(f"  {len(eps):,} episodes")

print("Done.")
