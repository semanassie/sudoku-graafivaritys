'use strict';

const palette = ['#cd5142', '#e3943e', '#e8c145', '#40845e', '#3b66ac', '#8767a6', '#359b96', '#c56f8c', '#73a5c2'];
const examples = {
  demo: '530070000600195000098000060800060003400803001700020006060000280000419005000080079',
  backtracking: '100007090030020008009600500005300900010080002600004000300000010040000007007000300',
  empty: '0'.repeat(81)
};
const $ = id => document.getElementById(id);
const solver = createSudokuSolver();
const canvas = $('graph');
const ctx = canvas.getContext('2d');
const cells = [];
let puzzle = solver.parsePuzzle(examples.demo);
let state = puzzle.slice();
let result = null, index = 0, playing = false, last = 0, busy = false;
let worker = null, workerURL = null, solutionView = false;
let notice = 'Muokkaa vihjeitä ja paina Ratkaise.';
let isError = false;
const box = i => Math.floor(i / 27) * 3 + Math.floor(i % 9 / 3);
const positions = Array.from({length: 81}, (_, i) => {
  const a = -Math.PI / 2 + box(i) * 2 * Math.PI / 9;
  const r = Math.floor(i / 9) % 3, c = i % 3;
  return [
    500 + 360 * Math.cos(a) + (c - 1) * 39 * -Math.sin(a) + (r - 1) * 39 * Math.cos(a),
    500 + 360 * Math.sin(a) + (c - 1) * 39 * Math.cos(a) + (r - 1) * 39 * Math.sin(a)
  ];
});

function line(i, j, color, width = 1) {
  const a = positions[i], b = positions[j];
  ctx.beginPath();
  ctx.moveTo(...a);
  ctx.bezierCurveTo(a[0] * 0.69 + 155, a[1] * 0.69 + 155, b[0] * 0.69 + 155, b[1] * 0.69 + 155, ...b);
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.stroke();
}

