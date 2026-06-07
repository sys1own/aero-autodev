"""Sample complex codebase simulating a quantum gravity simulator.

Contains:
- External library dependencies (numpy, scipy)
- Multi-threading patterns
- Hardware-specific operations (ctypes)
- Pure computation functions (translatable hot-paths)
"""

import numpy as np
from scipy import linalg
import threading
import ctypes


# --- Hot path: pure computation, no external deps ---
def gravitational_potential(masses, positions):
    """Compute pairwise gravitational potential energy."""
    total = 0.0
    for i in range(len(masses)):
        for j in range(i + 1, len(masses)):
            dx = positions[i][0] - positions[j][0]
            dy = positions[i][1] - positions[j][1]
            dz = positions[i][2] - positions[j][2]
            r = (dx*dx + dy*dy + dz*dz) ** 0.5
            if r > 0:
                total += -masses[i] * masses[j] / r
    return total


# --- Hot path: pure computation ---
def runge_kutta_step(state, dt, derivative_fn):
    """Single RK4 integration step."""
    k1 = derivative_fn(state)
    k2 = derivative_fn([s + 0.5 * dt * k for s, k in zip(state, k1)])
    k3 = derivative_fn([s + 0.5 * dt * k for s, k in zip(state, k2)])
    k4 = derivative_fn([s + dt * k for s, k in zip(state, k3)])
    result = []
    for i in range(len(state)):
        result.append(state[i] + (dt / 6.0) * (k1[i] + 2*k2[i] + 2*k3[i] + k4[i]))
    return result


# --- Cold path: uses numpy (external) ---
def eigenstate_solver(hamiltonian_matrix):
    """Solve for eigenstates using numpy/scipy."""
    H = np.array(hamiltonian_matrix)
    eigenvalues, eigenvectors = np.linalg.eigh(H)
    return eigenvalues.tolist(), eigenvectors.tolist()


# --- Cold path: uses scipy (external) ---
def matrix_exponential(operator_matrix, time_step):
    """Compute matrix exponential for time evolution."""
    M = np.array(operator_matrix)
    result = linalg.expm(-1j * time_step * M)
    return result.tolist()


# --- Cold path: multi-threading ---
def parallel_field_evolution(field_grid, steps, workers=4):
    """Evolve field grid in parallel using threads."""
    results = [None] * workers
    lock = threading.Lock()

    def evolve_chunk(chunk_id, start, end):
        local_sum = 0.0
        for i in range(start, end):
            for s in range(steps):
                local_sum += field_grid[i] * 0.99
        with lock:
            results[chunk_id] = local_sum

    chunk = len(field_grid) // workers
    threads = []
    for w in range(workers):
        t = threading.Thread(target=evolve_chunk,
                             args=(w, w * chunk, (w + 1) * chunk))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return results


# --- Cold path: ctypes / hardware driver ---
def gpu_kernel_dispatch(data_ptr, kernel_id):
    """Dispatch computation to GPU via ctypes FFI."""
    lib = ctypes.CDLL("libcompute.so")
    buf = (ctypes.c_double * len(data_ptr))(*data_ptr)
    lib.dispatch_kernel(kernel_id, buf, len(data_ptr))
    return [buf[i] for i in range(len(data_ptr))]
