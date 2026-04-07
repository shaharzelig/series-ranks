# New Metrics: Trajectory & Density — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `compute_verdict()` with density (how many ahead episodes beat your watched quality) and trajectory (per-season medians + short-term momentum) metrics, then surface them in the verdict card and a new season breakdown section.

**Architecture:** All new metric computation lives in `backend/verdict.py`. The existing `/api/verdict` endpoint returns whatever `compute_verdict()` returns, so no endpoint changes are needed. The frontend renders two new lines in the verdict card and a new `renderSeasonBreakdown()` function populates a new `#seasonBreakdown` div.

**Tech Stack:** Python `statistics` stdlib (median), FastAPI (no changes), Chart.js (no changes), plain CSS/HTML/JS.

---

## File map

| File | Change |
|------|--------|
| `backend/verdict.py` | Add `import statistics`; add density, momentum, seasons to `compute_verdict()` return |
| `tests/test_verdict.py` | Add tests for all new verdict fields |
| `frontend/style.css` | Add `.verdict-metric`, `#seasonBreakdown`, `.season-row`, `.season-bar-*` styles |
| `frontend/index.html` | Add `<div id="seasonBreakdown" class="hidden">` below `#verdictCard` |
| `frontend/app.js` | Update `renderVerdictCard`; add `renderSeasonBreakdown`; call both from `checkVerdict`; hide breakdown in `loadSeries` |

---

## Task 1: Backend — density metrics

**Files:**
- Modify: `backend/verdict.py`
- Test: `tests/test_verdict.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_verdict.py`:

```python
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
```

- [ ] **Step 2: Run to confirm they fail**

```
source venv/bin/activate
python -m pytest tests/test_verdict.py::test_density_basic tests/test_verdict.py::test_density_all_none_when_no_watched_rated tests/test_verdict.py::test_density_zero_when_nothing_ahead -v
```

Expected: `KeyError: 'watched_median'` (field does not exist yet)

- [ ] **Step 3: Add `import statistics` and implement density in `verdict.py`**

At the top of `backend/verdict.py`, after `import re`, add:

```python
import statistics
```

In `compute_verdict()`, after the `watched` set is built (line ~45) and before the `top_n_ahead`/threshold block, insert:

```python
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
```

Also update the early-return dict at the top of `compute_verdict()` (lines 25–34) so all paths return the same shape. Replace it with:

```python
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
```

Then add the four density fields to the main `return` dict at the bottom of `compute_verdict()`:

```python
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
    }
```

(Momentum and seasons will be added in Tasks 2 and 3.)

- [ ] **Step 4: Run density tests — confirm they pass**

```
python -m pytest tests/test_verdict.py::test_density_basic tests/test_verdict.py::test_density_all_none_when_no_watched_rated tests/test_verdict.py::test_density_zero_when_nothing_ahead -v
```

Expected: all 3 PASS

- [ ] **Step 5: Run full test suite — confirm nothing broke**

```
python -m pytest tests/ -q
```

Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add backend/verdict.py tests/test_verdict.py
git commit -m "feat: add density metrics to compute_verdict (watched_median, pct_ahead_beats_*)"
```

---

## Task 2: Backend — momentum metric

**Files:**
- Modify: `backend/verdict.py`
- Test: `tests/test_verdict.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_verdict.py`:

```python
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
```

- [ ] **Step 2: Run to confirm they fail**

```
python -m pytest tests/test_verdict.py -k "momentum" -v
```

Expected: `KeyError: 'momentum'`

- [ ] **Step 3: Implement momentum in `verdict.py`**

In `compute_verdict()`, directly after the density block from Task 1, insert:

```python
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
```

Add `"momentum": momentum` to the return dict.

- [ ] **Step 4: Run momentum tests — confirm they pass**

```
python -m pytest tests/test_verdict.py -k "momentum" -v
```

Expected: all 5 PASS

- [ ] **Step 5: Run full test suite**

```
python -m pytest tests/ -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/verdict.py tests/test_verdict.py
git commit -m "feat: add momentum metric to compute_verdict (behind/ahead median, direction)"
```

---

## Task 3: Backend — season breakdown

**Files:**
- Modify: `backend/verdict.py`
- Test: `tests/test_verdict.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_verdict.py`:

```python
# ── season breakdown ─────────────────────────────────────────────────────────

