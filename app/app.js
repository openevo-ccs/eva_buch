// Data-driven UI controller for the Lehrplananalyse prototype.
// The app loads repository data from the keyword search, BERTopic, and LDA output folders
// and renders a polished GitHub Pages experience with tables, heatmaps, and SVG visuals.
const appState = {
  theme: 'dark',
  conceptOrder: [],
  manifest: null,
  documentCatalog: null,
  keywordRows: [],
  keywordWordCounts: [],
  matrixRows: [],
  selectedConcept: 'Anpassung',
  conceptData: {},
  ldaCache: {}
};

const dimensionOptions = [
  { value: 'concept', label: 'Konzept' },
  { value: 'subject', label: 'Fach' },
  { value: 'state', label: 'Bundesland' }
];

function initialize() {
  bindEvents();
  applyTheme(appState.theme);
  loadAppData();
}

async function loadAppData() {
  try {
    const [manifest, documentCatalog] = await Promise.all([
      fetchJson('../bertopic/src/data/manifest.json'),
      fetchJson('data/document_catalog.json')
    ]);

    const keywordRows = await loadCsv('../keyword_search/out/results.csv');
    const keywordWordCounts = await loadCsv('../keyword_search/out/doc_word_counts.csv');
    const matrixRows = await loadCsv('../keyword_search/out/state_subject_count_matrix.csv');

    appState.manifest = manifest;
    appState.documentCatalog = documentCatalog;
    appState.keywordRows = keywordRows;
    appState.keywordWordCounts = keywordWordCounts;
    appState.matrixRows = matrixRows;
    appState.conceptOrder = manifest.concept_order || [];

    populateConceptSelectors();
    renderHero();
    renderDocumentOverview();
    renderKeywordExplorer();
    renderBerTopic();
    renderLda();
  } catch (error) {
    console.error(error);
    document.querySelector('main').innerHTML = '<section class="card"><h3>Daten konnten nicht geladen werden.</h3><p>Bitte prüfen Sie, ob die App über einen lokalen Server oder GitHub Pages bereitgestellt wird.</p></section>';
  }
}

function bindEvents() {
  document.getElementById('theme-toggle').addEventListener('click', () => {
    appState.theme = appState.theme === 'dark' ? 'light' : 'dark';
    applyTheme(appState.theme);
  });

  document.getElementById('download-document-table').addEventListener('click', () => {
    downloadCsvFromArray(appState.documentCatalog.documents, 'lehrplandokumente.csv');
  });

  document.getElementById('download-keyword-table').addEventListener('click', () => {
    const currentRows = getKeywordTableData();
    downloadCsvFromArray(currentRows, 'schlagwortsuche.csv');
  });

  document.getElementById('bertopic-concept').addEventListener('change', (event) => {
    appState.selectedConcept = event.target.value;
    renderBerTopic();
    renderLda();
  });

  document.getElementById('bertopic-show-outliers').addEventListener('change', renderBerTopic);
  document.getElementById('bertopic-projection').addEventListener('change', renderBerTopic);
  document.getElementById('bertopic-point-size').addEventListener('input', (event) => {
    appState.pointSize = Number(event.target.value);
    renderBerTopic();
  });
  document.getElementById('bertopic-orbit').addEventListener('change', renderBerTopic);
  document.getElementById('bertopic-orbit-speed').addEventListener('input', (event) => {
    appState.orbitSpeed = Number(event.target.value);
    renderBerTopic();
  });

  document.getElementById('lda-concept').addEventListener('change', (event) => {
    appState.selectedConcept = event.target.value;
    renderBerTopic();
    renderLda();
  });

  ['keyword-concept-filter', 'keyword-dimension-a', 'keyword-dimension-b', 'keyword-filter-dimension', 'keyword-filter-value', 'keyword-mode']
    .forEach((id) => document.getElementById(id).addEventListener('change', renderKeywordExplorer));
}

function applyTheme(theme) {
  document.body.classList.toggle('light', theme === 'light');
  const toggle = document.getElementById('theme-toggle');
  toggle.textContent = theme === 'dark' ? '🌙 Dunkelmodus' : '☀️ Hellmodus';
}

