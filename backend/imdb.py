# backend/imdb.py
import gzip
import os
import time
import urllib.request

import pandas as pd

IMDB_BASE = "https://datasets.imdbws.com"
# IMDB_DATA_DIR env var lets Render point this to the build directory so
# files downloaded at build time persist across cold starts without re-downloading.
CACHE_DIR = os.environ.get("IMDB_DATA_DIR", os.path.expanduser("~/.cache/imdb_datasets"))
CACHE_TTL = 86400  # 24 hours

# Module-level dataframe cache — loaded once per process
_df_cache: dict[str, pd.DataFrame] = {}

_USECOLS = {
    "title.basics.tsv.gz":  ["tconst", "titleType", "primaryTitle", "startYear"],
    "title.episode.tsv.gz": ["tconst", "parentTconst", "seasonNumber", "episodeNumber"],
    "title.ratings.tsv.gz": ["tconst", "averageRating", "numVotes"],
}


def _cache_path(filename: str) -> str:
    return os.path.join(CACHE_DIR, filename.replace(".gz", ""))


def _needs_download(filename: str) -> bool:
    path = _cache_path(filename)
    if not os.path.exists(path):
        return True
    return (time.time() - os.path.getmtime(path)) > CACHE_TTL


def _download_tsv(filename: str) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    url = f"{IMDB_BASE}/{filename}"
    with urllib.request.urlopen(url) as response:
        data = gzip.decompress(response.read())
    with open(_cache_path(filename), "wb") as f:
        f.write(data)


def _get_df(filename: str) -> pd.DataFrame:
    if filename not in _df_cache:
        if _needs_download(filename):
            _download_tsv(filename)
        df = pd.read_csv(
            _cache_path(filename), sep="\t", low_memory=False, na_values=["\\N"],
            usecols=_USECOLS[filename],
        )
        # Keep only TV series rows — reduces basics from 10M → ~200K rows
        if filename == "title.basics.tsv.gz":
            df = df[df["titleType"] == "tvSeries"].reset_index(drop=True)
        _df_cache[filename] = df
    return _df_cache[filename]


def search_series(query: str, limit: int = 5) -> list[dict]:
    """Return up to `limit` TV series whose title contains `query`."""
    basics = _get_df("title.basics.tsv.gz")
    episodes = _get_df("title.episode.tsv.gz")

    q = query.lower()
    matches = basics[basics["primaryTitle"].str.lower().str.contains(q, na=False)].copy()

    ep_counts = episodes.groupby("parentTconst").size().rename("episode_count")
    matches = matches.join(ep_counts, on="tconst")

    # Relevance: 0=exact, 1=starts-with, 2=contains — then by episode_count desc
    def relevance(title: str) -> int:
        t = title.lower()
        if t == q:
            return 0
        if t.startswith(q):
            return 1
        return 2

    matches["_relevance"] = matches["primaryTitle"].map(relevance)
    matches = matches.sort_values(
        ["_relevance", "episode_count"], ascending=[True, False]
    ).head(limit)

    return [
        {
            "imdb_id": row["tconst"],
            "title": row["primaryTitle"],
            "year": str(int(row["startYear"])) if pd.notna(row.get("startYear")) else None,
            "episode_count": int(row["episode_count"]) if pd.notna(row.get("episode_count")) else 0,
        }
        for _, row in matches.iterrows()
    ]


def get_series_info(imdb_id: str) -> dict | None:
    """Return basic metadata for a series by its IMDB ID, or None if not found."""
    basics = _get_df("title.basics.tsv.gz")
    rows = basics[basics["tconst"] == imdb_id]
    if rows.empty:
        return None
    r = rows.iloc[0]
    return {
        "imdb_id": imdb_id,
        "title": r["primaryTitle"],
        "year": str(int(r["startYear"])) if pd.notna(r.get("startYear")) else None,
    }


def get_episodes(imdb_id: str) -> list[dict]:
    """
    Return all episodes for a series sorted by (season, episode).
    Each episode has: season, episode, title, imdb_score, imdb_votes.
    """
    basics = _get_df("title.basics.tsv.gz")
    episodes = _get_df("title.episode.tsv.gz")
    ratings = _get_df("title.ratings.tsv.gz")

    eps = episodes[episodes["parentTconst"] == imdb_id].copy()
    eps = eps.merge(ratings, on="tconst", how="left")
    eps = eps.merge(basics[["tconst", "primaryTitle"]], on="tconst", how="left")

    for col in ("seasonNumber", "episodeNumber", "averageRating", "numVotes"):
        eps[col] = pd.to_numeric(eps[col], errors="coerce")

    eps = eps.dropna(subset=["seasonNumber", "episodeNumber"])
    eps = eps.sort_values(["seasonNumber", "episodeNumber"])

    return [
        {
            "tconst": row["tconst"],
            "season": int(row["seasonNumber"]),
            "episode": int(row["episodeNumber"]),
            "title": row["primaryTitle"] if pd.notna(row["primaryTitle"]) else None,
            "imdb_score": float(row["averageRating"]) if pd.notna(row["averageRating"]) else None,
            "imdb_votes": int(row["numVotes"]) if pd.notna(row["numVotes"]) else 0,
        }
        for _, row in eps.iterrows()
    ]
