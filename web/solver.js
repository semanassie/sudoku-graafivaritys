/* Exact Sudoku graph coloring. No libraries, answer tables, or remote calls. */
'use strict';

function createSudokuSolver() {
  const peers = Array.from({length: 81}, () => []);
  const edges = [];
  const box = i => Math.floor(i / 27) * 3 + Math.floor(i % 9 / 3);
  for (let i = 0; i < 81; i++) {
    for (let j = i + 1; j < 81; j++) {
      if (Math.floor(i / 9) === Math.floor(j / 9) || i % 9 === j % 9 || box(i) === box(j)) {
        peers[i].push(j);
        peers[j].push(i);
        edges.push([i, j]);
      }
    }
  }

  function parsePuzzle(value) {
    if (typeof value === 'string') {
      const text = value.replace(/[\s|+\-]/g, '');
      if (!/^[0-9.]{81}$/.test(text)) {
        throw new Error('Enter exactly 81 digits; use 0 or . for an empty cell.');
      }
      return Array.from(text, c => c === '.' ? 0 : Number(c));
    }
    if (!Array.isArray(value) || value.length !== 81 ||
        Array.from(value).some(v => !Number.isInteger(v) || v < 0 || v > 9)) {
      throw new Error('A puzzle must contain 81 integers from 0 to 9.');
    }
    return value.slice();
  }

  function validateGivens(puzzle) {
    for (const [i, j] of edges) {
      if (puzzle[i] && puzzle[i] === puzzle[j]) {
        throw new Error(`Conflicting givens at r${Math.floor(i / 9) + 1}c${i % 9 + 1} and ` +
          `r${Math.floor(j / 9) + 1}c${j % 9 + 1}: both are ${puzzle[i]}.`);
      }
    }
  }

  function solve(input, options = {}, onProgress = () => {}) {
    const puzzle = parsePuzzle(input);
    validateGivens(puzzle);
    const checkUnique = options.checkUnique !== false;
    const timeoutMs = options.timeoutMs ?? 30000;
    const maxTraceEvents = options.maxTraceEvents ?? 20000;
    if (!Number.isFinite(timeoutMs) || timeoutMs < 0 ||
        !Number.isInteger(maxTraceEvents) || maxTraceEvents < 0) {
      throw new Error('Timeout and trace limit must be nonnegative; the trace limit must be an integer.');
    }
    const state = puzzle.slice();
    const trace = [], answers = [];
    const stats = {search_nodes: 0, assignments: 0, undos: 0, dead_ends: 0};
    const started = performance.now();
    let lastProgress = started, firstFound = false, truncated = false, searchError = null;
    const limit = checkUnique ? 2 : 1;

    function record(kind, vertex, color, previousColor, choices, before) {
      if (firstFound) return;
      if (trace.length >= maxTraceEvents) {
        truncated = true;
        return;
      }
      trace.push({kind, vertex, color, previous_color: previousColor,
        allowed: choices.slice(), before, after: state.slice()});
    }

    function visit(previous) {
      stats.search_nodes++;
      const now = performance.now();
      if (timeoutMs && now - started >= timeoutMs) {
        throw new Error(`Search reached the ${timeoutMs / 1000} second limit.`);
      }
      if (now - lastProgress >= 150) {
        lastProgress = now;
        onProgress({...stats, elapsed_ms: now - started, solutions_found: answers.length});
      }

      let vertex = -1, bestSaturation = -1, bestDistance = Infinity, chosenMask = 0;
      for (let i = 0; i < 81; i++) {
        if (state[i]) continue;
        let used = 0;
        for (const j of peers[i]) if (state[j]) used |= 1 << state[j];
        let bits = used, saturation = 0;
        while (bits) { bits &= bits - 1; saturation++; }
        const distance = (Math.floor(i / 9) - Math.floor(previous / 9)) ** 2 +
          (i % 9 - previous % 9) ** 2;
        if (saturation > bestSaturation || (saturation === bestSaturation && distance < bestDistance)) {
          vertex = i;
          bestSaturation = saturation;
          bestDistance = distance;
          chosenMask = used;
        }
      }
      if (vertex === -1) {
        answers.push(state.slice());
        firstFound = true;
        return answers.length >= limit;
      }
      const choices = [];
      for (let color = 1; color <= 9; color++) if (!(chosenMask & (1 << color))) choices.push(color);
      if (!choices.length) {
        stats.dead_ends++;
        record('dead_end', vertex, 0, 0, [], state.slice());
        return false;
      }
      for (const color of choices) {
        const before = !firstFound && !truncated ? state.slice() : null;
        state[vertex] = color;
        stats.assignments++;
        record('assign', vertex, color, 0, choices, before);
        if (visit(vertex)) return true;
        const assigned = !firstFound && !truncated ? state.slice() : null;
        state[vertex] = 0;
        stats.undos++;
        record('undo', vertex, 0, color, choices, assigned);
      }
      return false;
    }

    let exhausted = false;
    try { exhausted = !visit(40); }
    catch (error) {
      if (!error.message.startsWith('Search reached the ')) throw error;
      searchError = error.message;
    }
    const solution = answers[0] || null;
    const unique = answers.length >= 2 ? false : checkUnique && exhausted && !searchError ? answers.length === 1 : null;
    return {
      schema: 1, implementation: 'JavaScript', status: solution ? 'solved' : searchError ? 'incomplete' : 'unsatisfiable',
      algorithm: 'DSATUR exact 9-coloring with backtracking', puzzle, solution, trace,
      trace_complete: !truncated, unique, solutions_found: answers.length,
      search_exhausted: exhausted, solution_count_limit: limit, error: searchError,
      graph: {vertices: 81, edges, edge_count: edges.length, degrees: peers.map(p => p.length), colors: 9},
      stats: {...stats, elapsed_ms: Math.round((performance.now() - started) * 1000) / 1000,
        recorded_assignments: trace.filter(e => e.kind === 'assign').length,
        recorded_undos: trace.filter(e => e.kind === 'undo').length,
        recorded_dead_ends: trace.filter(e => e.kind === 'dead_end').length}
    };
  }
  return {solve, parsePuzzle, validateGivens, peers, edges};
}

if (typeof module !== 'undefined' && module.exports) module.exports = {createSudokuSolver};
