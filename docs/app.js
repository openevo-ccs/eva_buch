const appState = {
  theme: localStorage.getItem('theme') || 'dark',
  manifest: null,
  keywordRows: [],
  keywordWordCounts: [],
  conceptOrder: [],
  page: document.body.dataset.page || 'home',
  lda: {
    concept: null,
    k: 10,
    ldavis: null,
    termMatrix: [],
    topicSubject: [],
    cooccurrence: null,
    lambda: 0.6,
    selectedTopic: 1,
    tableSort: { key: 'total_across_topics', dir: 'desc' }
  },
  bertopic: {
    manifest: null,
    colorMaps: null,
    conceptData: {},
    loading: {},
    active: [],
    colorBy: 'subject',
    showOutliers: true,
    projection: 'local',
    dimension: '3d',
    pointSize: 4,
    orbit: { enabled: false, speed: 1, elevation: 0.35, theta: 0, raf: null },
    selection: null
  }
};

const BERTOPIC_MAX_CONCEPTS = 9;
const BERTOPIC_DATA_BASE = './data/bertopic';
const LDA_DATA_BASE = './data/lda';

// Canonical German state names, mirroring bertopic_pipeline_v2.py's STATE_ALIASES,
// so results.csv/doc_word_counts.csv (which still carry raw abbreviations) render
// consistently with the rest of the app. KMK-issued national documents have no
// Bundesland, hence "None"/blank -> "KMK" (not "Unbekannt").
const STATE_ALIASES = {
  'bawü': 'Baden-Württemberg', 'bawue': 'Baden-Württemberg', 'bw': 'Baden-Württemberg',
  'baden wuerttemberg': 'Baden-Württemberg', 'baden-wuerttemberg': 'Baden-Württemberg',
  'baden-württemberg': 'Baden-Württemberg',
  'by': 'Bayern', 'bayern': 'Bayern',
  'be': 'Berlin', 'berlin': 'Berlin',
  'bb': 'Brandenburg', 'brandenburg': 'Brandenburg',
  'hb': 'Bremen', 'bremen': 'Bremen',
  'hh': 'Hamburg', 'hamburg': 'Hamburg',
  'he': 'Hessen', 'hessen': 'Hessen',
  'meckpomm': 'Mecklenburg-Vorpommern', 'mv': 'Mecklenburg-Vorpommern',
  'mecklenburg vorpommern': 'Mecklenburg-Vorpommern', 'mecklenburg-vorpommern': 'Mecklenburg-Vorpommern',
  'ni': 'Niedersachsen', 'niedersachsen': 'Niedersachsen',
  'nrw': 'Nordrhein-Westfalen', 'nordrhein westfalen': 'Nordrhein-Westfalen',
  'nordrhein-westfalen': 'Nordrhein-Westfalen',
  'rp': 'Rheinland-Pfalz', 'rlp': 'Rheinland-Pfalz',
  'rheinland pfalz': 'Rheinland-Pfalz', 'rheinland-pfalz': 'Rheinland-Pfalz',
  'sl': 'Saarland', 'saarland': 'Saarland',
  'sn': 'Sachsen', 'sachsen': 'Sachsen',
  'st': 'Sachsen-Anhalt', 'sachsen anhalt': 'Sachsen-Anhalt', 'sachsen-anhalt': 'Sachsen-Anhalt',
  'sh': 'Schleswig-Holstein', 'schleswig holstein': 'Schleswig-Holstein',
  'schleswig-holstein': 'Schleswig-Holstein',
  'th': 'Thüringen', 'thueringen': 'Thüringen', 'thüringen': 'Thüringen',
  'kmk': 'KMK', 'none': 'KMK', 'na': 'KMK', 'n/a': 'KMK', '<na>': 'KMK', 'nan': 'KMK',
};

function normalizeState(raw) {
  const value = String(raw ?? '').trim();
  if (!value) return 'KMK';
  return STATE_ALIASES[value.toLowerCase()] || value;
}

const dimensionOptions = [
  { value: 'concept', label: 'Konzept' },
  { value: 'subject', label: 'Fach' },
  { value: 'state', label: 'Bundesland' }
];

function init() {
  applyTheme(appState.theme);
  bindEvents();
  setActiveNav();
  loadData();
}

function setActiveNav() {
  const current = appState.page;
  document.querySelectorAll('.nav-links a').forEach((link) => {
    const href = link.getAttribute('href') || '';
    const target = href.replace(/\.html$/, '').replace(/^\//, '');
    link.classList.toggle('is-active', target === current || (current === 'home' && target === 'index'));
  });
}

function bindEvents() {
  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    appState.theme = appState.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('theme', appState.theme);
    applyTheme(appState.theme);
  });

  document.getElementById('bertopic-color-by')?.addEventListener('change', (event) => {
    appState.bertopic.colorBy = event.target.value;
    appState.bertopic.selection = null;
    rebuildAllBerTopicPanels();
    renderBerTopicLegend();
  });
  document.getElementById('bertopic-show-outliers')?.addEventListener('change', (event) => {
    appState.bertopic.showOutliers = event.target.checked;
    rebuildAllBerTopicPanels();
  });
  document.getElementById('bertopic-projection')?.addEventListener('change', (event) => {
    appState.bertopic.projection = event.target.value;
    rebuildAllBerTopicPanels();
  });
  document.getElementById('bertopic-dimension')?.addEventListener('change', (event) => {
    appState.bertopic.dimension = event.target.value;
    rebuildAllBerTopicPanels();
  });
  document.getElementById('bertopic-point-size')?.addEventListener('input', (event) => {
    appState.bertopic.pointSize = Number(event.target.value);
    restylePointSizes();
  });
  document.getElementById('bertopic-orbit-enabled')?.addEventListener('change', (event) => {
    appState.bertopic.orbit.enabled = event.target.checked;
    if (appState.bertopic.orbit.enabled) {
      seedBerTopicOrbitFromCurrentView();
      startBerTopicOrbit();
    } else {
      stopBerTopicOrbit();
    }
  });
  document.getElementById('bertopic-orbit-speed')?.addEventListener('input', (event) => {
    appState.bertopic.orbit.speed = Number(event.target.value);
  });
  document.getElementById('bertopic-orbit-elevation')?.addEventListener('input', (event) => {
    appState.bertopic.orbit.elevation = Number(event.target.value);
    if (!appState.bertopic.orbit.enabled) applyBerTopicCameraToAllPanels();
  });
  document.getElementById('keyword-dimension-a')?.addEventListener('change', renderKeywordPage);
  document.getElementById('keyword-dimension-b')?.addEventListener('change', renderKeywordPage);
  document.getElementById('keyword-filter-dimension')?.addEventListener('change', () => {
    populateKeywordFilterValues();
    renderKeywordPage();
  });
  document.getElementById('keyword-filter-value')?.addEventListener('change', renderKeywordPage);
  document.getElementById('keyword-mode')?.addEventListener('change', renderKeywordPage);
  document.getElementById('keyword-concept-filter')?.addEventListener('change', renderKeywordPage);
  document.getElementById('keyword-shading-scope')?.addEventListener('change', renderKeywordPage);
  document.getElementById('keyword-download-csv')?.addEventListener('click', () => {
    downloadCsvFromArray(appState.keywordTableRows || [], 'schlagwortsuche.csv');
  });

  document.getElementById('lda-concept')?.addEventListener('change', (event) => {
    appState.lda.concept = event.target.value;
    loadLdaData();
  });
  document.getElementById('lda-k')?.addEventListener('change', (event) => {
    appState.lda.k = Number(event.target.value);
    loadLdaData();
    if (appState.wordcloud && appState.wordcloud.mode === 'collection') renderWordclouds();
  });
  document.getElementById('lda-lambda')?.addEventListener('input', (event) => {
    appState.lda.lambda = Number(event.target.value);
    const label = document.getElementById('lda-lambda-value');
    if (label) label.textContent = appState.lda.lambda.toFixed(2);
    renderLdaTermPanel();
  });
  document.getElementById('download-term-table')?.addEventListener('click', () => {
    downloadCsvFromArray(appState.lda.termMatrix, `lda_termhaeufigkeiten_${appState.lda.concept}_${appState.lda.k}.csv`);
  });
  document.getElementById('download-topic-subject-table')?.addEventListener('click', () => {
    downloadCsvFromArray(appState.lda.topicSubject, `lda_themenverteilung_${appState.lda.concept}_${appState.lda.k}.csv`);
  });
}

function applyTheme(theme) {
  document.body.classList.toggle('light', theme === 'light');
  const toggle = document.getElementById('theme-toggle');
  if (toggle) toggle.textContent = theme === 'dark' ? '☀️ Hellmodus' : '🌙 Dunkelmodus';
  if (appState.page === 'bertopic') relayoutAllBerTopicPanels(getPlotlyThemeColors());
  if (appState.page === 'lda' && appState.lda.ldavis) renderLdaMap();
}

