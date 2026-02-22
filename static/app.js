/*
  dotty v2 — frontend
  by jLaHire
*/

const DEFAULT_EXT_COLORS = {
  '.py':'#3776ab','.js':'#f7df1e','.html':'#e34c26','.css':'#264de4',
  '.json':'#00ff00','.sh':'#89e051','.c':'#555555','.cpp':'#f34b7d',
  '.java':'#b07219','.cs':'#178600','.go':'#00add8','.rs':'#dea584',
  '.php':'#4f5d95','.rb':'#701516','.swift':'#ffac45',
  '.md':'#083fa1','.txt':'#cccccc','.docx':'#2b579a','.doc':'#2b579a',
  '.pdf':'#ff0000','.rtf':'#8b7355','.odt':'#0080ff',
  '.jpg':'#ff69b4','.jpeg':'#ff69b4','.png':'#ff1493','.gif':'#ff00ff',
  '.bmp':'#ffc0cb','.svg':'#ffb13b','.ico':'#00ffff','.webp':'#ff6eb4',
  '.zip':'#ffaa00','.tar':'#ffaa00','.gz':'#ffaa00','.rar':'#ff8800','.7z':'#ff6600',
  '.exe':'#ff0000','.dll':'#ff6666','.so':'#ff6666','.app':'#ff3333',
  '.csv':'#00ff00','.xml':'#ff6600','.yaml':'#cb171e','.yml':'#cb171e',
  '.ini':'#d4d4d4','.cfg':'#d4d4d4','.conf':'#d4d4d4',
};

const WEB_COLORS = {
  'web_page':'#e91e63','web_script':'#f7df1e','web_style':'#264de4',
  'web_image':'#ff69b4','web_link':'#4fc3f7','web_form':'#ff5252',
  'web_iframe':'#ff9800','web_meta':'#888888','web_headers':'#66bb6a',
  'web_cookie':'#ff9800','web_input':'#ce93d8','web_finding':'#ff5252',
  'web_request':'#4fc3f7','web_redirect':'#ff9800','web_console':'#ce93d8',
};

const SEVERITY_COLORS = {
  'critical':'#ff5252','warning':'#ff9800','info':'#4fc3f7','pass':'#66bb6a',
};

const DEFAULT_COLOR = '#ce93d8';
const FOLDER_COLOR = '#4fc3f7';
const HIDDEN_COLOR = '#ff4500';
const DELETED_COLOR = '#ff5252';
const SYSTEM_COLOR = '#444444';
const CONTEXT_LINK_COLOR = '#ffab40';
const FAVORITE_COLOR = '#ffd700';

let customColors = JSON.parse(localStorage.getItem('dotty_colors') || '{}');

function saveCustomColors() { localStorage.setItem('dotty_colors', JSON.stringify(customColors)); }

function getExtColor(ext) {
  if (customColors[ext]) return customColors[ext];
  return DEFAULT_EXT_COLORS[ext] || DEFAULT_COLOR;
}

function nodeColor(n) {
  const d = n.data();
  if (d.is_deleted) return DELETED_COLOR;
  if (d.is_hidden) return HIDDEN_COLOR;
  if (d.is_system) return SYSTEM_COLOR;
  if (d.kind === 'folder') return FOLDER_COLOR;
  if (d.kind === 'web_finding' && d.severity && SEVERITY_COLORS[d.severity]) return SEVERITY_COLORS[d.severity];
  if (WEB_COLORS[d.kind]) return WEB_COLORS[d.kind];
  return getExtColor(d.extension);
}

let cy = null;
let ws = null;
let focusNodeId = null;
let chatStreamEl = null;
let sessionActive = false;
let sessionEvents = [];


// ── graph ──

function initGraph() {
  cy = cytoscape({
    container: document.getElementById('graph-container'),
    style: [
      {
        selector: 'node',
        style: {
          'label': 'data(name)',
          'background-color': n => nodeColor(n),
          'color': '#d4d4d4',
          'font-size': '10px',
          'text-valign': 'bottom',
          'text-margin-y': 6,
          'width': n => n.data('kind') === 'folder' ? 20 : 14,
          'height': n => n.data('kind') === 'folder' ? 20 : 14,
          'shape': n => n.data('kind') === 'folder' ? 'round-rectangle' : 'ellipse',
          'border-width': 0,
          'text-max-width': '80px',
          'text-wrap': 'ellipsis',
          'min-zoomed-font-size': 8,
        }
      },
      { selector: 'node:selected', style: { 'border-width': 3, 'border-color': '#ffff00' } },
      {
        selector: 'node[_hop = 0]',
        style: { 'border-width': 3, 'border-color': '#00ffff', 'width': 30, 'height': 30, 'font-size': '12px', 'font-weight': 'bold' }
      },
      {
        selector: 'node[?favorite]',
        style: { 'border-width': 2, 'border-color': FAVORITE_COLOR, 'border-style': 'double' }
      },
      {
        selector: '.tagged',
        style: { 'shape': 'diamond' }
      },
      { selector: 'edge', style: { 'width': 1, 'line-color': '#444', 'curve-style': 'bezier', 'opacity': 0.4 } },
      { selector: 'edge[link_type = "parent_folder"]', style: { 'line-color': '#4fc3f7', 'opacity': 0.6, 'width': 1.5 } },
      { selector: 'edge[link_type = "same_ext"]', style: { 'line-color': '#ce93d8', 'opacity': 0.3 } },
      {
        selector: 'edge[link_type = "context"]',
        style: { 'line-color': CONTEXT_LINK_COLOR, 'opacity': 0.9, 'width': 2.5, 'line-style': 'dashed', 'target-arrow-shape': 'diamond', 'target-arrow-color': CONTEXT_LINK_COLOR }
      },
      {
        selector: 'edge[link_type = "security"]',
        style: { 'line-color': '#ff5252', 'opacity': 0.3, 'width': 1, 'line-style': 'dotted' }
      },
      {
        selector: 'edge[link_type = "web_third_party"]',
        style: { 'line-color': '#555', 'opacity': 0.2, 'width': 0.5, 'line-style': 'dotted' }
      },
      {
        selector: 'edge[link_type = "redirect_chain"]',
        style: { 'line-color': '#ff9800', 'opacity': 0.6, 'width': 1.5, 'target-arrow-shape': 'triangle', 'target-arrow-color': '#ff9800', 'arrow-scale': 0.6 }
      },
      {
        selector: 'node[kind = "web_request"]',
        style: { 'width': 10, 'height': 10, 'font-size': '8px', 'text-max-width': '70px' }
      },
      {
        selector: 'node[kind = "web_redirect"]',
        style: { 'width': 8, 'height': 8, 'shape': 'triangle', 'font-size': '8px', 'text-max-width': '70px' }
      },
      {
        selector: 'node[kind = "web_console"]',
        style: { 'width': 10, 'height': 10, 'shape': 'round-rectangle', 'font-size': '8px' }
      },
    ],
    layout: { name: 'preset' },
    wheelSensitivity: 0.3,
  });

  cy.on('tap', 'node', evt => showNodeInfo(evt.target.data('id')));
  cy.on('dbltap', 'node', async evt => { focusNodeId = evt.target.data('id'); await loadGraph(focusNodeId); });
  cy.on('tap', evt => { if (evt.target === cy) document.getElementById('node-info').innerHTML = '<p class="placeholder">Select a node to view details</p>'; });
  cy.on('cxttap', 'node', evt => {
    const pos = evt.renderedPosition || evt.position;
    showContextMenu(evt.target, pos.x, pos.y);
  });
  document.addEventListener('click', () => hideContextMenu());
}

