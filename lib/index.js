/**
 * DSH adapter for the bundled ArchMap Python core.
 *
 * The plugin is intentionally thin: Python owns analysis, graph projection,
 * annotation validation and HTML rendering. This module owns DSH tool schemas,
 * workspace confinement, host-model orchestration and bundled Skill delivery.
 *
 * @module dsh-archmap-explorer
 */

import { readFile, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { BUNDLED_SKILL_RANK } from '@deepseek-ai/dsh-skill'
import { defineTool } from '@deepseek-ai/dsh-tools'
import z from '@deepseek-ai/schemastery'
import { annotationBatches, normalizeAnnotationResponse } from './annotations.js'
import { hostJson } from './host-llm.js'
import {
  fileExists,
  readJsonObject,
  resolveWorkspacePath,
  runPython,
  summarizeProcessError,
  workspaceRoot,
} from './python-bridge.js'

export const name = 'dsh-archmap-explorer'
export const inject = ['tools', 'skills', 'llm', 'workingDirectory']

const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const DEFAULT_PYTHON = process.env.ARCHMAP_PYTHON || 'python3'
const DEFAULT_OUTPUT_DIR = '.archmap'
const DEFAULT_TIMEOUT_MS = 120_000
const DEFAULT_LLM_MAX_TOKENS = 8192
const DEFAULT_ANNOTATION_BATCH_SIZE = 6
const DEFAULT_ANNOTATION_MAX_NODES = 50
const DEFAULT_ANNOTATION_MAX_CHARS = 6000
const PROVIDER_NAME = 'archmap'
const RESOURCE_BASE = { kind: 'directory', path: PACKAGE_ROOT }

const BUNDLED_SKILLS = [
  {
    name: 'archmap-config-generation',
    description:
      'Generate or validate an archmap.config.json from source facts: module ownership, include boundaries, entrypoints, execution entrypoints, Provider capabilities and deterministic validation.',
    whenToUse:
      'Use when creating, reviewing or repairing ArchMap module configuration for a Python project, or before the first architecture build.',
    invocation: { modelInvocable: true, userInvocable: true },
    provider: PROVIDER_NAME,
    source: 'bundled',
    resourceBase: RESOURCE_BASE,
    rank: BUNDLED_SKILL_RANK,
    locator: new URL('../docs/archmap-config-generation.md', import.meta.url),
  },
  {
    name: 'archmap-code-conventions',
    description:
      'Follow ArchMap source-code conventions for module boundaries, Provider roles, capability surfaces, entrypoints, execution flows, notes and tests.',
    whenToUse:
      'Use when writing or refactoring Python code that should remain analyzable by ArchMap, or when a project needs stable architecture and capability boundaries.',
    invocation: { modelInvocable: true, userInvocable: true },
    provider: PROVIDER_NAME,
    source: 'bundled',
    resourceBase: RESOURCE_BASE,
    rank: BUNDLED_SKILL_RANK,
    locator: new URL('../docs/archmap-code-conventions.md', import.meta.url),
  },
]

export const Config = z.object({
  pythonPath: z.string().default(DEFAULT_PYTHON),
  defaultOutputDir: z.string().default(DEFAULT_OUTPUT_DIR),
  toolTimeoutMs: z.number().default(DEFAULT_TIMEOUT_MS),
  provider: z.string().default(''),
  model: z.string().default(''),
  llmMaxTokens: z.number().default(DEFAULT_LLM_MAX_TOKENS),
  annotationBatchSize: z.number().default(DEFAULT_ANNOTATION_BATCH_SIZE),
  annotationMaxNodes: z.number().default(DEFAULT_ANNOTATION_MAX_NODES),
  annotationMaxCharsPerNode: z.number().default(DEFAULT_ANNOTATION_MAX_CHARS),
  includeSourceInAnnotations: z.boolean().default(true),
})

/**
 * Validate configuration that cannot be expressed by the schema alone.
 *
 * @param {ReturnType<typeof resolveConfig>} config
 */
function validateConfig(config) {
  if (config.pythonPath.trim() === '') {
    throw new Error('dsh-archmap-explorer: pythonPath must be non-empty')
  }
  if (config.defaultOutputDir.trim() === '') {
    throw new Error('dsh-archmap-explorer: defaultOutputDir must be non-empty')
  }
  for (const [key, value] of [
    ['toolTimeoutMs', config.toolTimeoutMs],
    ['llmMaxTokens', config.llmMaxTokens],
    ['annotationBatchSize', config.annotationBatchSize],
    ['annotationMaxNodes', config.annotationMaxNodes],
    ['annotationMaxCharsPerNode', config.annotationMaxCharsPerNode],
  ]) {
    if (!Number.isInteger(value) || value < 1) {
      throw new Error(`dsh-archmap-explorer: ${key} must be a positive integer`)
    }
  }
  if (Boolean(config.provider) !== Boolean(config.model)) {
    throw new Error('dsh-archmap-explorer: provider and model must be configured together')
  }
}

function resolveConfig(config) {
  return {
    pythonPath: config?.pythonPath || DEFAULT_PYTHON,
    defaultOutputDir: config?.defaultOutputDir || DEFAULT_OUTPUT_DIR,
    toolTimeoutMs: config?.toolTimeoutMs ?? DEFAULT_TIMEOUT_MS,
    provider: config?.provider || '',
    model: config?.model || '',
    llmMaxTokens: config?.llmMaxTokens ?? DEFAULT_LLM_MAX_TOKENS,
    annotationBatchSize: config?.annotationBatchSize ?? DEFAULT_ANNOTATION_BATCH_SIZE,
    annotationMaxNodes: config?.annotationMaxNodes ?? DEFAULT_ANNOTATION_MAX_NODES,
    annotationMaxCharsPerNode:
      config?.annotationMaxCharsPerNode ?? DEFAULT_ANNOTATION_MAX_CHARS,
    includeSourceInAnnotations: config?.includeSourceInAnnotations ?? true,
  }
}

/**
 * Register ArchMap tools and bundled Skills on the current Agent context.
 *
 * @param {import('@deepseek-ai/cordis').Context} ctx
 * @param {Partial<ReturnType<typeof resolveConfig>>} [config]
 */
export async function apply(ctx, config) {
  const resolved = resolveConfig(config)
  validateConfig(resolved)
  await validateBundledSkills()

  ctx.tools.register(buildTool(ctx, resolved))
  ctx.tools.register(annotateTool(ctx, resolved))
  ctx.skills.registerProvider(() => createSkillProvider())
}

/**
 * Verify the mandatory bundled configuration Skill and the companion source
 * conventions Skill before exposing any tool. A package missing either body is
 * not a working installation.
 */
async function validateBundledSkills() {
  for (const skill of BUNDLED_SKILLS) {
    let content
    try {
      content = await readFile(skill.locator, 'utf8')
    } catch (error) {
      throw new Error(
        `ARCHMAP_SKILL_MISSING: bundled Skill ${skill.name} is unreadable: ${error.message}`,
      )
    }
    if (content.trim() === '') {
      throw new Error(`ARCHMAP_SKILL_MISSING: bundled Skill ${skill.name} is empty`)
    }
  }
}

function createSkillProvider() {
  return {
    name: PROVIDER_NAME,
    list() {
      return Promise.resolve(BUNDLED_SKILLS)
    },
    async get(candidate, options = {}) {
      const skill = BUNDLED_SKILLS.find((item) => item.name === candidate?.name)
      if (!skill) return undefined
      const content = await readFile(skill.locator, {
        encoding: 'utf8',
        signal: options.signal,
      })
      if (content.trim() === '') {
        throw new Error(`ARCHMAP_SKILL_MISSING: bundled Skill ${skill.name} is empty`)
      }
      const { rank: _rank, locator: _locator, ...summary } = skill
      return { ...summary, content }
    },
  }
}

/**
 * Create the deterministic `archmap_build` tool definition.
 */
function buildTool(ctx, config) {
  return defineTool({
    name: 'archmap_build',
    description:
      'Build an ArchMap architecture artifact for a Python project through the bundled deterministic Python core. Returns project/module/function/flow counts, diagnostic statistics, and absolute architecture.json/architecture.html paths. Use this for architecture maps, module composition, function details, call topology, execution-flow inspection, or before generating LLM semantic annotations. The build itself never calls a model.',
    parameters: {
      projectPath: {
        type: 'string',
        required: true,
        description: 'Python project root, relative to the DSH session workspace.',
      },
      configPath: {
        type: 'string',
        description:
          'Optional archmap.config.json path, relative to the DSH session workspace. When omitted, ArchMap uses the project default or mechanical module discovery.',
      },
      outDir: {
        type: 'string',
        description:
          'Optional output directory inside the DSH session workspace. Defaults to <project>/.archmap.',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          ok: { type: 'boolean', required: true },
          text: { type: 'string', required: true },
          project: { type: 'string' },
          moduleCount: { type: 'integer' },
          functionCount: { type: 'integer' },
          executionFlowCount: { type: 'integer' },
          callSiteCount: { type: 'integer' },
          warningCount: { type: 'integer' },
          errorCount: { type: 'integer' },
          diagnostics: {
            type: 'object',
            required: true,
            additionalProperties: false,
            properties: {
              error: { type: 'integer', required: true },
              warning: { type: 'integer', required: true },
              info: { type: 'integer', required: true },
            },
          },
          fingerprint: { type: 'string' },
          jsonPath: { type: 'string' },
          htmlPath: { type: 'string' },
        },
      },
      render: (_args, value) => [{ type: 'text', text: value.text }],
    },
    timeoutMs: config.toolTimeoutMs,
    presentCall(args) {
      return {
        card: 'generic',
        title: `Build ArchMap: ${args.projectPath}`,
        kind: 'edit',
        rawInput: args.outDir || config.defaultOutputDir,
      }
    },
    async execute(args, exec) {
      const root = await workspaceRoot(ctx, exec)
      const project = resolveWorkspacePath(root, args.projectPath)
      const outDir = args.outDir
        ? resolveWorkspacePath(root, args.outDir)
        : resolveWorkspacePath(root, join(project, config.defaultOutputDir))
      const configPath = args.configPath
        ? resolveWorkspacePath(root, args.configPath)
        : null

      const cliArgs = ['build', project, '--out', outDir]
      if (configPath) cliArgs.push('--config', configPath)

      const processResult = await runPython(config, root, cliArgs, exec)
      const jsonPath = join(outDir, 'architecture.json')
      const htmlPath = join(outDir, 'architecture.html')
      const jsonExists = await fileExists(jsonPath)
      const htmlExists = await fileExists(htmlPath)

      if (!jsonExists) {
        return failure(
          'ArchMap build did not produce architecture.json',
          processResult,
          jsonPath,
          htmlPath,
        )
      }

      let bundle
      try {
        bundle = await readJsonObject(jsonPath)
      } catch (error) {
        return failure(
          `ArchMap build produced unreadable JSON: ${error instanceof Error ? error.message : String(error)}`,
          processResult,
          jsonPath,
          htmlPath,
        )
      }

      const stats = objectValue(bundle.stats)
      const diagnostics = objectValue(stats.diagnostics)
      const errorCount = integerValue(diagnostics.error)
      const warningCount = integerValue(diagnostics.warning)
      const infoCount = integerValue(diagnostics.info)
      const diagnosticsPayload = { error: errorCount, warning: warningCount, info: infoCount }
      const projectName = stringValue(objectValue(bundle.project).name)

      if (processResult.code !== 0 || errorCount > 0 || !htmlExists) {
        const reason =
          processResult.code !== 0
            ? `ArchMap build failed with exit code ${processResult.code}`
            : errorCount > 0
              ? `ArchMap build produced ${errorCount} validation error(s)`
              : 'ArchMap build did not produce architecture.html'
        return {
          ok: false,
          text: `${reason}\n${summarizeProcessError(processResult)}`.trim(),
          project: projectName,
          moduleCount: integerValue(stats.modules),
          functionCount: integerValue(stats.functions),
          executionFlowCount: integerValue(stats.executionFlows),
          callSiteCount: integerValue(stats.callSites),
          warningCount,
          errorCount,
          diagnostics: diagnosticsPayload,
          fingerprint: stringValue(objectValue(bundle.project).fingerprint),
          jsonPath,
          htmlPath,
        }
      }

      const lines = [
        `ArchMap build: ${projectName || args.projectPath}`,
        `fingerprint: ${stringValue(objectValue(bundle.project).fingerprint) || '-'}`,
        `modules: ${integerValue(stats.modules)}`,
        `functions: ${integerValue(stats.functions)}`,
        `execution flows: ${integerValue(stats.executionFlows)}`,
        `call sites: ${integerValue(stats.callSites)}`,
        `diagnostics: ${errorCount} error(s), ${warningCount} warning(s), ${infoCount} info`,
        `json: ${jsonPath}`,
        `html: ${htmlPath}`,
      ]
      const stderr = String(processResult.stderr || '').trim()
      if (stderr) lines.push(`warnings:\n${stderr.slice(0, 1600)}`)

      return {
        ok: true,
        text: lines.join('\n'),
        project: projectName,
        moduleCount: integerValue(stats.modules),
        functionCount: integerValue(stats.functions),
        executionFlowCount: integerValue(stats.executionFlows),
        callSiteCount: integerValue(stats.callSites),
        warningCount,
        errorCount,
        diagnostics: diagnosticsPayload,
        fingerprint: stringValue(objectValue(bundle.project).fingerprint),
        jsonPath,
        htmlPath,
      }
    },
  })
}