function populateConceptSelectors() {
  const concepts = appState.conceptOrder;
  const selects = [document.getElementById('bertopic-concept'), document.getElementById('lda-concept')];
  selects.forEach((select) => {
    select.innerHTML = concepts.map((concept) => `<option value="${concept}">${concept}</option>`).join('');
    select.value = appState.selectedConcept;
  });

  const conceptFilter = document.getElementById('keyword-concept-filter');
  conceptFilter.innerHTML = ['Alle', ...concepts].map((concept) => `<option value="${concept}">${concept === 'Alle' ? 'Alle Konzepte' : concept}</option>`).join('');

  const dimensionA = document.getElementById('keyword-dimension-a');
  const dimensionB = document.getElementById('keyword-dimension-b');
  const filterDimension = document.getElementById('keyword-filter-dimension');
  dimensionA.innerHTML = dimensionOptions.map((option) => `<option value="${option.value}">${option.label}</option>`).join('');
  dimensionB.innerHTML = dimensionOptions.map((option) => `<option value="${option.value}">${option.label}</option>`).join('');
  filterDimension.innerHTML = dimensionOptions.map((option) => `<option value="${option.value}">${option.label}</option>`).join('');

  dimensionA.value = 'concept';
  dimensionB.value = 'subject';
  filterDimension.value = 'state';
  updateKeywordFilterValues();
}

function updateKeywordFilterValues() {
  const filterDimension = document.getElementById('keyword-filter-dimension').value;
  const values = getDistinctValues(filterDimension);
  const select = document.getElementById('keyword-filter-value');
  select.innerHTML = ['Alle', ...values].map((value) => `<option value="${value}">${value === 'Alle' ? 'Alle' : value}</option>`).join('');
}

function getDistinctValues(dimension) {
  const rows = appState.keywordRows;
  const values = rows.map((row) => row[dimensionToKey(dimension)]).filter(Boolean);
  return [...new Set(values)].sort();
}

function dimensionToKey(dimension) {
  const map = {
    concept: 'search_term',
    subject: 'subject',
    state: 'state'
  };
  return map[dimension] || 'search_term';
}

function renderHero() {
  const concepts = appState.conceptOrder;
  const totalDocs = concepts.reduce((sum, concept) => sum + (appState.manifest.concepts[concept]?.n_docs || 0), 0);
  const outliers = concepts.reduce((sum, concept) => sum + (appState.manifest.concepts[concept]?.n_outliers || 0), 0);
  const subjects = new Set();
  concepts.forEach((concept) => {
    Object.keys(appState.manifest.concepts[concept]?.subjects || {}).forEach((value) => subjects.add(value));
  });

  const stats = [
    { label: 'Konzept-Cluster', value: `${concepts.length}` },
    { label: 'Dokumente im Fokus', value: totalDocs.toLocaleString('de-DE') },
    { label: 'Ausreißer', value: outliers.toLocaleString('de-DE') },
    { label: 'Fächer abgedeckt', value: subjects.size }
  ];

  document.getElementById('metric-cards').innerHTML = stats.map((stat) => `
    <article class="metric-card">
      <strong>${stat.value}</strong>
      <span>${stat.label}</span>
    </article>
  `).join('');
}

function renderDocumentOverview() {
  const documents = [...(appState.documentCatalog?.documents || [])].sort((a, b) => (b.year || 0) - (a.year || 0));
  const tableRows = documents.map((doc) => ({
    Titel: doc.title,
    Fach: doc.subject,
    Bundesland: doc.state,
    Jahr: doc.year || '—',
    Pfad: doc.path
  }));

  document.getElementById('document-table').innerHTML = renderTable(tableRows, ['Titel', 'Fach', 'Bundesland', 'Jahr', 'Pfad']);

  const stateNames = [...new Set(documents.map((doc) => doc.state).filter(Boolean))].sort();
  const subjects = [...new Set(documents.map((doc) => doc.subject).filter(Boolean))].sort();
  const matrix = [['Bundesland', ...subjects, 'Gesamt'], ...stateNames.map((state) => {
    const rowValues = subjects.map((subject) => documents.filter((doc) => doc.state === state && doc.subject === subject).length);
    const total = rowValues.reduce((sum, value) => sum + value, 0);
    return [state, ...rowValues, total];
  }), ['Gesamt', ...subjects.map((subject) => documents.filter((doc) => doc.subject === subject).length), documents.length]]];

  document.getElementById('document-matrix').innerHTML = renderMatrix(matrix);
}

