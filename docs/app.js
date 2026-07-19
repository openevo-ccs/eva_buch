const appState = {
  theme: localStorage.getItem('theme') || 'dark',
  manifest: null,
  documentCatalog: null,
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
    pointSize: 4,
    orbit: { enabled: false, speed: 1, elevation: 0.35, theta: 0, raf: null },
    isolated: new Set()
  }
};

const BERTOPIC_MAX_CONCEPTS = 6;
const BERTOPIC_DATA_BASE = './data/bertopic';
const LDA_DATA_BASE = './data/lda';

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
  document.getElementById('bertopic-point-size')?.addEventListener('input', (event) => {
    appState.bertopic.pointSize = Number(event.target.value);
    restyleAllBerTopicPanels({ 'marker.size': appState.bertopic.pointSize });
  });
  document.getElementById('bertopic-orbit-enabled')?.addEventListener('change', (event) => {
    appState.bertopic.orbit.enabled = event.target.checked;
    if (appState.bertopic.orbit.enabled) startBerTopicOrbit(); else stopBerTopicOrbit();
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

  document.getElementById('lda-concept')?.addEventListener('change', (event) => {
    appState.lda.concept = event.target.value;
    loadLdaData();
  });
  document.getElementById('lda-k')?.addEventListener('change', (event) => {
    appState.lda.k = Number(event.target.value);
    loadLdaData();
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

    const [manifest, documentCatalog, keywordRows, keywordWordCounts, matrixRows] = await Promise.all([
      fetchJson('./data/manifest.json'),
      fetchJson('./data/document_catalog.json'),
      needsKeywordData ? fetchCsv('./data/results.csv') : Promise.resolve([]),
      needsKeywordData ? fetchCsv('./data/doc_word_counts.csv') : Promise.resolve([]),
      fetchCsv('./data/state_subject_count_matrix.csv')
    ]);

    appState.manifest = manifest;
    appState.documentCatalog = documentCatalog;
    appState.keywordRows = keywordRows;
    appState.keywordWordCounts = keywordWordCounts;
    appState.matrixRows = matrixRows;
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

function renderDocumentPage() {
  const documents = [...(appState.documentCatalog?.documents || [])].sort((a, b) => (b.year || 0) - (a.year || 0));
  const tableRows = documents.map((doc) => ({ Titel: doc.title, Fach: doc.subject, Bundesland: doc.state, Jahr: doc.year || '—', Pfad: doc.path }));
  document.getElementById('document-table').innerHTML = renderTable(tableRows, ['Titel', 'Fach', 'Bundesland', 'Jahr', 'Pfad']);

  const states = [...new Set(documents.map((doc) => doc.state).filter(Boolean))].sort();
  const subjects = [...new Set(documents.map((doc) => doc.subject).filter(Boolean))].sort();
  const matrix = [['Bundesland', ...subjects, 'Gesamt'], ...states.map((state) => {
    const rowValues = subjects.map((subject) => documents.filter((doc) => doc.state === state && doc.subject === subject).length);
    return [state, ...rowValues, rowValues.reduce((sum, value) => sum + value, 0)];
  }), ['Gesamt', ...subjects.map((subject) => documents.filter((doc) => doc.subject === subject).length), documents.length]];
  document.getElementById('document-matrix').innerHTML = renderMatrix(matrix);
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

  const tableRows = rowValues.map((rowValue) => {
    const entry = { [dimensionLabel(dimensionA)]: rowValue };
    columnValues.forEach((columnValue) => {
      const matches = rows.filter((row) => row[dimensionToKey(dimensionA)] === rowValue && row[dimensionToKey(dimensionB)] === columnValue);
      const totalWords = matches.reduce((sum, row) => sum + (wordCounts[row.file] || 1), 0);
      const value = mode === 'relative' ? (matches.length / Math.max(totalWords, 1)) * 10000 : matches.length;
      entry[columnValue] = Number(value.toFixed(2));
    });
    return entry;
  });

  document.getElementById('keyword-table').innerHTML = renderTable(tableRows, [dimensionLabel(dimensionA), ...columnValues]);

  const heatmapRows = [[dimensionLabel(dimensionA), ...columnValues], ...tableRows.map((row) => [row[dimensionLabel(dimensionA)], ...columnValues.map((column) => row[column])])];
  document.getElementById('keyword-heatmap').innerHTML = renderHeatmap(heatmapRows, mode === 'relative' ? 'Relative Häufigkeit je 10.000 Wörter' : 'Absolute Treffer');

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
    (active.length >= 5 ? ' grid-6' : active.length >= 3 ? ' grid-4' : active.length === 2 ? ' grid-2' : '');

  if (active.length === 0) {
    grid.innerHTML = '<div class="bt-panel-empty">Wählen Sie oben bis zu sechs Konzepte aus, um die Themenräume zu vergleichen.</div>';
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

function berTopicColorFor(record, concept) {
  const colorMaps = appState.bertopic.colorMaps || {};
  if (record.is_outlier) return colorMaps.outlier_color || '#8a8a8a';
  if (appState.bertopic.colorBy === 'subject') {
    return (colorMaps.subject || {})[record.subject] || hashColor(record.subject, 'subject');
  }
  return hashColor(`${concept}::${record.topic}`, 'topic');
}

function drawBerTopicPanel(concept) {
  const panel = findBerTopicPanel(concept);
  if (!panel || typeof Plotly === 'undefined') return;
  const plotEl = panel.querySelector('.bt-panel-plot');
  if (!plotEl) return;

  const records = getBerTopicFilteredRecords(concept);
  const coordKey = appState.bertopic.projection === 'global' ? 'umap_3d_global' : 'umap_3d';
  const theme = getPlotlyThemeColors();

  const trace = {
    type: 'scatter3d',
    mode: 'markers',
    x: records.map((r) => r[coordKey][0]),
    y: records.map((r) => r[coordKey][1]),
    z: records.map((r) => r[coordKey][2]),
    marker: { size: appState.bertopic.pointSize, color: records.map((r) => berTopicColorFor(r, concept)), opacity: 0.85 },
    customdata: records.map((r) => [r.subject, r.state, r.topic, r.excerpt, r.is_outlier]),
    hoverinfo: 'none'
  };

  const layout = {
    margin: { l: 0, r: 0, t: 0, b: 0 },
    paper_bgcolor: theme.paper,
    scene: {
      xaxis: { visible: false }, yaxis: { visible: false }, zaxis: { visible: false },
      camera: currentBerTopicCameraEye(), bgcolor: theme.paper
    },
    showlegend: false,
    uirevision: concept
  };

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
        <div class="legend-row">
          <span class="legend-swatch" style="background:${(colorMaps.subject || {})[subject] || hashColor(subject, 'subject')}"></span>
          <span class="legend-label">${escapeHtml(subject)}</span>
          <span class="legend-count">${counts.get(subject)}</span>
        </div>`).join('')}
      <div class="legend-row"><span class="legend-swatch" style="background:${colorMaps.outlier_color || '#8a8a8a'}"></span><span class="legend-label">Ausreißer</span></div>
    `;
  } else {
    el.innerHTML = `<h4>Legende — Topic</h4>${active.map((concept) => {
      const counts = new Map();
      (appState.bertopic.conceptData[concept] || []).forEach((r) => {
        if (!r.is_outlier) counts.set(r.topic, (counts.get(r.topic) || 0) + 1);
      });
      const topics = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a));
      return `
        <div class="legend-group">
          <div class="legend-group-title">${escapeHtml(concept)}</div>
          ${topics.map((topic) => `
            <div class="legend-row">
              <span class="legend-swatch" style="background:${hashColor(`${concept}::${topic}`, 'topic')}"></span>
              <span class="legend-label">${escapeHtml(topic)}</span>
              <span class="legend-count">${counts.get(topic)}</span>
            </div>`).join('')}
        </div>`;
    }).join('')}`;
  }
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
  populateLdaControls();
  loadLdaData();
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
      line: { color: theme.border, width: 1 }
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
        <thead><tr>${headers.map((h) => `<th data-key="${h}" style="cursor:pointer;">${escapeHtml(ldaTermColumnLabel(h))}${sort.key === h ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead>
        <tbody>${sorted.map((row) => `<tr>${headers.map((h) => `<td>${escapeHtml(row[h])}</td>`).join('')}</tr>`).join('')}</tbody>
      </table>
    </div>
  `;
  container.querySelectorAll('th').forEach((th) => {
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
  container.innerHTML = renderMatrix(matrix);
}

function renderLdaCooccurrence() {
  const container = document.getElementById('lda-cooccurrence');
  if (!container) return;
  const data = appState.lda.cooccurrence;
  if (!data) { container.innerHTML = '<p>Keine Daten verfügbar.</p>'; return; }
  const matrix = [['Konzept', ...data.concepts], ...data.concepts.map((c, i) => [c, ...data.matrix[i]])];
  container.innerHTML = renderMatrix(matrix);
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

function renderTable(rows, headers) {
  if (!rows.length) return '<p>Keine Daten verfügbar.</p>';
  return `
    <div class="table-shell">
      <table>
        <thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join('')}</tr></thead>
        <tbody>${rows.map((row) => `<tr>${headers.map((header) => `<td>${escapeHtml(row[header] ?? '—')}</td>`).join('')}</tr>`).join('')}</tbody>
      </table>
    </div>
  `;
}

function renderMatrix(matrix) {
  const [headerRow, ...rows] = matrix;
  return `
    <div class="table-shell">
      <table>
        <thead><tr>${headerRow.map((value) => `<th>${escapeHtml(value)}</th>`).join('')}</tr></thead>
        <tbody>${rows.map((row) => `<tr>${row.map((value, index) => {
          const isHeader = index === 0;
          const number = Number(value);
          const isNumber = !Number.isNaN(number);
          return `<td class="${isHeader ? '' : 'heat-cell'}" style="${isNumber ? `background: rgba(8,94,101,${Math.min(0.8, 0.15 + number / 30)});` : ''}">${escapeHtml(value)}</td>`;
        }).join('')}</tr>`).join('')}</tbody>
      </table>
    </div>
  `;
}

function renderHeatmap(rows, title) {
  return `
    <div class="panel">
      <h4>${title}</h4>
      <div class="table-shell">
        <table>${rows.map((row) => `<tr>${row.map((value, index) => {
          const numeric = Number(value);
          return `<td class="${Number.isNaN(numeric) ? '' : 'heat-cell'}" style="${Number.isNaN(numeric) ? '' : `background: rgba(8,94,101,${Math.max(0.14, Math.min(0.9, numeric / 20))});`}">${escapeHtml(value)}</td>`;
        }).join('')}</tr>`).join('')}</table>
      </div>
    </div>
  `;
}

function dimensionLabel(value) {
  return dimensionOptions.find((option) => option.value === value)?.label || value;
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