/**
 * Create the host-model `archmap_annotate` tool definition.
 */
function annotateTool(ctx, config) {
  return defineTool({
    name: 'archmap_annotate',
    description:
      'Generate source-backed LLM semantic annotations for ArchMap project/module/function nodes through the current DSH host model, write llm-annotations.json, and re-render architecture.html. Provide projectPath to build first or bundlePath to annotate an existing bundle. Manual and existing annotations are preserved unless force=true. The deterministic Python core owns node identity, source hashes, proposal validation and rendering; the model only returns summary/details text.',
    parameters: {
      projectPath: {
        type: 'string',
        description:
          'Python project root to build first. Mutually exclusive with bundlePath.',
      },
      bundlePath: {
        type: 'string',
        description:
          'Existing architecture.json to annotate. Mutually exclusive with projectPath.',
      },
      scope: {
        type: 'string',
        enum: ['project', 'modules', 'functions', 'all'],
        description: 'Annotation target scope. Defaults to functions.',
      },
      nodeIds: {
        type: 'array',
        items: { type: 'string' },
        description: 'Optional exact node IDs to annotate.',
      },
      maxNodes: {
        type: 'integer',
        description: 'Maximum nodes in this call. Defaults to plugin annotationMaxNodes.',
      },
      includeSource: {
        type: 'boolean',
        description:
          'Whether Python should include bounded source excerpts in the model context.',
      },
      force: {
        type: 'boolean',
        description:
          'Overwrite existing/manual annotations. Defaults to false so existing annotations are preserved.',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          ok: { type: 'boolean', required: true },
          text: { type: 'string', required: true },
          applied: { type: 'integer', required: true },
          skipped: { type: 'integer', required: true },
          rejected: { type: 'integer', required: true },
          batchCount: { type: 'integer', required: true },
          provider: { type: 'string', required: true },
          model: { type: 'string', required: true },
          promptVersion: { type: 'string', required: true },
          bundlePath: { type: 'string', required: true },
          annotationsPath: { type: 'string', required: true },
          htmlPath: { type: 'string', required: true },
        },
      },
      render: (_args, value) => [{ type: 'text', text: value.text }],
    },
    timeoutMs: config.toolTimeoutMs,
    presentCall(args) {
      return {
        card: 'generic',
        title: `Generate ArchMap annotations: ${args.bundlePath || args.projectPath || 'project'}`,
        kind: 'edit',
        rawInput: args.scope || 'functions',
      }
    },
    async execute(args, exec) {
      let bundlePath = ''
      try {
        if (Boolean(args.projectPath) === Boolean(args.bundlePath)) {
          return annotationFailure(
            'ARCHMAP_ARGUMENT_INVALID: provide exactly one of projectPath or bundlePath',
          )
        }
        const root = await workspaceRoot(ctx, exec)
        if (args.projectPath) {
          const project = resolveWorkspacePath(root, args.projectPath)
          const outDir = resolveWorkspacePath(root, join(project, config.defaultOutputDir))
          const buildResult = await runPython(
            config,
            root,
            ['build', project, '--out', outDir],
            exec,
          )
          bundlePath = join(outDir, 'architecture.json')
          if (buildResult.code !== 0 || !(await fileExists(bundlePath))) {
            return annotationFailure(
              `ArchMap build before annotation failed:\n${summarizeProcessError(buildResult)}`,
            )
          }
        } else {
          bundlePath = resolveWorkspacePath(root, args.bundlePath)
          if (!(await fileExists(bundlePath))) {
            return annotationFailure(`ARCHMAP_BUNDLE_MISSING: ${bundlePath}`)
          }
        }

        const maxNodes = args.maxNodes ?? config.annotationMaxNodes
        if (!Number.isInteger(maxNodes) || maxNodes < 1) {
          return annotationFailure('ARCHMAP_ARGUMENT_INVALID: maxNodes must be a positive integer')
        }
        const includeSource = args.includeSource ?? config.includeSourceInAnnotations
        const scope = args.scope || 'functions'
        const contextArgs = [
          'annotations',
          'context',
          bundlePath,
          '--scope',
          scope,
          '--max-nodes',
          String(maxNodes),
          '--max-chars',
          String(config.annotationMaxCharsPerNode),
          '--json',
        ]
        for (const nodeId of args.nodeIds || []) contextArgs.push('--node-id', nodeId)
        if (!includeSource) contextArgs.push('--no-source')

        const contextResult = await runPython(config, root, contextArgs, exec)
        if (contextResult.code !== 0) {
          return annotationFailure(
            `ArchMap annotation context failed:\n${summarizeProcessError(contextResult)}`,
            { bundlePath },
          )
        }
        const context = parseJsonStdout(contextResult.stdout, 'annotations context')
        const contextNodes = Array.isArray(context.nodes) ? context.nodes : []
        const candidates = args.force
          ? contextNodes
          : contextNodes.filter((node) => node.existingAnnotation === null || node.existingAnnotation === undefined)
        if (candidates.length === 0) {
          const bundleDir = dirname(bundlePath)
          return {
            ok: true,
            text: `ArchMap annotations: nothing to generate (${contextNodes.length} node(s) already annotated or out of scope)`,
            applied: 0,
            skipped: 0,
            rejected: 0,
            batchCount: 0,
            provider: '',
            model: '',
            promptVersion: String(context.promptVersion || ''),
            bundlePath,
            annotationsPath: join(bundleDir, 'llm-annotations.json'),
            htmlPath: join(bundleDir, 'architecture.html'),
          }
        }

        const batches = annotationBatches(candidates, config.annotationBatchSize)
        const proposalNodes = []
        let rejectedCount = 0
        let provider = ''
        let model = ''
        for (const batch of batches) {
          const modeled = await requestAnnotationBatch(ctx, exec, config, context, batch)
          proposalNodes.push(...modeled.nodes)
          rejectedCount += modeled.rejected.length
          provider = modeled.route.provider
          model = modeled.route.model
        }
        if (proposalNodes.length === 0) {
          return annotationFailure(
            'HOST_MODEL_INVALID_SHAPE: model returned no usable annotation nodes',
            { bundlePath, provider, model, batchCount: batches.length },
          )
        }

        const proposalPath = join(dirname(bundlePath), 'annotation-proposal.json')
        await writeFile(
          proposalPath,
          JSON.stringify({ nodes: proposalNodes }, null, 2) + '\n',
          'utf8',
        )
        const applyArgs = [
          'annotations',
          'apply',
          bundlePath,
          '--proposal',
          proposalPath,
          '--provider',
          provider,
          '--model',
          model,
          '--prompt-version',
          String(context.promptVersion || 'archmap-annotation-v1'),
          '--json',
        ]
        if (args.force) applyArgs.push('--force')
        const applyResult = await runPython(config, root, applyArgs, exec)
        if (applyResult.code !== 0) {
          return annotationFailure(
            `ArchMap annotation apply failed:\n${summarizeProcessError(applyResult)}`,
            { bundlePath, provider, model, batchCount: batches.length },
          )
        }
        const appliedPayload = parseJsonStdout(applyResult.stdout, 'annotations apply')
        const skipped = Array.isArray(appliedPayload.skipped) ? appliedPayload.skipped.length : 0
        const applied = Number.isInteger(appliedPayload.applied) ? appliedPayload.applied : 0
        const lines = [
          `ArchMap annotations generated: ${context.project?.name || bundlePath}`,
          `scope: ${scope}`,
          `provider: ${provider || '-'}`,
          `model: ${model || '-'}`,
          `applied: ${applied}`,
          `skipped: ${skipped}`,
          `rejected model nodes: ${rejectedCount}`,
          `batches: ${batches.length}`,
          `annotations: ${appliedPayload.annotationsPath || ''}`,
          `html: ${appliedPayload.htmlPath || ''}`,
        ]
        if (skipped > 0) {
          for (const item of appliedPayload.skipped.slice(0, 20)) {
            lines.push(`- ${item.nodeId}: ${item.reason}`)
          }
        }
        return {
          ok: appliedPayload.ok !== false,
          text: lines.join('\n'),
          applied,
          skipped,
          rejected: rejectedCount,
          batchCount: batches.length,
          provider,
          model,
          promptVersion: String(context.promptVersion || ''),
          bundlePath,
          annotationsPath: String(appliedPayload.annotationsPath || ''),
          htmlPath: String(appliedPayload.htmlPath || ''),
        }
      } catch (error) {
        if (error?.name === 'AbortError') throw error
        return annotationFailure(
          error instanceof Error ? error.message : String(error),
          { bundlePath },
        )
      }
    },
  })
}