function renderKeywordExplorer() {
  updateKeywordFilterValues();
  const conceptFilter = document.getElementById('keyword-concept-filter').value;
  const dimensionA = document.getElementById('keyword-dimension-a').value;
  const dimensionB = document.getElementById('keyword-dimension-b').value;
  const filterDimension = document.getElementById('keyword-filter-dimension').value;
  const filterValue = document.getElementById('keyword-filter-value').value;
  const mode = document.getElementById('keyword-mode').value;

  let filteredRows = appState.keywordRows;
  if (conceptFilter !== 'Alle') {
    filteredRows = filteredRows.filter((row) => row.search_term === conceptFilter);
  }
  if (filterValue !== 'Alle') {
    filteredRows = filteredRows.filter((row) => row[dimensionToKey(filterDimension)] === filterValue);
  }

  const rowValues = [...new Set(filteredRows.map((row) => row[dimensionToKey(dimensionA)]).filter(Boolean))].sort();
  const columnValues = [...new Set(filteredRows.map((row) => row[dimensionToKey(dimensionB)]).filter(Boolean))].sort();
  const wordCountMap = new Map(appState.keywordWordCounts.map((row) => [row.file, Number(row.word_count || 0)]));

  const tableRows = rowValues.map((rowValue) => {
    const entry = { [dimensionLabel(dimensionA)]: rowValue };
    columnValues.forEach((columnValue) => {
      const matches = filteredRows.filter((row) => row[dimensionToKey(dimensionA)] === rowValue && row[dimensionToKey(dimensionB)] === columnValue);
      const count = matches.length;
      const wordCount = matches.reduce((sum, row) => sum + (wordCountMap.get(row.file) || 1), 0);
      const value = mode === 'relative' ? (count / Math.max(wordCount, 1)) * 10000 : count;
      entry[columnValue] = Number(value.toFixed(2));
    });
    return entry;
  });

  document.getElementById('keyword-table').innerHTML = renderTable(tableRows, [dimensionLabel(dimensionA), ...columnValues], { numeric: true });

  const summaryCards = [
    { title: 'Treffer gesamt', value: filteredRows.length.toLocaleString('de-DE') },
    { title: 'Konzept-Filter', value: conceptFilter === 'Alle' ? 'Alle' : conceptFilter },
    { title: 'Relative Reichweite', value: `${(filteredRows.length / Math.max(appState.keywordWordCounts.length, 1)).toFixed(2)} je Dokument` }
  ];
  document.getElementById('keyword-summary').innerHTML = summaryCards.map((card) => `
    <article class="summary-card">
      <strong>${card.title}</strong>
      <span>${card.value}</span>
    </article>
  `).join('');

  const heatmapRows = [
    [dimensionLabel(dimensionA), ...columnValues],
    ...tableRows.map((row) => [row[dimensionLabel(dimensionA)], ...columnValues.map((columnValue) => row[columnValue])])
  ];
  document.getElementById('keyword-matrix').innerHTML = renderHeatmap(heatmapRows, mode === 'relative' ? 'Je 10.000 Wörter' : 'Absolute Treffer');
}

