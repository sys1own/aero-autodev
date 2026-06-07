//! Verification binary for the Anyon Simulator.
//!
//! Runs each hot-path function with deterministic inputs and prints
//! output checksums for differential verification.

use anyon_sim::{apply_unitary, compute_braiding_matrix, evolve_state_rk4, topological_invariant};

fn hash_vec(v: &[f64]) -> u64 {
    let mut h: u64 = 0xcbf29ce484222325; // FNV-1a offset basis
    for &x in v {
        let bits = x.to_bits();
        h ^= bits;
        h = h.wrapping_mul(0x100000001b3);
    }
    h
}

fn main() {
    // Test vector: 8-element state
    let state = vec![1.0, 0.0, 0.5, -0.3, 0.8, -0.1, 0.2, 0.9];
    let potential = vec![0.1, 0.2, 0.15, 0.05];

    // apply_unitary
    let result_unitary = apply_unitary(&state, 4, 0.5);
    println!("apply_unitary: hash={:#018x} len={}", hash_vec(&result_unitary), result_unitary.len());

    // compute_braiding_matrix
    let matrix = compute_braiding_matrix(4, 0.7);
    let flat: Vec<f64> = matrix.into_iter().flatten().collect();
    println!("compute_braiding_matrix: hash={:#018x} len={}", hash_vec(&flat), flat.len());

    // evolve_state_rk4
    let evolved = evolve_state_rk4(&state, 0.01, &potential);
    println!("evolve_state_rk4: hash={:#018x} len={}", hash_vec(&evolved), evolved.len());

    // topological_invariant
    let lattice = vec![
        vec![0.1, 0.2, 0.3, 0.4],
        vec![0.5, 0.6, 0.7, 0.8],
        vec![0.9, 1.0, 1.1, 1.2],
    ];
    let inv = topological_invariant(&lattice, 0.3);
    println!("topological_invariant: value={:.15e}", inv);

    println!("VERIFICATION_COMPLETE");
}
