//! Anyon Simulator — Topological Quantum Computing Engine
//!
//! Core mathematical routines for simulating anyon braiding,
//! state evolution, and topological invariant computation.

use std::sync::{Arc, Mutex};
use std::thread;

// ---------------------------------------------------------------------------
// Hot path: apply_unitary — primary target for Aero bytecode translation
// ---------------------------------------------------------------------------

/// Apply a unitary transformation matrix to a quantum state vector.
/// This is the critical hot path: O(N^2) nested loops with heavy
/// floating-point arithmetic (sin, cos, exp) on every iteration.
pub fn apply_unitary(state: &[f64], dim: usize, coupling: f64) -> Vec<f64> {
    let n = state.len();
    let mut result = vec![0.0f64; n];

    for i in 0..n {
        for j in 0..n {
            let phase = ((i * j) as f64 * coupling).cos();
            let amplitude = ((i as f64 + j as f64) / dim as f64).sin();
            result[i] += state[j] * phase * amplitude;
        }
        // Normalization factor per row
        let row_norm: f64 = (0..n)
            .map(|k| ((i * k) as f64 * coupling).cos().powi(2))
            .sum::<f64>()
            .sqrt();
        if row_norm > 1e-15 {
            result[i] /= row_norm;
        }
    }
    result
}

// ---------------------------------------------------------------------------
// Hot path: braiding matrix computation
// ---------------------------------------------------------------------------

/// Compute the R-matrix for anyon braiding at a given topological charge.
/// Triple-nested loop over fusion state space with trigonometric kernels.
pub fn compute_braiding_matrix(dim: usize, charge: f64) -> Vec<Vec<f64>> {
    let mut matrix = vec![vec![0.0f64; dim]; dim];
    for i in 0..dim {
        for j in 0..dim {
            let mut val = 0.0;
            for k in 0..dim {
                val += (k as f64 * charge).sin()
                    * ((i + k) as f64 * 0.1).cos()
                    * ((j + k) as f64 * 0.1).exp().min(1e6);
            }
            matrix[i][j] = val / (dim as f64);
        }
    }
    matrix
}

// ---------------------------------------------------------------------------
// Hot path: RK4 state evolution
// ---------------------------------------------------------------------------

/// Evolve a quantum state using 4th-order Runge-Kutta integration.
/// Multi-loop tensor operations on state vectors.
pub fn evolve_state_rk4(state: &[f64], dt: f64, potential: &[f64]) -> Vec<f64> {
    let n = state.len();
    let mut k1 = vec![0.0; n];
    let mut k2 = vec![0.0; n];
    let mut k3 = vec![0.0; n];
    let mut k4 = vec![0.0; n];
    let mut result = vec![0.0; n];

    for i in 0..n {
        k1[i] = -potential[i % potential.len()] * state[i];
    }
    for i in 0..n {
        k2[i] = -potential[i % potential.len()] * (state[i] + 0.5 * dt * k1[i]);
    }
    for i in 0..n {
        k3[i] = -potential[i % potential.len()] * (state[i] + 0.5 * dt * k2[i]);
    }
    for i in 0..n {
        k4[i] = -potential[i % potential.len()] * (state[i] + dt * k3[i]);
    }
    for i in 0..n {
        result[i] = state[i] + (dt / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]);
    }
    result
}

// ---------------------------------------------------------------------------
// Hot path: topological invariant
// ---------------------------------------------------------------------------

/// Compute the topological invariant via tensor contraction.
/// Double-nested loop with trigonometric accumulation.
pub fn topological_invariant(lattice: &[Vec<f64>], twist: f64) -> f64 {
    let mut invariant = 0.0;
    for row in lattice.iter() {
        for val in row.iter() {
            invariant += val.sin() * twist.cos();
            invariant *= 1.0 + val.abs() * 0.001;
        }
    }
    invariant
}

// ---------------------------------------------------------------------------
// Cold path: unsafe memory management (do NOT translate)
// ---------------------------------------------------------------------------

/// Raw buffer allocation for GPU interop — unsafe, pointer arithmetic.
pub unsafe fn raw_buffer_alloc(size: usize) -> *mut f64 {
    let layout = std::alloc::Layout::from_size_align(
        size * std::mem::size_of::<f64>(),
        std::mem::align_of::<f64>(),
    )
    .unwrap();
    let ptr = std::alloc::alloc(layout) as *mut f64;
    for i in 0..size {
        std::ptr::write(ptr.add(i), 0.0);
    }
    ptr
}

/// Transmute raw bytes to f64 slice — unsafe memory reinterpretation.
pub unsafe fn transmute_to_state(data: &[u8]) -> &[f64] {
    let ptr = data.as_ptr() as *const f64;
    let len = data.len() / std::mem::size_of::<f64>();
    std::slice::from_raw_parts(ptr, len)
}

// ---------------------------------------------------------------------------
// Cold path: multi-threaded lattice evolution (do NOT translate)
// ---------------------------------------------------------------------------

/// Parallel lattice evolution across worker threads.
pub fn parallel_evolve(
    lattice: Vec<Vec<f64>>,
    steps: usize,
    workers: usize,
) -> Vec<Vec<f64>> {
    let shared = Arc::new(Mutex::new(lattice));
    let mut handles = vec![];

    for w in 0..workers {
        let data = Arc::clone(&shared);
        let handle = thread::spawn(move || {
            let mut grid = data.lock().unwrap();
            let chunk = grid.len() / workers;
            let start = w * chunk;
            let end = if w == workers - 1 { grid.len() } else { start + chunk };
            for _ in 0..steps {
                for i in start..end {
                    for j in 0..grid[i].len() {
                        grid[i][j] *= 0.999;
                    }
                }
            }
        });
        handles.push(handle);
    }
    for h in handles {
        h.join().unwrap();
    }
    Arc::try_unwrap(shared).unwrap().into_inner().unwrap()
}

// ---------------------------------------------------------------------------
// Cold path: lifetime-constrained views (do NOT translate)
// ---------------------------------------------------------------------------

/// Borrowed view with explicit lifetime — cannot be translated to bytecode.
pub fn state_view<'a>(state: &'a [f64], start: usize, end: usize) -> &'a [f64] {
    &state[start..end]
}
