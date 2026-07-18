const appState = {
  theme: localStorage.getItem('theme') || 'dark',
  manifest: null,
  documentCatalog: null,
  keywordRows: [],
  keywordWordCounts: [],
  conceptOrder: [],
  selectedConcept: 'Anpassung',
  conceptData: {},
  page: document.body.dataset.page || 'home'
};

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

  document.getElementById('bertopic-concept')?.addEventListener('change', (event) => {
    appState.selectedConcept = event.target.value;
    renderBerTopic();
  });
  document.getElementById('bertopic-show-outliers')?.addEventListener('change', renderBerTopic);
  document.getElementById('bertopic-projection')?.addEventListener('change', renderBerTopic);
  document.getElementById('bertopic-point-size')?.addEventListener('input', (event) => {
    appState.pointSize = Number(event.target.value);
    renderBerTopic();
  });
  document.getElementById('keyword-dimension-a')?.addEventListener('change', renderKeywordExplorer);
  document.getElementById('keyword-dimension-b')?.addEventListener('change', renderKeywordExplorer);
  document.getElementById('keyword-filter-dimension')?.addEventListener('change', () => {
    populateKeywordFilterValues();
    renderKeywordExplorer();
  });
  document.getElementById('keyword-filter-value')?.addEventListener('change', renderKeywordExplorer);
  document.getElementById('keyword-mode')?.addEventListener('change', renderKeywordExplorer);
  document.getElementById('keyword-concept-filter')?.addEventListener('change', renderKeywordExplorer);
}

function applyTheme(theme) {
  document.body.classList.toggle('light', theme === 'light');
  const toggle = document.getElementById('theme-toggle');
  if (toggle) toggle.textContent = theme === 'dark' ? '☀️ Hellmodus' : '🌙 Dunkelmodus';
}

