/**
 * Query builder logic for the album create/edit form.
 */

// ---- Chip management -------------------------------------------------------

function addChip(containerId, inputId, value) {
  const container = document.getElementById(containerId);
  const input = inputId ? document.getElementById(inputId) : null;
  const val = (value !== undefined ? value : (input ? input.value.trim() : '')).trim();
  if (!val) return;

  // Prevent duplicates
  const existing = [...container.querySelectorAll('.chip-label')].map(e => e.textContent);
  if (existing.includes(val)) {
    if (input) input.value = '';
    return;
  }

  const chip = document.createElement('span');
  chip.className = 'chip';
  chip.innerHTML = `<span class="chip-label">${escHtml(val)}</span>
    <span class="chip-remove" onclick="this.parentElement.remove(); syncQueryConfig()">&times;</span>`;
  container.appendChild(chip);

  if (input) input.value = '';
  syncQueryConfig();
}

function getChips(containerId) {
  return [...document.getElementById(containerId).querySelectorAll('.chip-label')]
    .map(e => e.textContent);
}

// Allow pressing Enter in chip inputs
['personInput', 'anyPersonInput', 'tagInput', 'countryInput'].forEach(id => {
  document.addEventListener('DOMContentLoaded', () => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const map = {
          personInput: 'peopleChips',
          anyPersonInput: 'anyPeopleChips',
          tagInput: 'tagsChips',
          countryInput: 'countryChips',
        };
        addChip(map[id], id);
      }
    });
  });
});

// ---- Timespan management ---------------------------------------------------

let timespanCount = 0;

function addTimespan(start, end) {
  const i = timespanCount++;
  const row = document.createElement('div');
  row.className = 'timespan-row d-flex align-items-center gap-2';
  row.innerHTML = `
    <div class="flex-grow-1 row g-2">
      <div class="col">
        <label class="form-label mb-1 small text-secondary">Start</label>
        <input type="date" class="form-control form-control-sm ts-start" id="ts_start_${i}"
               value="${start || ''}" onchange="syncQueryConfig()">
      </div>
      <div class="col">
        <label class="form-label mb-1 small text-secondary">End</label>
        <input type="date" class="form-control form-control-sm ts-end" id="ts_end_${i}"
               value="${end || ''}" onchange="syncQueryConfig()">
      </div>
    </div>
    <button type="button" class="btn btn-sm btn-outline-danger align-self-end mb-1"
            onclick="this.parentElement.remove(); syncQueryConfig()">
      <i class="bi bi-trash3"></i>
    </button>`;
  document.getElementById('timespanList').appendChild(row);
  syncQueryConfig();
}

function getTimespans() {
  const rows = document.querySelectorAll('#timespanList .timespan-row');
  return [...rows].map(r => ({
    start: r.querySelector('.ts-start').value,
    end: r.querySelector('.ts-end').value,
  })).filter(ts => ts.start && ts.end);
}

// ---- JSON sync -------------------------------------------------------------

function syncQueryConfig() {
  const q = buildQuery();
  document.getElementById('query_config').value = JSON.stringify(q);
  const ta = document.getElementById('jsonTextarea');
  if (ta) ta.value = JSON.stringify(q, null, 2);
}

function buildQuery() {
  const q = {};

  const people = getChips('peopleChips');
  if (people.length) {
    q.people = people;
    if (document.getElementById('people_strict_mode')?.checked) q.people_strict_mode = true;
  }

  const anyPeople = getChips('anyPeopleChips');
  if (anyPeople.length) q.any_people = anyPeople;

  const tags = getChips('tagsChips');
  if (tags.length) q.tags = tags;

  const countries = getChips('countryChips');
  if (countries.length) q.country = countries.length === 1 ? countries[0] : countries;

  const state = document.getElementById('stateInput')?.value.trim();
  if (state) q.state = state;

  const city = document.getElementById('cityInput')?.value.trim();
  if (city) q.city = city;

  const path = document.getElementById('pathInput')?.value.trim();
  if (path) q.path = path;

  if (document.getElementById('favoriteCheck')?.checked) q.favorite = true;

  const timespans = getTimespans();
  if (timespans.length === 1) q.timespan = timespans[0];
  else if (timespans.length > 1) q.timespan = timespans;

  return q;
}

function loadQueryConfig(cfg) {
  if (!cfg || typeof cfg !== 'object') return;

  const setChips = (containerId, values) => {
    const arr = Array.isArray(values) ? values : (values ? [values] : []);
    arr.forEach(v => addChip(containerId, null, v));
  };

  setChips('peopleChips', cfg.people);
  if (cfg.people_strict_mode) {
    const sm = document.getElementById('people_strict_mode');
    if (sm) sm.checked = true;
  }
  setChips('anyPeopleChips', cfg.any_people);
  setChips('tagsChips', cfg.tags);
  setChips('countryChips', cfg.country);

  const set = (id, val) => { const el = document.getElementById(id); if (el && val) el.value = val; };
  set('stateInput', cfg.state);
  set('cityInput', cfg.city);
  set('pathInput', cfg.path);

  if (cfg.favorite) {
    const fav = document.getElementById('favoriteCheck');
    if (fav) fav.checked = true;
  }

  const timespans = cfg.timespan
    ? (Array.isArray(cfg.timespan) ? cfg.timespan : [cfg.timespan])
    : [];
  timespans.forEach(ts => addTimespan(ts.start, ts.end));

  syncQueryConfig();
}

// ---- Attach live sync to plain inputs --------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  ['stateInput', 'cityInput', 'pathInput', 'favoriteCheck', 'people_strict_mode'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', syncQueryConfig);
  });

  // JSON toggle
  const jsonToggle = document.getElementById('jsonToggle');
  const jsonEditor = document.getElementById('jsonEditor');
  const queryBuilder = document.getElementById('queryBuilder');
  if (jsonToggle) {
    jsonToggle.addEventListener('click', () => {
      const showJson = jsonEditor.style.display === 'none';
      jsonEditor.style.display = showJson ? '' : 'none';
      queryBuilder.style.display = showJson ? 'none' : '';
      jsonToggle.innerHTML = showJson
        ? '<i class="bi bi-sliders me-1"></i>Visual Builder'
        : '<i class="bi bi-code-slash me-1"></i>Raw JSON';

      if (showJson) {
        // Populate textarea from current hidden input
        try {
          const ta = document.getElementById('jsonTextarea');
          ta.value = JSON.stringify(JSON.parse(document.getElementById('query_config').value), null, 2);
          ta.addEventListener('input', () => {
            try {
              const parsed = JSON.parse(ta.value);
              document.getElementById('query_config').value = JSON.stringify(parsed);
            } catch (_) { /* user still typing */ }
          });
        } catch (_) {}
      }
    });
  }

  // Pre-fill form for submit guard
  document.getElementById('albumForm').addEventListener('submit', () => {
    syncQueryConfig();
  });
});

// ---- Utility ---------------------------------------------------------------

function escHtml(str) {
  return str.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}
