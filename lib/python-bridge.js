/**
 * Thin, bounded bridge between DSH tools and the bundled ArchMap Python core.
 *
 * Responsibilities are deliberately limited to workspace path confinement,
 * spawning `python -m archmap`, cancellation/timeout forwarding, and bounded
 * process output capture. AST, graph, validation, layout and rendering remain
 * in Python.
 */

import { spawn } from 'node:child_process'
import { access, readFile } from 'node:fs/promises'
import { delimiter, dirname, isAbsolute, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const PYTHON_CORE_ROOT = PACKAGE_ROOT
const MAX_CAPTURE_BYTES = 8 * 1024 * 1024

/**
 * Resolve the live session workspace root through the Host working-directory
 * service. The plugin must never silently operate from the DSH process cwd.
 *
 * @param {import('@deepseek-ai/cordis').Context} ctx
 * @param {{ agent?: unknown, signal?: AbortSignal }} exec
 * @returns {Promise<string>} absolute workspace root
 */
export async function workspaceRoot(ctx, exec) {
  if (!exec?.agent) {
    throw new Error('ARCHMAP_WORKSPACE_UNAVAILABLE: ArchMap tools require an Agent-backed session')
  }
  if (!ctx?.workingDirectory || typeof ctx.workingDirectory.ensure !== 'function') {
    throw new Error('ARCHMAP_WORKSPACE_UNAVAILABLE: DSH workingDirectory service is not available')
  }
  const root = await ctx.workingDirectory.ensure(exec.agent, exec.signal)
  if (typeof root !== 'string' || root.trim() === '') {
    throw new Error('ARCHMAP_WORKSPACE_UNAVAILABLE: session working directory is empty')
  }
  return resolve(root)
}

/**
 * Resolve a user/model supplied path and reject traversal outside the current
 * DSH workspace.
 *
 * @param {string} root absolute workspace root
 * @param {string} value relative or absolute path from the tool argument
 * @returns {string} absolute path inside the workspace
 */
export function resolveWorkspacePath(root, value) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error('ARCHMAP_PATH_INVALID: path must be a non-empty string')
  }
  const workspace = resolve(root)
  const target = isAbsolute(value) ? resolve(value) : resolve(workspace, value)
  const rel = relative(workspace, target)
  if (rel === '..' || rel.startsWith(`..${sep}`) || isAbsolute(rel)) {
    throw new Error(`ARCHMAP_PATH_ESCAPE: path escapes workspace: ${value}`)
  }
  return target
}

/**
 * Run one bundled Python CLI command.
 *
 * @param {{ pythonPath: string, toolTimeoutMs: number }} config
 * @param {string} cwd workspace root
 * @param {string[]} args ArchMap CLI arguments
 * @param {{ signal?: AbortSignal }} exec DSH execution context
 * @returns {Promise<{ code: number, signal: string | null, stdout: string, stderr: string }>}
 */
export function runPython(config, cwd, args, exec) {
  return new Promise((resolvePromise, reject) => {
    const signal = exec?.signal
    if (signal?.aborted) {
      reject(abortError())
      return
    }

    const env = {
      ...process.env,
      PYTHONPATH: process.env.PYTHONPATH
        ? `${PYTHON_CORE_ROOT}${delimiter}${process.env.PYTHONPATH}`
        : PYTHON_CORE_ROOT,
      PYTHONUNBUFFERED: '1',
      PYTHONUTF8: '1',
      ARCHMAP_DSH_PLUGIN: '1',
    }

    let child
    try {
      child = spawn(config.pythonPath, ['-m', 'archmap', ...args], {
        cwd,
        env,
        stdio: ['ignore', 'pipe', 'pipe'],
        signal,
      })
    } catch (error) {
      reject(new Error(`ARCHMAP_SPAWN_FAILED: ${error instanceof Error ? error.message : String(error)}`))
      return
    }

    let stdout = ''
    let stderr = ''
    let settled = false
    let capExceeded = false
    let timedOut = false

    const clear = () => {
      clearTimeout(timer)
    }
    const settle = (callback, value) => {
      if (settled) return
      settled = true
      clear()
      callback(value)
    }
    const append = (current, chunk) => {
      const next = current + String(chunk)
      if (Buffer.byteLength(next, 'utf8') > MAX_CAPTURE_BYTES) {
        capExceeded = true
        child.kill('SIGTERM')
        return current
      }
      return next
    }

    const timer = setTimeout(() => {
      timedOut = true
      child.kill('SIGTERM')
    }, config.toolTimeoutMs)
    timer.unref?.()

    child.stdout.on('data', (chunk) => {
      stdout = append(stdout, chunk)
    })
    child.stderr.on('data', (chunk) => {
      stderr = append(stderr, chunk)
    })
    child.on('error', (error) => {
      if (signal?.aborted || error?.name === 'AbortError') {
        settle(reject, abortError())
      } else {
        settle(reject, new Error(`ARCHMAP_SPAWN_FAILED: ${error.message}`))
      }
    })
    child.on('close', (code, closeSignal) => {
      if (timedOut) {
        settle(reject, new Error(`ARCHMAP_TIMEOUT: command exceeded ${config.toolTimeoutMs}ms`))
        return
      }
      if (capExceeded) {
        settle(reject, new Error(`ARCHMAP_OUTPUT_LIMIT: command output exceeded ${MAX_CAPTURE_BYTES} bytes`))
        return
      }
      if (signal?.aborted) {
        settle(reject, abortError())
        return
      }
      settle(resolvePromise, {
        code: code ?? -1,
        signal: closeSignal ?? null,
        stdout,
        stderr,
      })
    })
  })
}

/**
 * Read one JSON object from a workspace artifact.
 *
 * @param {string} path absolute file path
 * @returns {Promise<Record<string, unknown>>}
 */
export async function readJsonObject(path) {
  const text = await readFile(path, 'utf8')
  const value = JSON.parse(text)
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`ARCHMAP_INVALID_JSON: expected a JSON object at ${path}`)
  }
  return value
}

/**
 * Check whether one artifact exists.
 *
 * @param {string} path absolute file path
 * @returns {Promise<boolean>}
 */
export async function fileExists(path) {
  try {
    await access(path)
    return true
  } catch {
    return false
  }
}

/**
 * Produce a bounded, actionable process error string for a tool result.
 *
 * @param {{ code?: number, stdout?: string, stderr?: string }} result
 * @returns {string}
 */
export function summarizeProcessError(result) {
  const text = String(result.stderr || result.stdout || `exit code ${result.code ?? -1}`).trim()
  return text.slice(0, 2400)
}

function abortError() {
  const error = new Error('ARCHMAP_ABORTED: ArchMap command was cancelled')
  error.name = 'AbortError'
  return error
}

export const PACKAGE_ROOT_PATH = PACKAGE_ROOT
export const PYTHON_CORE_PATH = PYTHON_CORE_ROOT
