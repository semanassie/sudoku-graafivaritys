#!/usr/bin/env python3
"""Independent trace replay and Sudoku validation; does not import solver.py."""
import argparse
import itertools
import json
from pathlib import Path


def units():
    return (
        [list(range(r * 9, r * 9 + 9)) for r in range(9)]
        + [[r * 9 + c for r in range(9)] for c in range(9)]
        + [
            [(br * 3 + r) * 9 + bc * 3 + c for r in range(3) for c in range(3)]
            for br in range(3)
            for bc in range(3)
        ]
    )


UNITS = units()
EXPECTED_EDGES = {
    tuple(sorted((a, b))) for unit in UNITS for a, b in itertools.combinations(unit, 2)
}


def allowed(state, vertex):
    related = set().union(*(set(u) for u in UNITS if vertex in u)) - {vertex}
    return sorted(set(range(1, 10)) - {state[i] for i in related})


def check_partial(state):
    assert len(state) == 81 and all(type(v) is int and 0 <= v <= 9 for v in state)
    for unit in UNITS:
        filled = [state[i] for i in unit if state[i]]
        assert len(filled) == len(set(filled)), "A row, column or box contains a repeated color"


def verify_result(result):
    puzzle = list(result["puzzle"])
    state = puzzle.copy()
    check_partial(state)
    assert result["graph"]["vertices"] == 81
    assert len(result["graph"]["edges"]) == 810
    actual_edges = {tuple(e) for e in result["graph"]["edges"]}
    assert actual_edges == EXPECTED_EDGES, "Graph omits or invents a Sudoku constraint"
    stack = []
    assigned = undone = dead_ends = 0
    for number, e in enumerate(result["trace"]):
        assert e["before"] == state, f"Trace discontinuity at event {number}"
        i = e["vertex"]
        assert 0 <= i < 81 and not puzzle[i], "A clue was overwritten"
        if e["kind"] == "assign":
            assert state[i] == 0 and e["previous_color"] == 0
            choices = allowed(state, i)
            assert e["allowed"] == choices and e["color"] in choices
            state[i] = e["color"]
            stack.append((i, e["color"]))
            assigned += 1
        elif e["kind"] == "undo":
            assert stack and stack.pop() == (i, e["previous_color"]), "Backtracking is not LIFO"
            assert state[i] == e["previous_color"] and e["color"] == 0
            state[i] = 0
            undone += 1
        elif e["kind"] == "dead_end":
            assert state[i] == 0 and allowed(state, i) == [] and e["allowed"] == []
            dead_ends += 1
        else:
            raise AssertionError("Unknown event kind")
        assert e["after"] == state, f"Incorrect state after event {number}"
        check_partial(state)
        assert all(not v or state[i] == v for i, v in enumerate(puzzle)), "A clue changed"
    if result["status"] == "solved":
        solution = result["solution"]
        check_partial(solution)
        assert all(solution) and all(not v or solution[i] == v for i, v in enumerate(puzzle))
        if result.get("trace_complete", True):
            assert state == solution
        for unit in UNITS:
            assert {solution[i] for i in unit} == set(range(1, 10))
    elif result["status"] == "unsatisfiable":
        assert result["solution"] is None
        if result.get("trace_complete", True):
            assert state == puzzle and not stack
        assert result["search_exhausted"]
    return {
        "valid": True,
        "events": len(result["trace"]),
        "assignments": assigned,
        "undos": undone,
        "dead_ends": dead_ends,
        "graph_edges_checked": 810,
        "sudoku_units_checked": 27,
        "status": result["status"],
    }


def independent_solution_count(puzzle, limit=2):
    """A separate row/column/box bitmask search checks solution multiplicity."""
    state = list(puzzle)
    rows, cols, boxes = [0] * 9, [0] * 9, [0] * 9
    for i, v in enumerate(state):
        if not v:
            continue
        r, c = divmod(i, 9)
        b, bit = r // 3 * 3 + c // 3, 1 << (v - 1)
        if (rows[r] | cols[c] | boxes[b]) & bit:
            return 0
        rows[r] |= bit
        cols[c] |= bit
        boxes[b] |= bit
    found = 0

    def visit():
        nonlocal found
        best, mask = None, 0
        for i, v in enumerate(state):
            if v:
                continue
            r, c = divmod(i, 9)
            m = 511 & ~(rows[r] | cols[c] | boxes[r // 3 * 3 + c // 3])
            if not m:
                return
            if best is None or m.bit_count() < mask.bit_count():
                best, mask = i, m
        if best is None:
            found += 1
            return
        r, c = divmod(best, 9)
        b = r // 3 * 3 + c // 3
        while mask and found < limit:
            bit = mask & -mask
            mask -= bit
            state[best] = bit.bit_length()
            rows[r] |= bit
            cols[c] |= bit
            boxes[b] |= bit
            visit()
            rows[r] ^= bit
            cols[c] ^= bit
            boxes[b] ^= bit
            state[best] = 0

    visit()
    return found


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("trace", type=Path)
    args = p.parse_args()
    result = json.loads(args.trace.read_text())
    report = verify_result(result)
    report["independent_solutions_up_to_two"] = independent_solution_count(result["puzzle"])
    if result["unique"] is True:
        assert report["independent_solutions_up_to_two"] == 1
    print(json.dumps(report, indent=2))
