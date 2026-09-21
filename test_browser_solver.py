"""Compare the browser engine with Python and independently verify its moves."""
import copy
import json
from pathlib import Path
import random
import shutil
import subprocess
import unittest

from solver import DEMO, parse_puzzle, solve
from verify import independent_solution_count, verify_result

ROOT = Path(__file__).resolve().parent


def javascript(requests):
    if not shutil.which("node"):
        raise RuntimeError("Node.js is required for browser solver tests.")
    output = subprocess.run(
        ["node", str(ROOT / "scripts/solve-js.cjs")],
        input=json.dumps(requests),
        text=True,
        capture_output=True,
        check=True,
        timeout=60,
    )
    return json.loads(output.stdout)


class BrowserSolverTests(unittest.TestCase):
    def test_python_javascript_parity_and_independent_replay(self):
        unsatisfiable = parse_puzzle(DEMO)
        unsatisfiable[2] = 1
        inputs = [
            DEMO,
            (ROOT / "puzzles/backtracking.txt").read_text(),
            unsatisfiable,
            [0] * 81,
            solve(DEMO)["solution"],
        ]
        actual = javascript([{"puzzle": puzzle} for puzzle in inputs])
        for puzzle, result in zip(inputs, actual):
            with self.subTest(puzzle=str(puzzle)[:20]):
                expected = json.loads(json.dumps(solve(puzzle)))
                for field in [
                    "solution",
                    "trace",
                    "status",
                    "unique",
                    "solutions_found",
                    "search_exhausted",
                    "graph",
                ]:
                    self.assertEqual(result[field], expected[field], field)
                self.assertTrue(verify_result(result)["valid"])
                self.assertEqual(
                    result["solutions_found"], independent_solution_count(result["puzzle"])
                )

    def test_transformed_puzzles_are_solved_from_their_clues(self):
        rng = random.Random(2026)
        original = solve(DEMO)
        cases, expected = [], []
        for _ in range(12):
            digits = list(range(1, 10))
            rng.shuffle(digits)
            rows, cols = [], []
            for target in (rows, cols):
                bands = [0, 1, 2]
                rng.shuffle(bands)
                for band in bands:
                    order = [0, 1, 2]
                    rng.shuffle(order)
                    target.extend(band * 3 + i for i in order)
            transpose = rng.choice([False, True])

            def transform(board, digits=digits, rows=rows, cols=cols, transpose=transpose):
                indexes = [c * 9 + r if transpose else r * 9 + c for r in rows for c in cols]
                return [digits[board[i] - 1] if board[i] else 0 for i in indexes]

            cases.append({"puzzle": transform(original["puzzle"])})
            expected.append(transform(original["solution"]))
        for result, solution in zip(javascript(cases), expected):
            self.assertEqual(result["solution"], solution)
            self.assertTrue(result["unique"])
            self.assertTrue(verify_result(result)["valid"])

    def test_truncated_trace_does_not_stop_search_or_invent_events(self):
        puzzle = (ROOT / "puzzles/backtracking.txt").read_text()
        result = javascript([{"puzzle": puzzle, "options": {"maxTraceEvents": 10}}])[0]
        self.assertEqual(result["status"], "solved")
        self.assertTrue(result["unique"])
        self.assertFalse(result["trace_complete"])
        self.assertEqual(len(result["trace"]), 10)
        self.assertEqual(result["trace"], solve(puzzle)["trace"][:10])
        self.assertTrue(verify_result(result)["valid"])
        tampered = copy.deepcopy(result)
        tampered["solution"][0] = 0
        with self.assertRaises(AssertionError):
            verify_result(tampered)

    def test_unsatisfiable_with_limited_recording_still_exhausts_search(self):
        puzzle = parse_puzzle(DEMO)
        puzzle[2] = 1
        result = javascript([{"puzzle": puzzle, "options": {"maxTraceEvents": 0}}])[0]
        self.assertEqual(result["status"], "unsatisfiable")
        self.assertTrue(result["search_exhausted"])
        self.assertFalse(result["trace_complete"])
        self.assertTrue(verify_result(result)["valid"])
        self.assertEqual(independent_solution_count(puzzle), 0)

    def test_timeout_is_incomplete_never_impossible_or_unique(self):
        result = javascript([{"puzzle": DEMO, "options": {"timeoutMs": 1e-12}}])[0]
        self.assertEqual(result["status"], "incomplete")
        self.assertFalse(result["search_exhausted"])
        self.assertIsNone(result["unique"])
        self.assertIsNone(result["solution"])
        self.assertTrue(verify_result(result)["valid"])

    def test_first_solution_mode_does_not_claim_uniqueness(self):
        result = javascript([{"puzzle": DEMO, "options": {"checkUnique": False, "timeoutMs": 0}}])[0]
        self.assertEqual(result["status"], "solved")
        self.assertIsNone(result["unique"])
        self.assertEqual(result["solutions_found"], 1)
        self.assertTrue(verify_result(result)["valid"])

    def test_invalid_input_and_conflicts_are_rejected(self):
        values = [
            "",
            "0" * 80,
            "a" * 81,
            [True] * 81,
            [10] * 81,
            [None] * 81,
            "55" + DEMO[2:],
            "0" * 81 + "1",
        ]
        for result in javascript([{"puzzle": value} for value in values]):
            self.assertEqual(result["status"], "invalid")
        for option in [{"timeoutMs": -1}, {"maxTraceEvents": -1}, {"maxTraceEvents": 1.5}]:
            self.assertEqual(
                javascript([{"puzzle": DEMO, "options": option}])[0]["status"], "invalid"
            )

    def test_multiline_and_dot_input(self):
        formatted = "\n".join(DEMO[i : i + 9].replace("0", ".") for i in range(0, 81, 9))
        result = javascript([{"puzzle": formatted}])[0]
        self.assertEqual(result["puzzle"], parse_puzzle(DEMO))
        self.assertTrue(verify_result(result)["valid"])


if __name__ == "__main__":
    unittest.main()
