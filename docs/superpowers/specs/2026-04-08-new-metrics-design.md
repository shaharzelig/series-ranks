# New Metrics: Trajectory & Density — Design Spec

**Date:** 2026-04-08
**Status:** Approved

---

## Overview

Extend the "Should I keep watching?" verdict with two new signals:

1. **Density** — what fraction of remaining episodes beat what you've already seen (benchmarked against your watched median and your personal best)
2. **Trajectory** — short-term momentum (next 5 vs last 5 episodes) and long-term trend (per-season median breakdown)

These address the gap in the current system: it tells you *how many* top episodes are ahead but not *how hard you'll have to work* to reach them or *whether the series is heading up or down* from your position.

---

## Backend

### Changes to `backend/verdict.py`

`compute_verdict()` gains three new metric groups added to its return dict. No new endpoint, no new data sources.

#### Density

Benchmarked against what the user has already watched:

| Field | Type | Description |
|-------|------|-------------|
| `watched_median` | `float \| None` | Median score of watched rated episodes |
| `watched_best` | `float \| None` | Highest score among watched rated episodes |
| `pct_ahead_beats_median` | `int \| None` | % of ahead rated episodes scoring above `watched_median` (0–100) |
| `pct_ahead_beats_best` | `int \| None` | % of ahead rated episodes scoring above `watched_best` (0–100) |

All four are `None` if the user has no watched rated episodes.

#### Momentum

Short-term trajectory around the current position:

```python
"momentum": {
    "behind_median": float | None,   # median of last 5 watched rated eps; None if none exist
    "ahead_median":  float | None,   # median of next 5 ahead rated eps; None if none exist
    "direction":     "up" | "down" | "flat" | None  # None if either median is None
}
```

- Window: last/next 5 rated episodes (fewer if not enough exist; `None` if window is empty)
- `direction` threshold: difference ≥ 0.3 → up/down; < 0.3 → flat
- `direction` is `None` if either `behind_median` or `ahead_median` is `None`
- The `momentum` object is always present (never `None` itself)

#### Season breakdown

One entry per season, ordered by season number:

```python
"seasons": [
    {
        "season":              int,
        "median":              float | None,  # None if no rated episodes in season
        "rated_count":         int,
        "is_fully_watched":    bool,   # all eps in season ≤ current position
        "is_partially_watched": bool,  # season straddles the current position
        "is_ahead":            bool,   # all eps in season are after current position
        # Exactly one of the three status flags is True per season.
    },
    ...
]
```

Median is used (not average) — resistant to single outlier episodes inflating or deflating season quality.

### `backend/main.py`

No changes. The verdict endpoint already returns whatever `compute_verdict()` returns.

---

## Frontend

### Verdict card additions (`frontend/app.js` — `renderVerdictCard`)

Two new lines added below the existing verdict headline, before the top-N badge:

**Density line** (hidden if `watched_median` is null):
```
📊 45% of episodes ahead beat your typical watch · 12% beat your best
```
- `pct_ahead_beats_median` > 50% → green; 25–50% → yellow; < 25% → red
- Applied as a CSS class on the line element

**Momentum line** (hidden if `momentum` is null):
```
↑ Next 5 episodes trend higher than your last 5  (8.1 vs 7.5)
```
- Arrow symbol: ↑ up, ↓ down, → flat
- Both medians shown in parentheses

### Season breakdown section (`frontend/app.js` — new `renderSeasonBreakdown`)

New function called alongside `renderVerdictCard` after verdict submission. Renders into a new `<div id="seasonBreakdown">` in `index.html`, placed below the verdict card.

Hidden until verdict is submitted (same behaviour as verdict card).

Layout — one row per season:
```
Season  │ Bar + Median score │ Status
────────┼────────────────────┼─────────
S1      │ ████░░  8.2        │ ✓ watched
S2      │ ███░░░  7.6        │ ✓ watched
S3      │ ████░░  8.0        │ ▶ you are here
S4      │ ██░░░░  6.9        │ ahead
S5      │ █████░  8.8        │ ahead
```

Bar rendering:
- CSS `width` set as `((median - 5) / 5) * 100%` to fill a 5–10 range
- Past seasons: grey bar
- Current (partially watched) season: yellow bar
- Future seasons: blue bar if median > `watched_median`, muted red if below
- `rated_count` shown as episode count; seasons with no ratings show "No ratings yet"

---

## Data flow

```
GET /api/verdict/{imdb_id}?at=S03E05
  → compute_verdict() returns:
      { ...existing fields..., watched_median, watched_best,
        pct_ahead_beats_median, pct_ahead_beats_best,
        momentum: { behind_median, ahead_median, direction },
        seasons: [...] }
  → frontend:
      renderVerdictCard(v)       — card + density + momentum lines
      renderSeasonBreakdown(v)   — season bar table
```

---

## Error / edge cases

| Case | Behaviour |
|------|-----------|
| User enters first episode of series (nothing watched) | `watched_median`, `watched_best`, all density fields → `None`; density line hidden |
| Series has only 1 season | Breakdown shows one row; momentum works if enough episodes |
| Season has no rated episodes | `median: null`, row shows "No ratings yet", bar omitted |
| Fewer than 5 episodes in a window | Momentum uses however many exist; still shown |
| All episodes ahead (user at S01E01) | Density computed against empty watched set → hidden |

---

## Out of scope

- Configurable "good episode" threshold (hardcoded as `watched_median`)
- Per-episode density view (season-level is sufficient)
- Saving or comparing verdicts across sessions