function getPlotlyThemeColors() {
  const styles = getComputedStyle(document.body);
  const read = (name) => styles.getPropertyValue(name).trim();
  return {
    paper: read('--panel-strong') || read('--panel'),
    text: read('--text'),
    muted: read('--muted'),
    border: read('--border')
  };
}

async function loadData() {
  try {
    const needsKeywordData = appState.page === 'schlagwortsuche';
    const needsDocumentData = appState.page === 'dokumente';

    const [manifest, keywordRows, keywordWordCounts, documentOverview] = await Promise.all([
      fetchJson('./data/manifest.json'),
      needsKeywordData ? fetchCsv('./data/results.csv') : Promise.resolve([]),
      needsKeywordData ? fetchCsv('./data/doc_word_counts.csv') : Promise.resolve([]),
      needsDocumentData ? fetchCsv(encodeURI('./Lehrplandokumente Übersicht.csv')) : Promise.resolve([])
    ]);

    appState.manifest = manifest;
    appState.keywordRows = keywordRows.map((row) => ({ ...row, state: normalizeState(row.state) }));
    appState.keywordWordCounts = keywordWordCounts.map((row) => ({ ...row, state: normalizeState(row.state) }));
    appState.documentOverview = documentOverview;
    appState.conceptOrder = manifest.concept_order || [];

    populateConceptSelectors();
    renderPage();

    if (appState.page === 'bertopic') {
      loadBerTopicManifest();
    }
  } catch (error) {
    console.error(error);
    const shell = document.querySelector('.page-shell');
    if (shell) {
      shell.innerHTML = `
        <section class="hero-card section-card">
          <p class="eyebrow">Datenstatus</p>
          <h3>Die Daten konnten nicht geladen werden.</h3>
          <p>Bitte stellen Sie sicher, dass die Seite über einen lokalen Server oder GitHub Pages ausgeliefert wird und dass die Datenordner im Repository vorhanden sind.</p>
        </section>`;
    }
  }
}

function populateConceptSelectors() {
  const conceptFilter = document.getElementById('keyword-concept-filter');
  if (conceptFilter) {
    conceptFilter.innerHTML = ['Alle', ...appState.conceptOrder].map((concept) => `<option value="${concept}">${concept === 'Alle' ? 'Alle Konzepte' : concept}</option>`).join('');
  }

  const filterDimension = document.getElementById('keyword-filter-dimension');
  if (filterDimension) {
    filterDimension.innerHTML = dimensionOptions.map((option) => `<option value="${option.value}">${option.label}</option>`).join('');
  }

  const dimensionA = document.getElementById('keyword-dimension-a');
  const dimensionB = document.getElementById('keyword-dimension-b');
  if (dimensionA && dimensionB) {
    dimensionA.innerHTML = dimensionOptions.map((option) => `<option value="${option.value}">${option.label}</option>`).join('');
    dimensionB.innerHTML = dimensionOptions.map((option) => `<option value="${option.value}">${option.label}</option>`).join('');
    dimensionA.value = 'concept';
    dimensionB.value = 'subject';
  }

  populateKeywordFilterValues();
}

function populateKeywordFilterValues() {
  const select = document.getElementById('keyword-filter-value');
  if (!select) return;
  const dimension = document.getElementById('keyword-filter-dimension').value;
  const values = [...new Set(appState.keywordRows.map((row) => row[dimensionToKey(dimension)]).filter(Boolean))].sort();
  select.innerHTML = ['Alle', ...values].map((value) => `<option value="${value}">${value === 'Alle' ? 'Alle' : value}</option>`).join('');
}

function dimensionToKey(dimension) {
  const map = { concept: 'search_term', subject: 'subject', state: 'state' };
  return map[dimension] || 'search_term';
}

function renderPage() {
  switch (appState.page) {
    case 'dokumente':
      renderDocumentPage();
      break;
    case 'schlagwortsuche':
      renderKeywordPage();
      break;
    case 'bertopic':
      renderBerTopicPage();
      break;
    case 'lda':
      renderLdaPage();
      break;
    default:
      renderHomePage();
      break;
  }
}

function renderHomePage() {
  const concepts = appState.conceptOrder;
  const totalDocs = concepts.reduce((sum, concept) => sum + (appState.manifest.concepts[concept]?.n_docs || 0), 0);
  const outliers = concepts.reduce((sum, concept) => sum + (appState.manifest.concepts[concept]?.n_outliers || 0), 0);
  const subjects = new Set(concepts.flatMap((concept) => Object.keys(appState.manifest.concepts[concept]?.subjects || {})));

  document.getElementById('hero-title').textContent = 'Ein moderner Zugang zur Lehrplananalyse';
  document.getElementById('hero-copy').textContent = 'Die Oberfläche verbindet Dokumentenübersicht, Schlagwortsuche, BERTopic- und LDA-Analysen in einer klaren, schnellen und gut lesbaren Erfahrung – ideal für GitHub Pages und für die Präsentation wissenschaftlicher Ergebnisse.';
  document.getElementById('metric-grid').innerHTML = [
    { label: 'Konzepte im Fokus', value: concepts.length },
    { label: 'Dokumente im Datensatz', value: totalDocs.toLocaleString('de-DE') },
    { label: 'Ausreißer insgesamt', value: outliers.toLocaleString('de-DE') },
    { label: 'Fächer abgedeckt', value: subjects.size }
  ].map((item) => `<article class="metric-card"><strong>${item.value}</strong><span>${item.label}</span></article>`).join('');
}

const DOKUMENTE_TABLE_COLUMNS = ['Bundesland', 'Fach', 'Schulart', 'Jahr', 'Gesamtwortzahl'];

function getDokumenteRows() {
  const rows = appState.documentOverview || [];
  return rows.map((row, index) => ({
    id: index + 1,
    Bundesland: normalizeState(row['Bundesland']),
    Fach: row['Fach'] || '—',
    Schulart: row['Schulart'] || '—',
    Jahr: row['Jahr'] || '—',
    Gesamtwortzahl: Number(row['Gesamtwortanzahl'] || 0),
    Referenz: row['Referenz'] || '—',
    Dateiname: row['Dateiname'] || ''
  }));
}

function txtFileLink(row) {
  if (!row.Dateiname || !row.Fach) return null;
  const txtName = row.Dateiname.replace(/\.pdf$/i, '.txt');
  return encodeURI(`./data/txtfiles/${row.Fach}/${txtName}`);
}

function renderDocumentPage() {
  initTabStrip('dokumente-tabs');
  if (!appState.dokumente) {
    appState.dokumente = { sort: { key: 'id', dir: 'asc' }, filters: { Bundesland: 'Alle', Fach: 'Alle', Schulart: 'Alle', Jahr: 'Alle' } };
  }
  renderDokumenteControls();
  renderDokumenteTable();
  renderDokumenteMatrix();
}

function renderDokumenteControls() {
  const container = document.getElementById('dokumente-table-controls');
  if (!container) return;
  const rows = getDokumenteRows();
  const filters = appState.dokumente.filters;
  const optionsFor = (key) => ['Alle', ...new Set(rows.map((r) => r[key]).filter((v) => v !== undefined && v !== '—'))].sort();

  container.innerHTML = ['Bundesland', 'Fach', 'Schulart', 'Jahr'].map((key) => `
    <label><span>${escapeHtml(key)}</span>
      <select data-filter-key="${key}">
        ${optionsFor(key).map((value) => `<option value="${escapeHtml(value)}" ${filters[key] === String(value) ? 'selected' : ''}>${escapeHtml(value)}</option>`).join('')}
      </select>
    </label>`).join('');

  container.querySelectorAll('select[data-filter-key]').forEach((select) => {
    select.addEventListener('change', () => {
      appState.dokumente.filters[select.dataset.filterKey] = select.value;
      renderDokumenteTable();
    });
  });
}

function renderDokumenteTable() {
  const container = document.getElementById('document-table');
  if (!container) return;
  const { sort, filters } = appState.dokumente;
  let rows = getDokumenteRows();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== 'Alle') rows = rows.filter((r) => String(r[key]) === value);
  });
  rows.sort((a, b) => {
    const [va, vb] = [a[sort.key], b[sort.key]];
    const cmp = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb));
    return sort.dir === 'asc' ? cmp : -cmp;
  });

  container.innerHTML = `
    <div class="table-shell">
      <table>
        <thead><tr>
          <th>#</th>
          ${DOKUMENTE_TABLE_COLUMNS.map((key) => sortableHeaderCell(key, key, sort)).join('')}
          <th>Referenz</th>
          <th>Volltext</th>
        </tr></thead>
        <tbody>${rows.map((row) => {
          const link = txtFileLink(row);
          return `<tr>
            <td>${row.id}</td>
            <td>${escapeHtml(row.Bundesland)}</td>
            <td>${escapeHtml(row.Fach)}</td>
            <td>${escapeHtml(row.Schulart)}</td>
            <td>${escapeHtml(row.Jahr)}</td>
            <td>${row.Gesamtwortzahl.toLocaleString('de-DE')}</td>
            <td>${escapeHtml(row.Referenz)}</td>
            <td>${link ? `<a href="${link}" target="_blank" rel="noopener">Text öffnen</a>` : '—'}</td>
          </tr>`;
        }).join('')}</tbody>
      </table>
    </div>
  `;

  container.querySelectorAll('th[data-key]').forEach((th) => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      const current = appState.dokumente.sort;
      appState.dokumente.sort = { key, dir: current.key === key && current.dir === 'asc' ? 'desc' : 'asc' };
      renderDokumenteTable();
    });
  });
}

