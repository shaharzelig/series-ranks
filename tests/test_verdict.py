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

def test_verdict_multi_season_boundary():
    # User at end of season 1 — season 2 episodes are all ahead
    eps = [
        {"season": 1, "episode": i, "title": f"S1E{i}", "score": 7.0 + i * 0.1, "imdb_score": 7.0 + i * 0.1, "imdb_votes": 100}
        for i in range(1, 6)
    ] + [
        {"season": 2, "episode": i, "title": f"S2E{i}", "score": 8.0 + i * 0.1, "imdb_score": 8.0 + i * 0.1, "imdb_votes": 100}
        for i in range(1, 6)
    ]
    result = compute_verdict(eps, current_season=1, current_episode=5)
    # All season 2 episodes are ahead
    ahead_seasons = {e["season"] for e in eps if (e["season"], e["episode"]) not in
                     {(e2["season"], e2["episode"]) for e2 in eps
                      if e2["season"] < 1 or (e2["season"] == 1 and e2["episode"] <= 5)}}
    assert result["avg_score_ahead"] is not None
    # The top episodes should mostly be in S2 (higher scores)
    assert result["best_episode_ahead"]["season"] == 2


# ── density metrics ─────────────────────────────────────────────────────────

def test_density_basic():
    # Watched: S1E1(6.0), S1E2(8.0) → median=7.0, best=8.0
    # Ahead: S1E3(9.0), S1E4(7.5), S1E5(6.5), S1E6(5.5)
    # beats median (7.0): [9.0, 7.5] = 2/4 = 50%
    # beats best  (8.0): [9.0]       = 1/4 = 25%
    eps = _make_episodes([6.0, 8.0, 9.0, 7.5, 6.5, 5.5])
    result = compute_verdict(eps, current_season=1, current_episode=2)
    assert result["watched_median"] == 7.0
    assert result["watched_best"] == 8.0
    assert result["pct_ahead_beats_median"] == 50
    assert result["pct_ahead_beats_best"] == 25

def test_density_all_none_when_no_watched_rated():
    # S1E1 is unrated — watched set is empty after filtering to rated
    eps = [
        {"season": 1, "episode": 1, "title": "E1", "score": None, "imdb_score": None, "imdb_votes": 0},
        {"season": 1, "episode": 2, "title": "E2", "score": 8.0,  "imdb_score": 8.0,  "imdb_votes": 100},
    ]
    result = compute_verdict(eps, current_season=1, current_episode=1)
    assert result["watched_median"] is None
    assert result["watched_best"] is None
    assert result["pct_ahead_beats_median"] is None
    assert result["pct_ahead_beats_best"] is None

def test_density_zero_when_nothing_ahead():
    # User at last episode — nothing ahead, percentages are 0 (not None)
    eps = _make_episodes([7.0, 8.0, 9.0])
    result = compute_verdict(eps, current_season=1, current_episode=3)
    assert result["watched_median"] == 8.0   # median of [7.0, 8.0, 9.0]
    assert result["pct_ahead_beats_median"] == 0
    assert result["pct_ahead_beats_best"] == 0

def test_early_return_includes_all_fields():
    # No rated episodes → early return; shape must match full return
    eps = [{"season": 1, "episode": 1, "title": "E1", "score": None, "imdb_score": None, "imdb_votes": 0}]
    result = compute_verdict(eps, current_season=1, current_episode=1)
    assert result["verdict"] == "you_can_stop"
    assert result["watched_median"] is None
    assert result["pct_ahead_beats_median"] is None
    assert result["momentum"] == {"behind_median": None, "ahead_median": None, "direction": None}
    assert result["seasons"] == []


# ── momentum ────────────────────────────────────────────────────────────────

def test_momentum_direction_up():
    # last 5 watched: [6.0,6.5,6.8,7.0,7.0] → sorted median = 6.8
    # next 5 ahead:   [8.0,7.9,8.0,8.2,8.5] → sorted median = 8.0
    # diff = 1.2 ≥ 0.3 → up
    eps = _make_episodes([6.0, 6.5, 6.8, 7.0, 7.0, 8.0, 7.9, 8.0, 8.2, 8.5])
    result = compute_verdict(eps, current_season=1, current_episode=5)
    assert result["momentum"]["direction"] == "up"
    assert result["momentum"]["behind_median"] < result["momentum"]["ahead_median"]

def test_momentum_direction_down():
    # reverse: good behind, weak ahead
    eps = _make_episodes([8.0, 7.9, 8.0, 8.2, 8.5, 6.0, 6.5, 6.8, 7.0, 7.0])
    result = compute_verdict(eps, current_season=1, current_episode=5)
    assert result["momentum"]["direction"] == "down"

def test_momentum_direction_flat():
    # both windows median ~7.2, diff < 0.3
    eps = _make_episodes([7.0, 7.5, 7.2, 7.3, 7.1, 7.3, 7.0, 7.4, 7.2, 7.1])
    result = compute_verdict(eps, current_season=1, current_episode=5)
    assert result["momentum"]["direction"] == "flat"

def test_momentum_direction_none_when_nothing_ahead():
    eps = _make_episodes([7.0, 8.0, 9.0])
    result = compute_verdict(eps, current_season=1, current_episode=3)
    assert result["momentum"]["direction"] is None
    assert result["momentum"]["ahead_median"] is None
    assert result["momentum"]["behind_median"] == 8.0  # median of [7,8,9]

def test_momentum_object_always_present():
    eps = _make_episodes([8.0])
    result = compute_verdict(eps, current_season=1, current_episode=1)
    assert "momentum" in result
    assert isinstance(result["momentum"], dict)
