#!/usr/bin/env python3
"""Behavior tests use an independent trace replay and independent Sudoku search."""
import copy
import json
import unittest
from pathlib import Path

from solver import solve, parse_puzzle, PuzzleError, DEMO
from verify import verify_result, independent_solution_count

ROOT = Path(__file__).resolve().parent


class SolverTests(unittest.TestCase):
    def assert_verified(self, result):
        self.assertTrue(verify_result(result)["valid"])
        count = independent_solution_count(result["puzzle"])
        self.assertEqual(result["solutions_found"], count)
        return result

    def test_recorded_puzzle_unique_and_trace_valid(self):
        r = self.assert_verified(solve(DEMO))
        self.assertTrue(r["unique"])
        self.assertEqual(r["stats"]["recorded_assignments"], 51)
        self.assertEqual(r["stats"]["recorded_undos"], 0)

    def test_real_backtracking_and_every_rollback(self):
        r = self.assert_verified(solve((ROOT / "puzzles/backtracking.txt").read_text()))
        self.assertTrue(r["unique"])
        self.assertGreater(r["stats"]["recorded_undos"], 0)
        self.assertGreater(r["stats"]["recorded_dead_ends"], 0)

    def test_locally_valid_but_unsatisfiable(self):
        p = parse_puzzle(DEMO)
        p[2] = 1
        r = self.assert_verified(solve(p))
        self.assertEqual(r["status"], "unsatisfiable")
        self.assertIsNone(r["solution"])

    def test_conflicting_givens_rejected(self):
        with self.assertRaises(PuzzleError):
            solve("55" + DEMO[2:])

    def test_already_solved_board_has_no_invented_moves(self):
        solved = solve(DEMO)["solution"]
        r = self.assert_verified(solve(solved))
        self.assertEqual(r["solution"], solved)
        self.assertEqual(r["trace"], [])

    def test_empty_board_reports_multiple_solutions(self):
        r = self.assert_verified(solve("0" * 81))
        self.assertFalse(r["unique"])
        self.assertEqual(r["solutions_found"], 2)

    def test_permuted_puzzle_is_computed_from_input(self):
        old = solve(DEMO)

        def transform(board):
            b = [((v + 2) % 9 + 1) if v else 0 for v in board]
            b[0:9], b[9:18] = b[9:18], b[0:9]
            return b

        r = self.assert_verified(solve(transform(old["puzzle"])))
        self.assertEqual(r["solution"], transform(old["solution"]))
        self.assertNotEqual(r["solution"], old["solution"])

    def test_bad_input_is_rejected(self):
        for value in ["", "0" * 80, [True] * 81, [10] * 81, "a" * 81]:
            with self.subTest(value=str(value)[:12]), self.assertRaises(PuzzleError):
                solve(value)

    def test_tampered_trace_is_rejected(self):
        r = copy.deepcopy(solve(DEMO))
        r["trace"][0]["color"] = r["trace"][0]["color"] % 9 + 1
        with self.assertRaises(AssertionError):
            verify_result(r)

    def test_missing_constraint_is_rejected(self):
        r = copy.deepcopy(solve(DEMO))
        r["graph"]["edges"] = r["graph"]["edges"][1:]
        with self.assertRaises(AssertionError):
            verify_result(r)

    def test_graph_has_eighty_one_vertices_and_eight_ten_edges(self):
        r = solve(DEMO, check_unique=False)
        self.assertEqual(r["graph"]["vertices"], 81)
        self.assertEqual(r["graph"]["edge_count"], 810)
        self.assertEqual(len(r["graph"]["edges"]), 810)
        self.assertTrue(all(d == 20 for d in r["graph"]["degrees"]))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SolverTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "passed": result.wasSuccessful(),
        "cases": sorted(name for name in dir(SolverTests) if name.startswith("test_")),
    }
    (ROOT / "qa").mkdir(exist_ok=True)
    (ROOT / "qa/test-results.json").write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
