# Aero AutoDev — Codebase Translator Execution Plan

## Objective
Transform the existing evolutionary build pipeline into a **selective codebase translator** that reads raw target folders, identifies performance hot-paths, and maps them into native Aero bytecode (`.aeroc`) recipes.

---

## Phase 1: Foundation (Complete)
Baseline verification and bug hardening of the existing pipeline.

### Completed
- Verified `evolve_loop.py` runs a full 300-second cycle with zero compilation faults.
- Fixed **family clamp bypass**: `call`-type families (`solver`, `mapper`) now embed their family tag in recipe text so the 5-per-family ceiling is enforced.
- Fixed **self-loop dependencies**: `relink_dependencies` excludes the current task from candidate targets.
- Fixed **doubled directory path**: blueprint seeds now write to `aero_mesh_core/dist/` instead of `aero_mesh_core/aero_mesh_core/dist/`.

### Guardrails Verified
| Constraint | Spec | Status |
|---|---|---|
| Alphanumeric task IDs | `node{N}` | Held |
| Family instances per mesh | <= 5 | Held (post-fix) |
| Max nodes per mesh | <= 25 | Held |
| Self-loop dependencies | 0 | Held (post-fix) |

---

## Phase 2: Translator Pipeline (Complete)
Core scanning and mapping modules under `translator/`.

### Architecture
```
target_dir/
  ├── source files (KV telemetry, code, configs)
  │
  ▼
[hotpath_scanner] ──scan──> ScannedFile[]
                   ──identify──> HotPath[]
  │
  ▼
[bytecode_mapper] ──hotpath_to_recipe──> MeshRecipe[]
  │
  ▼
[meta_compiler] ──compile_recipe──> validated .txt recipes
  │
  ▼
build_sandbox/recipes/*.aeroc   (output targets)
aero_mesh_core/swarm_blueprints/  (recipe storage)
```

### Modules
| Module | Responsibility |
|---|---|
| `translator/hotpath_scanner.py` | SHA-256 fingerprinting, KV field extraction, schema-based hot-path grouping |
| `translator/bytecode_mapper.py` | Converts hot-path groups into Aero mesh recipes respecting all guardrails |
| `translator/pipeline.py` | Orchestrates scan → identify → map → compile; CLI entrypoint |

### Usage
```bash
python -m translator.pipeline testbed/scans
python -m translator.pipeline /path/to/any/target/folder --output-dir build_sandbox/recipes
```

---

## Phase 3: Continuous Optimization Integration (Next)
Wire the translator output into the evolution loop for autonomous refinement.

### Steps
1. **Auto-discovery**: Extend `evolve_loop.py` to detect translator-generated recipes in `swarm_blueprints/` and include them in the mutation pool alongside the three core meshes.
2. **Fitness scoring**: Add payload-density metrics (bytes scanned per recipe node) to the fitness history so the evolution engine preferentially expands high-throughput pipelines.
3. **Scheduled re-scans**: Periodically re-run the translator on watched target directories to pick up new source files and regenerate stale recipes.

---

## Phase 4: Bytecode Emission (Future)
Extend `meta_compiler.py` to emit actual `.aeroc` binary bundles.

### Steps
1. Define a binary header format (magic bytes, version, constant pool offset, code segment offset).
2. Lower validated recipe tasks into VM opcodes (`OP_PRINT`, `OP_CALL`, `OP_LOAD_CONST`).
3. Serialize the constant pool (string literals, file paths) and instruction stream into the `.aeroc` output path declared in the recipe `[project]` header.
4. Wire the emitter into the pipeline so each `compile_recipe` call produces a runnable binary alongside validation.

---

## Phase 5: Multi-Language Source Mapping (Future)
Extend the scanner to parse structured source files beyond KV telemetry.

### Targets
- Python AST extraction (identify hot loops, heavy allocations)
- JSON/YAML config dependency graphs
- Log file pattern frequency analysis

Each source type gets a dedicated scanner plugin registered in `hotpath_scanner.py` that emits the same `ScannedFile` / `HotPath` interface.