async function loadGraph(focus) {
  const params = new URLSearchParams();
  if (focus) params.set('focus', focus);
  params.set('hops', '3');
  const resp = await fetch(`/api/graph?${params}`);
  const data = await resp.json();

  cy.elements().remove();
  cy.add(data.elements);

  cy.nodes().forEach(n => {
    if (n.data('tags') && n.data('tags').length) n.addClass('tagged');
  });

  const hasInteractive = cy.nodes().some(n => n.data('kind') === 'web_page' && n.data('name') && n.data('name').startsWith('Interactive:'));
  if (hasInteractive) {
    cy.layout({
      name: 'cose',
      animate: true,
      animationDuration: 800,
      nodeRepulsion: () => 6000,
      idealEdgeLength: () => 80,
      edgeElasticity: () => 100,
      gravity: 0.4,
      numIter: 300,
      padding: 40,
    }).run();
  } else {
    cy.layout({
      name: 'concentric',
      concentric: n => 4 - (n.data('_hop') || 0),
      levelWidth: () => 1, animate: true, animationDuration: 800, minNodeSpacing: 30,
    }).run();
  }

  buildFilterOptions();
  loadStats();
}


// ── right-click context menu ──

function showContextMenu(cyNode, x, y) {
  hideContextMenu();
  const nodeId = cyNode.data('id');
  const kind = cyNode.data('kind');
  const ext = cyNode.data('extension');
  const isFav = cyNode.data('favorite');
  const isFile = kind !== 'folder';

  const menu = document.createElement('div');
  menu.id = 'ctx-menu';
  menu.style.left = x + 'px';
  menu.style.top = y + 'px';

  const isWeb = kind.startsWith('web_');
  const nodePath = cyNode.data('path') || '';

  const items = [
    { label: 'Focus here', action: () => { focusNodeId = nodeId; loadGraph(nodeId); } },
    { label: 'View info', action: () => showNodeInfo(nodeId) },
    { label: isFav ? 'Unfavorite' : 'Favorite', action: () => toggleFavorite(nodeId, cyNode) },
    { label: 'Tag...', action: () => promptTag(nodeId, cyNode) },
  ];

  if (isWeb && nodePath.startsWith('http')) {
    items.push({ label: 'Open in new tab', action: () => window.open(nodePath, '_blank') });
  } else if (isFile) {
    items.push({ label: 'Preview file', action: () => previewFile(nodeId) });
    items.push({ label: 'Download file', action: () => downloadFile(nodeId) });
  }

  if (ext) {
    items.push({ label: `Set color for ${ext}`, action: () => pickColor(ext) });
  }

  for (const item of items) {
    const row = document.createElement('div');
    row.className = 'ctx-item';
    row.textContent = item.label;
    row.addEventListener('click', e => { e.stopPropagation(); hideContextMenu(); item.action(); });
    menu.appendChild(row);
  }

  document.getElementById('graph-container').appendChild(menu);
}

function hideContextMenu() {
  const old = document.getElementById('ctx-menu');
  if (old) old.remove();
}

async function toggleFavorite(nodeId, cyNode) {
  const resp = await fetch(`/api/graph/node/${nodeId}/favorite`, { method: 'POST' });
  const data = await resp.json();
  cyNode.data('favorite', data.favorite);
  loadFavorites();
}

function promptTag(nodeId, cyNode) {
  const tag = prompt('Enter tag name:');
  if (!tag || !tag.trim()) return;
  fetch(`/api/graph/node/${nodeId}/tag`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag: tag.trim() }),
  }).then(r => r.json()).then(data => {
    cyNode.data('tags', data.tags);
    if (data.tags.length) cyNode.addClass('tagged'); else cyNode.removeClass('tagged');
    loadFavorites();
  });
}

function pickColor(ext) {
  const current = getExtColor(ext);
  const input = document.createElement('input');
  input.type = 'color';
  input.value = current;
  input.addEventListener('input', () => {
    customColors[ext] = input.value;
    saveCustomColors();
    cy.style().update();
  });
  input.click();
}


// ── favorites / tags panel ──

async function loadFavorites() {
  const [favResp, tagsResp] = await Promise.all([
    fetch('/api/graph/favorites'), fetch('/api/graph/tags'),
  ]);
  const favs = await favResp.json();
  const tags = await tagsResp.json();

  let html = '';

  if (favs.length) {
    html += '<h4>Favorites</h4>';
    for (const f of favs) {
      const tagStr = f.tags.length ? ` <span class="tag-pills">${f.tags.map(t => `<span class="tag-pill">${t}</span>`).join('')}</span>` : '';
      html += `<div class="fav-item" data-id="${f.id}"><span class="fav-star">&#9733;</span> ${f.name}${tagStr}</div>`;
    }
  }

  if (tags.length) {
    html += '<h4>Tags</h4>';
    for (const t of tags)
      html += `<div class="tag-item" data-tag="${t}"><span class="tag-dot"></span> ${t}</div>`;
  }

  if (!html) html = '<p class="placeholder">Right-click nodes to favorite or tag them</p>';
  document.getElementById('favorites-view').innerHTML = html;
}

