# Aero AutoDev

Aero AutoDev is a high-performance, deterministic codebase optimization and refactoring engine. It is designed to programmatically analyze abstract syntax trees (AST), isolate high-throughput execution loops, and translate functional hot paths into native, bit-for-bit verified **Aero VM Assembly Blueprint** configurations (`blueprint.aero`).

Unlike stochastic or LLM-based refactoring tools, Aero AutoDev operates with complete mathematical determinism, ensuring zero drift, zero hallucination, and predictable micro-architectural hardware alignment.

---

## 🚀 Core Architectural Pillars

* **Bidirectional Blueprint Ingestion:** Aero AutoDev doesn't just emit code; it respects your existing environment. The engine actively parses and honors pre-configured micro-architectural variables within your `blueprint.aero`. Manual tuning of scratchpad dimensions, core affinity bindings, or JIT timeouts are preserved entirely across verification passes.
* **Semantic Filtering & Safety Gates:** To prevent hot-path over-harvesting loops, the system uses an internal infrastructure blacklist. The parser dynamically isolates and filters out foreign function interface (FFI) stubs, bridge hooks, and legacy wrappers—ensuring only pure application logic is optimized.
* **Workload-Bounded Convergence:** Bypasses unpredictable time-locked evolution windows. The orchestration pipeline tracks structural inventory statefully, executing programmatic refactoring loops until every single targeted code path reaches a completely verified, hardware-stable state.
* **Polyglot AST Frontend:** Built around a modular frontend layout utilizing Tree-sitter node architectures, capable of scaling across multiple high-throughput grammar definitions (including native Rust and Python optimization pipelines).

---

## 🛠️ How It Works: The Pipeline

Aero AutoDev treats optimization as a strict execution pipeline rather than an arbitrary text modification task:

1. **Scan:** `hotpath_scanner.py` parses the target AST (e.g., your Rust `lib.rs` modules via `rust_ast.py`) to map out complexity weights.
2. **Filter:** Unsafe, high-entropy, or low-throughput code paths are triaged by the `entropy_filter.py` and routed away via the `cold_pass_router.py`.
3. **Map & Synthesize:** Valid logic blocks are converted to explicit tokens by `bytecode_mapper.py` and compiled into native Aero VM tracks.
4. **Isolate & Verify:** Unsafe pointer hooks are split out cleanly via `ffi_codegen.py`, while `diff_sandbox.py` subjects the final code to differential bit-exact testing to guarantee original functional parity.

---

## 📁 Repository Map

```text
├── blueprint.aero              # Live native hardware interface blueprint map
├── compile_production_swap.py  # Atomic AST mutation and FFI splicing core module
├── evolve_loop.py              # Workload-bounded inventory orchestration loop driver
├── meta_compiler.py            # Multi-language build-sandbox orchestration pipeline
├── requirements.txt            # Package dependencies manifest
├── src/
│   └── lib.rs                  # Primary compilation target container file
└── translator/                 # Full Structural Analysis Engine & Core Pipeline
    ├── __init__.py             # Module namespace initialization package entry
    ├── aero_translator.py      # Main translation execution block wrapper
    ├── blueprint_manager.py    # State control and active configuration parser
    ├── bytecode_mapper.py      # Map compiler logic tokens to Aero VM tracks
    ├── code_profiler.py        # Complexity weight calculator logic analyzer
    ├── cold_pass_router.py     # Route low-throughput pathways to safety channels
    ├── diff_sandbox.py         # Differential bit-exact isolation testing gate
    ├── entropy_filter.py       # Chaos evaluation and mutation stabilizer
    ├── ffi_codegen.py          # Automated generation core for C-level pointer hooks
    ├── ffi_generator.py        # Structural schema compiler for native FFI bridges
    ├── ffi_isolation.py        # Encapsulate unsafe logic components away from core memory
    ├── hotpath_scanner.py      # AST search module identifying deep function loops
    ├── pipeline.py             # Sequence coordinator driving translation tasks
    ├── rust_ast.py             # Tree-sitter node boundary coordinate extractor
    └── translation_pipeline.py # Streamlined FFI compilation and emission pipeline
