import os
import sys
import time
import argparse
import json
import random
import contextlib

_HERE = os.path.dirname(os.path.abspath(__file__))
from meta_compiler import compile_recipe

def generate_swarm_environment():
    """Initializes the absolute directory matrix instantly at boot to resolve silent I/O compiler rejections"""
    os.makedirs(os.path.join(_HERE, "aero_mesh_core", "swarm_blueprints"), exist_ok=True)
    os.makedirs(os.path.join(_HERE, "aero_mesh_core", "dist"), exist_ok=True)
    os.makedirs(os.path.join(_HERE, "build_sandbox", "recipes"), exist_ok=True)
    os.makedirs(os.path.join(_HERE, "build_sandbox", "mesh_outputs"), exist_ok=True)
    os.makedirs(os.path.join(_HERE, "testbed", "scans"), exist_ok=True)

def ensure_swarm_blueprints(force_reset=False):
    """Guarantees that all three distinct architectural meshes are present on disk and structurally pristine"""
    blueprints = {
        "ingress_mesh.txt": (
            "[project]\nname = ingress_mesh\noutput = build_sandbox/recipes/ingress_mesh.aeroc\n\n"
            "[task:init]\nop = print\ntext = \"-- Initializing Ingress Nodes --\"\n\n"
            "[task:ingest]\nop = print\ntext = \"-- sentinel | Ingesting Raw Telemetry Data Stream from testbed/scans/raw_telemetry_0 --\"\nneeds = init\n"
        ),
        "processing_mesh.txt": (
            "[project]\nname = processing_mesh\noutput = build_sandbox/recipes/processing_mesh.aeroc\n\n"
            "[task:compute]\nop = print\ntext = \"-- Processing Parallel Computations --\"\n\n"
            "[task:transform]\nop = call\nfn = write_file\nargs = \"aero_mesh_core/dist/interim.tmp\", \"processed\"\nneeds = compute\n"
        ),
        "aggregation_mesh.txt": (
            "[project]\nname = aggregation_mesh\noutput = build_sandbox/recipes/aggregation_mesh.aeroc\n\n"
            "[task:consolidate]\nop = print\ntext = \"-- Aggregating Distributed State --\"\n\n"
            "[task:freeze]\nop = call\nfn = write_file\nargs = \"aero_mesh_core/dist/index_manifest.txt\", \"state complete\"\nneeds = consolidate\n"
        )
    }
    
    bp_dir = os.path.join(_HERE, "aero_mesh_core", "swarm_blueprints")
    for name, content in blueprints.items():
        path = os.path.join(bp_dir, name)
        if force_reset or not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