function initFavorites() {
  document.getElementById('favorites-view').addEventListener('click', async e => {
    const fav = e.target.closest('.fav-item');
    if (fav) {
      const id = fav.dataset.id;
      const n = cy.getElementById(id);
      if (n.length) {
        cy.animate({ center: { eles: n }, zoom: 2 }, { duration: 500 });
        n.select();
        await showNodeInfo(id);
      } else {
        focusNodeId = id;
        await loadGraph(id);
      }
      return;
    }
    const tag = e.target.closest('.tag-item');
    if (tag) {
      const resp = await fetch(`/api/graph/tagged?tag=${encodeURIComponent(tag.dataset.tag)}`);
      const items = await resp.json();
      if (items.length) {
        focusNodeId = items[0].id;
        await loadGraph(items[0].id);
      }
    }
  });
}


// ── file preview / download ──

async function previewFile(nodeId) {
  const resp = await fetch(`/api/graph/node/${nodeId}/preview`);
  const data = await resp.json();
  if (data.error) { showPreviewModal(data.error, 'text', 'Error'); return; }
  if (data.type === 'text') showPreviewModal(data.content, 'text', data.name);
  else if (data.type === 'image') showPreviewModal(data.url, 'image', data.name);
  else showPreviewModal(`Binary file: ${data.name}\nSize: ${formatSize(data.size)}\nType: ${data.mime}\n\nUse "Download file" to save.`, 'text', data.name);
}

function showPreviewModal(content, type, title) {
  hidePreviewModal();
  const overlay = document.createElement('div');
  overlay.id = 'preview-overlay';
  overlay.addEventListener('click', e => { if (e.target === overlay) hidePreviewModal(); });

  const modal = document.createElement('div');
  modal.id = 'preview-modal';
  const header = document.createElement('div');
  header.id = 'preview-header';
  header.innerHTML = `<span>${title || 'Preview'}</span><button id="preview-close">&times;</button>`;
  modal.appendChild(header);

  const body = document.createElement('div');
  body.id = 'preview-body';
  if (type === 'image') {
    const img = document.createElement('img');
    img.src = content;
    img.style.maxWidth = '100%';
    img.style.maxHeight = '80vh';
    body.appendChild(img);
  } else {
    const pre = document.createElement('pre');
    pre.textContent = content;
    body.appendChild(pre);
  }
  modal.appendChild(body);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
  document.getElementById('preview-close').addEventListener('click', hidePreviewModal);
  document.addEventListener('keydown', function esc(e) {
    if (e.key === 'Escape') { hidePreviewModal(); document.removeEventListener('keydown', esc); }
  });
}

function hidePreviewModal() { const el = document.getElementById('preview-overlay'); if (el) el.remove(); }

function downloadFile(nodeId) {
  const a = document.createElement('a');
  a.href = `/api/graph/node/${nodeId}/download`;
  a.download = '';
  a.click();
}


// ── node info ──

async function showNodeInfo(nodeId) {
  const resp = await fetch(`/api/graph/node/${nodeId}`);
  const node = await resp.json();
  if (node.error) return;

  const info = node.info || {};
  let html = `<div class="info-header">
    <span class="kind-badge">${node.kind}</span>
    <span class="node-name">${node.name}</span>
  </div>
  <div class="info-row"><span class="label">Path</span><span class="value">${node.path}</span></div>`;

  if (info.size !== undefined) html += `<div class="info-row"><span class="label">Size</span><span class="value">${formatSize(info.size)}</span></div>`;
  if (info.extension) html += `<div class="info-row"><span class="label">Ext</span><span class="value">${info.extension}</span></div>`;
  if (info.modified) html += `<div class="info-row"><span class="label">Modified</span><span class="value">${info.modified}</span></div>`;
  if (info.created) html += `<div class="info-row"><span class="label">Created</span><span class="value">${info.created}</span></div>`;
  if (info.owner) html += `<div class="info-row"><span class="label">Owner</span><span class="value">${info.owner}</span></div>`;
  html += `<div class="info-row"><span class="label">Connections</span><span class="value">${node.connections}</span></div>`;
  if (node.is_hidden) html += `<div class="info-row"><span class="label">Hidden</span><span class="value" style="color:#ff4500">Yes</span></div>`;
  if (node.is_deleted) html += `<div class="info-row"><span class="label">Deleted</span><span class="value" style="color:#ff5252">Yes</span></div>`;
  if (node.is_system) html += `<div class="info-row"><span class="label">System</span><span class="value" style="color:#888">Yes</span></div>`;

  const skip = new Set(['size','extension','modified','accessed','created','owner','relative']);
  for (const [k, v] of Object.entries(info)) {
    if (!skip.has(k) && v !== null && v !== undefined && v !== '')
      html += `<div class="info-row"><span class="label">${k}</span><span class="value">${typeof v === 'object' ? JSON.stringify(v) : v}</span></div>`;
  }

  document.getElementById('node-info').innerHTML = html;
}

async function loadStats() {
  const resp = await fetch('/api/graph/stats');
  const s = await resp.json();
  let html = '<h4>Stats</h4>';
  html += `<div class="info-row"><span class="label">Nodes</span><span class="value">${s.total_nodes}</span></div>`;
  html += `<div class="info-row"><span class="label">Links</span><span class="value">${s.total_links}</span></div>`;
  for (const [k, v] of Object.entries(s.kinds || {}))
    html += `<div class="info-row"><span class="label">${k}</span><span class="value">${v}</span></div>`;
  if (s.link_types)
    for (const [k, v] of Object.entries(s.link_types))
      html += `<div class="info-row"><span class="label">${k} links</span><span class="value">${v}</span></div>`;
  document.getElementById('graph-stats').innerHTML = html;
}


// ── search ──

function initSearch() {
  const input = document.getElementById('search-input');
  const results = document.getElementById('search-results');
  let timeout = null;

  input.addEventListener('input', () => {
    clearTimeout(timeout);
    const q = input.value.trim();
    if (q.length < 2) { results.classList.add('hidden'); return; }
    timeout = setTimeout(async () => {
      const resp = await fetch(`/api/graph/search?q=${encodeURIComponent(q)}`);
      const items = await resp.json();
      if (!items.length) { results.classList.add('hidden'); return; }
      results.innerHTML = items.map(i =>
        `<div class="dropdown-item" data-id="${i.id}"><span class="name">${i.name}</span><span class="path">${i.path}</span></div>`
      ).join('');
      results.classList.remove('hidden');
    }, 300);
  });

  results.addEventListener('click', async e => {
    const item = e.target.closest('.dropdown-item');
    if (!item) return;
    const id = item.dataset.id;
    results.classList.add('hidden');
    input.value = '';
    focusNodeId = id;
    await loadGraph(id);
    const n = cy.getElementById(id);
    if (n.length) { n.select(); await showNodeInfo(id); }
  });

  document.addEventListener('click', e => { if (!e.target.closest('.toolbar-right')) results.classList.add('hidden'); });
}


