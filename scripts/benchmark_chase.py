"""Seeded policy comparison; writes actual observations, never a strength claim."""
import argparse
import json
from pathlib import Path
from random import Random
from statistics import mean
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.chase import Rules, STRATEGIES, step
from src.chase_maps import load_arena, scenario


def runner_move(arena, state, mode, rng):
    observation = state.observation
    options = arena.reachable(state.runner, observation.rules.runner_budget)
    safe_exits = [n for n in options if n in observation.exits and n not in observation.hunters]
    if safe_exits:
        return safe_exits[0]
    safe = [n for n in options if n not in observation.hunters] or list(options)
    if mode == "random":
        return rng.choice(safe)
    if mode == "nearest_exit":
        return min(safe, key=lambda n: min(arena.distance(n, e) for e in observation.exits))
    # Uses only public hunter positions; risk is a heuristic, not predicted moves.
    def score(node):
        exit_distance = min(arena.distance(node, e) for e in observation.exits)
        exposure = sum(max(0, observation.rules.hunter_budget * 2 - arena.distance(h, node))
                       for h in observation.hunters)
        return exit_distance + 2 * exposure
    return min(safe, key=score)


def benchmark(source, seeds):
    arena = load_arena(source)
    results = []
    for runner_mode in ("random", "nearest_exit", "evasive"):
        for strategy in STRATEGIES:
            counts = {"escaped": 0, "caught": 0, "timeout": 0}
            turns, timings = [], []
            for seed in range(seeds):
                rng = Random(seed)
                state = scenario(arena, Rules(160, 160, 3, 18), seed)
                while state.status == "playing":
                    move = runner_move(arena, state, runner_mode, rng)
                    started = perf_counter()
                    previous = state
                    state = step(arena, state, move, strategy)
                    timings.append((perf_counter() - started) * 1000)
                    assert state.runner in state.observation.belief
                    assert arena.distance(previous.runner, state.runner) <= 160 + 1e-8
                    assert all(arena.distance(a, b) <= 160 + 1e-8 for a, b in
                               zip(previous.observation.hunters, state.observation.hunters))
                counts[state.status] += 1
                turns.append(state.observation.turn)
            results.append({"runner": runner_mode, "hunter": strategy, "games": seeds,
                            **counts, "mean_turns": round(mean(turns), 3),
                            "mean_step_ms": round(mean(timings), 3),
                            "max_step_ms": round(max(timings), 3)})
    return {"source": source, "nodes": len(arena.nodes), "edges": arena.graph.number_of_edges(),
            "rules": {"runner_budget": 160, "hunter_budget": 160, "reveal_every": 3, "max_turns": 18},
            "seeds": list(range(seeds)), "results": results,
            "limits": "Fixed scripted runners and starting layouts; not human play or optimal policies."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["demo", "osm"], default="demo")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.seeds <= 100:
        parser.error("--seeds must be between 1 and 100")
    result = benchmark(args.source, args.seeds)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