async function loadData() {
  try {
    const [manifest, documentCatalog, keywordRows, keywordWordCounts, matrixRows] = await Promise.all([
      fetchJson('./data/manifest.json'),
      fetchJson('./data/document_catalog.json'),
      fetchCsv('./data/results.csv'),
      fetchCsv('./data/doc_word_counts.csv'),
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
  const selector = document.getElementById('bertopic-concept');
  if (selector) {
    selector.innerHTML = appState.conceptOrder.map((concept) => `<option value="${concept}">${concept}</option>`).join('');
    selector.value = appState.selectedConcept;
  }

  const ldaSelector = document.getElementById('lda-concept');
  if (ldaSelector) {
    ldaSelector.innerHTML = appState.conceptOrder.map((concept) => `<option value="${concept}">${concept}</option>`).join('');
    ldaSelector.value = appState.selectedConcept;
  }

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

function renderBerTopicPage() {
  const concept = appState.selectedConcept || appState.conceptOrder[0];
  const showOutliers = document.getElementById('bertopic-show-outliers')?.checked ?? true;
  const pointSize = Number(document.getElementById('bertopic-point-size')?.value || 1.6);
  const projection = document.getElementById('bertopic-projection')?.value || 'local';
  const orbitEnabled = document.getElementById('bertopic-orbit')?.checked || false;

  const conceptMetrics = appState.manifest.concepts[concept] || {};
  const topics = Object.entries(conceptMetrics.topics || {}).map(([topic, count]) => ({ topic, count })).sort((a, b) => b.count - a.count);
  const scatter = createScatterPlot({ concept, projection, pointSize, orbitEnabled, topics });
  document.getElementById('bertopic-viz').innerHTML = scatter;
  document.getElementById('bertopic-chart').innerHTML = `
    <div class="chart-list">
      ${topics.slice(0, 8).map((item) => `
        <div class="bar-row">
          <span>${item.topic}</span>
          <strong>${item.count}</strong>
          <div class="bar-track"><div class="bar-fill" style="width:${(item.count / Math.max(topics[0]?.count || 1, 1)) * 100}%"></div></div>
        </div>
      `).join('')}
    </div>
  `;
  document.getElementById('bertopic-detail').innerHTML = `
    <h4>${concept}</h4>
    <p><strong>Dokumente:</strong> ${conceptMetrics.n_docs || 0}</p>
    <p><strong>Ausreißer:</strong> ${conceptMetrics.n_outliers || 0}</p>
    <p>Die Topic-Cluster zeigen, wie die relevanten Lehrplanpassagen in thematischen Blöcken organisiert sind. Ausreißer werden separat hervorgehoben, um die Randbereiche des Feldes sichtbar zu machen.</p>
  `;
}

function renderLdaPage() {
  const concept = document.getElementById('lda-concept')?.value || appState.selectedConcept;
  const csvUrl = `./data/lda/${encodeURIComponent(concept)}/10/topic_terms_${encodeURIComponent(concept)}_10.csv`;
  fetchText(csvUrl).then((text) => {
    const rows = parseCsv(text);
    const termRows = rows.slice(1).filter((row) => row.some((entry) => entry.trim().length));
    const frequency = new Map();
    termRows.flat().forEach((term) => {
      const value = normalizeTerm(term);
      if (!value) return;
      frequency.set(value, (frequency.get(value) || 0) + 1);
    });
    const topTerms = [...frequency.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
    document.getElementById('lda-chart').innerHTML = `
      <div class="chart-list">
        ${topTerms.map(([term, count]) => `
          <div class="bar-row">
            <span>${term}</span>
            <strong>${count}</strong>
            <div class="bar-track"><div class="bar-fill" style="width:${(count / Math.max(topTerms[0]?.[1] || 1, 1)) * 100}%"></div></div>
          </div>
        `).join('')}
      </div>
    `;
    const tableRows = (rows[0] || []).map((topicLabel, index) => ({ Thema: topicLabel, Terme: termRows.slice(0, 5).map((row) => row[index] || '').filter(Boolean).join(' · ') }));
    document.getElementById('lda-table').innerHTML = renderTable(tableRows, ['Thema', 'Terme']);
    document.getElementById('lda-cooccurrence').innerHTML = renderMatrix(buildCoOccurrenceMatrixFromManifest());
  }).catch((error) => {
    console.error(error);
    document.getElementById('lda-chart').innerHTML = '<p>Die LDA-Datei konnte nicht geladen werden.</p>';
  });
}

function buildCoOccurrenceMatrixFromManifest() {
  const concepts = appState.conceptOrder;
  const matrix = [['Konzept', ...concepts]];
  concepts.forEach((concept) => {
    const row = [concept];
    concepts.forEach((other) => {
      const left = new Set(Object.keys(appState.manifest.concepts[concept]?.topics || {}));
      const right = new Set(Object.keys(appState.manifest.concepts[other]?.topics || {}));
      row.push([...left].filter((value) => right.has(value)).length);
    });
    matrix.push(row);
  });
  return matrix;
}

function createScatterPlot({ concept, projection, pointSize, orbitEnabled, topics }) {
  const width = 620; const height = 340; const centerX = width / 2; const centerY = height / 2;
  const points = (topics || []).slice(0, 9).map((topic, index) => {
    const radius = 10 + Math.min(22, topic.count / 8 * pointSize);
    const angle = (index / Math.max(topics.length, 1)) * 2 * Math.PI;
    const orbitRadius = 90 + (index % 3) * 24;
    const x = centerX + Math.cos(angle) * orbitRadius;
    const y = centerY + Math.sin(angle) * orbitRadius * 0.7;
    return `<circle cx="${x}" cy="${y}" r="${radius}" fill="hsl(${index * 40} 70% 65%)" stroke="rgba(255,255,255,0.35)" />`;
  }).join('');
  return `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="100%" role="img" aria-label="BERTopic-Visualisierung für ${concept}">
      <rect x="0" y="0" width="${width}" height="${height}" rx="24" fill="rgba(255,255,255,0.03)"></rect>
      <circle cx="${centerX}" cy="${centerY}" r="86" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="2"></circle>
      <g>${points}</g>
      <text x="24" y="28" fill="var(--text)">${projection === 'local' ? `Topic-Atlas für ${concept}` : 'Globaler Themenrahmen'}</text>
      <text x="24" y="310" fill="var(--muted)">Die Größe der Punkte signalisiert die relative Topic-Frequenz; Ausreißer sind optional sichtbar.</text>
    </svg>
  `;
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

function normalizeTerm(value) {
  return String(value || '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
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
