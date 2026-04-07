# backend/scoring.py


def bayesian_score(v: float, R: float, C: float, m: float = 100.0) -> float:
    """
    Bayesian-weighted score. Pulls low-vote episodes toward the series mean C.
    v: vote count (must be >= 0), R: raw rating, C: series mean, m: minimum vote threshold.
    """
    if v <= 0:
        return C
    return (v / (v + m)) * R + (m / (v + m)) * C


def merge_episodes(imdb_eps: list[dict], tmdb_ratings: dict) -> list[dict]:
    """
    Merge IMDB episode list with optional TMDB ratings.
    tmdb_ratings: {(season, episode): {"tmdb_score": float, "tmdb_votes": int}}
    Returns episodes with added `score`, `tmdb_score`, `tmdb_votes` fields.
    """
    valid_scores = [e["imdb_score"] for e in imdb_eps if e.get("imdb_score") is not None]
    C = sum(valid_scores) / len(valid_scores) if valid_scores else 7.0

    result = []
    for ep in imdb_eps:
        key = (ep["season"], ep["episode"])
        tmdb = tmdb_ratings.get(key, {})

        imdb_b = None
        if ep.get("imdb_score") is not None:
            imdb_b = bayesian_score(ep.get("imdb_votes", 0), ep["imdb_score"], C)

        tmdb_b = None
        tmdb_score = tmdb.get("tmdb_score")
        tmdb_votes = tmdb.get("tmdb_votes", 0)
        if tmdb_score is not None and tmdb_score > 0:
            tmdb_b = bayesian_score(tmdb_votes, tmdb_score, C)

        components = [s for s in [imdb_b, tmdb_b] if s is not None]
        final = round(sum(components) / len(components), 3) if components else None

        result.append({
            **ep,
            "tmdb_score": tmdb_score,
            "tmdb_votes": tmdb_votes,
            "score": final,
        })

    return result