function renderDokumenteMatrix() {
  const container = document.getElementById('document-matrix');
  if (!container) return;
  const rows = getDokumenteRows();
  const states = [...new Set(rows.map((r) => r.Bundesland))].sort();
  const subjects = [...new Set(rows.map((r) => r.Fach))].sort();
  if (!appState.dokumente.matrixSort) appState.dokumente.matrixSort = { key: null, dir: 'desc' };
  const matrixSort = appState.dokumente.matrixSort;

  let stateRows = states.map((state) => {
    const counts = subjects.map((subject) => rows.filter((r) => r.Bundesland === state && r.Fach === subject).length);
    return { state, counts, total: counts.reduce((a, b) => a + b, 0) };
  });
  if (matrixSort.key) {
    const colIndex = matrixSort.key === 'Gesamt' ? -1 : subjects.indexOf(matrixSort.key);
    stateRows.sort((a, b) => {
      const va = colIndex === -1 ? a.total : a.counts[colIndex];
      const vb = colIndex === -1 ? b.total : b.counts[colIndex];
      return matrixSort.dir === 'asc' ? va - vb : vb - va;
    });
  }

  const subjectTotals = subjects.map((subject) => rows.filter((r) => r.Fach === subject).length);
  const grandTotal = rows.length;
  const maxCell = Math.max(1, ...stateRows.flatMap((r) => r.counts));

  const headerCells = [
    `<th>Bundesland</th>`,
    ...subjects.map((s) => sortableHeaderCell(s, s, matrixSort)),
    sortableHeaderCell('Gesamt', 'Gesamt', matrixSort),
  ];

  container.innerHTML = `
    <div class="table-shell">
      <table>
        <thead><tr>${headerCells.join('')}</tr></thead>
        <tbody>
          ${stateRows.map((row) => `<tr>
            <td>${escapeHtml(row.state)}</td>
            ${row.counts.map((value) => `<td class="heat-cell" style="background: rgba(8,94,101,${Math.min(0.85, 0.12 + (value / maxCell) * 0.6)});">${value}</td>`).join('')}
            <td>${row.total}</td>
          </tr>`).join('')}
          <tr>
            <td><strong>Gesamt</strong></td>
            ${subjectTotals.map((value) => `<td><strong>${value}</strong></td>`).join('')}
            <td><strong>${grandTotal}</strong></td>
          </tr>
        </tbody>
      </table>
    </div>
  `;

  container.querySelectorAll('th[data-key]').forEach((th) => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      const current = appState.dokumente.matrixSort;
      appState.dokumente.matrixSort = { key, dir: current.key === key && current.dir === 'desc' ? 'asc' : 'desc' };
      renderDokumenteMatrix();
    });
  });
}

function renderKeywordPage() {
  const conceptFilter = document.getElementById('keyword-concept-filter').value;
  const dimensionA = document.getElementById('keyword-dimension-a').value;
  const dimensionB = document.getElementById('keyword-dimension-b').value;
  const filterDimension = document.getElementById('keyword-filter-dimension').value;
  const filterValue = document.getElementById('keyword-filter-value').value;
  const mode = document.getElementById('keyword-mode').value;

  let rows = appState.keywordRows;
  if (conceptFilter !== 'Alle') rows = rows.filter((row) => row.search_term === conceptFilter);
  if (filterValue !== 'Alle') rows = rows.filter((row) => row[dimensionToKey(filterDimension)] === filterValue);

  const rowValues = [...new Set(rows.map((row) => row[dimensionToKey(dimensionA)]).filter(Boolean))].sort();
  const columnValues = [...new Set(rows.map((row) => row[dimensionToKey(dimensionB)]).filter(Boolean))].sort();
  const wordCounts = Object.fromEntries(appState.keywordWordCounts.map((row) => [row.file, Number(row.word_count || 0)]));

  // Word-count denominators are summed over the UNIQUE documents in a
  // slice, not per match-row -- a document with several matches in the
  // same cell shouldn't have its word count added more than once, and
  // when "concept" is one of the chosen dimensions a document can appear
  // in several columns, so row/column aggregates need their own dedup too.
  const wordsForSlice = (slice) => {
    const files = new Set(slice.map((row) => row.file));
    let sum = 0;
    files.forEach((file) => { sum += wordCounts[file] || 0; });
    return sum;
  };
  const cellDisplay = (count, words) => {
    const value = mode === 'relative' ? (count / Math.max(words, 1)) * 10000 : count;
    return Number(value.toFixed(2));
  };

  const tableRows = rowValues.map((rowValue) => {
    const rowMatches = rows.filter((row) => row[dimensionToKey(dimensionA)] === rowValue);
    const entry = { [dimensionLabel(dimensionA)]: rowValue };
    columnValues.forEach((columnValue) => {
      const slice = rowMatches.filter((row) => row[dimensionToKey(dimensionB)] === columnValue);
      entry[columnValue] = cellDisplay(slice.length, wordsForSlice(slice));
    });
    // Gesamt is recomputed from this row's full match set (all columns
    // combined), not by summing the already-normalized per-cell values --
    // summing relative-frequency ratios across cells with different word-
    // count denominators does not equal the row's true combined rate.
    entry.Gesamt = cellDisplay(rowMatches.length, wordsForSlice(rowMatches));
    return entry;
  });

  const gesamtRow = { [dimensionLabel(dimensionA)]: 'Gesamt' };
  columnValues.forEach((columnValue) => {
    const colMatches = rows.filter((row) => row[dimensionToKey(dimensionB)] === columnValue);
    gesamtRow[columnValue] = cellDisplay(colMatches.length, wordsForSlice(colMatches));
  });
  gesamtRow.Gesamt = cellDisplay(rows.length, wordsForSlice(rows));

  // app_specs.md: "include only one table on this page" -- the shaded
  // heatmap below is that one table; a separate plain-table rendering of
  // the same data used to also exist here and has been removed. Keep
  // keywordTableRows (including the Gesamt row) around for CSV export.
  appState.keywordTableRows = [...tableRows, gesamtRow];

  const shadingScope = document.getElementById('keyword-shading-scope')?.value || 'table';
  const heatmapRows = [
    [dimensionLabel(dimensionA), ...columnValues, 'Gesamt'],
    ...tableRows.map((row) => [row[dimensionLabel(dimensionA)], ...columnValues.map((column) => row[column]), row.Gesamt]),
    ['Gesamt', ...columnValues.map((column) => gesamtRow[column]), gesamtRow.Gesamt],
  ];
  if (!appState.keywordSort) appState.keywordSort = { key: null, dir: 'desc' };
  const heatmapEl = document.getElementById('keyword-heatmap');
  heatmapEl.innerHTML = renderHeatmap(
    heatmapRows, mode === 'relative' ? 'Relative Häufigkeit je 10.000 Wörter' : 'Absolute Treffer',
    shadingScope, appState.keywordSort,
  );
  heatmapEl.querySelectorAll('th[data-key]').forEach((th) => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      const current = appState.keywordSort;
      appState.keywordSort = { key, dir: current.key === key && current.dir === 'desc' ? 'asc' : 'desc' };
      renderKeywordPage();
    });
  });

  document.getElementById('keyword-summary').innerHTML = [
    { title: 'Treffer gesamt', value: rows.length.toLocaleString('de-DE') },
    { title: 'Konzept-Filter', value: conceptFilter === 'Alle' ? 'Alle' : conceptFilter },
    { title: 'Ausgewählte Kombination', value: `${dimensionLabel(dimensionA)} × ${dimensionLabel(dimensionB)}` }
  ].map((card) => `<article class="summary-card"><strong>${card.title}</strong><span>${card.value}</span></article>`).join('');
}

// ─────────────────────────────────────────────────────────────────────────
// BERTopic — real 3D UMAP atlas (Plotly), multi-concept comparison
// ─────────────────────────────────────────────────────────────────────────

const BERTOPIC_ORBIT_RADIUS = 2.2;

function loadBerTopicManifest() {
  Promise.all([
    fetchJson(`${BERTOPIC_DATA_BASE}/manifest.json`),
    fetchJson(`${BERTOPIC_DATA_BASE}/color_maps.json`)
  ]).then(([manifest, colorMaps]) => {
    appState.bertopic.manifest = manifest;
    appState.bertopic.colorMaps = colorMaps;
    if (appState.bertopic.active.length === 0) {
      const first = (manifest.concept_order || [])[0];
      if (first) appState.bertopic.active = [first];
    }
    renderBerTopicPage();
  }).catch((error) => {
    console.error(error);
    const panels = document.getElementById('bertopic-panels');
    if (panels) panels.innerHTML = '<p>Die BERTopic-Daten konnten nicht geladen werden.</p>';
  });
}

