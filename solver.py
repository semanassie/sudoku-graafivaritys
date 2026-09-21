#!/usr/bin/env python3
"""Exact Sudoku precoloring extension on its constraint graph. Standard library only."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEMO = "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
COLORS = frozenset(range(1, 10))


class PuzzleError(ValueError):
    pass


def parse_puzzle(value):
    if isinstance(value, str):
        value = "".join(c for c in value if not c.isspace() and c not in "|+-")
        if len(value) != 81 or any(c not in "0123456789." for c in value):
            raise PuzzleError("Enter exactly 81 digits; use 0 or . for an empty cell.")
        return [0 if c == "." else int(c) for c in value]
    if not isinstance(value, (list, tuple)) or len(value) != 81:
        raise PuzzleError("A puzzle must contain 81 cells.")
    if any(type(v) is not int or not 0 <= v <= 9 for v in value):
        raise PuzzleError("Each cell must be an integer from 0 to 9.")
    return list(value)


def box(i):
    return i // 27 * 3 + i % 9 // 3


def build_graph():
    """One vertex per cell; edges encode row, column, or box inequality."""
    neighbors = [set() for _ in range(81)]
    for i in range(81):
        for j in range(i + 1, 81):
            if i // 9 == j // 9 or i % 9 == j % 9 or box(i) == box(j):
                neighbors[i].add(j)
                neighbors[j].add(i)
    edges = [(i, j) for i, ns in enumerate(neighbors) for j in sorted(ns) if i < j]
    return neighbors, edges


NEIGHBORS, EDGES = build_graph()


def validate_givens(puzzle):
    for i, j in EDGES:
        if puzzle[i] and puzzle[i] == puzzle[j]:
            raise PuzzleError(
                f"Conflicting givens at r{i // 9 + 1}c{i % 9 + 1} and "
                f"r{j // 9 + 1}c{j % 9 + 1}: both are {puzzle[i]}."
            )


def legal_colors(state, vertex):
    return sorted(COLORS - {state[j] for j in NEIGHBORS[vertex]})


def choose_vertex(state, previous=40):
    """DSATUR: highest neighbor-color saturation; spatial ties stabilize the display."""
    uncolored = [i for i, value in enumerate(state) if value == 0]
    if not uncolored:
        return None

    def key(i):
        saturation = len({state[j] for j in NEIGHBORS[i] if state[j]})
        distance = (i // 9 - previous // 9) ** 2 + (i % 9 - previous % 9) ** 2
        return saturation, -distance, -i

    return max(uncolored, key=key)


def solve(puzzle=DEMO, *, check_unique=True, event_limit=100000, timeout=20.0):
    """Find an exact 9-coloring, retaining every assignment, dead end, and undo.

    No answer grid is accepted or stored. Colors are chosen solely from adjacent
    vertices. The uniqueness search continues after the first solution without
    changing the saved first-solution trace. A time limit is reported explicitly.
    """
    puzzle = parse_puzzle(puzzle)
    validate_givens(puzzle)
    state = puzzle.copy()
    events = []
    answers = []
    first_trace = None
    limit = 2 if check_unique else 1
    start = time.perf_counter()
    stats = {"search_nodes": 0, "assignments": 0, "undos": 0, "dead_ends": 0}

    def event(kind, vertex, color, previous_color, candidates, before):
        if first_trace is not None:
            return
        if len(events) >= event_limit:
            raise TimeoutError(
                f"Trace exceeded {event_limit} events; no result has been fabricated."
            )
        events.append(
            {
                "kind": kind,
                "vertex": vertex,
                "color": color,
                "previous_color": previous_color,
                "allowed": list(candidates),
                "before": before,
                "after": state.copy(),
            }
        )

    def visit(previous):
        nonlocal first_trace
        stats["search_nodes"] += 1
        if time.perf_counter() - start > timeout:
            raise TimeoutError(f"Search exceeded {timeout:g} seconds.")
        vertex = choose_vertex(state, previous)
        if vertex is None:
            answers.append(state.copy())
            if first_trace is None:
                first_trace = list(events)
            return len(answers) >= limit
        choices = legal_colors(state, vertex)
        if not choices:
            stats["dead_ends"] += 1
            event("dead_end", vertex, 0, 0, [], state.copy())
            return False
        for color in choices:
            before = state.copy()
            state[vertex] = color
            stats["assignments"] += 1
            event("assign", vertex, color, 0, choices, before)
            if visit(vertex):
                return True
            before = state.copy()
            state[vertex] = 0
            stats["undos"] += 1
            event("undo", vertex, 0, color, choices, before)
        return False

    exhausted = False
    search_error = None
    try:
        exhausted = not visit(40)
    except TimeoutError as exc:
        search_error = str(exc)

    trace = first_trace if first_trace is not None else events
    solution = answers[0] if answers else None
    status = "solved" if solution else "incomplete" if search_error else "unsatisfiable"
    if check_unique and exhausted and not search_error:
        unique = len(answers) == 1
    elif len(answers) >= 2:
        unique = False
    else:
        unique = None
    result = {
        "schema": 1,
        "status": status,
        "algorithm": "DSATUR exact 9-coloring with backtracking",
        "puzzle": puzzle,
        "solution": solution,
        "trace": trace,
        "unique": unique,
        "solutions_found": len(answers),
        "search_exhausted": exhausted,
        "solution_count_limit": limit,
        "error": search_error,
        "graph": {
            "vertices": 81,
            "edges": EDGES,
            "edge_count": len(EDGES),
            "degrees": [len(x) for x in NEIGHBORS],
            "colors": 9,
        },
        "stats": {
            **stats,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
            "recorded_assignments": sum(e["kind"] == "assign" for e in trace),
            "recorded_undos": sum(e["kind"] == "undo" for e in trace),
            "recorded_dead_ends": sum(e["kind"] == "dead_end" for e in trace),
        },
        "solver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    result["trace_sha256"] = hashlib.sha256(
        json.dumps(trace, separators=(",", ":")).encode()
    ).hexdigest()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group()
    source.add_argument("--puzzle", help="81 digits, with 0 or . for blanks")
    source.add_argument("--puzzle-file", type=Path)
    p.add_argument(
        "--out", type=Path, help="Write the full graph, solution and actual trace as JSON"
    )
    p.add_argument("--first-only", action="store_true", help="Skip the separate uniqueness search")
    p.add_argument("--timeout", type=float, default=20.0)
    args = p.parse_args()
    puzzle = args.puzzle_file.read_text() if args.puzzle_file else args.puzzle or DEMO
    try:
        result = solve(puzzle, check_unique=not args.first_only, timeout=args.timeout)
    except PuzzleError as exc:
        p.error(str(exc))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{result['status']}; vertices=81 edges=810; unique={result['unique']}")
    if result["solution"]:
        for r in range(9):
            print(" ".join(map(str, result["solution"][r * 9 : r * 9 + 9])))
    print(json.dumps(result["stats"], sort_keys=True))
    if result["error"]:
        print(result["error"])
    if args.out:
        print(args.out.resolve())
    raise SystemExit(0 if result["status"] == "solved" else 2)


if __name__ == "__main__":
    main()
