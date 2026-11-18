/**
 * Pure helpers for batching annotation context and validating model proposals.
 *
 * Node identity and source hashes are always copied from Python-provided
 * context. Model-supplied hashes, source labels, and unknown node ids never
 * become sidecar facts.
 */

/**
 * Split an array into bounded sequential batches.
 *
 * @template T
 * @param {readonly T[]} items
 * @param {number} size
 * @returns {T[][]}
 */
export function annotationBatches(items, size) {
  const batches = []
  for (let index = 0; index < items.length; index += size) {
    batches.push(items.slice(index, index + size))
  }
  return batches
}

/**
 * Normalize one model JSON response against the exact context nodes sent in
 * the batch.
 *
 * @param {Record<string, unknown>} response
 * @param {readonly Record<string, unknown>[]} contextNodes
 * @returns {{ nodes: Record<string, string>[], rejected: string[] }}
 */
export function normalizeAnnotationResponse(response, contextNodes) {
  const rawNodes = response?.nodes
  if (!Array.isArray(rawNodes)) {
    throw new Error('HOST_MODEL_INVALID_SHAPE: annotation response must contain a nodes array')
  }

  const allowed = new Map(
    contextNodes
      .filter((node) => typeof node?.nodeId === 'string' && node.nodeId)
      .map((node) => [node.nodeId, node]),
  )
  const normalized = []
  const rejected = []
  const seen = new Set()
  for (const item of rawNodes) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      rejected.push('INVALID_NODE_ITEM')
      continue
    }
    const nodeId = String(item.nodeId || '').trim()
    if (!allowed.has(nodeId)) {
      rejected.push(nodeId || 'MISSING_NODE_ID')
      continue
    }
    if (seen.has(nodeId)) {
      rejected.push(nodeId)
      continue
    }
    seen.add(nodeId)
    const summary = String(item.summary || '').trim()
    const details = String(item.details || '').trim()
    if (!summary) {
      rejected.push(nodeId)
      continue
    }
    normalized.push({
      nodeId,
      summary,
      details,
      sourceHash: String(allowed.get(nodeId).sourceHash || ''),
      source: 'host-llm',
    })
  }
  return { nodes: normalized, rejected }
}