// ── tree ──

async function loadTree() {
  const resp = await fetch('/api/graph/tree');
  const tree = await resp.json();
  const view = document.getElementById('tree-view');
  view.innerHTML = renderTree(tree);
  if (tree.length && tree[0].id && tree[0].id.startsWith('_cat_'))
    view.querySelectorAll('.tree-folder').forEach(f => f.classList.add('open'));
}

function renderTree(nodes) {
  if (!nodes || !nodes.length) return '';
  let html = '';
  for (const n of nodes) {
    if (n.children !== undefined) {
      const files = (n.files || []).map(f => renderTreeFile(f)).join('');
      html += `<div class="tree-folder"><div class="tree-folder-header" data-id="${n.id}"><span class="arrow">&#9654;</span><span>${n.name}</span></div>
        <div class="tree-children">${renderTree(n.children)}${files}</div></div>`;
    } else {
      html += renderTreeFile(n);
    }
  }
  return html;
}

function renderTreeFile(f) {
  const url = f.url || '';
  const isWeb = url.startsWith('http');
  const badge = f.third_party ? '<span class="tree-badge tp">3rd</span>' : f.external ? '<span class="tree-badge ext">ext</span>' : '';
  const subtitle = isWeb ? `<span class="tree-url">${f.domain || url}</span>` : '';
  const linkAttr = isWeb ? `data-url="${url.replace(/"/g, '&quot;')}"` : '';
  return `<div class="tree-file" data-id="${f.id}" ${linkAttr}>${badge}${f.name}${subtitle}</div>`;
}

function initTree() {
  document.getElementById('tree-view').addEventListener('click', async e => {
    const header = e.target.closest('.tree-folder-header');
    if (header) { header.parentElement.classList.toggle('open'); return; }
    const file = e.target.closest('.tree-file');
    if (!file) return;
    const id = file.dataset.id;
    const url = file.dataset.url;
    const n = cy.getElementById(id);
    if (n.length) {
      cy.animate({ center: { eles: n }, zoom: 2 }, { duration: 500 });
      n.select();
      await showNodeInfo(id);
    } else if (url) {
      window.open(url, '_blank');
    }
  });
}


// ── filters ──

function buildFilterOptions() {
  const kinds = new Set();
  const exts = new Set();
  cy.nodes().forEach(n => { kinds.add(n.data('kind')); const ext = n.data('extension'); if (ext) exts.add(ext); });

  let html = '';
  for (const k of [...kinds].sort()) html += `<label><input type="checkbox" class="kind-cb" value="${k}" checked> ${k}</label>`;
  document.getElementById('kind-filters').innerHTML = html;

  html = '';
  for (const e of [...exts].sort()) {
    const color = getExtColor(e);
    html += `<label><input type="checkbox" class="ext-cb" value="${e}" checked> <span class="ext-swatch" style="background:${color}"></span>${e}</label>`;
  }
  document.getElementById('ext-filters').innerHTML = html;
}

function initFilters() {
  const apply = () => applyFilters();
  document.getElementById('f-hidden').addEventListener('change', apply);
  document.getElementById('f-system').addEventListener('change', apply);
  document.getElementById('f-folders').addEventListener('change', apply);
  document.getElementById('f-deleted').addEventListener('change', apply);
  document.getElementById('f-size-apply').addEventListener('click', apply);
  document.getElementById('f-date-apply').addEventListener('click', apply);
  document.getElementById('filter-controls').addEventListener('change', e => {
    if (e.target.classList.contains('kind-cb') || e.target.classList.contains('ext-cb')) applyFilters();
  });
  document.getElementById('f-reset').addEventListener('click', () => {
    document.querySelectorAll('#filter-controls input[type="checkbox"]').forEach(c => c.checked = true);
    document.getElementById('f-size-min').value = '';
    document.getElementById('f-size-max').value = '';
    document.getElementById('f-date-min').value = '';
    document.getElementById('f-date-max').value = '';
    cy.nodes().show(); cy.edges().show();
  });
}

function applyFilters() {
  const showHidden = document.getElementById('f-hidden').checked;
  const showSystem = document.getElementById('f-system').checked;
  const showFolders = document.getElementById('f-folders').checked;
  const showDeleted = document.getElementById('f-deleted').checked;
  const activeKinds = new Set(); document.querySelectorAll('.kind-cb:checked').forEach(c => activeKinds.add(c.value));
  const activeExts = new Set(); document.querySelectorAll('.ext-cb:checked').forEach(c => activeExts.add(c.value));
  const sizeMin = parseInt(document.getElementById('f-size-min').value) || 0;
  const sizeMax = parseInt(document.getElementById('f-size-max').value) || Infinity;
  const dateMin = document.getElementById('f-date-min').value;
  const dateMax = document.getElementById('f-date-max').value;

  cy.batch(() => {
    cy.nodes().forEach(n => {
      const d = n.data();
      let show = true;
      if (!showHidden && d.is_hidden) show = false;
      if (!showSystem && d.is_system) show = false;
      if (!showFolders && d.kind === 'folder') show = false;
      if (!showDeleted && d.is_deleted) show = false;
      if (!activeKinds.has(d.kind)) show = false;
      const ext = d.extension;
      if (ext && !activeExts.has(ext)) show = false;
      const size = d.size || 0;
      if (size < sizeMin || size > sizeMax) show = false;
      if (dateMin || dateMax) {
        const mod = (d.modified || '').slice(0, 10);
        if (mod) { if (dateMin && mod < dateMin) show = false; if (dateMax && mod > dateMax) show = false; }
      }
      if (show) n.show(); else n.hide();
    });
    cy.edges().forEach(e => { if (e.source().hidden() || e.target().hidden()) e.hide(); else e.show(); });
  });
}


// ── heatmap / timeline ──

let timelineEvents = [];
let tlMuted = new Set();

