# Aero AutoDev System Architecture Framework
This document serves as the absolute single source of truth context file for autonomous agents (Claude/Devin) initializing the workspace.

## 1. System Topology Map
The repository layout must be strictly maintained across development cycles:
* `/aero_mesh_core/swarm_blueprints/` : Storage home of active system configuration maps.
* `/build_sandbox/recipes/`           : Output target of fully compiled bytecode bundles (`.aeroc`).
* `/meta_compiler.py`                  : Core local interpreter engine parsing stack primitives.
* `/evolve_loop.py`                    : Evolutionary pipeline optimizing execution networks.

## 2. Immutable System Guardrails
To prevent code deadlocks, volume leakage, or infinite loop padding, any automation script must strictly obey these three ironclad architectural design rules:
1. **Pristine Alphanumeric Token Schemas**: All task identifiers must use clean alphanumeric formats (`node{round_counter}`). Do not embed complex string layout patterns inside task name strings.
2. **Global Frequency Clamps**: Every operational component family is capped at exactly 5 instances total per mesh file. Volume expansion must cap permanently at 25 total nodes.
3. **Symmetrical Stack Cleanliness**: The codebase must enforce strict stack clearing on every execution path step. Primitives must never leave stranded values or open string pollution behind on the virtual data stack.
