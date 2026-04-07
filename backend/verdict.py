# backend/verdict.py
import math
import re
import statistics


def parse_episode_code(code: str) -> tuple[int, int]:
    """
    Parse 'S03E05', '3x05', 's3e5' → (season, episode).
    Raises ValueError if format is unrecognised.
    """
    code = code.strip().upper()
    m = re.match(r"S(\d+)E(\d+)$", code) or re.match(r"(\d+)X(\d+)$", code)
    if not m:
        raise ValueError(f"Invalid episode format: {code!r}. Use S03E05 or 3x05.")
    return int(m.group(1)), int(m.group(2))


def compute_verdict(episodes: list[dict], current_season: int, current_episode: int) -> dict:
    """
    Given a merged episode list and the user's current position,
    return a verdict dict.
    """
    rated = [e for e in episodes if e.get("score") is not None]
    if not rated:
        return {
            "verdict": "you_can_stop",
            "message": "No rated episodes found",
            "top_n": 0,
            "top_n_ahead": 0,
            "top_n_behind": 0,
            "best_episode_ahead": None,
            "avg_score_ahead": None,
            "avg_score_behind": None,
            "watched_median": None,
            "watched_best": None,
            "pct_ahead_beats_median": None,
            "pct_ahead_beats_best": None,
            "momentum": {"behind_median": None, "ahead_median": None, "direction": None},
            "seasons": [],
        }

    top_n = min(10, len(rated))
    top_eps = sorted(rated, key=lambda e: e["score"], reverse=True)[:top_n]
    top_set = {(e["season"], e["episode"]) for e in top_eps}

    watched = {
        (e["season"], e["episode"])
        for e in rated
        if e["season"] < current_season
        or (e["season"] == current_season and e["episode"] <= current_episode)
    }

    # ── Density ─────────────────────────────────────────────────────────────
    watched_eps = [e for e in rated if (e["season"], e["episode"]) in watched]
    ahead_eps   = [e for e in rated if (e["season"], e["episode"]) not in watched]

    watched_scores = [e["score"] for e in watched_eps]
    ahead_scores   = [e["score"] for e in ahead_eps]

    if watched_scores:
        watched_median = round(statistics.median(watched_scores), 3)
        watched_best   = round(max(watched_scores), 3)
        if ahead_scores:
            pct_ahead_beats_median = round(
                100 * sum(1 for s in ahead_scores if s > watched_median) / len(ahead_scores)
            )
            pct_ahead_beats_best = round(
                100 * sum(1 for s in ahead_scores if s > watched_best) / len(ahead_scores)
            )
        else:
            pct_ahead_beats_median = 0
            pct_ahead_beats_best   = 0
    else:
        watched_median = watched_best = pct_ahead_beats_median = pct_ahead_beats_best = None

    top_n_ahead = sum(1 for key in top_set if key not in watched)
    top_n_behind = top_n - top_n_ahead

    threshold_keep = math.ceil(top_n * 0.7)
    threshold_up = math.ceil(top_n * 0.4)

    if top_n_ahead >= threshold_keep:
        verdict = "keep_watching"
    elif top_n_ahead >= threshold_up:
        verdict = "up_to_you"
    else:
        verdict = "you_can_stop"

    ahead  = ahead_eps
    best_ahead = max(ahead, key=lambda e: e["score"], default=None)

    avg_ahead = round(sum(e["score"] for e in ahead) / len(ahead), 1) if ahead else None
    behind = watched_eps
    avg_behind = round(sum(e["score"] for e in behind) / len(behind), 1) if behind else None

    # ── Momentum ─────────────────────────────────────────────────────────────
    behind_window    = watched_eps[-5:]
    ahead_window     = ahead_eps[:5]

    behind_scores_m  = [e["score"] for e in behind_window]
    ahead_scores_m   = [e["score"] for e in ahead_window]

    behind_median_m  = round(statistics.median(behind_scores_m), 3) if behind_scores_m else None
    ahead_median_m   = round(statistics.median(ahead_scores_m),  3) if ahead_scores_m  else None

    if behind_median_m is not None and ahead_median_m is not None:
        diff      = ahead_median_m - behind_median_m
        direction = "up" if diff >= 0.3 else "down" if diff <= -0.3 else "flat"
    else:
        direction = None

    momentum = {
        "behind_median": behind_median_m,
        "ahead_median":  ahead_median_m,
        "direction":     direction,
    }

    return {
        "verdict": verdict,
        "message": f"{top_n_ahead} of the top {top_n} episodes are still ahead of you",
        "top_n": top_n,
        "top_n_ahead": top_n_ahead,
        "top_n_behind": top_n_behind,
        "best_episode_ahead": best_ahead,
        "avg_score_ahead": avg_ahead,
        "avg_score_behind": avg_behind,
        "watched_median": watched_median,
        "watched_best": watched_best,
        "pct_ahead_beats_median": pct_ahead_beats_median,
        "pct_ahead_beats_best": pct_ahead_beats_best,
        "momentum": momentum,
        "seasons": [],
    }