def execute_complexity_mutation(recipe_text, mesh_name, round_counter):
    """Generates mutations tracking category limits safely via inline string literals"""
    lines = recipe_text.split("\n")
    tasks = []
    
    for line in lines:
        if line.strip().startswith("[task:"):
            tasks.append(line.split("[task:")[1].split("]")[0].strip())

    strategy = random.choice(["expand_nodes", "relink_dependencies", "fuzz_logs"])
    
    # RAILING 1: Absolute high-density structure ceiling limited to 25 nodes max per file
    if len(tasks) >= 25 and strategy == "expand_nodes":
        strategy = "relink_dependencies"

    if strategy == "expand_nodes" and tasks:
        cluster_tier = round_counter % 5000  
        
        if "ingress" in mesh_name:
            pool = [
                {"family": "sentinel", "op": "print", "body": f'text = "-- sentinel | Gateway Security Auth Check Sequence: Tier {cluster_tier} Key {round_counter} --"', "label": "Security Boundary"},
                {"family": "balancer", "op": "print", "body": f'text = "-- balancer | Traffic Pool Load Balancing Routine Cluster Shard {cluster_tier} Frame {round_counter} --"', "label": "Stream Load Balancer"},
                {"family": "buffer", "op": "call", "body": f'fn = write_file\nargs = "build_sandbox/mesh_outputs/buffer_ingress_stream_{round_counter}.dat", "stream"', "label": "Ingestion I/O Flush"}
            ]
        elif "processing" in mesh_name:
            pool = [
                {"family": "optimizer", "op": "print", "body": f'text = "-- optimizer | Optimization Engine State Synchronized: Segment {cluster_tier} Step {round_counter} --"', "label": "DAG Index Step"},
                {"family": "memory", "op": "print", "body": f'text = "-- memory | Interlock Memory Latch Set: Range {cluster_tier} Frame {round_counter} --"', "label": "Shared Memory Link"},
                {"family": "solver", "op": "call", "body": f'fn = write_file\nargs = "build_sandbox/mesh_outputs/matrix_block_{round_counter}.tmp", "bin"\nfamily = solver', "label": "Matrix solver farm Flush"}
            ]
        else:
            pool = [
                {"family": "signer", "op": "print", "body": f'text = "-- signer | Release Package Cryptographic Seal Generated: Block {cluster_tier} ID {round_counter} --"', "label": "Integrity Handshake"},
                {"family": "boxer", "op": "print", "body": f'text = "-- boxer | Standalone Swarm Package Bundled: Node {cluster_tier} Archive {round_counter} --"', "label": "Unified Box Output Bundle"},
                {"family": "mapper", "op": "call", "body": f'fn = write_file\nargs = "aero_mesh_core/dist/global_swarm_index_{round_counter}.idx", "sync"\nfamily = mapper', "label": "Index Map Row"}
            ]
            
        chosen = random.choice(pool)
        unique_marker = f"_{round_counter}"
        
        # RAILING 2: Absolute global family clamp. Max 5 instances per operational family per file.
        if recipe_text.count(chosen['family']) >= 5 or unique_marker in recipe_text:
            strategy = "relink_dependencies"
        else:
            new_node_id = f"node{round_counter}"
            parent_dependency = tasks[-1] 
            
            node_block = (
                f"\n\n[task:{new_node_id}]\n"
                f"op = {chosen['op']}\n"
                f"{chosen['body']}\n"
                f"needs = {parent_dependency}\n"
            )
            return recipe_text + node_block, f"Chained Clean Segment [{chosen['label']}] -> Node: {new_node_id}"

    if strategy == "relink_dependencies" and len(tasks) > 2:
        new_lines = []
        mutated = False
        current_task = None
        for line in lines:
            if line.strip().startswith("[task:"):
                current_task = line.split("[task:")[1].split("]")[0].strip()
            if "needs =" in line and random.random() > 0.7:
                candidates = [t for t in tasks[:-1] if t != current_task]
                if candidates:
                    t_target = random.choice(candidates)
                    new_lines.append(f"needs = {t_target}")
                    mutated = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        desc = "Reconfigured Dependency Routing Graph Pathing" if mutated else "Maintained Current Graph Equilibrium"
        return "\n".join(new_lines), desc

    new_lines = []
    mutated = False
    for line in lines:
        if "text =" in line and "Cluster Pulse Sequence" in line and random.random() > 0.5:
            new_lines.append(f'text = "-- Swarm Matrix Execution Cluster Pulse Sequence #{round_counter} Global Entry --"')
            mutated = True
        else:
            new_lines.append(line)
    desc = "Updated Cluster Heartbeat Frame Strings" if mutated else "Stabilized Current Code Matrix States"
    return "\n".join(new_lines), desc