function renderBerTopicPage() {
  renderBerTopicConceptPicker();
  syncBerTopicPanelGrid();
  renderBerTopicLegend();
}

function renderBerTopicConceptPicker() {
  const container = document.getElementById('bertopic-concept-picker');
  if (!container || !appState.bertopic.manifest) return;
  const concepts = appState.bertopic.manifest.concept_order || [];
  const active = appState.bertopic.active;
  container.innerHTML = concepts.map((concept) => {
    const isActive = active.includes(concept);
    const disabled = !isActive && active.length >= BERTOPIC_MAX_CONCEPTS;
    return `<button type="button" class="concept-btn${isActive ? ' is-active' : ''}" data-concept="${escapeHtml(concept)}" ${disabled ? 'disabled' : ''}>${escapeHtml(concept)}</button>`;
  }).join('');
  container.querySelectorAll('.concept-btn').forEach((btn) => {
    btn.addEventListener('click', () => toggleBerTopicConcept(btn.dataset.concept));
  });
}

function toggleBerTopicConcept(concept) {
  const active = appState.bertopic.active;
  const idx = active.indexOf(concept);
  if (idx >= 0) {
    active.splice(idx, 1);
  } else {
    if (active.length >= BERTOPIC_MAX_CONCEPTS) return;
    active.push(concept);
  }
  renderBerTopicConceptPicker();
  syncBerTopicPanelGrid();
  renderBerTopicLegend();
}

function syncBerTopicPanelGrid() {
  const grid = document.getElementById('bertopic-panels');
  if (!grid) return;
  const active = appState.bertopic.active;
  grid.className = 'bertopic-panels' +
    (active.length >= 7 ? ' grid-9' : active.length >= 5 ? ' grid-6' : active.length >= 3 ? ' grid-4' : active.length === 2 ? ' grid-2' : '');

  if (active.length === 0) {
    grid.innerHTML = '<div class="bt-panel-empty">Wählen Sie oben bis zu neun Konzepte aus, um die Themenräume zu vergleichen.</div>';
    return;
  }

  const emptyState = grid.querySelector('.bt-panel-empty');
  if (emptyState) emptyState.remove();

  const existing = new Map();
  grid.querySelectorAll('.bt-panel').forEach((el) => existing.set(el.dataset.concept, el));

  existing.forEach((el, concept) => {
    if (!active.includes(concept)) {
      const plotEl = el.querySelector('.bt-panel-plot');
      if (plotEl && plotEl.data && typeof Plotly !== 'undefined') Plotly.purge(plotEl);
      el.remove();
    }
  });

  active.forEach((concept) => {
    let panel = existing.get(concept);
    if (!panel) {
      panel = document.createElement('div');
      panel.className = 'bt-panel';
      panel.dataset.concept = concept;
      panel.innerHTML = `
        <div class="bt-panel-head">
          <span>${escapeHtml(concept)}</span>
          <button type="button" class="bt-panel-remove" title="Entfernen">✕</button>
        </div>
        <div class="bt-panel-plot"></div>
      `;
      panel.querySelector('.bt-panel-remove').addEventListener('click', () => toggleBerTopicConcept(concept));
    }
    grid.appendChild(panel);
    ensureBerTopicPanelData(concept);
  });

  setTimeout(resizeAllBerTopicPanels, 60);
}

function findBerTopicPanel(concept) {
  const grid = document.getElementById('bertopic-panels');
  if (!grid) return null;
  return [...grid.querySelectorAll('.bt-panel')].find((el) => el.dataset.concept === concept) || null;
}

function ensureBerTopicPanelData(concept) {
  if (appState.bertopic.conceptData[concept]) {
    drawBerTopicPanel(concept);
    return;
  }
  if (appState.bertopic.loading[concept]) return;
  appState.bertopic.loading[concept] = true;
  fetchJson(`${BERTOPIC_DATA_BASE}/${encodeURIComponent(concept)}.json`)
    .then((records) => {
      appState.bertopic.conceptData[concept] = records;
      appState.bertopic.loading[concept] = false;
      drawBerTopicPanel(concept);
      renderBerTopicLegend();
    })
    .catch((error) => {
      console.error(error);
      appState.bertopic.loading[concept] = false;
      const panel = findBerTopicPanel(concept);
      const plotEl = panel && panel.querySelector('.bt-panel-plot');
      if (plotEl) plotEl.innerHTML = '<p style="padding:16px;color:var(--muted)">Daten konnten nicht geladen werden.</p>';
    });
}

function getBerTopicFilteredRecords(concept) {
  const records = appState.bertopic.conceptData[concept] || [];
  return appState.bertopic.showOutliers ? records : records.filter((r) => !r.is_outlier);
}

const LEGEND_HIGHLIGHT_COLOR = '#ffe600';

function isBerTopicSelected(record, concept) {
  const sel = appState.bertopic.selection;
  if (!sel || record.is_outlier) return false;
  if (sel.type === 'subject') return record.subject === sel.value;
  return concept === sel.concept && record.topic === sel.value;
}

function berTopicColorFor(record, concept) {
  if (isBerTopicSelected(record, concept)) return LEGEND_HIGHLIGHT_COLOR;
  const colorMaps = appState.bertopic.colorMaps || {};
  if (record.is_outlier) return colorMaps.outlier_color || '#8a8a8a';
  if (appState.bertopic.colorBy === 'subject') {
    return (colorMaps.subject || {})[record.subject] || hashColor(record.subject, 'subject');
  }
  return hashColor(`${concept}::${record.topic}`, 'topic');
}

function berTopicSizeFor(record, concept) {
  const base = appState.bertopic.pointSize;
  return isBerTopicSelected(record, concept) ? base + 2 : base;
}

function drawBerTopicPanel(concept) {
  const panel = findBerTopicPanel(concept);
  if (!panel || typeof Plotly === 'undefined') return;
  const plotEl = panel.querySelector('.bt-panel-plot');
  if (!plotEl) return;

  const records = getBerTopicFilteredRecords(concept);
  const is3d = appState.bertopic.dimension !== '2d';
  const suffix = appState.bertopic.projection === 'global' ? '_global' : '';
  const coordKey = (is3d ? 'umap_3d' : 'umap_2d') + suffix;
  const theme = getPlotlyThemeColors();

  const trace = {
    type: is3d ? 'scatter3d' : 'scattergl',
    mode: 'markers',
    x: records.map((r) => r[coordKey][0]),
    y: records.map((r) => r[coordKey][1]),
    marker: {
      size: records.map((r) => berTopicSizeFor(r, concept)),
      color: records.map((r) => berTopicColorFor(r, concept)),
      opacity: 0.85
    },
    customdata: records.map((r) => [r.subject, r.state, r.topic, r.excerpt, r.is_outlier]),
    hoverinfo: 'none'
  };
  if (is3d) trace.z = records.map((r) => r[coordKey][2]);

  const layout = {
    margin: { l: 0, r: 0, t: 0, b: 0 },
    paper_bgcolor: theme.paper,
    plot_bgcolor: theme.paper,
    showlegend: false,
    uirevision: `${concept}-${appState.bertopic.dimension}`
  };
  if (is3d) {
    layout.scene = {
      xaxis: { visible: false }, yaxis: { visible: false }, zaxis: { visible: false },
      camera: currentBerTopicCameraEye(), bgcolor: theme.paper
    };
  } else {
    layout.xaxis = { visible: false };
    layout.yaxis = { visible: false, scaleanchor: 'x' };
  }

  Plotly.react(plotEl, [trace], layout, { displayModeBar: false, responsive: true }).then(() => {
    attachBerTopicHoverHandlers(plotEl, concept);
  });
}

function currentBerTopicCameraEye() {
  const { theta, elevation } = appState.bertopic.orbit;
  return { eye: { x: BERTOPIC_ORBIT_RADIUS * Math.cos(theta), y: BERTOPIC_ORBIT_RADIUS * Math.sin(theta), z: elevation } };
}

function applyBerTopicCameraToAllPanels() {
  const camera = currentBerTopicCameraEye();
  appState.bertopic.active.forEach((concept) => {
    const panel = findBerTopicPanel(concept);
    const plotEl = panel && panel.querySelector('.bt-panel-plot');
    if (plotEl && plotEl.data) Plotly.relayout(plotEl, { 'scene.camera': camera });
  });
}

function seedBerTopicOrbitFromCurrentView() {
  const concept = appState.bertopic.active.find((c) => appState.bertopic.dimension !== '2d' && findBerTopicPanel(c));
  const panel = concept && findBerTopicPanel(concept);
  const plotEl = panel && panel.querySelector('.bt-panel-plot');
  const eye = plotEl && plotEl.layout && plotEl.layout.scene && plotEl.layout.scene.camera && plotEl.layout.scene.camera.eye;
  if (!eye) return;
  appState.bertopic.orbit.theta = Math.atan2(eye.y, eye.x);
  appState.bertopic.orbit.elevation = eye.z;
  const elevationInput = document.getElementById('bertopic-orbit-elevation');
  if (elevationInput) elevationInput.value = String(eye.z);
}