function getKeywordTableData() {
  const dimensionA = document.getElementById('keyword-dimension-a').value;
  const dimensionB = document.getElementById('keyword-dimension-b').value;
  const conceptFilter = document.getElementById('keyword-concept-filter').value;
  const filterDimension = document.getElementById('keyword-filter-dimension').value;
  const filterValue = document.getElementById('keyword-filter-value').value;
  const mode = document.getElementById('keyword-mode').value;

  let rows = appState.keywordRows;
  if (conceptFilter !== 'Alle') {
    rows = rows.filter((row) => row.search_term === conceptFilter);
  }
  if (filterValue !== 'Alle') {
    rows = rows.filter((row) => row[dimensionToKey(filterDimension)] === filterValue);
  }

  const rowValues = [...new Set(rows.map((row) => row[dimensionToKey(dimensionA)]).filter(Boolean))].sort();
  const columnValues = [...new Set(rows.map((row) => row[dimensionToKey(dimensionB)]).filter(Boolean))].sort();

  return rowValues.map((rowValue) => {
    const entry = { [dimensionLabel(dimensionA)]: rowValue };
    columnValues.forEach((columnValue) => {
      const count = rows.filter((row) => row[dimensionToKey(dimensionA)] === rowValue && row[dimensionToKey(dimensionB)] === columnValue).length;
      entry[columnValue] = count;
    });
    return entry;
  });
}

async function renderBerTopic() {
  const concept = appState.selectedConcept;
  const conceptData = appState.conceptData[concept] || (await loadJson(`../bertopic/src/data/${concept}.json`));
  appState.conceptData[concept] = conceptData;

  const manifestConcept = appState.manifest.concepts[concept];
  const showOutliers = document.getElementById('bertopic-show-outliers').checked;
  const projection = document.getElementById('bertopic-projection').value;
  const pointSize = Number(document.getElementById('bertopic-point-size').value);
  const orbitEnabled = document.getElementById('bertopic-orbit').checked;
  const orbitSpeed = Number(document.getElementById('bertopic-orbit-speed').value);

  const filteredData = conceptData.filter((item) => showOutliers || !item.is_outlier);
  const topicStats = Object.entries(groupBy(filteredData, 'topic')).map(([topic, items]) => ({ topic, count: items.length, excerpt: items[0]?.excerpt || '—' }));
  topicStats.sort((a, b) => b.count - a.count);

  const svg = createScatterPlot({
    concept,
    projection,
    pointSize,
    orbitEnabled,
    orbitSpeed,
    data: projection === 'local' ? topicStats : Object.entries(appState.manifest.concepts).map(([name, details]) => ({
      label: name,
      count: details.n_docs,
      x: averagePair(details.bbox_2d[0], details.bbox_2d[1])[0],
      y: averagePair(details.bbox_2d[0], details.bbox_2d[1])[1]
    }))
  });

  document.getElementById('bertopic-scatter').innerHTML = svg;

  document.getElementById('bertopic-topic-chart').innerHTML = `
    <h4>Top-Topics</h4>
    <div class="chart-list">
      ${topicStats.slice(0, 8).map((topic) => `
        <div class="bar-row">
          <span>${topic.topic}</span>
          <strong>${topic.count}</strong>
          <div class="bar-track" style="grid-column: 1 / -1;">
            <div class="bar-fill" style="width: ${(topic.count / Math.max(topicStats[0]?.count || 1, 1)) * 100}%;"></div>
          </div>
        </div>
      `).join('')}
    </div>
  `;

  const firstTopic = topicStats[0];
  document.getElementById('bertopic-detail').innerHTML = `
    <h4>${concept}</h4>
    <p><strong>Dokumente:</strong> ${manifestConcept?.n_docs || 0}</p>
    <p><strong>Ausreißer:</strong> ${manifestConcept?.n_outliers || 0}</p>
    <p><strong>Stärkstes Topic:</strong> ${firstTopic?.topic || '—'}</p>
    <p>${firstTopic?.excerpt ? `Beispielauszug: “${truncate(firstTopic.excerpt, 220)}”` : 'Die Topic-Details sind noch nicht vollständig verfügbar.'}</p>
  `;
}

