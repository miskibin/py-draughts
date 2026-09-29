/* py-draughts server UI */
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const config = JSON.parse($('#server-config').textContent);
const state = {
  variant: config.variant, position: null, fen: '', legal: {}, engine: null,
  mode: 'analysis', side: 'moves', selected: null, flipped: false, numbers: false,
  autoplay: false, nonce: 0, timer: null, busy: false, engineTask: null,
  timeline: [],
};
const names = config.variants;
const sizeFor = variant => ['american', 'russian', 'brazilian'].includes(variant) ? 8 : 10;
const size = () => Math.sqrt(state.position.position.length);
const icon = (name, small = false) => `<svg class="icon${small ? ' small' : ''}"><use href="#i-${name}"/></svg>`;

async function api(path, body, signal) {
  const response = await fetch(path, body === undefined ? { signal } : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw Error(typeof detail?.detail === 'string' ? detail.detail : `Request failed (${response.status})`);
  }
  return response.json();
}
function toast(message) {
  const el = $('#toast'); el.textContent = message; el.classList.add('visible');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.remove('visible'), 3600);
}
function error(err) { if (err.name !== 'AbortError') toast(err.message || 'Request failed.'); }
function stopAutoPlay() {
  state.autoplay = false; state.nonce++;
  clearTimeout(state.timer);
  $('#autoplay-label').textContent = 'Auto play';
}
async function refresh(data, preserveTimeline = false) {
  state.position = data;
  if (!preserveTimeline) state.timeline = data.history.map(row => [...row]);
  state.selected = null;
  const [fen, legal] = await Promise.all([api('/fen'), api('/legal_moves')]);
  state.fen = fen.fen;
  state.legal = JSON.parse(legal.legal_moves);
  render();
}
function render() {
  if (!state.position) return;
  const { position, turn, history, game_over, result } = state.position;
  const n = size(), board = $('#board');
  board.style.setProperty('--size', n);
  board.classList.toggle('numbers-off', !state.numbers);
  board.setAttribute('aria-label', `${names[state.variant]} draughts, ${n} by ${n}`);
  board.replaceChildren();
  const indices = Array.from({ length: n * n }, (_, i) => i);
  if (state.flipped) indices.reverse();
  const destinations = state.selected ? state.legal[state.selected - 1] || [] : [];
  for (const i of indices) {
    const row = Math.floor(i / n), col = i % n, dark = (row + col) % 2 === 1;
    const sq = row * (n / 2) + Math.floor(col / 2) + 1;
    const piece = position[i], tile = document.createElement('button');
    tile.type = 'button'; tile.className = `square${dark ? ' dark' : ''}`;
    tile.disabled = !dark;
    if (dark) {
      tile.dataset.square = sq;
      if (sq === state.selected) tile.classList.add('selected');
      tile.setAttribute('aria-label', `Square ${sq}, ${piece ? `${piece < 0 ? 'white' : 'black'} ${Math.abs(piece) > 1 ? 'king' : 'man'}` : destinations.includes(sq - 1) ? 'legal destination' : 'empty'}`);
      const num = document.createElement('span'); num.className = 'num'; num.textContent = sq; tile.append(num);
      if (piece) {
        const disc = document.createElement('span');
        disc.className = `piece ${piece < 0 ? 'white' : 'black'}${Math.abs(piece) > 1 ? ' king' : ''}`;
        tile.append(disc);
      } else if (destinations.includes(sq - 1)) {
        const dot = document.createElement('span'); dot.className = 'move-dot'; tile.append(dot);
      }
    }
    board.append(tile);
  }
  $('#turn-disc').className = `tiny-piece ${turn}`;
  $('#turn-label').textContent = game_over ? `Game over · ${result}` : `${turn[0].toUpperCase() + turn.slice(1)} to move`;
  $('#variant-name').textContent = names[state.variant];
  $('#variant-size').textContent = `${n} × ${n}`;
  $('#fen-text').textContent = state.fen;
  $('#position-turn').textContent = turn[0].toUpperCase() + turn.slice(1);
  $('#legal-count').textContent = Object.values(state.legal).reduce((sum, targets) => sum + targets.length, 0);
  $('#material-count').textContent = `${position.filter(p => p < 0).length} : ${position.filter(p => p > 0).length}`;
  $('#analysis-engine-name').textContent = (turn === 'white' ? state.engine?.white_engine : state.engine?.black_engine) || 'No engine';
  $('#play-engine-name').textContent = $('#analysis-engine-name').textContent;
  $('#depth-label').textContent = state.engine?.depth || 6;
  $('#match-depth').value = state.engine?.depth || 6;
  $$('[data-action="hint"]').forEach(b => b.disabled = game_over || !currentEngine() || state.busy);
  renderHistory(history);
}
function renderHistory(history) {
  const list = $('#move-list'); list.replaceChildren();
  if (!state.timeline.length) {
    const empty = document.createElement('p'); empty.className = 'form-note'; empty.textContent = 'No moves yet.'; list.append(empty);
  }
  const currentPly = history.reduce((sum, row) => sum + row.length - 1, 0);
  state.timeline.forEach(([number, white, black]) => {
    const row = document.createElement('div'); row.className = 'move-row';
    const index = document.createElement('span'); index.className = 'move-index'; index.textContent = `${number}.`; row.append(index);
    for (const [move, ply] of [[white, (number - 1) * 2 + 1], [black, number * 2]]) {
      const button = document.createElement('button'); button.className = 'move-button mono';
      button.type = 'button'; button.textContent = move || ''; button.disabled = !move;
      button.classList.toggle('active', ply === currentPly);
      button.classList.toggle('future', ply > currentPly);
      button.dataset.ply = ply; row.append(button);
    }
    list.append(row);
  });
  const total = state.timeline.reduce((sum, row) => sum + row.length - 1, 0);
  $('#history-count').textContent = `${total} ${total === 1 ? 'move' : 'moves'}`;
  $('#ply-label').textContent = `${currentPly} / ${total}`;
  $$('[data-action="first"],[data-action="prev"]').forEach(b => b.disabled = currentPly === 0);
  $$('[data-action="next"],[data-action="last"]').forEach(b => b.disabled = currentPly === total);
  list.scrollTop = list.scrollHeight;
}
function currentEngine() {
  return state.position?.turn === 'white' ? state.engine?.white_engine : state.engine?.black_engine;
}
async function onSquare(square) {
  if (state.busy || state.position.game_over) return;
  const target = square - 1;
  if (state.selected && (state.legal[state.selected - 1] || []).includes(target)) {
    const source = state.selected; state.selected = null;
    try { await refresh(await api(`/move/${source}/${square}`, {})); }
    catch (err) { error(err); render(); }
    return;
  }
  state.selected = state.legal[target]?.length ? (state.selected === square ? null : square) : null;
  render();
}
async function navigate(ply) {
  stopAutoPlay();
  if (state.engineTask) await state.engineTask;
  try { await refresh(await api(`/goto/${ply}`), true); } catch (err) { error(err); }
}
function engineMove() {
  if (state.busy || !currentEngine() || state.position.game_over) return;
  state.busy = true; render();
  state.engineTask = (async () => {
    try {
      const data = await api('/best_move');
      await refresh(data);
      if (data.game_over) { stopAutoPlay(); toast(`Game over · ${data.result}`); }
    } catch (err) { error(err); stopAutoPlay(); }
    finally { state.busy = false; render(); }
  })();
  return state.engineTask.finally(() => { state.engineTask = null; });
}
function autoPlay() {
  if (state.autoplay) { stopAutoPlay(); return; }
  if (!state.engine?.white_engine || !state.engine?.black_engine) { toast('Configure both engines in Python to auto play.'); return; }
  state.autoplay = true; const nonce = ++state.nonce; $('#autoplay-label').textContent = 'Stop';
  const tick = async () => {
    if (!state.autoplay || nonce !== state.nonce) return;
    await engineMove();
    if (state.autoplay && nonce === state.nonce && !state.position.game_over) state.timer = setTimeout(tick, 500);
  };
  tick();
}
function setMode(mode) {
  state.mode = mode;
  $$('[data-mode]').forEach(b => {
    const active = b.dataset.mode === mode;
    b.classList.toggle('active', active);
    if (active) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  $('#standard-sidebar').classList.toggle('hidden', mode === 'engines');
  $('#match-sidebar').classList.toggle('hidden', mode !== 'engines');
  $('#analysis-panel').classList.toggle('hidden', mode !== 'analysis');
  $('#play-panel').classList.toggle('hidden', mode !== 'play');
}
function setSide(side) {
  state.side = side;
  $$('[data-side]').forEach(b => { b.classList.toggle('active', b.dataset.side === side); b.setAttribute('aria-selected', String(b.dataset.side === side)); });
  $('#moves-panel').classList.toggle('hidden', side !== 'moves');
  $('#position-panel').classList.toggle('hidden', side !== 'position');
}
function closeActions(restore = true) {
  $('#actions-menu').hidden = true; $('#actions-toggle').setAttribute('aria-expanded', 'false');
  if (restore) $('#actions-toggle').focus();
}
function closeDialog() {
  const modal = $('#modal-layer'); if (!modal.open) return;
  modal.close(); document.body.style.overflow = '';
  state.focusReturn?.focus();
}
async function copy(value) {
  try { await navigator.clipboard.writeText(value); toast('Copied.'); }
  catch { toast('Clipboard unavailable. Select the text to copy it.'); }
}
function save(value, name, type = 'text/plain') {
  const link = document.createElement('a'), url = URL.createObjectURL(new Blob([value], { type }));
  link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function boardSVG() {
  const n = size(), cell = 64, position = state.position.position;
  let content = '';
  for (let i = 0; i < n * n; i++) {
    const r = Math.floor(i / n), c = i % n, x = (state.flipped ? n - c - 1 : c) * cell, y = (state.flipped ? n - r - 1 : r) * cell;
    const dark = (r + c) % 2 === 1, piece = position[i];
    content += `<rect x="${x}" y="${y}" width="64" height="64" fill="${dark ? '#a5b09b' : '#edf0e7'}"/>`;
    if (dark && piece) content += `<circle cx="${x + 32}" cy="${y + 32}" r="23" fill="${piece < 0 ? '#fffef7' : '#394233'}" stroke="#607058"/>${Math.abs(piece) > 1 ? `<path d="m${x + 32} ${y + 23} 9 9-9 9-9-9Z" fill="none" stroke="#929e81"/>` : ''}`;
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${n * cell}" height="${n * cell}" viewBox="0 0 ${n * cell} ${n * cell}">${content}</svg>`;
}
async function openDialog(type) {
  if (!['new', 'import', 'export', 'settings', 'api', 'shortcuts'].includes(type)) return;
  state.focusReturn = document.activeElement.closest('.actions-menu') ? $('#actions-toggle') : document.activeElement;
  closeActions(false);
  const box = $('#dialog'), modal = $('#modal-layer');
  modal.classList.toggle('wide', ['import', 'export', 'api'].includes(type));
  const head = title => `<div class="dialog-head"><h2 id="dialog-title">${title}</h2><button class="icon-btn" data-close aria-label="Close">${icon('close')}</button></div>`;
  const footer = content => `<div class="dialog-footer"><button class="button" data-close>Cancel</button>${content}</div>`;
  let body = '', tail = '';
  if (type === 'new') {
    body = `<label class="field-label" for="new-variant">Variant</label><select class="select" id="new-variant">${Object.entries(names).map(([id, name]) => `<option value="${id}" ${id === state.variant ? 'selected' : ''}>${name} · ${sizeFor(id)} × ${sizeFor(id)}</option>`).join('')}</select><p class="form-note">Starts a new game in the selected variant.</p>`;
    tail = footer('<button class="button primary" id="create-game">Create game</button>');
  } else if (type === 'import') {
    body = `<div class="radio-tabs"><button class="active" data-format="PDN">PDN game</button><button data-format="FEN">FEN position</button></div><textarea id="import-text" aria-label="Paste notation" spellcheck="false" placeholder="Paste PDN here…"></textarea>`;
    tail = footer('<button class="button primary" id="import-button">Import</button>');
  } else if (type === 'export') {
    body = `<div class="radio-tabs"><button class="active" data-export="FEN">FEN position</button><button data-export="PDN">PDN game</button><button data-export="SVG">SVG board</button></div><textarea id="export-text" readonly aria-label="Export notation"></textarea>`;
    tail = `<div class="dialog-footer"><button class="button" id="copy-export">${icon('copy', true)}Copy</button><button class="button primary" id="save-export">${icon('download', true)}Download</button></div>`;
  } else if (type === 'settings') {
    body = `<p class="form-note">White: ${state.engine?.white_engine || 'Human'} · Black: ${state.engine?.black_engine || 'Human'}. Engines are configured when starting the Python server.</p><div class="form-line"><label for="depth-input">Depth limit</label><input type="number" id="depth-input" min="1" max="10" value="${state.engine?.depth || 6}"></div>`;
    tail = footer('<button class="button primary" id="apply-settings">Save</button>');
  } else if (type === 'api') {
    const cls = { standard: 'StandardBoard', american: 'AmericanBoard', frisian: 'FrisianBoard', russian: 'RussianBoard', brazilian: 'BrazilianBoard', antidraughts: 'AntidraughtsBoard', breakthrough: 'BreakthroughBoard', frysk: 'FryskBoard' }[state.variant];
    const code = `from draughts import ${cls}\n\nboard = ${cls}.from_fen(${JSON.stringify(state.fen)})\nprint(board.legal_moves)`;
    body = '<pre class="code api-code" id="api-code" tabindex="0"></pre>';
    tail = `<div class="dialog-footer"><button class="button" data-close>Close</button><button class="button primary" id="copy-api">${icon('copy', true)}Copy code</button></div>`;
    box.dataset.code = code;
  } else {
    body = [['←', 'Previous move'], ['Home', 'Starting position'], ['F', 'Flip board'], ['N', 'Square numbers'], ['Esc', 'Close dialog']].map(([key, label]) => `<div class="form-line"><span>${label}</span><span class="mono muted">${key}</span></div>`).join('');
  }
  box.innerHTML = head({ new: 'New game', import: 'Import', export: 'Export', settings: 'Engine settings', api: 'Python API', shortcuts: 'Keyboard shortcuts' }[type]) + `<div class="dialog-body">${body}</div>` + tail;
  if (!modal.open) modal.showModal();
  document.body.style.overflow = 'hidden';
  $$('[data-close]', box).forEach(b => b.addEventListener('click', closeDialog));
  if (type === 'new') $('#create-game').onclick = () => { stopAutoPlay(); location.assign(`/set_board/${$('#new-variant').value}`); };
  if (type === 'import') {
    let format = 'PDN';
    $$('[data-format]', box).forEach(b => b.onclick = () => { format = b.dataset.format; $$('[data-format]', box).forEach(x => x.classList.toggle('active', x === b)); $('#import-text').placeholder = format === 'FEN' ? 'W:W31-50:B1-20' : 'Paste PDN here…'; });
    $('#import-button').onclick = async () => {
      const value = $('#import-text').value.trim(); if (!value) return toast('Paste notation first.');
      try { stopAutoPlay(); if (state.engineTask) await state.engineTask; await refresh(await api(format === 'FEN' ? '/load_fen' : '/load_pdn', { [format.toLowerCase()]: value })); closeDialog(); toast(`${format} loaded.`); }
      catch (err) { error(err); }
    };
  }
  if (type === 'export') {
    let format = 'FEN';
    const values = { FEN: state.fen, SVG: boardSVG() };
    try { values.PDN = (await api('/pdn')).pdn; } catch (err) { error(err); values.PDN = ''; }
    const show = () => { $('#export-text').value = values[format]; };
    show();
    $$('[data-export]', box).forEach(b => b.onclick = () => { format = b.dataset.export; $$('[data-export]', box).forEach(x => x.classList.toggle('active', x === b)); show(); });
    $('#copy-export').onclick = () => copy(values[format]);
    $('#save-export').onclick = () => save(values[format], `draughts.${format.toLowerCase()}`, format === 'SVG' ? 'image/svg+xml' : 'text/plain');
  }
  if (type === 'settings') $('#apply-settings').onclick = async () => {
    const depth = Number($('#depth-input').value);
    if (!Number.isInteger(depth) || depth < 1 || depth > 10) return toast('Choose a depth from 1 to 10.');
    try { state.engine.depth = (await api(`/set_depth/${depth}`)).depth; render(); closeDialog(); } catch (err) { error(err); }
  };
  if (type === 'api') { $('#api-code').textContent = box.dataset.code; $('#copy-api').onclick = () => copy(box.dataset.code); }
  box.querySelector('select, textarea, input, button')?.focus();
}
const actions = {
  first: () => navigate(0), prev: () => navigate(Math.max(0, state.position.history.reduce((n, row) => n + row.length - 1, 0) - 1)),
  next: () => navigate(state.position.history.reduce((n, row) => n + row.length - 1, 0) + 1),
  last: () => navigate(state.timeline.reduce((n, row) => n + row.length - 1, 0)),
  hint: engineMove, autoplay: autoPlay,
  flip: () => { state.flipped = !state.flipped; render(); },
  numbers: () => { state.numbers = !state.numbers; $('[data-action="numbers"]').setAttribute('aria-pressed', String(state.numbers)); render(); },
  'copy-fen': () => copy(state.fen), svg: () => save(boardSVG(), 'draughts-board.svg', 'image/svg+xml'),
  demo: () => { stopAutoPlay(); location.assign('/set_board/standard'); },
  theme: () => { const dark = document.body.classList.toggle('dark-theme'); $('[data-action="theme"]').setAttribute('aria-pressed', String(dark)); },
};
$('#board').addEventListener('click', e => { const square = e.target.closest('[data-square]'); if (square) onSquare(Number(square.dataset.square)); });
$('#move-list').addEventListener('click', e => { const button = e.target.closest('[data-ply]'); if (button && !button.disabled) navigate(Number(button.dataset.ply)); });
$$('[data-action]').forEach(b => b.addEventListener('click', () => actions[b.dataset.action]?.()));
$$('[data-dialog]').forEach(b => b.addEventListener('click', () => openDialog(b.dataset.dialog)));
$$('[data-mode]').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)));
$$('[data-side]').forEach(b => b.addEventListener('click', () => setSide(b.dataset.side)));
$('#actions-toggle').onclick = () => { const menu = $('#actions-menu'); menu.hidden = !menu.hidden; $('#actions-toggle').setAttribute('aria-expanded', String(!menu.hidden)); if (!menu.hidden) menu.querySelector('button').focus(); };
$('#actions-menu').addEventListener('click', e => { if (e.target.closest('button')) closeActions(false); });
document.addEventListener('pointerdown', e => { if (!e.target.closest('.actions-wrap')) closeActions(false); });
$('#modal-layer').addEventListener('click', e => { if (e.target === $('#modal-layer')) closeDialog(); });
$('#modal-layer').addEventListener('cancel', e => { e.preventDefault(); closeDialog(); });
$('#match-depth').addEventListener('change', async e => {
  const depth = Number(e.target.value); if (!Number.isInteger(depth) || depth < 1 || depth > 10) { e.target.value = state.engine.depth; return toast('Choose a depth from 1 to 10.'); }
  try { state.engine.depth = (await api(`/set_depth/${depth}`)).depth; render(); } catch (err) { error(err); }
});
document.addEventListener('keydown', e => {
  if ($('#modal-layer').open || ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) || e.ctrlKey || e.metaKey || e.altKey) return;
  const keys = { ArrowLeft: 'prev', ArrowRight: 'next', Home: 'first', End: 'last', f: 'flip', n: 'numbers' };
  if (keys[e.key]) { e.preventDefault(); actions[keys[e.key]](); }
});
window.addEventListener('beforeunload', stopAutoPlay);
(async () => {
  try {
    state.engine = await api('/engine_info');
    $('#engine-summary').textContent = `White: ${state.engine.white_engine || 'Human'} · Black: ${state.engine.black_engine || 'Human'}`;
    await refresh(await api('/position'));
  } catch (err) { error(err); }
})();
