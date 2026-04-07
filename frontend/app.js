// frontend/app.js

// ── State ──────────────────────────────────────────────────────────────────
let currentSeries = null;  // { imdb_id, title, episodes: [...] }
let chart = null;

// ── DOM refs ───────────────────────────────────────────────────────────────
const searchInput  = document.getElementById('searchInput');
const dropdown     = document.getElementById('dropdown');
const loadingMsg   = document.getElementById('loadingMsg');
const mainContent  = document.getElementById('mainContent');
const seriesTitle  = document.getElementById('seriesTitle');
const episodeInput = document.getElementById('episodeInput');
const checkBtn     = document.getElementById('checkBtn');
const episodeError = document.getElementById('episodeError');
const verdictCard  = document.getElementById('verdictCard');
const legend       = document.getElementById('legend');

// ── Search (debounced) ─────────────────────────────────────────────────────
let searchTimer = null;
searchInput.addEventListener('input', () => {
  clearTimeout(searchTimer);
  const q = searchInput.value.trim();
  if (!q) { hideDropdown(); return; }
  searchTimer = setTimeout(() => fetchSearch(q), 300);
});

searchInput.addEventListener('keydown', e => {
  if (e.key === 'Escape') hideDropdown();
});

document.addEventListener('click', e => {
  if (!e.target.closest('.search-wrap')) hideDropdown();
});

async function fetchSearch(q) {
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const results = await res.json();
    showDropdown(results);
  } catch (_) {}
}

function showDropdown(results) {
  dropdown.innerHTML = '';
  if (!results.length) {
    dropdown.innerHTML = `<li style="color:var(--muted)">No results for "${searchInput.value}"</li>`;
    dropdown.classList.remove('hidden');
    return;
  }
  results.forEach(r => {
    const li = document.createElement('li');
    li.innerHTML = `
      <span class="dd-title">${r.title}</span>
      <span class="dd-meta">${r.year || ''} · ${r.episode_count} eps</span>
    `;
    li.addEventListener('click', () => loadSeries(r));
    dropdown.appendChild(li);
  });
  dropdown.classList.remove('hidden');
}

function hideDropdown() {
  dropdown.classList.add('hidden');
}

// ── Load series ────────────────────────────────────────────────────────────
async function loadSeries(result) {
  hideDropdown();
  searchInput.value = result.title;

  mainContent.classList.add('hidden');
  loadingMsg.classList.remove('hidden');

  try {
    const res = await fetch(`/api/series/${result.imdb_id}`);
    if (!res.ok) throw new Error('Not found');
    const data = await res.json();
    currentSeries = data;

    loadingMsg.classList.add('hidden');
    mainContent.classList.remove('hidden');
    seriesTitle.textContent = data.title;

    verdictCard.classList.add('hidden');
    verdictCard.innerHTML = '';
    episodeInput.value = '';
    episodeError.classList.add('hidden');

    renderChart(data.episodes, null, null);
    renderLegend(false);
  } catch (err) {
    loadingMsg.textContent = 'Failed to load series. Please try again.';
  }
}

// ── Chart ──────────────────────────────────────────────────────────────────
function renderChart(episodes, youAreHereIndex, topNSet) {
  const canvas = document.getElementById('chart');

  // Compute min width so episodes don't get squashed on mobile
  const minWidth = Math.max(600, episodes.length * 8);
  document.getElementById('chartWrap').style.width = minWidth + 'px';

  const labels  = episodes.map(e => `S${String(e.season).padStart(2,'0')}E${String(e.episode).padStart(2,'0')}`);
  const scores  = episodes.map(e => e.score ?? null);

  // Season separator positions (x-index of first episode of each new season)
  const seasonLines = [];
  episodes.forEach((ep, i) => {
    if (i > 0 && ep.season !== episodes[i - 1].season) {
      seasonLines.push(i);
    }
  });

  // Per-point colors
  function pointColor(ctx) {
    const i = ctx.dataIndex;
    const ep = episodes[i];
    if (youAreHereIndex === null || topNSet === null) return '#58a6ff';
    const key = `${ep.season}-${ep.episode}`;
    const isTop = topNSet.has(key);
    const isPast = i < youAreHereIndex;
    if (isTop && !isPast) return '#f85149';
    if (isTop && isPast)  return '#555';
    return isPast ? 'transparent' : '#58a6ff';
  }

  function segmentColor(ctx) {
    if (youAreHereIndex === null) return '#58a6ff';
    return ctx.p0DataIndex < youAreHereIndex ? '#3d444d' : '#58a6ff';
  }

  function pointRadius(ctx) {
    const i = ctx.dataIndex;
    if (youAreHereIndex === null || topNSet === null) return 3;
    const ep = episodes[i];
    const key = `${ep.season}-${ep.episode}`;
    return topNSet.has(key) ? 5 : 3;
  }

  // Season separator plugin (custom vertical lines + labels)
  const seasonPlugin = {
    id: 'seasonLines',
    afterDraw(chart) {
      const { ctx, chartArea: { top, bottom }, scales: { x } } = chart;
      const isMobile = window.innerWidth < 480;
      ctx.save();
      seasonLines.forEach(idx => {
        const xPos = x.getPixelForValue(idx);
        ctx.beginPath();
        ctx.setLineDash([4, 3]);
        ctx.strokeStyle = '#444';
        ctx.lineWidth = 1;
        ctx.moveTo(xPos, top);
        ctx.lineTo(xPos, bottom);
        ctx.stroke();
        if (!isMobile) {
          ctx.setLineDash([]);
          ctx.fillStyle = '#555';
          ctx.font = '10px sans-serif';
          ctx.textAlign = 'left';
          ctx.fillText(`S${episodes[idx].season}`, xPos + 3, top + 12);
        }
      });
      // "You are here" line
      if (youAreHereIndex !== null) {
        const xPos = x.getPixelForValue(youAreHereIndex);
        ctx.beginPath();
        ctx.setLineDash([]);
        ctx.strokeStyle = '#f0e040';
        ctx.lineWidth = 2;
        ctx.moveTo(xPos, top);
        ctx.lineTo(xPos, bottom);
        ctx.stroke();
        ctx.fillStyle = '#f0e040';
        ctx.font = 'bold 10px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('You are here', xPos + 4, top + 12);
      }
      ctx.restore();
    },
  };

  if (chart) chart.destroy();

  chart = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: scores,
        borderWidth: 2,
        pointRadius: ctx => pointRadius(ctx),
        pointHoverRadius: 6,
        pointBackgroundColor: ctx => pointColor(ctx),
        pointBorderColor: 'transparent',
        tension: 0.2,
        spanGaps: true,
        segment: { borderColor: ctx => segmentColor(ctx) },
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: ctx => {
              const ep = episodes[ctx[0].dataIndex];
              return `${labels[ctx[0].dataIndex]} — ${ep.title || ''}`;
            },
            label: ctx => {
              const ep = episodes[ctx.dataIndex];
              const parts = [`Score: ${ctx.parsed.y?.toFixed(2) ?? '—'}`];
              if (ep.imdb_score) parts.push(`IMDB: ${ep.imdb_score}`);
              if (ep.tmdb_score) parts.push(`TMDB: ${ep.tmdb_score}`);
              return parts;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { display: false },
          grid: { display: false },
        },
        y: {
          min: 5,
          max: 10,
          ticks: { color: '#8b949e', font: { size: 11 } },
          grid: { color: '#1c2128' },
        },
      },
    },
    plugins: [seasonPlugin],
  });
}