function drawHeatmap() {
  const canvas = document.getElementById('heatmap-canvas');
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.fillStyle = '#1e1e1e';
  ctx.fillRect(0, 0, w, h);

  if (!cy || cy.nodes().length === 0) {
    ctx.fillStyle = '#555'; ctx.font = '11px sans-serif';
    ctx.fillText('Scan a directory to see activity', 10, h / 2);
    document.getElementById('timeline-info').textContent = 'No data';
    return;
  }

  const dayCounts = {};
  let minDate = null, maxDate = null;
  cy.nodes().forEach(n => {
    const mod = n.data('modified');
    if (!mod) return;
    const day = mod.slice(0, 10);
    if (day.length !== 10) return;
    dayCounts[day] = (dayCounts[day] || 0) + 1;
    if (!minDate || day < minDate) minDate = day;
    if (!maxDate || day > maxDate) maxDate = day;
  });

  const days = Object.keys(dayCounts).sort();
  if (!days.length) {
    ctx.fillStyle = '#555'; ctx.font = '11px sans-serif';
    ctx.fillText('No date data available', 10, h / 2);
    return;
  }

  const maxCount = Math.max(...Object.values(dayCounts));
  const cols = 52, rows = 7;
  const cellW = Math.floor((w - 30) / cols), cellH = Math.floor((h - 24) / rows);

  ctx.fillStyle = '#888'; ctx.font = '9px sans-serif';
  ctx.fillText(minDate || '', 4, 10);
  ctx.fillText(maxDate || '', w - 70, 10);

  const end = new Date(maxDate);
  const start = new Date(end);
  start.setDate(start.getDate() - (cols * rows));

  for (let col = 0; col < cols; col++) {
    for (let row = 0; row < rows; row++) {
      const d = new Date(start); d.setDate(d.getDate() + col * 7 + row);
      const key = d.toISOString().slice(0, 10);
      const count = dayCounts[key] || 0;
      if (count === 0) { ctx.fillStyle = '#2a2a2a'; }
      else {
        const t = Math.min(count / maxCount, 1);
        ctx.fillStyle = `rgb(${Math.round(30+t*49)},${Math.round(30+t*165)},${Math.round(30+t*217)})`;
      }
      ctx.fillRect(4 + col * cellW, 16 + row * cellH, cellW - 1, cellH - 1);
    }
  }

  document.getElementById('timeline-info').textContent = `${cy.nodes().length} nodes across ${days.length} days | ${minDate} to ${maxDate}`;
}

function showInteractiveTimeline() {
  document.getElementById('timeline-heatmap').style.display = 'none';
  document.getElementById('timeline-interactive').classList.remove('hidden');
  timelineEvents = [];
  tlMuted = new Set();
  document.getElementById('tl-flow').innerHTML = '';
  document.getElementById('tl-status').textContent = '';
  document.querySelectorAll('.tl-legend-item').forEach(el => el.classList.remove('muted'));
}

function showHeatmapTimeline() {
  document.getElementById('timeline-heatmap').style.display = '';
  document.getElementById('timeline-interactive').classList.add('hidden');
}

function classifyTimelineEvent(evt) {
  const e = evt.event;
  if (e === 'navigation' || e === 'session_started' || e === 'session_ended') return 'navigation';
  if (e === 'redirect') return 'redirect';
  if (e === 'cookie_set' || e === 'cookie_modified' || e === 'cookie_deleted') return 'cookie';
  if (e === 'js_error' || e === 'navigation_error') return 'error';
  if (e === 'request' && evt.resource_type === 'document') return 'request';
  if (e === 'response' && evt.status >= 400) return 'error';
  return null; // filtered out — not pertinent
}

function tlTruncUrl(url) {
  try {
    const u = new URL(url);
    let path = u.pathname;
    if (path.length > 35) path = path.slice(0, 16) + '...' + path.slice(-12);
    return `<span class="tl-url" title="${escHtml(url)}">${escHtml(u.hostname + path)}</span>`;
  } catch { return `<span class="tl-url">${escHtml((url || '').slice(0, 50))}</span>`; }
}

function renderTimelineNode(evt, kind) {
  const time = (evt.time || '').slice(11, 19);
  let label = '';

  switch (evt.event) {
    case 'session_started':
      return `<div class="tl-node" data-kind="session"><span class="tl-time">${time}</span><span class="tl-label"><b>Session started</b> ${tlTruncUrl(evt.url)}</span></div>`;
    case 'session_ended': {
      const s = evt.stats || {};
      return `<div class="tl-node" data-kind="session"><span class="tl-time">${time}</span><span class="tl-label"><b>Session ended</b> ${s.requests||0} requests, ${s.cookies||0} cookies, ${s.pages||0} pages</span></div>`;
    }
    case 'navigation':
      label = `<b>Navigated</b> ${tlTruncUrl(evt.url)}`;
      break;
    case 'redirect':
      label = `<span class="tl-status s3xx">\u21AA</span> ${tlTruncUrl(evt.from)} \u2192 ${tlTruncUrl(evt.to)}`;
      break;
    case 'cookie_set':
      label = `<b>Cookie set:</b> ${escHtml(evt.name)}`;
      if (evt.domain) label += ` <span class="tl-url">@ ${escHtml(evt.domain)}</span>`;
      label += '<span class="tl-cookie-flags">';
      label += evt.secure ? '<span class="tl-cflag ok">Secure</span>' : '<span class="tl-cflag bad">!Secure</span>';
      label += evt.httpOnly ? '<span class="tl-cflag ok">HttpOnly</span>' : '<span class="tl-cflag bad">!HttpOnly</span>';
      if (evt.sameSite) label += `<span class="tl-cflag ok">${escHtml(evt.sameSite)}</span>`;
      label += '</span>';
      break;
    case 'cookie_modified':
      label = `<b>Cookie changed:</b> ${escHtml(evt.name)}`;
      if (evt.domain) label += ` <span class="tl-url">@ ${escHtml(evt.domain)}</span>`;
      break;
    case 'cookie_deleted':
      label = `<b>Cookie deleted:</b> ${escHtml(evt.name)}`;
      break;
    case 'request':
      label = `<b>${escHtml(evt.method)}</b> ${tlTruncUrl(evt.url)}`;
      break;
    case 'response': {
      const cls = evt.status >= 500 ? 'se-err' : evt.status >= 400 ? 'se-warn' : '';
      label = `<span class="tl-status ${cls}">${evt.status}</span> ${tlTruncUrl(evt.url)}`;
      break;
    }
    case 'js_error':
    case 'navigation_error':
      label = `<b>Error:</b> ${escHtml((evt.text || evt.error || '').slice(0, 120))}`;
      break;
    default:
      label = escHtml(evt.event);
  }

  const hidden = tlMuted.has(kind) ? ' style="display:none"' : '';
  return `<div class="tl-node" data-kind="${kind}"${hidden}><span class="tl-time">${time}</span><span class="tl-label">${label}</span></div>`;
}