function createScatterPlot({ concept, projection, pointSize, orbitEnabled, orbitSpeed, data }) {
  const width = 580;
  const height = 320;
  const viewBox = `0 0 ${width} ${height}`;
  const xValues = data.map((point) => point.x);
  const yValues = data.map((point) => point.y);
  const minX = Math.min(...xValues);
  const maxX = Math.max(...xValues);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);
  const scaleX = (value) => ((value - minX) / Math.max(maxX - minX, 1)) * 500 + 40;
  const scaleY = (value) => height - (((value - minY) / Math.max(maxY - minY, 1)) * 240 + 40);

  const points = data.map((point, index) => {
    const radius = Math.max(6, Math.min(24, point.count / 12 * pointSize + 6));
    const fill = `hsl(${(index * 45) % 360} 65% 60%)`;
    return `<circle cx="${scaleX(point.x)}" cy="${scaleY(point.y)}" r="${radius}" fill="${fill}" stroke="rgba(255,255,255,0.35)" />`;
  }).join('');

  const title = projection === 'local' ? `Topic-Atlas für ${concept}` : 'Globaler Themenrahmen';
  const orbitClass = orbitEnabled ? 'orbit-enabled' : '';
  return `
    <style>
      .scatter-svg { width: 100%; height: 100%; }
      ${orbitEnabled ? '.scatter-svg .orbit-layer { animation: drift 4s linear infinite; }' : ''}
      @keyframes drift { from { transform: rotate(0deg); } to { transform: rotate(360deg); }}
    </style>
    <svg class="scatter-svg ${orbitClass}" viewBox="${viewBox}" role="img" aria-label="${title}">
      <rect width="100%" height="100%" rx="18" fill="rgba(255,255,255,0.03)"></rect>
      <g class="orbit-layer">
        ${points}
      </g>
      <text x="40" y="28" fill="var(--text)">${title}</text>
      <text x="40" y="300" fill="var(--muted)">Punkte repräsentieren Topics oder Konzepte; größere Kreise zeigen mehr Dokumente.</text>
    </svg>
  `;
}