def _make_multi_season_episodes():
    """3 seasons, 5 episodes each. S1: 7s, S2: 8s, S3: 6s."""
    data = {
        1: [7.0, 7.5, 7.2, 7.8, 7.3],
        2: [8.0, 8.5, 8.2, 8.8, 8.3],
        3: [6.0, 6.5, 6.2, 6.8, 6.3],
    }
    eps = []
    for season, scores in data.items():
        for ep_num, score in enumerate(scores, 1):
            eps.append({
                "season": season, "episode": ep_num,
                "title": f"S{season}E{ep_num}",
                "score": score, "imdb_score": score, "imdb_votes": 100,
            })
    return eps

def test_seasons_status_flags():
    eps = _make_multi_season_episodes()
    # User at S2E3: S1 fully watched, S2 partial, S3 ahead
    result = compute_verdict(eps, current_season=2, current_episode=3)
    by_season = {s["season"]: s for s in result["seasons"]}

    assert by_season[1]["is_fully_watched"]    is True
    assert by_season[1]["is_partially_watched"] is False
    assert by_season[1]["is_ahead"]             is False

    assert by_season[2]["is_fully_watched"]    is False
    assert by_season[2]["is_partially_watched"] is True
    assert by_season[2]["is_ahead"]             is False

    assert by_season[3]["is_fully_watched"]    is False
    assert by_season[3]["is_partially_watched"] is False
    assert by_season[3]["is_ahead"]             is True

def test_seasons_median_and_rated_count():
    eps = _make_multi_season_episodes()
    result = compute_verdict(eps, current_season=1, current_episode=1)
    by_season = {s["season"]: s for s in result["seasons"]}
    # S1 sorted: [7.0, 7.2, 7.3, 7.5, 7.8] → median = 7.3
    assert by_season[1]["median"] == 7.3
    assert by_season[1]["rated_count"] == 5

def test_seasons_null_median_when_unrated():
    eps = [
        {"season": 1, "episode": 1, "title": "E1", "score": None, "imdb_score": None, "imdb_votes": 0},
        {"season": 1, "episode": 2, "title": "E2", "score": None, "imdb_score": None, "imdb_votes": 0},
    ]
    result = compute_verdict(eps, current_season=1, current_episode=1)
    assert result["seasons"][0]["median"] is None
    assert result["seasons"][0]["rated_count"] == 0

def test_seasons_ordered_by_season_number():
    eps = _make_multi_season_episodes()
    result = compute_verdict(eps, current_season=1, current_episode=1)
    season_nums = [s["season"] for s in result["seasons"]]
    assert season_nums == sorted(season_nums)
```

- [ ] **Step 2: Run to confirm they fail**

```
python -m pytest tests/test_verdict.py -k "season" -v
```

Expected: `KeyError: 'seasons'`

- [ ] **Step 3: Implement seasons in `verdict.py`**

In `compute_verdict()`, directly after the momentum block, insert:

```python
    # ── Season breakdown ─────────────────────────────────────────────────────
    seasons_dict: dict[int, list] = {}
    for e in episodes:
        seasons_dict.setdefault(e["season"], []).append(e)

    seasons = []
    for season_num in sorted(seasons_dict.keys()):
        s_eps    = seasons_dict[season_num]
        s_rated  = [e for e in s_eps if e.get("score") is not None]
        s_scores = [e["score"] for e in s_rated]

        any_watched = any(
            e["season"] < current_season
            or (e["season"] == current_season and e["episode"] <= current_episode)
            for e in s_eps
        )
        all_watched = all(
            e["season"] < current_season
            or (e["season"] == current_season and e["episode"] <= current_episode)
            for e in s_eps
        )

        seasons.append({
            "season":               season_num,
            "median":               round(statistics.median(s_scores), 3) if s_scores else None,
            "rated_count":          len(s_rated),
            "is_fully_watched":     all_watched,
            "is_partially_watched": any_watched and not all_watched,
            "is_ahead":             not any_watched,
        })
