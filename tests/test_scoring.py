# tests/test_scoring.py
import pytest
from backend.scoring import bayesian_score, merge_episodes


def test_bayesian_high_votes_trusts_raw_rating():
    # 10000 votes → nearly equal to raw rating
    result = bayesian_score(v=10000, R=9.0, C=7.5, m=100)
    assert abs(result - 9.0) < 0.02


def test_bayesian_zero_votes_returns_mean():
    result = bayesian_score(v=0, R=9.0, C=7.5, m=100)
    assert result == 7.5


def test_bayesian_pulls_low_votes_toward_mean():
    result = bayesian_score(v=50, R=9.0, C=7.5, m=100)
    assert 7.5 < result < 9.0


def test_merge_episodes_imdb_only():
    eps = [
        {"season": 1, "episode": 1, "title": "Pilot", "imdb_score": 8.0, "imdb_votes": 500},
        {"season": 1, "episode": 2, "title": "Ep2",   "imdb_score": 7.5, "imdb_votes": 300},
    ]
    result = merge_episodes(eps, tmdb_ratings={})
    assert result[0]["score"] is not None
    assert result[0]["tmdb_score"] is None
    # higher-voted episode stays closer to raw score
    assert result[0]["score"] > result[1]["score"]


def test_merge_episodes_tmdb_averages_in():
    eps = [
        {"season": 1, "episode": 1, "title": "Pilot", "imdb_score": 8.0, "imdb_votes": 500},
    ]
    tmdb = {(1, 1): {"tmdb_score": 9.0, "tmdb_votes": 200}}
    result = merge_episodes(eps, tmdb_ratings=tmdb)
    # final score is between imdb bayesian and tmdb bayesian
    assert 8.0 < result[0]["score"] < 9.0


def test_merge_episodes_no_imdb_score_gives_none():
    eps = [{"season": 1, "episode": 1, "title": "Pilot", "imdb_score": None, "imdb_votes": 0}]
    result = merge_episodes(eps, tmdb_ratings={})
    assert result[0]["score"] is None


def test_merge_episodes_fewer_than_10_episodes():
    eps = [
        {"season": 1, "episode": i, "title": f"Ep{i}", "imdb_score": 7.0 + i * 0.1, "imdb_votes": 100}
        for i in range(1, 6)
    ]
    result = merge_episodes(eps, tmdb_ratings={})
    assert len(result) == 5
    assert all(r["score"] is not None for r in result)