// ── Verdict ────────────────────────────────────────────────────────────────
checkBtn.addEventListener('click', checkVerdict);
episodeInput.addEventListener('keydown', e => { if (e.key === 'Enter') checkVerdict(); });

async function checkVerdict() {
  episodeError.classList.add('hidden');
  const code = episodeInput.value.trim();
  if (!currentSeries || !code) return;

  const res = await fetch(`/api/verdict/${currentSeries.imdb_id}?at=${encodeURIComponent(code)}`);
  if (res.status === 422) {
    const err = await res.json();
    episodeError.textContent = err.detail;
    episodeError.classList.remove('hidden');
    return;
  }
  const v = await res.json();

  // Compute "you are here" index in episode array
  const parts = code.toUpperCase().match(/S(\d+)E(\d+)/) || code.toUpperCase().match(/(\d+)X(\d+)/);
  const [, season, episode] = parts ? parts.map(Number) : [null, 0, 0];
  const youAreHereIndex = currentSeries.episodes.findIndex(
    e => e.season === season && e.episode === episode
  );

  // Build top-N set
  const topNSet = new Set(
    [...currentSeries.episodes]
      .filter(e => e.score !== null)
      .sort((a, b) => b.score - a.score)
      .slice(0, v.top_n)
      .map(e => `${e.season}-${e.episode}`)
  );

  renderChart(currentSeries.episodes, youAreHereIndex, topNSet);
  renderLegend(true);
  renderVerdictCard(v);
}

function renderVerdictCard(v) {
  const icons = { keep_watching: '✅', up_to_you: '🤔', you_can_stop: '🛑' };
  const labels = { keep_watching: 'Keep Watching', up_to_you: 'Up to You', you_can_stop: 'You Can Stop' };
  const classes = { keep_watching: 'keep', up_to_you: 'up', you_can_stop: 'stop' };

  let bestLine = '';
  if (v.best_episode_ahead) {
    const b = v.best_episode_ahead;
    const epCode = `S${String(b.season).padStart(2,'0')}E${String(b.episode).padStart(2,'0')}`;
    const epTitle = b.title ? ` "${b.title}"` : '';
    bestLine = `Best ahead: ${epCode}${epTitle} ⭐ ${b.score?.toFixed(1) ?? '—'}`;
  }

  verdictCard.className = `verdict-card ${classes[v.verdict]}`;
  verdictCard.innerHTML = `
    <div>
      <div class="verdict-headline">${icons[v.verdict]} ${labels[v.verdict]}</div>
      <div class="verdict-sub">${v.message}${bestLine ? ' · ' + bestLine : ''}</div>
    </div>
    <div class="top-n-badge">
      <div class="top-n-number">${v.top_n_ahead}<span class="top-n-denom">/${v.top_n}</span></div>
      <div class="top-n-label">top episodes<br>still ahead</div>
    </div>
  `;
  verdictCard.classList.remove('hidden');
}

function renderLegend(withVerdict) {
  if (!withVerdict) {
    legend.innerHTML = `<span class="legend-item"><span class="dot blue"></span> Episode</span>`;
    return;
  }
  legend.innerHTML = `
    <span class="legend-item"><span class="dot grey"></span> Already watched</span>
    <span class="legend-item"><span class="dot blue"></span> Still ahead</span>
    <span class="legend-item"><span class="dot red"></span> Top episode ahead</span>
    <span class="legend-item"><span class="dot" style="background:#555"></span> Top episode passed</span>
    <span class="legend-item"><span class="dot yellow"></span> You are here</span>
  `;
}