```

Add `"seasons": seasons` to the return dict.

- [ ] **Step 4: Run season tests — confirm they pass**

```
python -m pytest tests/test_verdict.py -k "season" -v
```

Expected: all 4 PASS

- [ ] **Step 5: Run full test suite**

```
python -m pytest tests/ -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/verdict.py tests/test_verdict.py
git commit -m "feat: add season breakdown to compute_verdict (median, status flags)"
```

---

## Task 4: Frontend — verdict card density & momentum lines

**Files:**
- Modify: `frontend/app.js` (function `renderVerdictCard`)
- Modify: `frontend/style.css`

- [ ] **Step 1: Add CSS for verdict metric lines**

In `frontend/style.css`, after the `.verdict-sub` rule (line 148), add:

```css
.verdict-metric {
  font-size: 12px;
  color: var(--muted);
  margin-top: 6px;
}
.verdict-metric.density-green  { color: var(--green); }
.verdict-metric.density-yellow { color: var(--orange); }
.verdict-metric.density-red    { color: var(--red); }
```

- [ ] **Step 2: Replace `renderVerdictCard` in `frontend/app.js`**

Replace the entire `renderVerdictCard` function (lines 281–306) with:

```javascript
function renderVerdictCard(v) {
  const icons   = { keep_watching: '✅', up_to_you: '🤔', you_can_stop: '🛑' };
  const labels  = { keep_watching: 'Keep Watching', up_to_you: 'Up to You', you_can_stop: 'You Can Stop' };
  const classes = { keep_watching: 'keep', up_to_you: 'up', you_can_stop: 'stop' };

  let bestLine = '';
  if (v.best_episode_ahead) {
    const b = v.best_episode_ahead;
    const epCode  = `S${String(b.season).padStart(2,'0')}E${String(b.episode).padStart(2,'0')}`;
    const epTitle = b.title ? ` "${b.title}"` : '';
    bestLine = `Best ahead: ${epCode}${epTitle} ⭐ ${b.score?.toFixed(1) ?? '—'}`;
  }

  let densityLine = '';
  if (v.watched_median != null && v.pct_ahead_beats_median != null) {
    const cls = v.pct_ahead_beats_median >= 50 ? 'density-green'
              : v.pct_ahead_beats_median >= 25 ? 'density-yellow'
              : 'density-red';
    densityLine = `<div class="verdict-metric ${cls}">📊 ${v.pct_ahead_beats_median}% of episodes ahead beat your typical watch · ${v.pct_ahead_beats_best}% beat your best</div>`;
  }

  let momentumLine = '';
  if (v.momentum && v.momentum.direction != null) {
    const arrows = { up: '↑', down: '↓', flat: '→' };
    const dirs   = { up: 'higher', down: 'lower', flat: 'similar' };
    momentumLine = `<div class="verdict-metric">${arrows[v.momentum.direction]} Next 5 episodes trend ${dirs[v.momentum.direction]} than your last 5 (${v.momentum.ahead_median} vs ${v.momentum.behind_median})</div>`;
  }

  verdictCard.className = `verdict-card ${classes[v.verdict]}`;
  verdictCard.innerHTML = `
    <div>
      <div class="verdict-headline">${icons[v.verdict]} ${labels[v.verdict]}</div>
      <div class="verdict-sub">${v.message}${bestLine ? ' · ' + bestLine : ''}</div>
      ${densityLine}
      ${momentumLine}
    </div>
    <div class="top-n-badge">
      <div class="top-n-number">${v.top_n_ahead}<span class="top-n-denom">/${v.top_n}</span></div>
      <div class="top-n-label">top episodes<br>still ahead</div>
    </div>
  `;
  verdictCard.classList.remove('hidden');
}
```

- [ ] **Step 3: Smoke-test in browser**

Start the dev server:
```
source venv/bin/activate
uvicorn backend.main:app --reload
```
Open `http://localhost:8000`, search for a series, enter a mid-series episode, click "Should I keep watching?". Confirm:
- Density line appears below the verdict sub-text (green/yellow/red)
- Momentum line appears with an arrow and two medians in parentheses
- Existing top-N badge is unchanged
- No JS console errors

- [ ] **Step 4: Commit**

```bash
git add frontend/app.js frontend/style.css
git commit -m "feat: add density and momentum lines to verdict card"
```

---

## Task 5: Frontend — season breakdown section

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/app.js` (add `renderSeasonBreakdown`, update `checkVerdict` and `loadSeries`)
- Modify: `frontend/style.css`

- [ ] **Step 1: Add `#seasonBreakdown` div to `index.html`**

In `frontend/index.html`, after line 53 (`<div id="verdictCard" ...>`), add:

```html
      <!-- Season breakdown — hidden until verdict submitted -->
      <div id="seasonBreakdown" class="hidden"></div>
```