function appendTimelineEvent(evt) {
  const kind = classifyTimelineEvent(evt);
  if (!kind) return;

  timelineEvents.push({ evt, kind });
  const flow = document.getElementById('tl-flow');
  flow.insertAdjacentHTML('beforeend', renderTimelineNode(evt, kind));
  flow.scrollTop = flow.scrollHeight;

  updateTimelineStatus();
}

function updateTimelineStatus() {
  const counts = {};
  for (const { kind } of timelineEvents) {
    counts[kind] = (counts[kind] || 0) + 1;
  }
  const parts = [];
  if (counts.navigation) parts.push(`${counts.navigation} nav`);
  if (counts.redirect) parts.push(`${counts.redirect} redir`);
  if (counts.cookie) parts.push(`${counts.cookie} cookies`);
  if (counts.request) parts.push(`${counts.request} req`);
  if (counts.error) parts.push(`${counts.error} err`);
  document.getElementById('tl-status').textContent = parts.join(' \u00B7 ') || '';
}

function applyTimelineLegendFilter() {
  document.querySelectorAll('#tl-flow .tl-node').forEach(el => {
    const kind = el.dataset.kind;
    if (kind === 'session') return;
    el.style.display = tlMuted.has(kind) ? 'none' : '';
  });
}

function initTimeline() {
  document.getElementById('tl-legend').addEventListener('click', e => {
    const item = e.target.closest('.tl-legend-item');
    if (!item) return;
    const kind = item.dataset.kind;
    if (tlMuted.has(kind)) {
      tlMuted.delete(kind);
      item.classList.remove('muted');
    } else {
      tlMuted.add(kind);
      item.classList.add('muted');
    }
    applyTimelineLegendFilter();
  });
}


// ── security panel ──

async function loadSecurity() {
  try {
    const resp = await fetch('/api/graph/security');
    const data = await resp.json();
    renderSecurityScore(data.summary);
    renderSecurityFindings(data.by_severity);
    renderSecurityCookies(data.cookies);
  } catch (e) {
    document.getElementById('security-score').innerHTML = '';
    document.getElementById('security-findings').innerHTML = '<p class="placeholder">No security data</p>';
    document.getElementById('security-cookies').innerHTML = '';
  }
}

function renderSecurityScore(summary) {
  const el = document.getElementById('security-score');
  if (!summary) { el.innerHTML = ''; return; }
  const score = summary.score || 0;
  const color = score >= 70 ? '#66bb6a' : score >= 40 ? '#ff9800' : '#ff5252';
  el.innerHTML = `<div class="sec-score-wrap">
    <div class="sec-score-circle" style="border-color:${color}"><span>${score}</span></div>
    <div class="sec-score-detail">
      <div class="sec-count critical">${summary.critical || 0} critical</div>
      <div class="sec-count warning">${summary.warning || 0} warning</div>
      <div class="sec-count info">${summary.info || 0} info</div>
      <div class="sec-count pass">${summary.pass || 0} pass</div>
    </div>
  </div>`;
}

function renderSecurityFindings(bySeverity) {
  const el = document.getElementById('security-findings');
  if (!bySeverity) { el.innerHTML = ''; return; }
  let html = '';
  for (const sev of ['critical','warning','info','pass']) {
    const items = bySeverity[sev] || [];
    if (!items.length) continue;
    const color = SEVERITY_COLORS[sev] || '#888';
    html += `<div class="sec-group"><h4 style="color:${color}">${sev.toUpperCase()} (${items.length})</h4>`;
    for (const f of items) {
      const badge = sev[0].toUpperCase();
      html += `<div class="sec-finding" data-id="${f.id}">
        <span class="sec-badge" style="background:${color}">${badge}</span>
        <div class="sec-finding-body">
          <div class="sec-finding-title">${f.title || f.name}</div>
          <div class="sec-finding-detail">${f.detail || ''}</div>
        </div>
      </div>`;
    }
    html += '</div>';
  }
  el.innerHTML = html || '<p class="placeholder">No findings</p>';
}

function renderSecurityCookies(cookies) {
  const el = document.getElementById('security-cookies');
  if (!cookies || !cookies.length) { el.innerHTML = ''; return; }
  let html = '<h4 class="sec-cookies-header">Cookies</h4>';
  for (const c of cookies) {
    html += `<div class="sec-cookie" data-id="${c.id}">
      <span class="sec-cookie-name">${c.name}</span>
      <div class="sec-cookie-flags">
        <span class="sec-flag ${c.secure ? 'pass' : 'warn'}">Secure: ${c.secure ? 'Yes' : 'No'}</span>
        <span class="sec-flag ${c.httponly ? 'pass' : 'warn'}">HttpOnly: ${c.httponly ? 'Yes' : 'No'}</span>
        <span class="sec-flag ${c.samesite ? 'pass' : 'warn'}">SameSite: ${c.samesite || 'None'}</span>
      </div>
    </div>`;
  }
  el.innerHTML = html;
}

function initSecurity() {
  document.getElementById('security-findings').addEventListener('click', async e => {
    const card = e.target.closest('.sec-finding');
    if (!card) return;
    const id = card.dataset.id;
    const n = cy.getElementById(id);
    if (n.length) {
      cy.animate({ center: { eles: n }, zoom: 2 }, { duration: 500 });
      n.select();
      await showNodeInfo(id);
    } else {
      focusNodeId = id;
      await loadGraph(id);
    }
  });
  document.getElementById('security-cookies').addEventListener('click', async e => {
    const card = e.target.closest('.sec-cookie');
    if (!card) return;
    const id = card.dataset.id;
    const n = cy.getElementById(id);
    if (n.length) {
      cy.animate({ center: { eles: n }, zoom: 2 }, { duration: 500 });
      n.select();
      await showNodeInfo(id);
    }
  });
}


// ── scan ──