async function requestAnnotationBatch(ctx, exec, config, context, batch) {
  const payload = { project: context.project, nodes: batch }
  let result
  try {
    result = await hostJson(ctx, exec, config, {
      system: context.systemPrompt,
      payload,
      maxTokens: config.llmMaxTokens,
    })
    return { route: result.route, ...normalizeOrThrow(result, batch) }
  } catch (error) {
    if (!error?.rawText || error?.name === 'AbortError') throw error
    const repaired = await hostJson(ctx, exec, config, {
      system: context.systemPrompt,
      payload: {
        ...payload,
        repair: {
          previousResponse: String(error.rawText).slice(0, 12000),
          error: String(error.message || error).slice(0, 1200),
        },
      },
      maxTokens: config.llmMaxTokens,
    })
    return { route: repaired.route, ...normalizeOrThrow(repaired, batch) }
  }
}

function normalizeOrThrow(modelResult, batch) {
  let normalized
  try {
    normalized = normalizeAnnotationResponse(modelResult.json, batch)
  } catch (error) {
    const wrapped = new Error(error instanceof Error ? error.message : String(error))
    wrapped.rawText = modelResult.text
    throw wrapped
  }
  if (normalized.nodes.length === 0) {
    const error = new Error('HOST_MODEL_INVALID_SHAPE: model returned no usable annotation nodes')
    error.rawText = modelResult.text
    throw error
  }
  return normalized
}

