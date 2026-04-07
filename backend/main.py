# backend/main.py
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from backend import imdb, tmdb
from backend.scoring import merge_episodes
from backend.verdict import compute_verdict, parse_episode_code

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    imdb.preload()  # load parquet files before accepting requests
    yield


app = FastAPI(title="Series Ranks", lifespan=lifespan)


def _get_merged_episodes(imdb_id: str) -> list[dict]:
    """Fetch IMDB episodes and optionally merge TMDB ratings."""
    eps = imdb.get_episodes(imdb_id)
    tmdb_ratings: dict = {}
    if os.getenv("TMDB_API_KEY"):
        try:
            info = imdb.get_series_info(imdb_id)
            if info:
                show_id = tmdb.find_show_id(info["title"])
                if show_id:
                    tmdb_ratings = tmdb.get_episode_ratings(show_id)
        except Exception:
            pass  # TMDB unavailable — silently fall back to IMDB only
    return merge_episodes(eps, tmdb_ratings)


@app.get("/api/search")
def search(q: str = Query(..., min_length=1)):
    return imdb.search_series(q)


@app.get("/api/series/{imdb_id}")
def get_series(imdb_id: str):
    info = imdb.get_series_info(imdb_id)
    if not info:
        raise HTTPException(status_code=404, detail="Series not found")
    episodes = _get_merged_episodes(imdb_id)
    return {
        "title": info["title"],
        "imdb_id": imdb_id,
        "total_episodes": len(episodes),
        "episodes": episodes,
    }


@app.get("/api/verdict/{imdb_id}")
def get_verdict(imdb_id: str, at: str = Query(...)):
    try:
        season, episode = parse_episode_code(at)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    episodes = _get_merged_episodes(imdb_id)
    return compute_verdict(episodes, season, episode)


# Serve frontend — must come last so API routes take priority
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