function isUrl(str) { return /^https?:\/\//i.test(str) || /^[\w-]+\.\w{2,}/i.test(str); }

function initScan() {
  const pathInput = document.getElementById('scan-path');
  const modeSelect = document.getElementById('scan-mode');
  pathInput.addEventListener('input', () => { if (isUrl(pathInput.value.trim()) && modeSelect.value !== 'web-interactive') modeSelect.value = 'web'; });

  document.getElementById('scan-form').addEventListener('submit', async e => {
    e.preventDefault();
    const path = pathInput.value.trim();
    if (!path) return;
    let mode = modeSelect.value;
    if (isUrl(path) && mode !== 'web-interactive') mode = 'web';
    const endpoint = { live:'/api/scan/live', forensic:'/api/scan/forensic', memory:'/api/scan/memory', iso:'/api/scan/iso', web:'/api/scan/web', 'web-interactive':'/api/scan/web-interactive' }[mode];
    document.getElementById('scan-btn').disabled = true;

    if (mode === 'web-interactive') {
      sessionEvents = [];
      document.getElementById('session-log').innerHTML = '';
      document.getElementById('session-stats').textContent = '';
      sessionActive = true;
      document.getElementById('session-stop-btn').disabled = false;
      activateTab('session-panel');
      showInteractiveTimeline();
      showProgress(0, 'Launching browser...');
    } else {
      showHeatmapTimeline();
      showProgress(0, 'Starting...');
    }

    await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }) });
  });
}


// ── analyzer buttons ──

function initAnalyzers() {
  const scanPath = () => document.getElementById('scan-path').value.trim();
  for (const [btn, endpoint] of [['analyze-browser-btn','/api/analyze/browser'],['analyze-email-btn','/api/analyze/email'],['analyze-prefetch-btn','/api/analyze/prefetch']]) {
    document.getElementById(btn).addEventListener('click', async () => {
      const path = scanPath(); if (!path) return;
      const resp = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }) });
      const data = await resp.json();
      if (data.added) await loadGraph(focusNodeId);
    });
  }
}


// ── session ──

function activateTab(panelId) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  const container = panel.closest('.panel');
  if (!container) return;
  container.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  container.querySelectorAll('.panel-content').forEach(p => p.classList.remove('active'));
  const tab = container.querySelector(`.tab[data-panel="${panelId}"]`);
  if (tab) tab.classList.add('active');
  panel.classList.add('active');
}

const SESSION_ICONS = {
  request: '\u2192', response: '\u2190', redirect: '\u21AA',
  cookie_set: '\uD83C\uDF6A', cookie_modified: '\u270F', cookie_deleted: '\u2716',
  console: '\u25B6', js_error: '\u26A0', navigation: '\uD83C\uDFE0',
  session_started: '\u25B6', session_ended: '\u23F9', navigation_error: '\u26A0',
};

const SESSION_COLORS = {
  request: 'var(--accent)', response: '#66bb6a', redirect: '#ff9800',
  cookie_set: '#ff9800', cookie_modified: '#ce93d8', cookie_deleted: '#ff5252',
  console: '#888', js_error: '#ff5252', navigation: '#4fc3f7',
  session_started: '#66bb6a', session_ended: '#888', navigation_error: '#ff5252',
};

function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function truncUrl(url) {
  try {
    const u = new URL(url);
    let path = u.pathname;
    if (path.length > 40) path = path.slice(0, 20) + '...' + path.slice(-15);
    return `<span class="se-url" title="${escHtml(url)}">${escHtml(u.hostname + path)}</span>`;
  } catch { return `<span class="se-url">${escHtml((url || '').slice(0, 60))}</span>`; }
}

function renderSessionEvent(evt) {
  const event = evt.event || 'unknown';
  const time = (evt.time || '').slice(11, 19);
  const icon = SESSION_ICONS[event] || '\u2022';
  const color = SESSION_COLORS[event] || '#888';

  let detail = '';
  switch (event) {
    case 'request':
      detail = `<span class="se-method">${escHtml(evt.method)}</span> ${truncUrl(evt.url)}`;
      break;
    case 'response': {
      const cls = evt.status < 300 ? 'se-ok' : evt.status < 400 ? 'se-warn' : 'se-err';
      detail = `<span class="${cls}">${evt.status}</span> ${truncUrl(evt.url)}`;
      break;
    }
    case 'redirect':
      detail = `${truncUrl(evt.from)} <span class="se-method">\u2192</span> ${truncUrl(evt.to)}`;
      break;
    case 'cookie_set':
      detail = `<b>${escHtml(evt.name)}</b> @ ${escHtml(evt.domain || '')}`;
      if (evt.secure) detail += ' <span class="se-flag-ok">Secure</span>';
      if (evt.httpOnly) detail += ' <span class="se-flag-ok">HttpOnly</span>';
      if (evt.sameSite) detail += ` <span class="se-flag-ok">${escHtml(evt.sameSite)}</span>`;
      break;
    case 'cookie_modified':
      detail = `<b>${escHtml(evt.name)}</b> modified @ ${escHtml(evt.domain || '')}`;
      break;
    case 'cookie_deleted':
      detail = `<b>${escHtml(evt.name)}</b> deleted`;
      break;
    case 'console':
      detail = `<span class="se-level">[${escHtml(evt.level)}]</span> ${escHtml(evt.text || '')}`;
      break;
    case 'js_error':
      detail = escHtml(evt.text || '');
      break;
    case 'navigation':
      detail = truncUrl(evt.url);
      break;
    case 'session_started':
      detail = `Session started: ${truncUrl(evt.url)}`;
      break;
    case 'session_ended': {
      const s = evt.stats || {};
      detail = `Session ended — ${s.requests||0} req, ${s.cookies||0} cookies, ${s.redirects||0} redirects`;
      break;
    }
    case 'navigation_error':
      detail = escHtml(evt.error || '');
      break;
    default:
      detail = escHtml(JSON.stringify(evt));
  }

  return `<div class="session-event" data-event="${event}" style="border-left-color:${color}">
    <span class="se-time">${time}</span>
    <span class="se-icon">${icon}</span>
    <span class="se-detail">${detail}</span>
  </div>`;
}

function appendSessionEvent(evt) {
  sessionEvents.push(evt);
  const log = document.getElementById('session-log');
  const html = renderSessionEvent(evt);
  log.insertAdjacentHTML('beforeend', html);

  applySessionFilters();
  updateSessionStats();

  // auto-scroll
  log.scrollTop = log.scrollHeight;
}