function startBerTopicOrbit() {
  if (appState.bertopic.orbit.raf) return;
  const step = () => {
    appState.bertopic.orbit.theta += 0.01 * appState.bertopic.orbit.speed;
    applyBerTopicCameraToAllPanels();
    appState.bertopic.orbit.raf = requestAnimationFrame(step);
  };
  appState.bertopic.orbit.raf = requestAnimationFrame(step);
}

function stopBerTopicOrbit() {
  if (appState.bertopic.orbit.raf) {
    cancelAnimationFrame(appState.bertopic.orbit.raf);
    appState.bertopic.orbit.raf = null;
  }
}

function rebuildAllBerTopicPanels() {
  appState.bertopic.active.forEach((concept) => drawBerTopicPanel(concept));
}

function restyleAllBerTopicPanels(update) {
  appState.bertopic.active.forEach((concept) => {
    const panel = findBerTopicPanel(concept);
    const plotEl = panel && panel.querySelector('.bt-panel-plot');
    if (plotEl && plotEl.data) Plotly.restyle(plotEl, update);
  });
}

function restylePointSizes() {
  appState.bertopic.active.forEach((concept) => {
    const panel = findBerTopicPanel(concept);
    const plotEl = panel && panel.querySelector('.bt-panel-plot');
    if (!plotEl || !plotEl.data) return;
    const records = getBerTopicFilteredRecords(concept);
    Plotly.restyle(plotEl, { 'marker.size': [records.map((r) => berTopicSizeFor(r, concept))] });
  });
}

function relayoutAllBerTopicPanels(theme) {
  appState.bertopic.active.forEach((concept) => {
    const panel = findBerTopicPanel(concept);
    const plotEl = panel && panel.querySelector('.bt-panel-plot');
    if (plotEl && plotEl.data) Plotly.relayout(plotEl, { paper_bgcolor: theme.paper, 'scene.bgcolor': theme.paper });
  });
}

function resizeAllBerTopicPanels() {
  appState.bertopic.active.forEach((concept) => {
    const panel = findBerTopicPanel(concept);
    const plotEl = panel && panel.querySelector('.bt-panel-plot');
    if (plotEl && plotEl.data && typeof Plotly !== 'undefined') Plotly.Plots.resize(plotEl);
  });
}

function attachBerTopicHoverHandlers(plotEl, concept) {
  plotEl.on('plotly_hover', (event) => {
    const point = event.points && event.points[0];
    if (!point || !point.customdata) return;
    const [subject, state, topic, excerpt, isOutlier] = point.customdata;
    showBerTopicTooltip(event.event, { subject, state, topic, excerpt, isOutlier });
  });
  plotEl.on('plotly_unhover', hideBerTopicTooltip);
}

function showBerTopicTooltip(mouseEvent, info) {
  const tooltip = document.getElementById('bertopic-tooltip');
  if (!tooltip || !mouseEvent) return;
  tooltip.innerHTML = `
    <div class="bt-tooltip-meta"><span>${escapeHtml(info.subject || '—')}</span><span>·</span><span>${escapeHtml(info.state || '—')}</span></div>
    <div class="bt-tooltip-meta" style="color:var(--muted);font-weight:400;">${escapeHtml(info.isOutlier ? 'Ausreißer' : (info.topic || '—'))}</div>
    <div class="bt-tooltip-excerpt">${escapeHtml(info.excerpt || '')}</div>
  `;
  const x = Math.max(8, Math.min(mouseEvent.clientX + 16, window.innerWidth - 340));
  const y = Math.max(8, Math.min(mouseEvent.clientY + 16, window.innerHeight - 220));
  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
  tooltip.hidden = false;
}

function hideBerTopicTooltip() {
  const tooltip = document.getElementById('bertopic-tooltip');
  if (tooltip) tooltip.hidden = true;
}

function renderBerTopicLegend() {
  const el = document.getElementById('bertopic-legend');
  if (!el) return;
  const active = appState.bertopic.active;
  const selection = appState.bertopic.selection;
  if (active.length === 0) {
    el.innerHTML = '<h4>Legende</h4><p style="color:var(--muted);font-size:0.86rem;">Keine Konzepte ausgewählt.</p>';
    return;
  }

  if (appState.bertopic.colorBy === 'subject') {
    const colorMaps = appState.bertopic.colorMaps || {};
    const counts = new Map();
    active.forEach((concept) => {
      (appState.bertopic.conceptData[concept] || []).forEach((r) => {
        if (!r.is_outlier) counts.set(r.subject, (counts.get(r.subject) || 0) + 1);
      });
    });
    const subjects = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a));
    el.innerHTML = `
      <h4>Legende — Fach</h4>
      ${subjects.map((subject) => `
        <div class="legend-row${selection && selection.value !== subject ? ' dimmed' : ''}" data-type="subject" data-value="${escapeHtml(subject)}">
          <span class="legend-swatch" style="background:${(colorMaps.subject || {})[subject] || hashColor(subject, 'subject')}"></span>
          <span class="legend-label">${escapeHtml(subject)}</span>
          <span class="legend-count">${counts.get(subject)}</span>
        </div>`).join('')}
      <div class="legend-row"><span class="legend-swatch" style="background:${colorMaps.outlier_color || '#8a8a8a'}"></span><span class="legend-label">Ausreißer</span></div>
    `;
  } else {
    // Topic counts per concept now range up to ~30 (data-driven per-concept
    // ceiling, METHODOLOGY.md §4.4) rather than a flat ~10, so a concept
    // group can be long enough to bury the others in scroll. <details> keeps
    // every group present and clickable while defaulting small/single/
    // currently-selected groups open and large multi-concept ones collapsed.
    el.innerHTML = `<h4>Legende — Topic</h4>${active.map((concept) => {
      const counts = new Map();
      (appState.bertopic.conceptData[concept] || []).forEach((r) => {
        if (!r.is_outlier) counts.set(r.topic, (counts.get(r.topic) || 0) + 1);
      });
      const topics = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a));
      const isOpen = active.length === 1 || topics.length <= 12 || (selection && selection.concept === concept);
      return `
        <details class="legend-group"${isOpen ? ' open' : ''}>
          <summary class="legend-group-title">${escapeHtml(concept)} <span class="legend-group-count">(${topics.length})</span></summary>
          ${topics.map((topic) => `
            <div class="legend-row${selection && (selection.concept !== concept || selection.value !== topic) ? ' dimmed' : ''}" data-type="topic" data-concept="${escapeHtml(concept)}" data-value="${escapeHtml(topic)}">
              <span class="legend-swatch" style="background:${hashColor(`${concept}::${topic}`, 'topic')}"></span>
              <span class="legend-label">${escapeHtml(topic)}</span>
              <span class="legend-count">${counts.get(topic)}</span>
            </div>`).join('')}
        </details>`;
    }).join('')}`;
  }

  el.querySelectorAll('.legend-row[data-type]').forEach((row) => {
    row.addEventListener('click', () => {
      const type = row.dataset.type;
      const value = row.dataset.value;
      const concept = row.dataset.concept;
      const current = appState.bertopic.selection;
      const isSame = current && current.type === type && current.value === value && current.concept === concept;
      appState.bertopic.selection = isSame ? null : { type, value, concept };
      renderBerTopicLegend();
      rebuildAllBerTopicPanels();
    });
  });
}

