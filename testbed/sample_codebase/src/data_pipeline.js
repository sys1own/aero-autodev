// Sample hot-path: array method chains + nested loops

function processRecords(records) {
    const filtered = records.filter(r => r.active);
    const mapped = filtered.map(r => ({
        id: r.id,
        score: r.values.reduce((sum, v) => sum + v, 0),
    }));
    mapped.sort((a, b) => b.score - a.score);
    return mapped;
}

function deepSearch(matrix) {
    for (let i = 0; i < matrix.length; i++) {
        for (let j = 0; j < matrix[i].length; j++) {
            const cell = matrix[i][j];
            if (cell.includes("target")) {
                const parts = cell.split("-");
                return parts.join("_");
            }
        }
    }
    return null;
}

const flattenTree = function flattenTree(node) {
    if (!node.children) return [node.value];
    const results = [node.value];
    for (const child of node.children) {
        results.push(...flattenTree(child));
    }
    return results;
};