function applySessionFilters() {
  const checked = new Set();
  document.querySelectorAll('.session-filter-cb:checked').forEach(cb => checked.add(cb.dataset.event));
  // also allow through meta events that aren't filterable
  const always = new Set(['session_started', 'session_ended', 'navigation_error']);

  document.querySelectorAll('.session-event').forEach(el => {
    const event = el.dataset.event;
    el.style.display = (checked.has(event) || always.has(event)) ? '' : 'none';
  });
}

function updateSessionStats() {
  const counts = {};
  for (const evt of sessionEvents) {
    const e = evt.event || 'unknown';
    counts[e] = (counts[e] || 0) + 1;
  }
  const parts = [];
  if (counts.request) parts.push(`${counts.request} req`);
  if (counts.response) parts.push(`${counts.response} resp`);
  if (counts.redirect) parts.push(`${counts.redirect} redir`);
  const cookies = (counts.cookie_set || 0) + (counts.cookie_modified || 0) + (counts.cookie_deleted || 0);
  if (cookies) parts.push(`${cookies} cookies`);
  if (counts.console) parts.push(`${counts.console} log`);
  if (counts.js_error) parts.push(`${counts.js_error} err`);
  if (counts.navigation) parts.push(`${counts.navigation} nav`);
  document.getElementById('session-stats').textContent = parts.join(' | ') || '';
}

function initSession() {
  document.getElementById('session-stop-btn').addEventListener('click', async () => {
    await fetch('/api/scan/web-interactive/stop', { method: 'POST' });
    document.getElementById('session-stop-btn').disabled = true;
  });

  document.getElementById('session-filter-bar').addEventListener('change', () => {
    applySessionFilters();
  });
}


// ── progress ──

function showProgress(pct, msg) {
  document.getElementById('progress-bar').classList.remove('hidden');
  document.getElementById('progress-fill').style.width = (pct * 100) + '%';
  document.getElementById('progress-text').textContent = msg || '';
  showLoadingOverlay(msg);
}

function hideProgress() {
  document.getElementById('progress-bar').classList.add('hidden');
  hideLoadingOverlay();
}

function showLoadingOverlay(msg) {
  let overlay = document.getElementById('loading-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'loading-overlay';
    overlay.innerHTML = '<div class="loading-spinner"></div><div class="loading-text"></div>';
    document.getElementById('graph-container').appendChild(overlay);
  }
  overlay.style.display = 'flex';
  overlay.querySelector('.loading-text').textContent = msg || 'Loading...';
}

function hideLoadingOverlay() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.style.display = 'none';
}


// ── websocket ──

function initWebSocket() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws`);
  ws.onmessage = async event => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'session_event') {
      appendSessionEvent(msg);
      appendTimelineEvent(msg);
      if (msg.event === 'session_started') hideProgress();
      if (msg.event === 'session_ended') {
        sessionActive = false;
        document.getElementById('session-stop-btn').disabled = true;
      }
    }
    else if (msg.type === 'progress') showProgress(msg.percent, msg.message);
    else if (msg.type === 'scan_complete') {
      hideProgress();
      document.getElementById('scan-btn').disabled = false;
      if (msg.error) { showProgress(0, msg.error); setTimeout(hideProgress, 3000); return; }
      focusNodeId = msg.focus;
      await loadGraph(msg.focus);
      await loadTree();
      drawHeatmap();
      loadFavorites();
      loadSecurity();
    }
  };
  ws.onclose = () => setTimeout(initWebSocket, 3000);
}


// ── chat ──

function initChat() {
  document.getElementById('chat-form').addEventListener('submit', async e => {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';
    sendChat(msg);
  });
  document.querySelectorAll('.quick-action').forEach(btn => { btn.addEventListener('click', () => sendChat(btn.dataset.msg)); });
}

async function sendChat(message) {
  appendChatMsg('user', message);
  const resp = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message }) });
  if (!resp.ok) { const err = await resp.json(); appendChatMsg('assistant', err.error || 'Chat unavailable', true); return; }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  chatStreamEl = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    for (const line of decoder.decode(value).split('\n'))
      if (line.startsWith('data: ')) { const data = line.slice(6); if (data === '[DONE]') chatStreamEl = null; else appendToken(data); }
  }
}

function appendChatMsg(role, text, isError = false) {
  const c = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = `chat-msg ${role}${isError ? ' error' : ''}`;
  div.textContent = text;
  c.appendChild(div);
  c.scrollTop = c.scrollHeight;
}

function appendToken(token) {
  const c = document.getElementById('chat-messages');
  if (!chatStreamEl) { chatStreamEl = document.createElement('div'); chatStreamEl.className = 'chat-msg assistant'; c.appendChild(chatStreamEl); }
  chatStreamEl.textContent += token;
  c.scrollTop = c.scrollHeight;
}


// ── tabs ──

function initTabs() {
  document.querySelectorAll('.panel-tabs').forEach(bar => {
    bar.addEventListener('click', e => {
      const tab = e.target.closest('.tab');
      if (!tab) return;
      const panel = tab.closest('.panel');
      panel.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      panel.querySelectorAll('.panel-content').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.panel).classList.add('active');
    });
  });
}


// ── keyboard shortcuts ──

function initKeyboard() {
  document.addEventListener('keydown', e => {
    if (e.ctrlKey && e.key === 'f') { e.preventDefault(); document.getElementById('search-input').focus(); }
    if (e.ctrlKey && e.key === 'e') { e.preventDefault(); exportGraph(); }
    if (e.ctrlKey && e.key === 'o') { e.preventDefault(); document.getElementById('scan-path').focus(); }
    if (e.key === 'Escape') {
      document.getElementById('search-results').classList.add('hidden');
      document.getElementById('search-input').blur();
      hideContextMenu(); hidePreviewModal();
      if (cy) cy.elements().unselect();
    }
  });
}


// ── export ──

async function exportGraph() {
  const resp = await fetch('/api/graph/export');
  const data = await resp.json();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'dotty-export.json'; a.click();
  URL.revokeObjectURL(url);
}

function initExport() { document.getElementById('export-btn').addEventListener('click', exportGraph); }


// ── utils ──

function formatSize(bytes) {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
}


// ── init ──

document.addEventListener('DOMContentLoaded', () => {
  initGraph();
  initTabs();
  initScan();
  initAnalyzers();
  initSearch();
  initTree();
  initFilters();
  initFavorites();
  initChat();
  initSession();
  initTimeline();
  initSecurity();
  initKeyboard();
  initExport();
  initWebSocket();
  drawHeatmap();
  loadFavorites();
});
