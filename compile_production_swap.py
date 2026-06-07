"""Production Code Swap — AST-clamped atomic compilation utility.

Executes the Aero AutoDev translation pipeline against a real Rust target
codebase:

1. Ingest the target project (``--target``).
2. Parse ``src/lib.rs`` into a Tree-Sitter syntax tree and isolate hot
   calculation pathways by their AST ``function_item`` node boundaries.
3. Deactivate each hot path in place (``/* ... */`` clamped strictly to the
   node's byte coordinates) and inject a standardized ``unsafe extern "C"`` FFI hook.
4. Compile the modified project and run differential verification.
5. Persist only if outputs match legacy behaviour bit-for-bit; otherwise roll
   back automatically.

This module is import-friendly: :func:`dispatch_target_pipeline` is the shared
entrypoint used by both this CLI and ``evolve_loop.py``.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from translator.code_profiler import analyze_rust
from translator.cold_pass_router import analyze_routing_dispatch
from translator import rust_ast
from translator.rust_ast import RustFn, Edit
from translator import ffi_codegen


# Hot-path selection threshold (kept identical to the legacy pipeline).
_HOT_SCORE_THRESHOLD = 5.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class HotPath:
    """A hot-path function (AST node) selected for translation."""
    fn: RustFn
    score: float

    @property
    def name(self) -> str:
        return self.fn.name

    @property
    def start_line(self) -> int:
        return self.fn.start_line

    @property
    def end_line(self) -> int:
        return self.fn.end_line


@dataclass
class SwapResult:
    """Result of the production swap operation."""
    target_dir: str
    hot_paths_found: list[str] = field(default_factory=list)
    cold_paths_preserved: list[str] = field(default_factory=list)
    ffi_handles_generated: list[str] = field(default_factory=list)
    compilation_success: bool = False
    verification_passed: bool = False
    legacy_output: str = ""
    swapped_output: str = ""
    rolled_back: bool = False
    error: str = ""


# ---------------------------------------------------------------------------
# Phase 1: Ingest Target
# ---------------------------------------------------------------------------

def ingest_target(target_dir: str) -> str:
    """Validate the target directory and locate src/lib.rs."""
    abs_target = os.path.abspath(target_dir)
    if not os.path.isdir(abs_target):
        raise FileNotFoundError(f"Target directory not found: {abs_target}")

    lib_rs = os.path.join(abs_target, "src", "lib.rs")
    if not os.path.isfile(lib_rs):
        raise FileNotFoundError(f"No src/lib.rs found in target: {abs_target}")

    cargo_toml = os.path.join(abs_target, "Cargo.toml")
    if not os.path.isfile(cargo_toml):
        raise FileNotFoundError(f"No Cargo.toml found in target: {abs_target}")

    print(f"[ingest] Target: {abs_target}")
    print(f"[ingest] Found src/lib.rs ({os.path.getsize(lib_rs)} bytes)")
    return abs_target


# ---------------------------------------------------------------------------
# Phase 2: Parse Rust AST & Identify Hot Paths
# ---------------------------------------------------------------------------

def parse_and_identify(lib_rs_path: str) -> tuple[list[HotPath], list[str]]:
    """Parse src/lib.rs via Tree-Sitter and identify hot paths.

    Function boundaries and signatures come from the AST; complexity scoring
    and cold-path routing reuse the existing profiler/router (unchanged), so
    hot-path selection is identical to the legacy pipeline.
    """
    with open(lib_rs_path, "r", encoding="utf-8") as f:
        source = f.read()

    functions = rust_ast.extract_functions(source)

    # Complexity scores (analysis layer — unchanged), keyed by name.
    scores = {fp.name: fp.complexity_score for fp in analyze_rust(source, lib_rs_path)}

    # Cold-path routing (analysis layer — unchanged).
    routing = analyze_routing_dispatch(lib_rs_path)
    cold_names = {fr.name for fr in routing.functions if fr.is_cold_passthrough}

    hot_paths: list[HotPath] = []
    cold_preserved: list[str] = []

    for fn in functions:
        score = scores.get(fn.name, 0.0)
        if fn.name in cold_names or score < _HOT_SCORE_THRESHOLD:
            cold_preserved.append(fn.name)
            continue
        hot_paths.append(HotPath(fn=fn, score=score))

    print(f"[parse] Found {len(hot_paths)} hot path(s): {[h.name for h in hot_paths]}")
    print(f"[parse] Preserved {len(cold_preserved)} cold path(s): {cold_preserved}")
    return hot_paths, cold_preserved


# ---------------------------------------------------------------------------
# Phase 3: Generate Modified Source via AST-Clamped Splicing
# ---------------------------------------------------------------------------

def generate_swapped_source(
    original_source: str,
    hot_paths: list[HotPath],
    aeroc_module: str,
) -> tuple[str, str, str]:
    """Generate the modified lib.rs, the legacy module, and the FFI module.

    The modified lib.rs is produced by *byte-exact splicing*: each hot path's
    AST node is replaced with a deactivation comment clamped to that node's
    index boundaries followed by its FFI wrapper. ``mod`` declarations are
    injected at a byte-exact anchor. No regex / line-slicing / ``.replace``
    source mutation is involved.
    """
    nodes = ffi_codegen.assign_nodes([hp.fn for hp in hot_paths])

    edits: list[Edit] = []
    for node in nodes:
        original = node.fn.node_text(original_source)
        deactivated = rust_ast.deactivation_block(
            original, f"node{node.index}", node.hook,
        )
        wrapper = ffi_codegen.generate_wrapper_fn(node)
        edits.append(Edit(
            start=node.fn.start_byte,
            end=node.fn.end_byte,
            replacement=f"{deactivated}\n\n{wrapper}",
        ))

    anchor = rust_ast.module_anchor_byte(original_source)
    edits.append(Edit(start=anchor, end=anchor, replacement="\n\nmod legacy;\nmod aero_ffi;"))

    modified_lib = rust_ast.apply_edits(original_source, edits)
    legacy_mod = ffi_codegen.generate_legacy_dispatch(nodes)
    ffi_mod = ffi_codegen.generate_aero_ffi_module(nodes, aeroc_module)
    return modified_lib, legacy_mod, ffi_mod


# ---------------------------------------------------------------------------
# Phase 3b: Blueprint emission (dry run)
# ---------------------------------------------------------------------------

def serialize_swap_blueprint(target_dir: str,
                             hot_paths: list[HotPath],
                             cold_names: list[str],
                             aeroc_module: str) -> str:
    """Render the planned swap as a ``blueprint.aero`` mapping configuration."""
    nodes = ffi_codegen.assign_nodes([hp.fn for hp in hot_paths])
    score_by_name = {hp.name: hp.score for hp in hot_paths}

    lines = [
        "[project]",
        f"name = {os.path.basename(os.path.abspath(target_dir))}",
        "version = 1.0",
        f"target = {os.path.abspath(target_dir)}",
        "source = src/lib.rs",
        f"module = {aeroc_module}",
        "generator = aero-autodev/ast-clamped",
        "",
        "[domain:hotpaths]",
        "",
    ]

    for node in nodes:
        fn = node.fn
        params = ", ".join(f"{p.name}:{p.ffi_type}" for p in fn.params) or "(none)"
        lines += [
            f"[domain:hotpaths:task:node{node.index}]",
            f"function = {fn.name}",
            f"lines = {fn.start_line}-{fn.end_line}",
            f"bytes = {fn.start_byte}-{fn.end_byte}",
            f"score = {score_by_name.get(fn.name, 0.0)}",
            f"hook = {node.hook}",
            f"params = {params}",
            f"returns = {fn.return_type}",
            "",
        ]

    if cold_names:
        lines.append("[cold_paths]")
        for cp in cold_names:
            lines.append(f"exclude = {cp}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 4: Compile & Differential Verification
# ---------------------------------------------------------------------------

def compile_project(project_dir: str) -> tuple[bool, str]:
    """Run cargo build on the project. Returns (success, output)."""
    result = subprocess.run(
        ["cargo", "build"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=180,
    )
    output = result.stdout + result.stderr
    return result.returncode == 0, output


def run_verification_binary(project_dir: str) -> tuple[bool, str]:
    """Run the verification binary and capture output."""
    result = subprocess.run(
        ["cargo", "run", "--bin", "anyon_verify"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = result.stdout
    success = result.returncode == 0 and "VERIFICATION_COMPLETE" in output
    return success, output


def differential_verify(
    target_dir: str,
    modified_lib: str,
    legacy_mod: str,
    ffi_mod: str,
) -> tuple[bool, str, str]:
    """Compile the modified project (in a temp copy) and compare outputs.

    Returns (passed, legacy_output, modified_output).
    """
    print("[verify] Running legacy binary for baseline output...")
    ok, legacy_output = run_verification_binary(target_dir)
    if not ok:
        return False, f"Legacy binary failed: {legacy_output}", ""

    print(f"[verify] Legacy baseline captured ({len(legacy_output)} bytes)")

    tmp_dir = tempfile.mkdtemp(prefix="aero_swap_")
    try:
        shutil.copytree(target_dir, os.path.join(tmp_dir, "project"),
                        dirs_exist_ok=True)
        proj_dir = os.path.join(tmp_dir, "project")
        src_dir = os.path.join(proj_dir, "src")

        with open(os.path.join(src_dir, "lib.rs"), "w") as f:
            f.write(modified_lib)
        with open(os.path.join(src_dir, "legacy.rs"), "w") as f:
            f.write(legacy_mod)
        with open(os.path.join(src_dir, "aero_ffi.rs"), "w") as f:
            f.write(ffi_mod)

        target_build = os.path.join(proj_dir, "target")
        if os.path.exists(target_build):
            shutil.rmtree(target_build)

        print("[verify] Compiling modified project...")
        ok, build_output = compile_project(proj_dir)
        if not ok:
            return False, legacy_output, f"Compilation failed:\n{build_output}"

        print("[verify] Modified project compiled successfully")

        print("[verify] Running modified binary...")
        ok, modified_output = run_verification_binary(proj_dir)
        if not ok:
            return False, legacy_output, f"Modified binary failed: {modified_output}"

        legacy_lines = [l for l in legacy_output.strip().split("\n") if l.strip()]
        modified_lines = [l for l in modified_output.strip().split("\n") if l.strip()]

        if legacy_lines == modified_lines:
            print("[verify] PASS — Outputs match exactly")
            return True, legacy_output, modified_output

        print("[verify] FAIL — Output mismatch detected")
        for i, (a, b) in enumerate(zip(legacy_lines, modified_lines)):
            if a != b:
                print(f"  Line {i}: legacy={a!r}")
                print(f"           swapped={b!r}")
        return False, legacy_output, modified_output

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Phase 5: Persist or Rollback
# ---------------------------------------------------------------------------

def persist_swap(
    target_dir: str,
    modified_lib: str,
    legacy_mod: str,
    ffi_mod: str,
    hot_paths: list[HotPath],
    aeroc_module: str,
) -> list[str]:
    """Write the verified swap to the target project."""
    src_dir = os.path.join(target_dir, "src")
    actions = []

    lib_rs = os.path.join(src_dir, "lib.rs")
    backup = lib_rs + ".pre_aero_backup"
    shutil.copy2(lib_rs, backup)
    actions.append(f"[backup] {lib_rs} -> {backup}")

    with open(lib_rs, "w") as f:
        f.write(modified_lib)
    actions.append(f"[write] {lib_rs} (AST-clamped FFI wrap)")

    with open(os.path.join(src_dir, "legacy.rs"), "w") as f:
        f.write(legacy_mod)
    actions.append("[write] src/legacy.rs (preserved implementations)")

    with open(os.path.join(src_dir, "aero_ffi.rs"), "w") as f:
        f.write(ffi_mod)
    actions.append("[write] src/aero_ffi.rs (zero-allocation bytecode bridge)")

    manifest = {
        "aeroc_module": aeroc_module,
        "hot_paths_swapped": [
            {"name": hp.name, "score": hp.score, "lines": f"{hp.start_line}-{hp.end_line}"}
            for hp in hot_paths
        ],
        "status": "verified_and_applied",
    }
    manifest_path = os.path.join(target_dir, "aero_swap_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    actions.append(f"[write] {manifest_path}")

    return actions


def rollback(target_dir: str) -> list[str]:
    """Restore the original source if verification failed."""
    src_dir = os.path.join(target_dir, "src")
    lib_rs = os.path.join(src_dir, "lib.rs")
    backup = lib_rs + ".pre_aero_backup"
    actions = []

    if os.path.exists(backup):
        shutil.copy2(backup, lib_rs)
        os.remove(backup)
        actions.append(f"[rollback] Restored {lib_rs} from backup")

    for fname in ("legacy.rs", "aero_ffi.rs"):
        fpath = os.path.join(src_dir, fname)
        if os.path.exists(fpath):
            os.remove(fpath)
            actions.append(f"[rollback] Removed {fpath}")

    return actions


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def execute_production_swap(target_dir: str,
                            aeroc_module: str = "anyon_sim.aeroc") -> SwapResult:
    """Execute the full atomic production code swap."""
    result = SwapResult(target_dir=target_dir)

    try:
        abs_target = ingest_target(target_dir)
        lib_rs_path = os.path.join(abs_target, "src", "lib.rs")

        with open(lib_rs_path, "r") as f:
            original_source = f.read()

        hot_paths, cold_paths = parse_and_identify(lib_rs_path)
        result.hot_paths_found = [hp.name for hp in hot_paths]
        result.cold_paths_preserved = cold_paths

        if not hot_paths:
            result.error = "No hot paths identified for translation"
            print(f"[abort] {result.error}")
            return result

        print(f"\n[swap] Generating AST-clamped FFI hooks for {len(hot_paths)} hot path(s)...")
        modified_lib, legacy_mod, ffi_mod = generate_swapped_source(
            original_source, hot_paths, aeroc_module,
        )
        nodes = ffi_codegen.assign_nodes([hp.fn for hp in hot_paths])
        result.ffi_handles_generated = [f"aero_ffi::{n.hook}" for n in nodes]

        print("\n[sandbox] Starting symmetrical differential verification...")
        passed, legacy_out, swapped_out = differential_verify(
            abs_target, modified_lib, legacy_mod, ffi_mod,
        )
        result.legacy_output = legacy_out
        result.swapped_output = swapped_out
        result.verification_passed = passed

        if not passed:
            if "Compilation failed" in swapped_out or "error" in swapped_out.lower():
                result.compilation_success = False
                result.error = f"Modified project failed to compile: {swapped_out[:500]}"
            else:
                result.compilation_success = True
                result.error = "Differential mismatch — output values diverged"
            result.rolled_back = True
            print(f"\n[ABORT] Verification failed: {result.error}")
            print("[ABORT] Changes NOT applied — legacy code preserved")
            return result

        result.compilation_success = True

        print("\n[persist] Verification passed — applying production swap...")
        actions = persist_swap(abs_target, modified_lib, legacy_mod, ffi_mod,
                               hot_paths, aeroc_module)
        for a in actions:
            print(f"  {a}")

        print("\n[final] Final compilation check on persisted source...")
        ok, _ = compile_project(abs_target)
        if not ok:
            print("[final] FAIL — rolling back")
            for a in rollback(abs_target):
                print(f"  {a}")
            result.rolled_back = True
            result.verification_passed = False
            result.error = "Final compilation check failed after persist"
        else:
            print("[final] PASS — production swap complete")

    except Exception as e:
        result.error = str(e)
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    return result


def run_dry_run(target_dir: str,
                aeroc_module: str = "anyon_sim.aeroc",
                blueprint_path: str | None = None) -> int:
    """Profile target AST structures and emit blueprint.aero (no target writes)."""
    abs_target = ingest_target(target_dir)
    lib_rs = os.path.join(abs_target, "src", "lib.rs")
    hot_paths, cold_names = parse_and_identify(lib_rs)

    blueprint = serialize_swap_blueprint(abs_target, hot_paths, cold_names, aeroc_module)
    out_path = blueprint_path or os.path.join(_HERE, "blueprint.aero")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(blueprint)

    nodes = ffi_codegen.assign_nodes([hp.fn for hp in hot_paths])
    print(f"\n[dry-run] Would swap {len(hot_paths)} function(s):")
    for hp, node in zip(hot_paths, nodes):
        print(f"  - {hp.name} (score={hp.score:.1f}, lines {hp.start_line}-{hp.end_line}) "
              f"-> aero_ffi::{node.hook}")
    print(f"[dry-run] Would preserve {len(cold_names)} cold path(s): {cold_names}")
    print(f"[dry-run] Blueprint written (no target files modified): {out_path}")
    return 0


def dispatch_target_pipeline(target_dir: str, *,
                             dry_run: bool = False,
                             execute_swap: bool = False,
                             aeroc_module: str = "anyon_sim.aeroc",
                             blueprint_path: str | None = None) -> int:
    """Shared CLI entrypoint for the targeted translation pipeline.

    Returns a process exit code (0 = success).
    """
    print("=" * 70)
    print(" Aero AutoDev — Production Code Swap (AST-clamped)")
    print("=" * 70)
    print()

    if dry_run:
        return run_dry_run(target_dir, aeroc_module, blueprint_path)

    if execute_swap:
        result = execute_production_swap(target_dir, aeroc_module=aeroc_module)
        _print_summary(result)
        return 0 if result.verification_passed else 1

    print("[info] No action flag supplied. Pass --execute-translation-swap to")
    print("[info] refactor the target, or --dry-run to emit blueprint.aero.")
    print("[info] Defaulting to a safe dry-run.\n")
    return run_dry_run(target_dir, aeroc_module, blueprint_path)


def _print_summary(result: SwapResult) -> None:
    print("\n" + "=" * 70)
    print(" RESULT SUMMARY")
    print("=" * 70)
    print(f"  Target:         {result.target_dir}")
    print(f"  Hot paths:      {result.hot_paths_found}")
    print(f"  Cold preserved: {result.cold_paths_preserved}")
    print(f"  FFI handles:    {result.ffi_handles_generated}")
    print(f"  Compiled:       {'YES' if result.compilation_success else 'NO'}")
    print(f"  Verified:       {'PASS' if result.verification_passed else 'FAIL'}")
    print(f"  Rolled back:    {'YES' if result.rolled_back else 'NO'}")
    if result.error:
        print(f"  Error:          {result.error}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Aero AutoDev Production Code Swap — AST-clamped utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python compile_production_swap.py --target testbed/anyon_simulator-main --dry-run
    python compile_production_swap.py --target testbed/anyon_simulator-main --execute-translation-swap
""",
    )
    parser.add_argument(
        "--target", required=True,
        help="Path to the target Rust project directory (must contain src/lib.rs)",
    )
    parser.add_argument(
        "--execute-translation-swap", action="store_true",
        help="Run the deterministic AST-clamped FFI swap against the target",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Profile target AST structures and emit blueprint.aero without modifying disk",
    )
    parser.add_argument(
        "--module", default="anyon_sim.aeroc",
        help="Name of the .aeroc bytecode module (default: anyon_sim.aeroc)",
    )
    parser.add_argument(
        "--blueprint", default=None,
        help="Path for the emitted blueprint.aero (default: repo root)",
    )
    args = parser.parse_args()

    rc = dispatch_target_pipeline(
        args.target,
        dry_run=args.dry_run,
        execute_swap=args.execute_translation_swap,
        aeroc_module=args.module,
        blueprint_path=args.blueprint,
    )
    sys.exit(rc)


if __name__ == "__main__":
    main()