function fnv1aHash(str) {
  let hash = 0x811c9dc5;
  for (let i = 0; i < str.length; i += 1) {
    hash ^= str.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

function hashColor(label, salt) {
  const hue = fnv1aHash(`${salt}::${label || ''}`) % 360;
  return hslToHex(hue, 62, 55);
}

function hslToHex(h, s, l) {
  s /= 100; l /= 100;
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  const toHex = (x) => Math.round(255 * x).toString(16).padStart(2, '0');
  return `#${toHex(f(0))}${toHex(f(8))}${toHex(f(4))}`;
}

window.addEventListener('resize', () => {
  clearTimeout(window.__btResizeTimer);
  window.__btResizeTimer = setTimeout(() => {
    if (appState.page === 'bertopic') resizeAllBerTopicPanels();
  }, 200);
});

// ─────────────────────────────────────────────────────────────────────────
// LDA — real pyLDAvis-derived intertopic map, term relevance, and
// cross-concept analytics (folded into the shared app.js patterns)
// ─────────────────────────────────────────────────────────────────────────

function renderLdaPage() {
  if (!appState.lda.concept) appState.lda.concept = appState.conceptOrder[0];
  initTabStrip('lda-tabs');
  populateLdaControls();
  loadLdaData();
  initWordclouds();
}

function populateLdaControls() {
  const conceptSelect = document.getElementById('lda-concept');
  if (conceptSelect) {
    conceptSelect.innerHTML = appState.conceptOrder.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
    conceptSelect.value = appState.lda.concept;
  }
  const kSelect = document.getElementById('lda-k');
  if (kSelect) kSelect.value = String(appState.lda.k);
  const lambdaInput = document.getElementById('lda-lambda');
  if (lambdaInput) lambdaInput.value = String(appState.lda.lambda);
  const lambdaLabel = document.getElementById('lda-lambda-value');
  if (lambdaLabel) lambdaLabel.textContent = appState.lda.lambda.toFixed(2);
}

function loadLdaData() {
  const { concept, k } = appState.lda;
  if (!concept) return;
  const base = `${LDA_DATA_BASE}/${encodeURIComponent(concept)}/${k}`;
  const cooccurrencePromise = appState.lda.cooccurrence
    ? Promise.resolve(appState.lda.cooccurrence)
    : fetchJson(`${LDA_DATA_BASE}/concept_cooccurrence.json`).catch(() => null);

  Promise.all([
    fetchJson(`${base}/ldavis_data_${encodeURIComponent(concept)}_${k}.json`),
    fetchCsv(`${base}/term_frequency_matrix_${encodeURIComponent(concept)}_${k}.csv`).catch(() => []),
    fetchCsv(`${base}/topic_distribution_by_subject_${encodeURIComponent(concept)}_${k}.csv`).catch(() => []),
    cooccurrencePromise
  ]).then(([ldavis, termMatrix, topicSubject, cooccurrence]) => {
    appState.lda.ldavis = ldavis;
    appState.lda.termMatrix = termMatrix;
    appState.lda.topicSubject = topicSubject;
    appState.lda.cooccurrence = cooccurrence;
    appState.lda.selectedTopic = (ldavis.topic_coordinates[0] || {}).topic || 1;
    renderLdaMap();
    renderLdaTermPanel();
    renderLdaTermTable();
    renderLdaTopicSubject();
    renderLdaCooccurrence();
  }).catch((error) => {
    console.error(error);
    const mapEl = document.getElementById('lda-map');
    if (mapEl) mapEl.innerHTML = '<p>Die LDA-Daten für dieses Konzept/k konnten nicht geladen werden.</p>';
  });
}

function renderLdaMap() {
  const el = document.getElementById('lda-map');
  if (!el || typeof Plotly === 'undefined' || !appState.lda.ldavis) return;
  const coords = appState.lda.ldavis.topic_coordinates || [];
  const theme = getPlotlyThemeColors();

  const selected = appState.lda.selectedTopic;

  const trace = {
    type: 'scatter',
    mode: 'markers+text',
    x: coords.map((t) => t.x),
    y: coords.map((t) => t.y),
    text: coords.map((t) => String(t.topic)),
    textfont: { color: '#fff', size: 12 },
    marker: {
      size: coords.map((t) => Math.max(20, Math.sqrt(Math.max(t.freq, 0.1)) * 7)),
      color: coords.map((t) => hashColor(`lda::${t.topic}`, 'lda-topic')),
      line: {
        color: coords.map((t) => (t.topic === selected ? LEGEND_HIGHLIGHT_COLOR : theme.border)),
        width: coords.map((t) => (t.topic === selected ? 3 : 1))
      }
    },
    customdata: coords.map((t) => t.topic),
    hoverinfo: 'none'
  };

  const layout = {
    margin: { l: 30, r: 20, t: 20, b: 30 },
    paper_bgcolor: theme.paper,
    plot_bgcolor: theme.paper,
    xaxis: { zeroline: false, showgrid: true, gridcolor: theme.border, color: theme.muted },
    yaxis: { zeroline: false, showgrid: true, gridcolor: theme.border, color: theme.muted },
    showlegend: false,
    uirevision: `${appState.lda.concept}-${appState.lda.k}`
  };

  Plotly.react(el, [trace], layout, { displayModeBar: false, responsive: true }).then(() => {
    el.on('plotly_click', (event) => {
      const point = event.points && event.points[0];
      if (!point) return;
      appState.lda.selectedTopic = point.customdata;
      renderLdaMap();
      renderLdaTermPanel();
    });
  });
}

function renderLdaTermPanel() {
  const titleEl = document.getElementById('lda-selected-topic-title');
  const chartEl = document.getElementById('lda-term-chart');
  if (!titleEl || !chartEl || !appState.lda.ldavis) return;

  const topicId = appState.lda.selectedTopic;
  const terms = (appState.lda.ldavis.topics || {})[String(topicId)] || [];
  const lambda = appState.lda.lambda;
  const ranked = terms
    .map((t) => ({ ...t, relevance: lambda * t.logprob + (1 - lambda) * t.loglift }))
    .sort((a, b) => b.relevance - a.relevance)
    .slice(0, 30);

  titleEl.textContent = `Thema ${topicId} — Top-Begriffe`;
  const maxFreq = Math.max(...ranked.map((t) => t.freq), 1);
  chartEl.innerHTML = ranked.length ? `
    <div class="chart-list">
      ${ranked.map((t) => `
        <div class="bar-row">
          <span>${escapeHtml(t.term)}</span>
          <strong title="Häufigkeit im Thema / gesamt im Korpus">${t.freq} / ${t.total}</strong>
          <div class="bar-track"><div class="bar-fill" style="width:${(t.freq / maxFreq) * 100}%"></div></div>
        </div>
      `).join('')}
    </div>
  ` : '<p>Keine Begriffe für dieses Thema verfügbar.</p>';
}

function renderLdaTermTable() {
  const container = document.getElementById('lda-term-table');
  if (!container) return;
  const rows = appState.lda.termMatrix || [];
  if (!rows.length) { container.innerHTML = '<p>Keine Daten verfügbar.</p>'; return; }

  const headers = Object.keys(rows[0]);
  const sort = appState.lda.tableSort;
  const sorted = [...rows].sort((a, b) => {
    const na = Number(a[sort.key]); const nb = Number(b[sort.key]);
    const cmp = (!Number.isNaN(na) && !Number.isNaN(nb)) ? na - nb : String(a[sort.key]).localeCompare(String(b[sort.key]));
    return sort.dir === 'asc' ? cmp : -cmp;
  });

  container.innerHTML = `
    <div class="table-shell">
      <table>
        <thead><tr>${headers.map((h) => sortableHeaderCell(ldaTermColumnLabel(h), h, sort)).join('')}</tr></thead>
        <tbody>${sorted.map((row) => `<tr>${headers.map((h) => `<td>${escapeHtml(row[h])}</td>`).join('')}</tr>`).join('')}</tbody>
      </table>
    </div>
  `;
  container.querySelectorAll('th[data-key]').forEach((th) => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      const current = appState.lda.tableSort;
      appState.lda.tableSort = { key, dir: current.key === key && current.dir === 'desc' ? 'asc' : 'desc' };
      renderLdaTermTable();
    });
  });
}

function ldaTermColumnLabel(header) {
  if (header === 'term') return 'Begriff';
  if (header === 'total_across_topics') return 'Gesamt (alle Themen)';
  return header.replace('Topic_', 'Thema ');
}

function renderLdaTopicSubject() {
  const container = document.getElementById('lda-topic-subject');
  if (!container) return;
  const rows = appState.lda.topicSubject || [];
  if (!rows.length) { container.innerHTML = '<p>Keine Daten verfügbar.</p>'; return; }
  const columns = Object.keys(rows[0]);
  const matrix = [
    ['Thema', ...columns.slice(1)],
    ...rows.map((row) => [`Thema ${row.topic_id}`, ...columns.slice(1).map((c) => row[c])])
  ];
  if (!appState.lda.topicSubjectSort) appState.lda.topicSubjectSort = { key: null, dir: 'desc' };
  container.innerHTML = renderMatrix(matrix, appState.lda.topicSubjectSort);
  container.querySelectorAll('th[data-key]').forEach((th) => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      const current = appState.lda.topicSubjectSort;
      appState.lda.topicSubjectSort = { key, dir: current.key === key && current.dir === 'desc' ? 'asc' : 'desc' };
      renderLdaTopicSubject();
    });
  });
}

function renderLdaCooccurrence() {
  const container = document.getElementById('lda-cooccurrence');
  const networkEl = document.getElementById('lda-cooccurrence-network');
  const data = appState.lda.cooccurrence;
  if (!data) {
    if (container) container.innerHTML = '<p>Keine Daten verfügbar.</p>';
    return;
  }
  if (container) {
    const matrix = [['Konzept', ...data.concepts], ...data.concepts.map((c, i) => [c, ...data.matrix[i]])];
    if (!appState.lda.cooccurrenceSort) appState.lda.cooccurrenceSort = { key: null, dir: 'desc' };
    container.innerHTML = renderMatrix(matrix, appState.lda.cooccurrenceSort);
    container.querySelectorAll('th[data-key]').forEach((th) => {
      th.addEventListener('click', () => {
        const key = th.dataset.key;
        const current = appState.lda.cooccurrenceSort;
        appState.lda.cooccurrenceSort = { key, dir: current.key === key && current.dir === 'desc' ? 'asc' : 'desc' };
        renderLdaCooccurrence();
      });
    });
  }
  if (networkEl) renderCooccurrenceNetwork(networkEl, data);
}