- [ ] **Step 2: Add CSS for the season breakdown**

In `frontend/style.css`, at the end of the file, add:

```css
/* ── Season breakdown ───────────────────────────────────────────────────── */
#seasonBreakdown {
  margin-top: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 20px;
}
.season-breakdown-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 12px;
}
.season-row {
  display: grid;
  grid-template-columns: 36px 1fr 100px;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.season-label { font-size: 12px; color: var(--muted); font-weight: 600; }
.season-bar-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}
.season-bar-track {
  flex: 1;
  height: 8px;
  background: var(--bg);
  border-radius: 4px;
  overflow: hidden;
}
.season-bar { height: 100%; border-radius: 4px; }
.season-score { font-size: 11px; color: var(--text); white-space: nowrap; min-width: 28px; }
.season-status { font-size: 11px; color: var(--muted); text-align: right; }
.season-status.season-here { color: var(--yellow); }

@media (max-width: 600px) {
  .season-row { grid-template-columns: 36px 1fr 80px; }
}
```

- [ ] **Step 3: Add `renderSeasonBreakdown` function to `app.js`**

In `frontend/app.js`, after the `renderLegend` function, add:

```javascript
function renderSeasonBreakdown(v) {
  const el = document.getElementById('seasonBreakdown');
  if (!v.seasons || !v.seasons.length) { el.classList.add('hidden'); return; }

  const rows = v.seasons.map(s => {
    const med      = s.median;
    const barWidth = med !== null ? ((med - 5) / 5 * 100).toFixed(1) : 0;

    let barColor;
    if (s.is_fully_watched) {
      barColor = 'var(--grey-line)';
    } else if (s.is_partially_watched) {
      barColor = 'var(--yellow)';
    } else {
      // ahead season: blue if above watched benchmark, red if below
      barColor = (v.watched_median != null && med !== null && med > v.watched_median)
        ? 'var(--blue)' : 'var(--red)';
    }

    const statusText = s.is_fully_watched    ? '✓ watched'
                     : s.is_partially_watched ? '▶ you are here'
                     : 'ahead';
    const hereClass  = s.is_partially_watched ? ' season-here' : '';

    const barHtml   = `<div class="season-bar-track"><div class="season-bar" style="width:${barWidth}%;background:${barColor}"></div></div>`;
    const scoreText = med !== null ? med.toFixed(1) : 'No ratings yet';

    return `
      <div class="season-row">
        <div class="season-label">S${s.season}</div>
        <div class="season-bar-wrap">${barHtml}<span class="season-score">${scoreText}</span></div>
        <div class="season-status${hereClass}">${statusText}</div>
      </div>`;
  }).join('');

  el.innerHTML = `<div class="season-breakdown-title">Season breakdown (median scores)</div>${rows}`;
  el.classList.remove('hidden');
}
```

- [ ] **Step 4: Call `renderSeasonBreakdown` from `checkVerdict`**

In `frontend/app.js`, in the `checkVerdict` function, find the two lines that call `renderChart` and `renderLegend` and `renderVerdictCard`. After the `renderVerdictCard(v)` call, add:

```javascript
  renderSeasonBreakdown(v);
```

- [ ] **Step 5: Hide breakdown when a new series is loaded**

In `frontend/app.js`, in `loadSeries()`, find the block that hides and clears the verdict card:

```javascript
    verdictCard.classList.add('hidden');
    verdictCard.innerHTML = '';
```

After those two lines, add:

```javascript
    document.getElementById('seasonBreakdown').classList.add('hidden');
```

- [ ] **Step 6: Smoke-test in browser**

With the dev server running, search for a multi-season series (e.g., Breaking Bad), enter a mid-series episode, click "Should I keep watching?". Confirm:
- Season breakdown section appears below the verdict card
- One row per season with a labelled bar
- Past seasons: grey bar, current season: yellow bar, future seasons: blue or red based on quality vs your watched median
- "▶ you are here" in yellow on the current (partial) season
- Hidden when loading a new series

- [ ] **Step 7: Commit**

```bash
git add frontend/index.html frontend/app.js frontend/style.css
git commit -m "feat: add season breakdown section with per-season median bars"
```

---

## Done

Run the full test suite one final time to confirm everything is clean:

```
source venv/bin/activate
python -m pytest tests/ -q
```

Expected output: all tests pass, no warnings.