function render() {
  const event = !solutionView && result && index > 0 ? result.trace[index - 1] : null;
  cells.forEach((el, i) => {
    el.value = state[i] || '';
    el.classList.toggle('given', !!puzzle[i]);
    el.classList.toggle('active', event?.vertex === i);
    el.style.background = state[i] && $('colors').checked ? palette[state[i] - 1] + '48' : '#ffffff';
    el.disabled = busy || playing;
  });
  ctx.clearRect(0, 0, 1000, 1000);
  solver.edges.forEach(([i, j]) => line(i, j, '#c0c0c0'));
  if (event) {
    solver.peers[event.vertex].forEach(j => line(event.vertex, j, state[j] ? palette[state[j] - 1] + 'bb' : '#808080', 2));
  }
  positions.forEach(([x, y], i) => {
    if (event?.vertex === i) {
      ctx.beginPath();
      ctx.arc(x, y, 21, 0, Math.PI * 2);
      ctx.strokeStyle = event.kind === 'dead_end' ? '#800000' : '#000080';
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(x, y, 12.5, 0, Math.PI * 2);
    ctx.fillStyle = state[i] ? palette[state[i] - 1] : '#ffffff';
    ctx.fill();
    ctx.strokeStyle = '#404040';
    ctx.lineWidth = 1.6;
    ctx.stroke();
  });
  const count = result?.trace.length || 0;
  $('solve').disabled = busy || playing;
  $('cancel').hidden = !busy;
  $('example').disabled = busy;
  $('unique').disabled = busy;
  $('timeout').disabled = busy;
  $('play').textContent = playing ? 'Tauko' : 'Toista jälki';
  $('play').disabled = !count || busy;
  $('previous').disabled = !count || (!index && !solutionView) || playing;
  $('next').disabled = !count || index >= count || solutionView || playing;
  $('finish').disabled = !result?.solution || busy;
  $('copy').disabled = !result?.solution;
  $('download').disabled = !result;
  $('seek').disabled = !count || busy;
  $('seek').max = Math.max(1, count);
  $('seek').value = index;
  $('step-count').textContent = `${index.toLocaleString()} / ${count.toLocaleString()}`;
  $('status').classList.toggle('error', isError);
  if (!result) {
    $('status').textContent = notice;
    $('detail').textContent = busy
      ? 'Täsmähaku pyörii taustasäikeessä. Voit perua ilman, että sivu jumittuu.'
      : 'Jokainen piste on yksi solu. Yhdistetyillä soluilla on oltava eri väri. Lihavoidut numerot ovat vihjeitä.';
    $('stat-valmis').textContent = busy ? 'Haetaan…' : 'Valmis. Muokkaa vihjeitä ja paina Ratkaise.';
    return;
  }
  const unique = result.unique === true
    ? 'Yksikäsitteinen ratkaisu'
    : result.solutions_found > 1
      ? 'Useita ratkaisuja — näytetään yksi'
      : 'Ratkaisu löytyi — yksikäsitteisyyttä ei vahvistettu';
  if (result.status === 'solved') {
    $('status').textContent = `${unique} · ${result.stats.search_nodes.toLocaleString()} hakutilaa`;
  } else if (result.status === 'unsatisfiable') {
    $('status').textContent = 'Näillä vihjeillä ei ole ratkaisua. Haku kävi kaikki haarat.';
  } else {
    $('status').textContent = `${result.error} Ei vielä johtopäätöstä; kasvata aikarajaa ja ratkaise uudelleen.`;
  }
  if (result.status === 'solved' && result.error) {
    $('status').textContent += ` · ${result.error}`;
  }
  let detail;
  if (solutionView) {
    detail = 'Näytetään laskettu ratkaisu.';
  } else if (event) {
    const rc = `r${Math.floor(event.vertex / 9) + 1}s${event.vertex % 9 + 1}`;
    if (event.kind === 'assign') {
      detail = `${rc}: väri ${event.color}. Sallitut: ${event.allowed.join(', ')}.`;
    } else if (event.kind === 'undo') {
      detail = `Takaisinotto: poista ${event.previous_color} solusta ${rc}.`;
    } else {
      detail = `Umpikuja solussa ${rc}: kaikki yhdeksän väriä ovat estettyjä.`;
    }
  } else {
    detail = `${result.stats.recorded_assignments.toLocaleString()} tallennettua sijoitusta · ${result.stats.recorded_undos.toLocaleString()} takaisinottoa. Toista tai selaa varsinaista hakua.`;
  }
  if (result.trace_complete === false) {
    detail += ` Toisto sisältää vain ensimmäiset ${count.toLocaleString()} tapahtumaa; haku jatkui niiden jälkeen.`;
  }
  $('detail').textContent = detail;
  $('stat-valmis').textContent = result.status === 'solved'
    ? 'Ratkaisu valmis.'
    : result.status === 'unsatisfiable'
      ? 'Mahdoton palapeli.'
      : 'Haku kesken.';
}

function stopWorker() {
  if (worker) worker.terminate();
  if (workerURL) URL.revokeObjectURL(workerURL);
  worker = null;
  workerURL = null;
  busy = false;
}

function resetTrace(message) {
  stopWorker();
  playing = false;
  result = null;
  index = 0;
  solutionView = false;
  state = puzzle.slice();
  notice = message || 'Muokkaa vihjeitä ja paina Ratkaise.';
  isError = false;
  render();
}

function setIndex(n) {
  solutionView = false;
  index = Math.max(0, Math.min(n, result.trace.length));
  state = index ? result.trace[index - 1].after.slice() : puzzle.slice();
  render();
}

function loadPuzzle(value) {
  try {
    puzzle = solver.parsePuzzle(value);
    resetTrace();
  } catch (error) {
    resetTrace(error.message);
    isError = true;
    render();
  }
}

for (let i = 0; i < 81; i++) {
  const el = document.createElement('input');
  el.className = 'cell';
  el.type = 'text';
  el.inputMode = 'numeric';
  el.maxLength = 1;
  el.autocomplete = 'off';
  el.dataset.row = String(Math.floor(i / 9));
  el.dataset.col = String(i % 9);
  el.setAttribute('aria-label', `Rivi ${Math.floor(i / 9) + 1} sarake ${i % 9 + 1}`);
  el.addEventListener('input', () => {
    puzzle[i] = /^[1-9]$/.test(el.value) ? Number(el.value) : 0;
    resetTrace();
  });
  el.addEventListener('focus', () => el.select());
  el.addEventListener('keydown', event => {
    const d = {ArrowRight: 1, ArrowLeft: -1, ArrowUp: -9, ArrowDown: 9}[event.key];
    if (d !== undefined && cells[i + d]) {
      event.preventDefault();
      cells[i + d].focus();
    }
  });
  el.addEventListener('paste', event => {
    const text = event.clipboardData.getData('text');
    if (text.replace(/\s/g, '').length > 1) {
      event.preventDefault();
      loadPuzzle(text);
    }
  });
  cells.push(el);
  $('board').append(el);
}

$('solve').onclick = () => {
  resetTrace();
  try {
    solver.validateGivens(puzzle);
    const code = `const solver = (${createSudokuSolver.toString()})();
      onmessage = ({data}) => {
        try { postMessage({type:'result', result:solver.solve(data.puzzle, data.options,
          progress => postMessage({type:'progress', progress}))}); }
        catch (error) { postMessage({type:'error', error:error.message}); }
      };`;
    workerURL = URL.createObjectURL(new Blob([code], {type: 'text/javascript'}));
    worker = new Worker(workerURL);
    const activeWorker = worker;
    busy = true;
    notice = 'Ajetaan täsmällistä graafiväritystä…';
    render();
    worker.onmessage = ({data}) => {
      if (worker !== activeWorker) return;
      if (data.type === 'progress') {
        const p = data.progress;
        $('status').textContent = `${p.solutions_found ? 'Ratkaisu löytyi; tarkistetaan yksikäsitteisyyttä' : 'Haetaan'} · ${p.search_nodes.toLocaleString()} tilaa · ${(p.elapsed_ms / 1000).toFixed(1)}s`;
        return;
      }
      stopWorker();
      if (data.type === 'error') {
        notice = data.error;
        isError = true;
      } else {
        result = data.result;
        isError = result.status !== 'solved';
      }
      render();
    };
    worker.onerror = event => {
      if (worker !== activeWorker) return;
      stopWorker();
      notice = event.message || 'Hakusäie ei käynnistynyt.';
      isError = true;
      render();
    };
    worker.postMessage({
      puzzle,
      options: {checkUnique: $('unique').checked, timeoutMs: Number($('timeout').value)}
    });
  } catch (error) {
    stopWorker();
    notice = error.message;
    isError = true;
    render();
  }
};

$('cancel').onclick = () => resetTrace('Haku peruttu. Vihjeet säilyivät.');
$('play').onclick = () => {
  if (solutionView || index >= result.trace.length) setIndex(0);
  playing = !playing;
  last = performance.now();
  render();
};
$('previous').onclick = () => setIndex(solutionView ? result.trace.length : index - 1);
$('next').onclick = () => setIndex(index + 1);
$('finish').onclick = () => {
  playing = false;
  solutionView = true;
  state = result.solution.slice();
  render();
};
$('seek').oninput = () => {
  playing = false;
  setIndex(Number($('seek').value));
};
$('reset').onclick = () => resetTrace();
$('clear').onclick = () => loadPuzzle(examples.empty);
$('example').onchange = () => loadPuzzle(examples[$('example').value]);
$('colors').onchange = render;
$('load-text').onclick = () => loadPuzzle($('puzzle-text').value);
$('copy').onclick = async () => {
  const text = Array.from({length: 9}, (_, row) => result.solution.slice(row * 9, row * 9 + 9).join('')).join('\n');
  try {
    await navigator.clipboard.writeText(text);
    $('detail').textContent = 'Ratkaisu kopioitu.';
  } catch {
    $('puzzle-text').value = text;
    $('puzzle-text').focus();
    $('puzzle-text').select();
    $('detail').textContent = 'Ratkaisu valittu alla. Kopioi Ctrl+C.';
  }
};
$('download').onclick = () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2) + '\n'], {type: 'application/json'}));
  const a = document.createElement('a');
  a.href = url;
  a.download = 'sudoku-trace.json';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

function tick(now) {
  if (playing && result) {
    const interval = 125 / Number($('speed').value);
    const count = Math.floor((now - last) / interval);
    if (count > 0) {
      last = now;
      setIndex(index + count);
      if (index >= result.trace.length) {
        playing = false;
        render();
      }
    }
  }
  requestAnimationFrame(tick);
}

function updateClock() {
  const now = new Date();
  $('clock').textContent = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
}

function setMinimized(hidden) {
  $('app-window').classList.toggle('hidden-window', hidden);
  $('task-btn').classList.toggle('active', !hidden);
  $('desktop-icon').classList.toggle('selected', !hidden);
}

function restoreWindow() {
  setMinimized(false);
}

$('btn-min').onclick = () => setMinimized(true);
$('btn-close').onclick = () => setMinimized(true);
$('task-btn').onclick = () => setMinimized($('app-window').classList.contains('hidden-window') ? false : true);
$('desktop-icon').onclick = restoreWindow;
$('desktop-icon').ondblclick = restoreWindow;
if ($('btn-start')) $('btn-start').onclick = restoreWindow;

updateClock();
setInterval(updateClock, 1000);
render();
requestAnimationFrame(tick);