function renderCooccurrenceNetwork(el, data) {
  if (typeof Plotly === 'undefined') return;
  const { concepts, matrix } = data;
  const n = concepts.length;
  const theme = getPlotlyThemeColors();

  // Simple force-directed layout: repulsion between all node pairs, attraction
  // along edges weighted by co-occurrence value, run for a fixed number of steps.
  const positions = concepts.map((_, i) => {
    const angle = (i / n) * Math.PI * 2;
    return { x: Math.cos(angle), y: Math.sin(angle) };
  });
  const maxWeight = Math.max(1, ...matrix.flat());
  for (let step = 0; step < 300; step += 1) {
    const forces = positions.map(() => ({ x: 0, y: 0 }));
    for (let i = 0; i < n; i += 1) {
      for (let j = i + 1; j < n; j += 1) {
        const dx = positions[i].x - positions[j].x;
        const dy = positions[i].y - positions[j].y;
        const distSq = Math.max(dx * dx + dy * dy, 0.001);
        const repulse = 0.02 / distSq;
        const weight = (matrix[i][j] + matrix[j][i]) / (2 * maxWeight);
        const attract = weight * 0.02;
        const fx = dx * repulse - dx * attract;
        const fy = dy * repulse - dy * attract;
        forces[i].x += fx; forces[i].y += fy;
        forces[j].x -= fx; forces[j].y -= fy;
      }
    }
    positions.forEach((p, i) => { p.x += forces[i].x; p.y += forces[i].y; });
  }

  const edgeTraces = [];
  for (let i = 0; i < n; i += 1) {
    for (let j = i + 1; j < n; j += 1) {
      const weight = matrix[i][j] + matrix[j][i];
      if (weight <= 0) continue;
      edgeTraces.push({
        type: 'scatter', mode: 'lines', hoverinfo: 'none', showlegend: false,
        x: [positions[i].x, positions[j].x], y: [positions[i].y, positions[j].y],
        line: { color: theme.border, width: Math.min(6, 0.6 + (weight / maxWeight) * 5) }
      });
    }
  }

  const nodeTrace = {
    type: 'scatter', mode: 'markers+text', showlegend: false,
    x: positions.map((p) => p.x), y: positions.map((p) => p.y),
    text: concepts, textposition: 'top center',
    textfont: { color: theme.text, size: 11 },
    marker: { size: 16, color: theme.paper, line: { color: '#53d1ff', width: 2 } },
    hovertext: concepts, hoverinfo: 'text'
  };

  Plotly.react(el, [...edgeTraces, nodeTrace], {
    margin: { l: 10, r: 10, t: 10, b: 10 },
    paper_bgcolor: theme.paper, plot_bgcolor: theme.paper,
    xaxis: { visible: false }, yaxis: { visible: false },
    showlegend: false, uirevision: 'cooccurrence-network'
  }, { displayModeBar: false, responsive: true });
}

// ─────────────────────────────────────────────────────────────────────────
// LDA — Wortwolken (word clouds), built from the already-loaded per-topic
// term-frequency data. No external word-cloud library: a small canvas-measured
// Archimedean-spiral packer renders circular, horizontal-only word clouds.
// ─────────────────────────────────────────────────────────────────────────

let _wcCanvas = null;
function wcMeasure(term, fontSize) {
  if (!_wcCanvas) _wcCanvas = document.createElement('canvas');
  const ctx = _wcCanvas.getContext('2d');
  ctx.font = `700 ${fontSize}px Nunito, sans-serif`;
  return ctx.measureText(term).width;
}

function wcScaleFontSize(weight, maxWeight) {
  const t = maxWeight > 0 ? Math.sqrt(Math.max(weight, 0) / maxWeight) : 0;
  return 5 + t * (30 - 5);
}

function wcRectsOverlap(a, b) {
  return !(a.x + a.width < b.x - 2 || b.x + b.width < a.x - 2 || a.y + a.height < b.y - 2 || b.y + b.height < a.y - 2);
}

function wcLayout(terms, size) {
  const center = size / 2;
  const placed = [];
  terms.forEach((t) => {
    const width = wcMeasure(t.term, t.fontSize);
    const height = t.fontSize * 1.15;
    let angle = Math.random() * Math.PI * 2;
    let radius = 0;
    let tries = 0;
    let rect;
    for (;;) {
      const x = center + radius * Math.cos(angle) - width / 2;
      const y = center + radius * Math.sin(angle) - height / 2;
      rect = { x, y, width, height };
      const outOfCircle = Math.hypot(x + width / 2 - center, y + height / 2 - center) + Math.max(width, height) / 2 > size / 2 - 4;
      const overlaps = !outOfCircle && placed.some((p) => wcRectsOverlap(rect, p));
      tries += 1;
      if ((!outOfCircle && !overlaps) || tries > 3000) break;
      angle += 0.36;
      radius += 1.4;
    }
    placed.push(rect);
    t.x = rect.x; t.y = rect.y; t.width = rect.width; t.height = rect.height;
  });
  return terms;
}

function renderWordCloudCard(title, termsRaw, size = 260) {
  const terms = termsRaw.filter((t) => t.weight > 0).sort((a, b) => b.weight - a.weight).slice(0, 50);
  if (!terms.length) {
    return `<div class="wc-card"><h4 class="wc-card-title">${escapeHtml(title)}</h4><div class="wc-circle" style="width:${size}px;height:${size}px;"></div></div>`;
  }
  const maxWeight = Math.max(1, ...terms.map((t) => t.weight));
  const sized = terms.map((t) => ({ ...t, fontSize: wcScaleFontSize(t.weight, maxWeight) }));
  wcLayout(sized, size);
  const words = sized.map((t) => `<span style="position:absolute;left:${t.x.toFixed(1)}px;top:${t.y.toFixed(1)}px;font-size:${t.fontSize.toFixed(1)}px;color:${hashColor(t.term, 'wordcloud-term')};font-family:'Nunito',sans-serif;font-weight:700;white-space:nowrap;line-height:1.15;">${escapeHtml(t.term)}</span>`).join('');
  return `
    <div class="wc-card">
      <h4 class="wc-card-title">${escapeHtml(title)}</h4>
      <div class="wc-circle" style="width:${size}px;height:${size}px;">${words}</div>
    </div>
  `;
}

async function fetchTermFrequencyMatrix(concept, k) {
  const key = `${concept}::${k}`;
  if (appState.wordcloud.cache[key]) return appState.wordcloud.cache[key];
  const rows = await fetchCsv(`${LDA_DATA_BASE}/${encodeURIComponent(concept)}/${k}/term_frequency_matrix_${encodeURIComponent(concept)}_${k}.csv`).catch(() => []);
  appState.wordcloud.cache[key] = rows;
  return rows;
}

function initWordclouds() {
  if (appState.wordcloud) { renderWordclouds(); return; }
  appState.wordcloud = {
    mode: 'collection',
    collectionConcepts: appState.conceptOrder.slice(0, 3),
    singleConcept: appState.conceptOrder[0],
    cache: {}
  };
  populateWordcloudControls();
  bindWordcloudEvents();
  renderWordclouds();
}

function populateWordcloudControls() {
  const picker = document.getElementById('wc-collection-picker');
  const singleSelect = document.getElementById('wc-single-concept');
  if (picker) {
    picker.innerHTML = appState.conceptOrder.map((concept) => `
      <label class="wc-checkbox"><input type="checkbox" value="${escapeHtml(concept)}" ${appState.wordcloud.collectionConcepts.includes(concept) ? 'checked' : ''} /> ${escapeHtml(concept)}</label>
    `).join('');
    picker.querySelectorAll('input[type="checkbox"]').forEach((input) => {
      input.addEventListener('change', () => {
        const list = appState.wordcloud.collectionConcepts;
        if (input.checked) {
          if (list.length >= BERTOPIC_MAX_CONCEPTS) { input.checked = false; return; }
          list.push(input.value);
        } else {
          const idx = list.indexOf(input.value);
          if (idx >= 0) list.splice(idx, 1);
        }
        renderWordclouds();
      });
    });
  }
  if (singleSelect) {
    singleSelect.innerHTML = appState.conceptOrder.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
    singleSelect.value = appState.wordcloud.singleConcept;
  }
}

function bindWordcloudEvents() {
  document.getElementById('wc-mode')?.addEventListener('change', (event) => {
    appState.wordcloud.mode = event.target.value;
    const collectionPicker = document.getElementById('wc-collection-picker');
    const singleWrap = document.getElementById('wc-single-picker-wrap');
    if (collectionPicker) collectionPicker.hidden = appState.wordcloud.mode !== 'collection';
    if (singleWrap) singleWrap.hidden = appState.wordcloud.mode !== 'single';
    renderWordclouds();
  });
  document.getElementById('wc-single-concept')?.addEventListener('change', (event) => {
    appState.wordcloud.singleConcept = event.target.value;
    renderWordclouds();
  });
}

