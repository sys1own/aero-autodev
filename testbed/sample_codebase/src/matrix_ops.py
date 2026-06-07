"""Sample hot-path: nested loops + array ops + recursion."""


def matrix_multiply(a, b):
    rows_a, cols_a = len(a), len(a[0])
    rows_b, cols_b = len(b), len(b[0])
    result = [[0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for j in range(cols_b):
            for k in range(cols_a):
                result[i][j] += a[i][k] * b[k][j]
    return result


def recursive_fib(n):
    if n <= 1:
        return n
    return recursive_fib(n - 1) + recursive_fib(n - 2)


def sort_and_filter(data):
    cleaned = []
    for item in data:
        stripped = item.strip()
        if stripped:
            cleaned.append(stripped)
    cleaned.sort()
    result = []
    for val in cleaned:
        parts = val.split(",")
        for p in parts:
            result.append(p.replace('"', '').strip())
    return result
