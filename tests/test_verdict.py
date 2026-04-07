# tests/test_verdict.py
import pytest
from backend.verdict import parse_episode_code, compute_verdict


# ── parse_episode_code ──────────────────────────────────────────────────────

def test_parse_standard_format():
    assert parse_episode_code("S03E05") == (3, 5)

def test_parse_lowercase():
    assert parse_episode_code("s03e05") == (3, 5)

def test_parse_x_format():
    assert parse_episode_code("3x05") == (3, 5)

def test_parse_no_leading_zeros():
    assert parse_episode_code("S3E5") == (3, 5)

def test_parse_invalid_raises():
    with pytest.raises(ValueError, match="Invalid episode format"):
        parse_episode_code("episode 5")


# ── compute_verdict ─────────────────────────────────────────────────────────

def _make_episodes(scores):
    """Helper: list of episodes with given scores, season 1."""
    return [
        {"season": 1, "episode": i + 1, "title": f"Ep{i+1}", "score": s,
         "imdb_score": s, "imdb_votes": 100}
        for i, s in enumerate(scores)
    ]

def test_verdict_keep_watching():
    # 10 episodes, user at ep 1, all top 10 still ahead
    eps = _make_episodes([9.0, 8.9, 8.8, 8.7, 8.6, 8.5, 8.4, 8.3, 8.2, 8.1])
    result = compute_verdict(eps, current_season=1, current_episode=1)
    assert result["verdict"] == "keep_watching"
    assert result["top_n_ahead"] == 9  # ep1 is watched, 9 remain
    assert result["top_n"] == 10

def test_verdict_you_can_stop():
    # user at end — all top episodes behind
    eps = _make_episodes([9.0, 8.9, 8.8, 8.7, 8.6, 8.5, 8.4, 8.3, 8.2, 8.1])
    result = compute_verdict(eps, current_season=1, current_episode=10)
    assert result["verdict"] == "you_can_stop"
    assert result["top_n_ahead"] == 0
    assert result["best_episode_ahead"] is None

def test_verdict_up_to_you():
    # ~half the top episodes still ahead
    eps = _make_episodes([9.0, 8.9, 8.8, 8.7, 8.6, 8.5, 8.4, 8.3, 8.2, 8.1])
    result = compute_verdict(eps, current_season=1, current_episode=5)
    assert result["verdict"] == "up_to_you"

def test_verdict_scales_with_fewer_than_10_episodes():
    # 5-episode series, user at ep 1
    eps = _make_episodes([9.0, 8.5, 8.0, 7.5, 7.0])
    result = compute_verdict(eps, current_season=1, current_episode=1)
    assert result["top_n"] == 5  # not 10
    assert result["verdict"] == "keep_watching"

def test_verdict_best_episode_ahead_is_highest_score_remaining():
    eps = _make_episodes([7.0, 7.5, 9.5, 8.0, 6.5])
    result = compute_verdict(eps, current_season=1, current_episode=1)
    assert result["best_episode_ahead"]["episode"] == 3  # score 9.5

def test_verdict_message_uses_top_n():
    eps = _make_episodes([9.0, 8.9, 8.8, 8.7, 8.6, 8.5, 8.4, 8.3, 8.2, 8.1])
    result = compute_verdict(eps, current_season=1, current_episode=1)
    assert "top 10" in result["message"]
