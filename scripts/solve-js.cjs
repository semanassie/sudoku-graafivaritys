#!/usr/bin/env node
// JSON adapter used by independent Python tests. No dependencies.
'use strict';
const fs = require('node:fs');
const {createSudokuSolver} = require('../web/solver.js');
const solver = createSudokuSolver();
const requests = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = requests.map(({puzzle, options}) => {
  try { return solver.solve(puzzle, options); }
  catch (error) { return {error: error.message, status: 'invalid'}; }
});
process.stdout.write(JSON.stringify(results));