async function renderLda() {
  const concept = appState.selectedConcept;
  const csvText = await fetchText(`../lda_topic_modelling/out/${concept}/10/topic_terms_${concept}_10.csv`);
  const rows = parseCsv(csvText);
  const dataRows = rows.slice(1).filter((row) => row.some((entry) => entry.trim().length));
  const terms = dataRows.flat();
  const frequency = new Map();
  terms.forEach((term) => {
    const cleaned = normalizeTerm(term);
    if (!cleaned) return;
    frequency.set(cleaned, (frequency.get(cleaned) || 0) + 1);
  });

  const topTerms = [...frequency.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
  document.getElementById('lda-term-chart').innerHTML = `
    <h4>Top-Terme über alle Topics</h4>
    <div class="chart-list">
      ${topTerms.map(([term, count]) => `
        <div class="bar-row">
          <span>${term}</span>
          <strong>${count}</strong>
          <div class="bar-track" style="grid-column: 1 / -1;">
            <div class="bar-fill" style="width: ${(count / Math.max(topTerms[0][1], 1)) * 100}%;"></div>
          </div>
        </div>
      `).join('')}
    </div>
  `;

  const topics = rows[0] ? rows[0].map((_, index) => `Topic ${index + 1}`) : [];
  const tableRows = topics.map((topic, index) => ({
    Thema: topic,
    Terme: dataRows.slice(0, 6).map((row) => row[index] || '').filter(Boolean).join(' · ')
  }));
  document.getElementById('lda-term-table').innerHTML = renderTable(tableRows, ['Thema', 'Terme']);

  const coocMatrix = await buildCoOccurrenceMatrix();
  document.getElementById('lda-cooccurrence').innerHTML = renderMatrix(coocMatrix);
}

async function buildCoOccurrenceMatrix() {
  const concepts = appState.conceptOrder;
  const termSets = {};
  for (const concept of concepts) {
    try {
      const csvText = await fetchText(`../lda_topic_modelling/out/${concept}/10/topic_terms_${concept}_10.csv`);
      const rows = parseCsv(csvText);
      const terms = rows.flat().map(normalizeTerm).filter(Boolean);
      const frequency = new Map();
      terms.forEach((term) => frequency.set(term, (frequency.get(term) || 0) + 1));
      const topTerms = [...frequency.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([term]) => term);
      termSets[concept] = new Set(topTerms);
    } catch (error) {
      termSets[concept] = new Set();
    }
  }

  const matrix = [['Konzept', ...concepts]];
  concepts.forEach((concept) => {
    const row = [concept];
    concepts.forEach((other) => {
      const overlap = [...termSets[concept]].filter((term) => termSets[other].has(term));
      row.push(overlap.length);
    });
    matrix.push(row);
  });
  return matrix;
}

function renderTable(rows, headers, options = {}) {
  if (!rows.length) {
    return '<p>Keine Daten verfügbar.</p>';
  }
  const body = rows.map((row) => `
    <tr>${headers.map((header) => `<td>${escapeHtml(row[header] ?? '—')}</td>`).join('')}</tr>
  `).join('');
  return `
    <table>
      <thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join('')}</tr></thead>
      <tbody>${body}</tbody>
    </table>
  `;
}

function renderMatrix(matrix) {
  const [headerRow, ...rows] = matrix;
  return `
    <table>
      <thead>
        <tr>${headerRow.map((value) => `<th>${escapeHtml(value)}</th>`).join('')}</tr>
      </thead>
      <tbody>
        ${rows.map((row) => `
          <tr>${row.map((value, index) => {
            const isHeader = index === 0;
            const cellValue = value;
            const className = isHeader ? '' : 'heat-cell';
            const style = isHeader ? '' : `style="background: rgba(8,94,101,${0.14 + Number(cellValue || 0) / 18 * 0.7});"`;
            return `<td class="${className}" ${style}>${escapeHtml(cellValue)}</td>`;
          }).join('')}</tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function renderHeatmap(rows, title) {
  return `
    <h4>${title}</h4>
    <table>
      <tbody>
        ${rows.map((row) => `
          <tr>${row.map((value, index) => {
            const isFirst = index === 0;
            const numeric = Number(value);
            const isNumber = !Number.isNaN(numeric);
            if (!isNumber) {
              return `<th>${escapeHtml(value)}</th>`;
            }
            const intensity = Math.max(0.12, Math.min(0.9, numeric / 20));
            return `<td class="heat-cell" style="background: rgba(8,94,101,${intensity});">${escapeHtml(value)}</td>`;
          }).join('')}</tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function groupBy(items, key) {
  return items.reduce((result, item) => {
    const value = item[key] || 'Unbekannt';
    if (!result[value]) {
      result[value] = [];
    }
    result[value].push(item);
    return result;
  }, {});
}

function averagePair(first, second) {
  return [((first[0] || 0) + (second[0] || 0)) / 2, ((first[1] || 0) + (second[1] || 0)) / 2];
}

function normalizeTerm(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim();
}

function truncate(value, length) {
  return value.length > length ? `${value.slice(0, length)}…` : value;
}

function dimensionLabel(value) {
  return dimensionOptions.find((option) => option.value === value)?.label || value;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function downloadCsvFromArray(rows, fileName) {
  if (!rows.length) {
    return;
  }
  const headers = Object.keys(rows[0]);
  const csv = [headers.join(','), ...rows.map((row) => headers.map((header) => `"${String(row[header] ?? '').replace(/"/g, '""')}"`).join(','))].join('\n');
  const file = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(file);
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to load ${url}`);
  return response.json();
}

async function fetchText(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to load ${url}`);
  return response.text();
}

async function loadCsv(url) {
  const text = await fetchText(url);
  const rows = parseCsv(text);
  if (!rows.length) {
    return [];
  }
  const headers = rows[0];
  return rows.slice(1).map((values) => {
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] ?? '';
    });
    return row;
  });
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
      if (char === '\r' && next === '\n') {
        index += 1;
      }
      row.push(value);
      if (row.some((entry) => entry.length > 0)) {
        rows.push(row);
      }
      row = [];
      value = '';
    } else {
      value += char;
    }
  }
  if (value.length > 0 || row.length) {
    row.push(value);
    rows.push(row);
  }
  return rows;
}

document.addEventListener('DOMContentLoaded', initialize);
