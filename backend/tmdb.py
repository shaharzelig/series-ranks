# backend/tmdb.py
import os

import requests

TMDB_BASE = "https://api.themoviedb.org/3"


def _headers() -> dict:
    key = os.getenv("TMDB_API_KEY", "")
    return {"Authorization": f"Bearer {key}"} if key else {}


def _get(path: str, params: dict | None = None) -> dict:
    r = requests.get(f"{TMDB_BASE}{path}", params=params, headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def find_show_id(title: str) -> int | None:
    """Return TMDB show ID for the best title match, or None."""
    data = _get("/search/tv", {"query": title, "language": "en-US"})
    results = data.get("results", [])
    return results[0]["id"] if results else None


def get_episode_ratings(show_id: int) -> dict[tuple[int, int], dict]:
    """
    Return {(season, episode): {"tmdb_score": float, "tmdb_votes": int}}
    for all episodes. Skips seasons that fail to fetch.
    """
    detail = _get(f"/tv/{show_id}")
    n_seasons = detail.get("number_of_seasons", 0)

    result: dict[tuple[int, int], dict] = {}
    for s in range(1, n_seasons + 1):
        try:
            season_data = _get(f"/tv/{show_id}/season/{s}")
        except Exception:
            continue
        for ep in season_data.get("episodes", []):
            key = (ep["season_number"], ep["episode_number"])
            result[key] = {
                "tmdb_score": ep.get("vote_average"),
                "tmdb_votes": ep.get("vote_count", 0),
            }
    return result
