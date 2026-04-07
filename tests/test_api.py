# tests/test_api.py
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


MOCK_EPISODES = [
    {"tconst": "tt111", "season": 1, "episode": i, "title": f"Ep{i}",
     "imdb_score": 7.0 + i * 0.1, "imdb_votes": 500}
    for i in range(1, 11)
]

MOCK_SERIES_INFO = {"imdb_id": "tt7587890", "title": "The Rookie", "year": "2018"}
MOCK_SEARCH = [{"imdb_id": "tt7587890", "title": "The Rookie", "year": "2018", "episode_count": 139}]


@pytest.fixture
def client():
    with patch("backend.imdb.search_series", return_value=MOCK_SEARCH), \
         patch("backend.imdb.get_series_info", return_value=MOCK_SERIES_INFO), \
         patch("backend.imdb.get_episodes", return_value=MOCK_EPISODES), \
         patch("backend.tmdb.find_show_id", return_value=None):
        from backend.main import app
        yield TestClient(app)


def test_search_returns_results(client):
    r = client.get("/api/search?q=Rookie")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["imdb_id"] == "tt7587890"


def test_search_requires_q(client):
    r = client.get("/api/search")
    assert r.status_code == 422


def test_series_returns_episodes(client):
    r = client.get("/api/series/tt7587890")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "The Rookie"
    assert len(data["episodes"]) == 10
    assert "score" in data["episodes"][0]


def test_series_not_found(client):
    with patch("backend.imdb.get_series_info", return_value=None):
        r = client.get("/api/series/tt0000000")
    assert r.status_code == 404


def test_verdict_keep_watching(client):
    r = client.get("/api/verdict/tt7587890?at=S01E01")
    assert r.status_code == 200
    data = r.json()
    assert data["verdict"] in ("keep_watching", "up_to_you", "you_can_stop")
    assert "top_n_ahead" in data
    assert "message" in data


def test_verdict_invalid_episode_format(client):
    r = client.get("/api/verdict/tt7587890?at=badformat")
    assert r.status_code == 422


def test_verdict_requires_at_param(client):
    r = client.get("/api/verdict/tt7587890")
    assert r.status_code == 422