async function renderWordclouds() {
  const container = document.getElementById('wc-grid');
  if (!container || !appState.wordcloud) return;
  container.innerHTML = '<p style="color:var(--muted);">Lade Wortwolken …</p>';

  if (appState.wordcloud.mode === 'collection') {
    const concepts = appState.wordcloud.collectionConcepts;
    if (!concepts.length) {
      container.innerHTML = '<p style="color:var(--muted);">Bitte mindestens ein Konzept auswählen.</p>';
      return;
    }
    const k = appState.lda.k || 10;
    const rowsByConcept = await Promise.all(concepts.map((c) => fetchTermFrequencyMatrix(c, k)));

    const globalTotals = new Map();
    rowsByConcept.forEach((rows) => {
      rows.forEach((row) => {
        const weight = Number(row.total_across_topics || 0);
        globalTotals.set(row.term, (globalTotals.get(row.term) || 0) + weight);
      });
    });
    const globalTerms = [...globalTotals.entries()].map(([term, weight]) => ({ term, weight }));

    const cols = concepts.length >= 5 ? 3 : concepts.length >= 3 ? 2 : concepts.length;
    const perConceptCards = concepts.map((concept, i) => {
      const terms = rowsByConcept[i].map((row) => ({ term: row.term, weight: Number(row.total_across_topics || 0) }));
      return renderWordCloudCard(concept, terms);
    }).join('');

    container.className = `wc-grid wc-cols-${Math.max(cols, 1)}`;
    container.innerHTML = `
      <div class="wc-global-wrap">${renderWordCloudCard('Global (alle ausgewählten Konzepte)', globalTerms, 300)}</div>
      ${perConceptCards}
    `;
  } else {
    const concept = appState.wordcloud.singleConcept;
    if (!concept) return;
    const rows = await fetchTermFrequencyMatrix(concept, 10);
    if (!rows.length) {
      container.innerHTML = '<p style="color:var(--muted);">Keine Daten verfügbar.</p>';
      return;
    }
    const topicCols = Object.keys(rows[0]).filter((h) => h.startsWith('Topic_'));
    const topicTotals = topicCols
      .map((col) => ({ col, total: rows.reduce((sum, row) => sum + Number(row[col] || 0), 0) }))
      .sort((a, b) => b.total - a.total);

    container.className = 'wc-grid wc-cols-4';
    container.innerHTML = topicTotals.map(({ col }) => {
      const terms = rows.map((row) => ({ term: row.term, weight: Number(row[col] || 0) }));
      return renderWordCloudCard(col.replace('Topic_', 'Thema '), terms, 220);
    }).join('');
  }
}

function downloadCsvFromArray(rows, filename) {
  if (!rows || !rows.length) return;
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(',')];
  rows.forEach((row) => lines.push(headers.map((h) => csvEscapeCell(row[h])).join(',')));
  const blob = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function csvEscapeCell(value) {
  const str = String(value ?? '');
  return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
}

function initTabStrip(stripId) {
  const strip = document.getElementById(stripId);
  if (!strip) return;
  strip.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      strip.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('is-active', b === btn));
      document.querySelectorAll(`.tab-panel[data-strip="${stripId}"]`).forEach((panel) => {
        panel.classList.toggle('is-active', panel.dataset.tab === btn.dataset.tab);
      });
    });
  });
}

function renderMatrix(matrix, sortState = null) {
  const [headerRow, ...allRows] = matrix;

  // As in renderHeatmap(): a trailing "Gesamt" row stays pinned at the
  // bottom regardless of sort -- only the other rows get reordered.
  const gesamtRow = allRows.length && allRows[allRows.length - 1][0] === 'Gesamt'
    ? allRows[allRows.length - 1] : null;
  let rows = gesamtRow ? allRows.slice(0, -1) : allRows;

  if (sortState && sortState.key) {
    const colIndex = headerRow.indexOf(sortState.key);
    if (colIndex > 0) {
      rows = [...rows].sort((a, b) => {
        const va = Number(a[colIndex]);
        const vb = Number(b[colIndex]);
        const cmp = (Number.isNaN(va) ? -Infinity : va) - (Number.isNaN(vb) ? -Infinity : vb);
        return sortState.dir === 'asc' ? cmp : -cmp;
      });
    }
  }
  const renderedRows = gesamtRow ? [...rows, gesamtRow] : rows;

  return `
    <div class="table-shell">
      <table>
        <thead><tr>${headerRow.map((value, index) => index === 0 ? `<th>${escapeHtml(value)}</th>` : sortableHeaderCell(value, value, sortState)).join('')}</tr></thead>
        <tbody>${renderedRows.map((row) => `<tr>${row.map((value, index) => {
          const isHeader = index === 0;
          const number = Number(value);
          const isNumber = !Number.isNaN(number);
          return `<td class="${isHeader ? '' : 'heat-cell'}" style="${isNumber ? `background: rgba(8,94,101,${Math.min(0.8, 0.15 + number / 30)});` : ''}">${escapeHtml(value)}</td>`;
        }).join('')}</tr>`).join('')}</tbody>
      </table>
    </div>
  `;
}

function renderHeatmap(rows, title, scope = 'table', sortState = null) {
  const [headerRow, ...allDataRows] = rows;

  // The "Gesamt" row (if present) always stays pinned at the bottom --
  // sorting reorders every other row around it, never the total itself.
  const gesamtRow = allDataRows.length && allDataRows[allDataRows.length - 1][0] === 'Gesamt'
    ? allDataRows[allDataRows.length - 1] : null;
  let dataRows = gesamtRow ? allDataRows.slice(0, -1) : allDataRows;

  if (sortState && sortState.key) {
    const colIndex = headerRow.indexOf(sortState.key);
    if (colIndex > 0) {
      dataRows = [...dataRows].sort((a, b) => {
        const va = Number(a[colIndex]);
        const vb = Number(b[colIndex]);
        const cmp = (Number.isNaN(va) ? -Infinity : va) - (Number.isNaN(vb) ? -Infinity : vb);
        return sortState.dir === 'asc' ? cmp : -cmp;
      });
    }
  }
  const renderedRows = gesamtRow ? [...dataRows, gesamtRow] : dataRows;

  const dataCells = renderedRows.map((row) => row.slice(1).map(Number));
  const tableMax = Math.max(1, ...dataCells.flat().filter((n) => !Number.isNaN(n)));
  const colMax = headerRow.slice(1).map((_, colIndex) => Math.max(1, ...dataCells.map((cells) => cells[colIndex]).filter((n) => !Number.isNaN(n))));
  const rowMax = dataCells.map((cells) => Math.max(1, ...cells.filter((n) => !Number.isNaN(n))));

  const shadeFor = (value, rowIndex, colIndex) => {
    const denom = scope === 'column' ? colMax[colIndex] : scope === 'row' ? rowMax[rowIndex] : tableMax;
    return Math.max(0.14, Math.min(0.9, value / Math.max(denom, 1)));
  };

  return `
    <div class="panel">
      <h4>${escapeHtml(title)}</h4>
      <div class="table-shell">
        <table>
          <tr>${headerRow.map((value, index) => index === 0 ? `<th>${escapeHtml(value)}</th>` : sortableHeaderCell(value, value, sortState)).join('')}</tr>
          ${renderedRows.map((row, rowIndex) => `<tr>${row.map((value, index) => {
            if (index === 0) return `<td>${escapeHtml(value)}</td>`;
            const numeric = Number(value);
            if (Number.isNaN(numeric)) return `<td>${escapeHtml(value)}</td>`;
            return `<td class="heat-cell" style="background: rgba(8,94,101,${shadeFor(numeric, rowIndex, index - 1)});">${escapeHtml(value)}</td>`;
          }).join('')}</tr>`).join('')}
        </table>
      </div>
    </div>
  `;
}

function dimensionLabel(value) {
  return dimensionOptions.find((option) => option.value === value)?.label || value;
}

function sortableHeaderCell(label, key, sortState) {
  // Every sortable column shows an arrow by default (neutral ↕ when not
  // the active sort column, ▲/▼ when it is) so users can tell at a glance
  // that the column is sortable, per app_specs.md's repeated requirement.
  const isActive = sortState && sortState.key === key;
  const arrow = isActive ? (sortState.dir === 'asc' ? ' ▲' : ' ▼') : ' ↕';
  return `<th data-key="${escapeHtml(key)}" style="cursor:pointer;">${escapeHtml(label)}${arrow}</th>`;
}

function escapeHtml(value) {
  return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load ${url}`);
  return response.json();
}

async function fetchCsv(url) {
  const text = await fetchText(url);
  const rows = parseCsv(text);
  if (!rows.length) return [];
  const headers = rows[0];
  return rows.slice(1).map((values) => {
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] || '';
    });
    return row;
  });
}

async function fetchText(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load ${url}`);
  return response.text();
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let value = '';
  let inQuotes = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"') {
      if (inQuotes && next === '"') {
        value += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      row.push(value);
      value = '';
    } else if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && next === '\n') index += 1;
      row.push(value);
      if (row.some((entry) => entry.length > 0)) rows.push(row);
      row = [];
      value = '';
    } else {
      value += char;
    }
  }
  if (value.length > 0 || row.length) { row.push(value); rows.push(row); }
  return rows;
}

document.addEventListener('DOMContentLoaded', init);