def push_git_checkpoint(reason, metrics):
    """Saves state telemetry metrics to disk locally across runner windows"""
    dist_dir = os.path.join(_HERE, "aero_mesh_core", "dist")
    os.makedirs(dist_dir, exist_ok=True)
    with open(os.path.join(dist_dir, "swarm_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Aero AutoDev — Evolution & Translation Orchestrator",
    )
    parser.add_argument('--duration', type=int, default=300)
    parser.add_argument(
        '--target', type=str, default=None,
        help="Isolate and profile an external target repository side-by-side",
    )
    parser.add_argument(
        '--execute-translation-swap', action='store_true',
        help="Trigger the deterministic AST-clamped code refactor pass against --target",
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help="Profile target AST structures and emit blueprint.aero without modifying disk",
    )
    parser.add_argument(
        '--module', type=str, default='anyon_sim.aeroc',
        help="Name of the .aeroc bytecode module for the FFI swap",
    )
    parser.add_argument(
        '--blueprint', type=str, default=None,
        help="Path for the emitted blueprint.aero (default: repo root)",
    )
    args, unknown = parser.parse_known_args()

    # --- Targeted translation pipeline -------------------------------------
    # When a target is supplied, route into the AST-clamped translation-swap
    # engine instead of the evolution loop. The loop's internal state tracking
    # is left entirely untouched in this path.
    if args.target:
        from compile_production_swap import dispatch_target_pipeline
        rc = dispatch_target_pipeline(
            args.target,
            dry_run=args.dry_run,
            execute_swap=args.execute_translation_swap,
            aeroc_module=args.module,
            blueprint_path=args.blueprint,
        )
        sys.exit(rc)

    print("🚀 Initializing Grid-Hardened Swarm Evolution Engine...", flush=True)
    generate_swarm_environment()
    ensure_swarm_blueprints(force_reset=False)
    
    start_time = time.time()
    last_git_time = time.time()
    last_heartbeat_time = time.time()
    
    total_rounds = 0
    champions_frozen = 0
    
    meshes = ["ingress_mesh.txt", "processing_mesh.txt", "aggregation_mesh.txt"]
    fitness_history = {m: {"node_count": 2, "compiled_successfully": True} for m in meshes}
    interval_stats = {"cycles": 0, "compilation_faults": 0, "champions_crowned": []}

    bp_dir = os.path.join(_HERE, "aero_mesh_core", "swarm_blueprints")

    while (time.time() - start_time) < args.duration:
        current_time = time.time()
        elapsed = int(current_time - start_time)
        total_rounds += 1
        interval_stats["cycles"] += 1
        
        target_mesh = random.choice(meshes)
        mesh_path = os.path.join(bp_dir, target_mesh)
        
        try:
            with open(mesh_path, "r", encoding="utf-8") as f_read:
                original_blueprint = f_read.read()
            
            mutated_blueprint, mutation_description = execute_complexity_mutation(original_blueprint, target_mesh, total_rounds)
            with open(mesh_path, "w", encoding="utf-8") as f_write:
                f_write.write(mutated_blueprint)
                
            with open(os.devnull, 'w') as fnull:
                with contextlib.redirect_stdout(fnull), contextlib.redirect_stderr(fnull):
                    compile_recipe(mesh_path, run=True)
            
            mutated_nodes = mutated_blueprint.count("[task:")
            if mutated_nodes > fitness_history[target_mesh]["node_count"]:
                fitness_history[target_mesh]["node_count"] = mutated_nodes
                champions_frozen += 1
            elif mutated_blueprint != original_blueprint and mutated_nodes == fitness_history[target_mesh]["node_count"]:
                pass
            else:
                with open(mesh_path, "w", encoding="utf-8") as f_revert:
                    f_revert.write(original_blueprint)
                    
        except Exception:
            interval_stats["compilation_faults"] += 1
            with open(mesh_path, "w", encoding="utf-8") as f_revert:
                f_revert.write(original_blueprint)

        if (current_time - last_heartbeat_time) >= 10:
            print(f"⏳ [SWARM STATE HEARTBEAT] Time: {elapsed}s | Velocity: {interval_stats['cycles']} cycles | Total Champs: {champions_frozen}", flush=True)
            interval_stats = {"cycles": 0, "compilation_faults": 0, "champions_crowned": []}
            last_heartbeat_time = current_time

        if (current_time - last_git_time) >= 180:
            last_git_time = current_time
            push_git_checkpoint(f"Runtime: {elapsed}s", fitness_history)

    push_git_checkpoint("Evolution run complete", fitness_history)
    print("🏁 Operational timeline achieved cleanly.", flush=True)

if __name__ == '__main__':
    main()
