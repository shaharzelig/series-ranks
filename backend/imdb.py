# backend/imdb.py
import os

import pandas as pd

CACHE_DIR = os.environ.get("IMDB_DATA_DIR", os.path.expanduser("~/.cache/imdb_datasets"))

# Series index — loaded once at startup, stays in memory (~20MB)
_series_df: pd.DataFrame | None = None


def _series() -> pd.DataFrame:
    global _series_df
    if _series_df is None:
        _series_df = pd.read_parquet(os.path.join(CACHE_DIR, "series.parquet"))
    return _series_df


def _episodes_path() -> str:
    return os.path.join(CACHE_DIR, "episodes.parquet")


def preload_series() -> None:
    """Eagerly load the series index at startup (small, ~20MB).
    Episodes are loaded lazily on first request."""
    _series()


def search_series(query: str, limit: int = 5) -> list[dict]:
    """Return up to `limit` TV series whose title contains `query`."""
    df = _series()
    q = query.lower()
    matches = df[df["primaryTitle"].str.lower().str.contains(q, na=False)].copy()

    def relevance(title: str) -> int:
        t = title.lower()
        if t == q:         return 0
        if t.startswith(q): return 1
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
    df = _series()
    rows = df[df["tconst"] == imdb_id]
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
    Uses parquet filter pushdown — only reads this series' rows from disk.
    """
    import pyarrow.parquet as pq
    table = pq.read_table(
        _episodes_path(),
        filters=[("parentTconst", "=", imdb_id)],
    )
    eps = table.to_pandas().sort_values(["seasonNumber", "episodeNumber"])

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