function parseJsonStdout(stdout, label) {
  const text = String(stdout || '').trim()
  if (!text) throw new Error(`ARCHMAP_INVALID_JSON: ${label} returned no output`)
  let value
  try {
    value = JSON.parse(text)
  } catch (error) {
    throw new Error(`ARCHMAP_INVALID_JSON: ${label} returned invalid JSON: ${error.message}`)
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`ARCHMAP_INVALID_JSON: ${label} must return a JSON object`)
  }
  return value
}

function annotationFailure(message, extra = {}) {
  return {
    ok: false,
    text: String(message || 'ArchMap annotation failed').trim(),
    applied: 0,
    skipped: 0,
    rejected: 0,
    batchCount: extra.batchCount ?? 0,
    provider: extra.provider || '',
    model: extra.model || '',
    promptVersion: '',
    bundlePath: extra.bundlePath || '',
    annotationsPath: extra.annotationsPath || '',
    htmlPath: extra.htmlPath || '',
  }
}

function failure(message, processResult, jsonPath, htmlPath) {
  return {
    ok: false,
    text: `${message}\n${summarizeProcessError(processResult)}`.trim(),
    project: '',
    moduleCount: 0,
    functionCount: 0,
    executionFlowCount: 0,
    callSiteCount: 0,
    warningCount: 0,
    errorCount: 1,
    diagnostics: { error: 1, warning: 0, info: 0 },
    fingerprint: '',
    jsonPath,
    htmlPath,
  }
}

function objectValue(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function integerValue(value) {
  return Number.isInteger(value) ? value : 0
}

function stringValue(value) {
  return typeof value === 'string' ? value : ''
}
