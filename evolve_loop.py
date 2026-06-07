"""Aero AutoDev — Deterministic Inventory Completion orchestrator.

Replaces the legacy time-locked evolution loop with a workload-bounded driver.
The execution model is:

  1. AST discovery: parse the targeted external repository with the Tree-Sitter
     frontend and index every eligible hot-path / math calculation candidate.
     The total is bound once to the global ``Total_Target_Count``.
  2. Stateful inventory tracking: an in-memory manifest records the convergence
     state of every target block.
  3. Convergence loop: each target is refactored, verified through the
     differential bit-level sandbox, and (on success) its native stack-allocated
     Aero FFI handle is committed to disk and the node is marked
     'Successfully Converged'.
  4. Deterministic termination: there are NO duration / clock / countdown
     conditions. The loop terminates the instant
     ``Converged_Target_Count == Total_Target_Count``.
  5. Stagnation escape: a per-target patience ceiling of 5,000 validation
     attempts bounds each block; idle spinning is prevented by escaping early
     when a block stalls with no fitness advancement.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from compile_production_swap import (
    ingest_target,
    parse_and_identify,
    generate_swapped_source,
    differential_verify,
    persist_swap,
    compile_project,
    serialize_swap_blueprint,
)
from translator import ffi_codegen

# Patience ceiling: the absolute maximum number of continuous validation
# attempts per target block before the stagnation-escape locks the block's
# highest stable state and advances the queue.
_PATIENCE_CEILING = 5000

# Global inventory counters. ``Total_Target_Count`` is bound exactly once during
# the AST discovery phase and treated as immutable thereafter.
Total_Target_Count = 0
Converged_Target_Count = 0


@dataclass
class TargetRecord:
    """Inventory tracking entry for a single hot-path target block."""
    name: str
    score: float
    lines: str
    hook: str = ""
    attempts: int = 0
    converged: bool = False
    processed: bool = False
    stable_state: str = "original"
    note: str = ""


# ---------------------------------------------------------------------------
# Phase 1: AST discovery
# ---------------------------------------------------------------------------

def discover_inventory(lib_rs_path: str):
    """Parse the target via the AST frontend and index hot-path candidates.

    Returns ``(hot_paths, cold_names)`` exactly as the AST-clamped engine sees
    them, so discovery and convergence operate on identical node boundaries.
    """
    return parse_and_identify(lib_rs_path)


# ---------------------------------------------------------------------------
# Phase 3: per-target convergence (bounded by the patience ceiling)
# ---------------------------------------------------------------------------

def _failure_signature(swapped_out: str) -> str:
    """Stable signature of a failed validation, used for stagnation detection.

    A deterministic transform yields an identical signature across attempts, so
    a repeated signature proves no fitness advancement is possible.
    """
    text = swapped_out or ""
    lowered = text.lower()
    if "compilation failed" in lowered or "error[" in lowered or "error:" in lowered:
        for line in text.splitlines():
            if "error" in line.lower():
                return f"compile:{line.strip()[:80]}"
        return "compile:unknown"
    return "diff_mismatch"


def converge_target(abs_target: str,
                    original_source: str,
                    converged_hotpaths: list,
                    hp,
                    aeroc_module: str,
                    record: TargetRecord) -> bool:
    """Attempt to converge a single target block within the patience ceiling.

    Each attempt regenerates the cumulative AST-clamped swap (already-converged
    blocks plus this candidate), verifies it in the differential sandbox, and on
    success commits the FFI handle to disk. Because the swap is deterministic,
    the idle-prevention guard escapes the moment a block stalls; the
    ``_PATIENCE_CEILING`` remains the hard upper bound on attempts.
    """
    candidate = converged_hotpaths + [hp]
    last_signature = None

    while record.attempts < _PATIENCE_CEILING:
        record.attempts += 1

        modified_lib, legacy_mod, ffi_mod = generate_swapped_source(
            original_source, candidate, aeroc_module,
        )
        passed, _legacy_out, swapped_out = differential_verify(
            abs_target, modified_lib, legacy_mod, ffi_mod,
        )

        if passed:
            # Safely commit the native stack-allocated Aero FFI handle to disk.
            for action in persist_swap(abs_target, modified_lib, legacy_mod,
                                       ffi_mod, candidate, aeroc_module):
                print(f"    {action}")
            return True

        signature = _failure_signature(swapped_out)
        record.note = signature

        if signature == last_signature:
            # No fitness advancement between attempts — deterministic stall.
            print(f"    [idle-prevention] attempt {record.attempts}: no fitness "
                  f"advancement; escaping (patience ceiling {_PATIENCE_CEILING}).")
            break
        last_signature = signature
        print(f"    [retry] attempt {record.attempts} failed: {signature}")

    if record.attempts >= _PATIENCE_CEILING:
        print(f"    [patience-exhausted] {record.attempts} attempts reached the "
              f"ceiling {_PATIENCE_CEILING}.")

    record.stable_state = f"held@{len(converged_hotpaths)}_converged"
    return False


# ---------------------------------------------------------------------------
# Phase 2 + 3 + 4: inventory completion loop
# ---------------------------------------------------------------------------

def run_inventory_completion(target_dir: str,
                             aeroc_module: str = "anyon_sim.aeroc") -> int:
    """Drive the deterministic inventory-completion loop to termination."""
    global Total_Target_Count, Converged_Target_Count

    abs_target = ingest_target(target_dir)
    lib_rs = os.path.join(abs_target, "src", "lib.rs")
    with open(lib_rs, "r", encoding="utf-8") as f:
        original_source = f.read()

    # --- Phase 1: AST discovery ---
    hot_paths, cold_names = discover_inventory(lib_rs)
    Total_Target_Count = len(hot_paths)
    Converged_Target_Count = 0
    print(f"\n[inventory] AST discovery complete — Total_Target_Count = {Total_Target_Count}")

    if Total_Target_Count == 0:
        print("[inventory] No eligible hot-path candidates; inventory already complete.")
        return 0

    # --- Phase 2: stateful inventory tracking matrix ---
    nodes = ffi_codegen.assign_nodes([hp.fn for hp in hot_paths])
    hook_by_name = {n.fn.name: n.hook for n in nodes}
    manifest: dict[str, TargetRecord] = {
        hp.name: TargetRecord(
            name=hp.name,
            score=hp.score,
            lines=f"{hp.start_line}-{hp.end_line}",
            hook=hook_by_name.get(hp.name, ""),
        )
        for hp in hot_paths
    }

    converged_hotpaths: list = []

    # --- Phase 3 + 4: convergence loop bounded by inventory completion ---
    for hp in hot_paths:
        record = manifest[hp.name]
        print(f"\n[converge] Target '{hp.name}' (score {hp.score:.1f}) -> {record.hook}")

        if converge_target(abs_target, original_source, converged_hotpaths,
                           hp, aeroc_module, record):
            converged_hotpaths.append(hp)
            record.converged = True
            record.processed = True
            record.stable_state = f"ffi:{record.hook}"
            Converged_Target_Count += 1
            print(f"[converge] '{hp.name}' Successfully Converged "
                  f"({Converged_Target_Count}/{Total_Target_Count})")
        else:
            record.processed = True
            print(f"[stagnation] '{hp.name}' locked at stable state "
                  f"'{record.stable_state}' after {record.attempts} attempt(s); "
                  f"advancing queue.")

        # Hard deterministic termination.
        if Converged_Target_Count == Total_Target_Count:
            print(f"\n[terminate] Converged_Target_Count == Total_Target_Count "
                  f"== {Total_Target_Count}. Inventory fully converged.")
            break

    # Final integrity check on the persisted target.
    if converged_hotpaths:
        ok, _ = compile_project(abs_target)
        print(f"[final] Persisted target compiles cleanly: {'YES' if ok else 'NO'}")

    _write_telemetry(abs_target, manifest)
    _print_summary(manifest)
    return 0 if Converged_Target_Count == Total_Target_Count else 2


# ---------------------------------------------------------------------------
# Dry run: AST discovery + blueprint, no disk modification
# ---------------------------------------------------------------------------

def run_discovery_only(target_dir: str,
                       aeroc_module: str = "anyon_sim.aeroc",
                       blueprint_path: str | None = None) -> int:
    """AST discovery phase only — emit blueprint.aero without modifying disk."""
    global Total_Target_Count

    abs_target = ingest_target(target_dir)
    lib_rs = os.path.join(abs_target, "src", "lib.rs")
    hot_paths, cold_names = discover_inventory(lib_rs)
    Total_Target_Count = len(hot_paths)

    blueprint = serialize_swap_blueprint(abs_target, hot_paths, cold_names, aeroc_module)
    out_path = blueprint_path or os.path.join(_HERE, "blueprint.aero")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(blueprint)

    nodes = ffi_codegen.assign_nodes([hp.fn for hp in hot_paths])
    print(f"\n[discovery] Total_Target_Count = {Total_Target_Count}")
    for hp, node in zip(hot_paths, nodes):
        print(f"  - {hp.name} (score {hp.score:.1f}, lines {hp.start_line}-{hp.end_line}) "
              f"-> aero_ffi::{node.hook}")
    print(f"[discovery] Cold paths preserved: {cold_names}")
    print(f"[discovery] Blueprint written (no disk modification): {out_path}")
    return 0


# ---------------------------------------------------------------------------
# Telemetry & reporting
# ---------------------------------------------------------------------------

def _write_telemetry(abs_target: str, manifest: dict[str, TargetRecord]) -> None:
    out_dir = os.path.join(_HERE, "build_sandbox")
    os.makedirs(out_dir, exist_ok=True)
    data = {
        "target": abs_target,
        "total_target_count": Total_Target_Count,
        "converged_target_count": Converged_Target_Count,
        "patience_ceiling": _PATIENCE_CEILING,
        "targets": {
            name: {
                "score": rec.score,
                "lines": rec.lines,
                "hook": rec.hook,
                "attempts": rec.attempts,
                "converged": rec.converged,
                "processed": rec.processed,
                "stable_state": rec.stable_state,
                "note": rec.note,
            }
            for name, rec in manifest.items()
        },
    }
    path = os.path.join(out_dir, "inventory_manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[telemetry] Inventory manifest written: {path}")


def _print_summary(manifest: dict[str, TargetRecord]) -> None:
    print("\n" + "=" * 70)
    print(" INVENTORY COMPLETION SUMMARY")
    print("=" * 70)
    print(f"  Total_Target_Count:     {Total_Target_Count}")
    print(f"  Converged_Target_Count: {Converged_Target_Count}")
    for rec in manifest.values():
        status = "CONVERGED" if rec.converged else "STAGNATED"
        print(f"  [{status:9s}] {rec.name:28s} attempts={rec.attempts} "
              f"hook={rec.hook or '-'}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Aero AutoDev — Deterministic Inventory Completion orchestrator",
    )
    parser.add_argument(
        '--target', required=True,
        help="External target repository to scan and converge (must contain src/lib.rs)",
    )
    parser.add_argument(
        '--execute-translation-swap', action='store_true',
        help="Run the deterministic inventory-completion convergence loop",
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help="AST discovery + blueprint.aero only; no disk modification",
    )
    parser.add_argument(
        '--module', default='anyon_sim.aeroc',
        help="Name of the .aeroc bytecode module for the FFI swap",
    )
    parser.add_argument(
        '--blueprint', default=None,
        help="Path for the emitted blueprint.aero (default: repo root)",
    )
    args, unknown = parser.parse_known_args()

    print("=" * 70)
    print(" Aero AutoDev — Deterministic Inventory Completion Engine")
    print("=" * 70)

    if args.dry_run:
        sys.exit(run_discovery_only(args.target, args.module, args.blueprint))

    if args.execute_translation_swap:
        sys.exit(run_inventory_completion(args.target, aeroc_module=args.module))

    print("[info] No action flag supplied. Use --execute-translation-swap to converge")
    print("[info] the inventory, or --dry-run for AST discovery + blueprint.")
    print("[info] Defaulting to a safe dry-run.")
    sys.exit(run_discovery_only(args.target, args.module, args.blueprint))


if __name__ == '__main__':
    main()
