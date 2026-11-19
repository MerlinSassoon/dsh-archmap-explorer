#!/usr/bin/env node
/**
 * Deterministic package self-check. This script must never use the network,
 * run the ArchMap pytest suite, create user project files, or launch a browser.
 */

import { readFile, readdir, stat } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const failures = []
const warnings = []

async function requireFile(path, label) {
  try {
    const info = await stat(path)
    if (!info.isFile()) failures.push(`${label} is not a file: ${path}`)
    else if (info.size === 0) failures.push(`${label} is empty: ${path}`)
  } catch {
    failures.push(`${label} is missing: ${path}`)
  }
}

async function main() {
  const packagePath = join(PACKAGE_ROOT, 'package.json')
  let pkg
  try {
    pkg = JSON.parse(await readFile(packagePath, 'utf8'))
  } catch (error) {
    failures.push(`package.json is not readable JSON: ${error instanceof Error ? error.message : String(error)}`)
    printResult()
    return
  }

  if (pkg.name !== 'dsh-archmap-explorer') failures.push('package.json name must be dsh-archmap-explorer')
  if (pkg.type !== 'module') failures.push('package.json type must be module')
  if (!pkg.dsh?.bundle?.patch) {
    failures.push('package.json dsh.bundle.patch is required')
  } else {
    await requireFile(resolve(PACKAGE_ROOT, pkg.dsh.bundle.patch), 'dsh bundle patch')
  }

  for (const file of [
    'archmap/__main__.py',
    'pyproject.toml',
    'docs/dsh-plugin.md',
    'docs/HANDOFF-DSH-PLUGIN-0.1.0.md',
    'docs/HANDOFF-DSH-PLUGIN-0.2.0.md',
    'docs/archmap-config-generation.md',
    'docs/archmap-code-conventions.md',
    'LICENSE',
  ]) {
    await requireFile(join(PACKAGE_ROOT, file), file)
  }

  for (const file of await collectJavaScriptFiles()) {
    await checkJavaScript(file)
  }

  checkPython()
  printResult()
}

async function collectJavaScriptFiles() {
  const libDir = join(PACKAGE_ROOT, 'lib')
  try {
    const entries = await readdir(libDir, { withFileTypes: true })
    const files = entries
      .filter((entry) => entry.isFile() && entry.name.endsWith('.js'))
      .map((entry) => join(libDir, entry.name))
      .sort()
    if (files.length === 0) failures.push('lib/ must contain at least one JavaScript file')
    return files
  } catch {
    failures.push('lib/ directory is missing')
    return []
  }
}

async function checkJavaScript(path) {
  try {
    const source = await readFile(path, 'utf8')
    if (source.trim() === '') failures.push(`JavaScript file is empty: ${path}`)
  } catch {
    failures.push(`JavaScript file is missing: ${path}`)
    return
  }
  const result = spawnSync(process.execPath, ['--check', path], { encoding: 'utf8' })
  if (result.status !== 0) {
    const detail = String(result.stderr || result.stdout || '').trim()
    failures.push(`JavaScript syntax check failed: ${relative(PACKAGE_ROOT, path)}${detail ? `\n${detail}` : ''}`)
  }
}

function checkPython() {
  const python = process.env.ARCHMAP_PYTHON || 'python3'
  const result = spawnSync(
    python,
    ['-c', 'import sys; print("%d.%d" % sys.version_info[:2]); raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'],
    { encoding: 'utf8' },
  )
  if (result.error) {
    warnings.push(`Python executable not found (${python}); install Python 3.10+ before using ArchMap`)
    return
  }
  if (result.status !== 0) {
    failures.push(`Python 3.10+ is required; ${python} reported ${String(result.stdout || result.stderr).trim()}`)
    return
  }
}

function printResult() {
  for (const warning of warnings) process.stderr.write(`prepare warning: ${warning}\n`)
  if (failures.length > 0) {
    for (const failure of failures) process.stderr.write(`prepare error: ${failure}\n`)
    process.exitCode = 1
    return
  }
  process.stderr.write('prepare: ok\n')
}

await main()
