/**
 * DSH adapter for the bundled ArchMap Python core.
 *
 * The plugin is intentionally thin: Python owns analysis, graph projection,
 * annotation validation and HTML rendering. This module owns DSH tool schemas,
 * workspace confinement, host-model orchestration and bundled Skill delivery.
 *
 * @module dsh-archmap-explorer
 */

import { readFile, stat, writeFile } from 'node:fs/promises'
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
  ctx.tools.register(queryTool(ctx, resolved))
  ctx.tools.register(guideTool(ctx, resolved))
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
          issues: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: true,
              properties: {
                severity: { type: 'string' },
                code: { type: 'string' },
                message: { type: 'string' },
                file: { type: 'string' },
                line: { type: 'integer' },
                functionId: { type: 'string' },
                moduleId: { type: 'string' },
                nodeId: { type: 'string' },
              },
            },
          },
          issueSummary: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                code: { type: 'string', required: true },
                count: { type: 'integer', required: true },
              },
            },
          },
          nextActions: { type: 'array', items: { type: 'string' } },
          durationMs: { type: 'integer' },
          bundleBytes: { type: 'integer' },
          htmlBytes: { type: 'integer' },
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
      const startedAt = Date.now()
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
      const artifacts = await artifactSizes(jsonPath, htmlPath)
      const durationMs = Date.now() - startedAt

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
      const validation = await readValidationIssues(config, root, jsonPath, exec)
      const issues = validation.issues
      const issueSummary = summarizeIssues(issues)
      const nextActions = buildNextActions(issues)
      const validationErrors = issues.filter((issue) => issue?.severity === 'error').length
      const warningIssues = issues.filter((issue) => issue?.severity !== 'error').length
      const errorCount = Math.max(integerValue(diagnostics.error), validationErrors)
      const warningCount = Math.max(integerValue(diagnostics.warning), warningIssues)
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
        const issueText = formatIssues(issues)
        const actionText = nextActions.length
          ? `\nnext actions:\n${nextActions.map((item) => `- ${item}`).join('\n')}`
          : ''
        return {
          ok: false,
          text: `${reason}\n${summarizeProcessError(processResult)}${issueText ? `\n${issueText}` : ''}${actionText}`.trim(),
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
          issues,
          issueSummary,
          nextActions,
          durationMs,
          bundleBytes: artifacts.jsonBytes,
          htmlBytes: artifacts.htmlBytes,
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
        `duration: ${durationMs}ms`,
        `json: ${jsonPath}`,
        `html: ${htmlPath}`,
      ]
      if (issues.length) lines.push(formatIssues(issues))
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
        issues,
        issueSummary,
        nextActions,
        durationMs,
        bundleBytes: artifacts.jsonBytes,
        htmlBytes: artifacts.htmlBytes,
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
      'Generate source-backed LLM semantic annotations for ArchMap project/module/function nodes through the current DSH host model, write llm-annotations.json, and re-render architecture.html. Provide projectPath to build first or bundlePath to annotate an existing bundle. refreshMode selects missing/stale/all targets before maxNodes truncation; force=true maps to refreshMode=all. Manual annotations are preserved unless all/force is used. The deterministic Python core owns node identity, source hashes, proposal validation and rendering; the model only returns summary/details text.',
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
          'Overwrite existing/manual annotations. Defaults to false so existing annotations are preserved. Maps to refreshMode=all.',
      },
      refreshMode: {
        type: 'string',
        enum: ['missing', 'stale', 'all'],
        description:
          'Target selection before maxNodes truncation: missing only absent annotations, stale missing plus hash-mismatched machine annotations, all every target. Defaults to missing; force=true overrides to all.',
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
          totalCandidates: { type: 'integer', required: true },
          eligibleCount: { type: 'integer', required: true },
          selectedCount: { type: 'integer', required: true },
          remainingCount: { type: 'integer', required: true },
          missingCount: { type: 'integer', required: true },
          freshCount: { type: 'integer', required: true },
          staleCount: { type: 'integer', required: true },
          manualPreservedCount: { type: 'integer', required: true },
          truncated: { type: 'boolean', required: true },
          durationMs: { type: 'integer' },
          batchDurationsMs: { type: 'array', items: { type: 'integer' } },
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
      const startedAt = Date.now()
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
        const refreshMode = args.force ? 'all' : String(args.refreshMode || 'missing')
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
          '--refresh-mode',
          refreshMode,
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
        const statusCounts = objectValue(context.statusCounts)
        const totalCandidates = integerValue(context.totalCandidates)
        const eligibleCount = integerValue(context.eligibleCount)
        const selectedCount = integerValue(context.selectedCount)
        const remainingCount = integerValue(context.remainingCount)
        const truncated = Boolean(context.truncated)
        const missingCount = integerValue(statusCounts.missing)
        const freshCount = integerValue(statusCounts.fresh)
        const staleCount = integerValue(statusCounts.stale)
        const manualPreservedCount = integerValue(statusCounts['manual-preserved'])
        const counts = {
          totalCandidates,
          eligibleCount,
          selectedCount,
          remainingCount,
          missingCount,
          freshCount,
          staleCount,
          manualPreservedCount,
          truncated,
        }
        if (contextNodes.length === 0) {
          const bundleDir = dirname(bundlePath)
          return {
            ok: true,
            text: `ArchMap annotations: nothing to generate (refreshMode=${refreshMode}, total=${totalCandidates}, remaining=${remainingCount})`,
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
            durationMs: Date.now() - startedAt,
            batchDurationsMs: [],
            ...counts,
          }
        }
        const candidates = contextNodes

        const batches = annotationBatches(candidates, config.annotationBatchSize)
        const proposalNodes = []
        const batchDurationsMs = []
        let rejectedCount = 0
        let provider = ''
        let model = ''
        for (const batch of batches) {
          const batchStartedAt = Date.now()
          const modeled = await requestAnnotationBatch(ctx, exec, config, context, batch)
          batchDurationsMs.push(Date.now() - batchStartedAt)
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
        if (args.force || refreshMode === 'all') applyArgs.push('--force')
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
          `refreshMode: ${refreshMode}`,
          `provider: ${provider || '-'}`,
          `model: ${model || '-'}`,
          `targets: total=${totalCandidates} selected=${selectedCount} remaining=${remainingCount} truncated=${truncated}`,
          `status: missing=${missingCount} fresh=${freshCount} stale=${staleCount} manual=${manualPreservedCount}`,
          `applied: ${applied}`,
          `skipped: ${skipped}`,
          `rejected model nodes: ${rejectedCount}`,
          `batches: ${batches.length}`,
          `duration: ${Date.now() - startedAt}ms (batch ms: ${batchDurationsMs.join(',') || '-'})`,
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
          durationMs: Date.now() - startedAt,
          batchDurationsMs,
          ...counts,
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

const GUIDE_TOPICS = {
  'code-conventions': new URL('../docs/archmap-code-conventions.md', import.meta.url),
  'config-generation': new URL('../docs/archmap-config-generation.md', import.meta.url),
  usage: new URL('../docs/dsh-plugin.md', import.meta.url),
}
const MAX_GUIDE_CHARS = 32000

/**
 * Deterministic fallback for hosts that do not expose the native `skill` tool.
 * It reads the same bundled Markdown bodies as the Skill provider; it does not
 * maintain a second copy of the conventions.
 */
function guideTool(ctx, config) {
  return defineTool({
    name: 'archmap_guide',
    description:
      'Read the authoritative bundled ArchMap guidance when the DSH native skill tool is unavailable or the user explicitly asks for conventions. Topics: code-conventions (module boundaries, Provider roles, capability surfaces, entrypoints, notes, tests), config-generation (archmap.config.json generation and validation), usage (plugin tools and workflow). Returns bounded Markdown content from the same package docs used by bundled Skills.',
    parameters: {
      topic: {
        type: 'string',
        required: true,
        enum: Object.keys(GUIDE_TOPICS),
        description: 'Guidance topic to read.',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          ok: { type: 'boolean', required: true },
          text: { type: 'string', required: true },
          topic: { type: 'string', required: true },
          sourcePath: { type: 'string', required: true },
          charCount: { type: 'integer', required: true },
          truncated: { type: 'boolean', required: true },
        },
      },
      render: (_args, value) => [{ type: 'text', text: value.text }],
    },
    timeoutMs: config.toolTimeoutMs,
    presentCall(args) {
      return {
        card: 'generic',
        title: `ArchMap guide: ${args.topic}`,
        kind: 'read',
        rawInput: args.topic,
      }
    },
    async execute(args) {
      const topic = String(args.topic || '')
      const locator = GUIDE_TOPICS[topic]
      if (!locator) {
        return {
          ok: false,
          text: `ARCHMAP_ARGUMENT_INVALID: unsupported guide topic ${topic || '(missing)'}`,
          topic,
          sourcePath: '',
          charCount: 0,
          truncated: false,
        }
      }
      try {
        const content = await readFile(locator, 'utf8')
        const sourcePath = fileURLToPath(locator)
        const truncated = content.length > MAX_GUIDE_CHARS
        const body = truncated ? content.slice(0, MAX_GUIDE_CHARS) : content
        return {
          ok: true,
          text: `ArchMap guide: ${topic}\n${sourcePath}\n\n${body}`,
          topic,
          sourcePath,
          charCount: content.length,
          truncated,
        }
      } catch (error) {
        return {
          ok: false,
          text: `ARCHMAP_GUIDE_UNAVAILABLE: ${error instanceof Error ? error.message : String(error)}`,
          topic,
          sourcePath: '',
          charCount: 0,
          truncated: false,
        }
      }
    },
  })
}

/**
 * Create the read-only `archmap_query` tool definition.
 *
 * Query results are bounded and never written back into the bundle. The tool
 * intentionally shells out to the bundled Python CLI so query semantics stay
 * authoritative in the Python core.
 */
function queryTool(ctx, config) {
  return defineTool({
    name: 'archmap_query',
    description:
      'Run read-only ArchMap queries through the bundled Python core: validate a bundle (check), trace call/polymorphic paths, compare before/after bundles for impact, list User Surfaces, build a module/provider DSM, or inspect one method detail. Prefer this tool over shelling out to the ArchMap CLI. Query results are bounded and never modify source, bundle, or annotations.',
    parameters: {
      operation: {
        type: 'string',
        required: true,
        enum: ['check', 'trace', 'impact', 'surfaces', 'dsm', 'method'],
        description: 'Query operation to execute.',
      },
      bundlePath: {
        type: 'string',
        description:
          'Existing architecture.json path for check/trace/surfaces/dsm. Relative to the DSH workspace.',
      },
      beforePath: {
        type: 'string',
        description: 'Before architecture.json path for impact.',
      },
      afterPath: {
        type: 'string',
        description: 'After architecture.json path for impact.',
      },
      projectPath: {
        type: 'string',
        description: 'Python project root for method lookup.',
      },
      configPath: {
        type: 'string',
        description: 'Optional archmap.config.json path for method lookup.',
      },
      file: {
        type: 'string',
        description: 'Optional method source filename filter for method lookup.',
      },
      function: {
        type: 'string',
        description: 'Optional function/method name filter for method lookup.',
      },
      start: {
        type: 'string',
        description: 'Trace start function/provider id or resolvable symbol.',
      },
      direction: {
        type: 'string',
        enum: ['outbound', 'inbound'],
        description: 'Trace direction. Defaults to outbound.',
      },
      module: {
        type: 'string',
        description: 'Optional module id filter for surfaces.',
      },
      level: {
        type: 'string',
        enum: ['module', 'provider'],
        description: 'DSM aggregation level. Defaults to module.',
      },
      maxDepth: {
        type: 'integer',
        description: 'Maximum trace/impact depth.',
      },
      maxNodes: {
        type: 'integer',
        description: 'Maximum trace/impact nodes.',
      },
      includeInternal: {
        type: 'boolean',
        description: 'Include internal functions/providers where supported.',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          ok: { type: 'boolean', required: true },
          text: { type: 'string', required: true },
          operation: { type: 'string', required: true },
          truncated: { type: 'boolean', required: true },
          warnings: { type: 'array', items: { type: 'string' }, required: true },
          data: { type: 'object', additionalProperties: true, required: true },
        },
      },
      render: (_args, value) => [{ type: 'text', text: value.text }],
    },
    timeoutMs: config.toolTimeoutMs,
    presentCall(args) {
      return {
        card: 'generic',
        title: `Query ArchMap: ${args.operation}`,
        kind: 'read',
        rawInput: args.bundlePath || args.beforePath || args.projectPath || '',
      }
    },
    async execute(args, exec) {
      const operation = String(args.operation || '')
      const root = await workspaceRoot(ctx, exec)
      let cliArgs
      if (operation === 'check') {
        const bundlePath = requireWorkspacePath(root, args.bundlePath, 'bundlePath')
        cliArgs = ['check', bundlePath, '--json']
      } else if (operation === 'trace') {
        if (!args.start) {
          return queryFailure(operation, 'ARCHMAP_ARGUMENT_INVALID: trace requires start')
        }
        const bundlePath = requireWorkspacePath(root, args.bundlePath, 'bundlePath')
        cliArgs = [
          'trace',
          bundlePath,
          '--from',
          String(args.start),
          '--direction',
          args.direction === 'inbound' ? 'inbound' : 'outbound',
          '--max-depth',
          String(positiveInteger(args.maxDepth, 8)),
          '--max-nodes',
          String(positiveInteger(args.maxNodes, 200)),
          '--json',
        ]
        if (args.includeInternal === false) cliArgs.push('--exclude-internal')
      } else if (operation === 'impact') {
        const beforePath = requireWorkspacePath(root, args.beforePath, 'beforePath')
        const afterPath = requireWorkspacePath(root, args.afterPath, 'afterPath')
        cliArgs = [
          'impact',
          beforePath,
          afterPath,
          '--max-depth',
          String(positiveInteger(args.maxDepth, 6)),
          '--max-nodes',
          String(positiveInteger(args.maxNodes, 200)),
          '--json',
        ]
      } else if (operation === 'surfaces') {
        const bundlePath = requireWorkspacePath(root, args.bundlePath, 'bundlePath')
        cliArgs = ['surfaces', bundlePath, '--json']
        if (args.module) cliArgs.push('--module', String(args.module))
      } else if (operation === 'dsm') {
        const bundlePath = requireWorkspacePath(root, args.bundlePath, 'bundlePath')
        cliArgs = [
          'dsm',
          bundlePath,
          '--level',
          String(args.level || 'module'),
          '--json',
        ]
        if (args.includeInternal) cliArgs.push('--include-internal')
      } else if (operation === 'method') {
        const projectPath = requireWorkspacePath(root, args.projectPath, 'projectPath')
        cliArgs = ['method', projectPath]
        if (args.configPath) {
          cliArgs.push('--config', requireWorkspacePath(root, args.configPath, 'configPath'))
        }
        if (args.file) cliArgs.push('--file', String(args.file))
        if (args.function) cliArgs.push('--function', String(args.function))
        cliArgs.push('--json')
      } else {
        return queryFailure(operation, `ARCHMAP_ARGUMENT_INVALID: unsupported query operation ${operation || '(missing)'}`)
      }

      const processResult = await runPython(config, root, cliArgs, exec)
      let data
      try {
        data =
          operation === 'surfaces'
            ? parseJsonStdoutValue(processResult.stdout, `archmap query ${operation}`)
            : parseJsonStdout(processResult.stdout, `archmap query ${operation}`)
      } catch (error) {
        return queryFailure(
          operation,
          `${error instanceof Error ? error.message : String(error)}\n${summarizeProcessError(processResult)}`,
          processResult.code,
        )
      }
      const maxNodes = positiveInteger(args.maxNodes, 200)
      if (operation === 'surfaces') {
        if (!Array.isArray(data)) {
          return queryFailure(
            operation,
            'ARCHMAP_INVALID_JSON: archmap query surfaces must return an array',
            processResult.code,
          )
        }
        const total = data.length
        const items = data.slice(0, maxNodes)
        data = {
          items,
          total,
          returned: items.length,
          omitted: total - items.length,
          truncated: items.length < total,
          budget: { maxNodes },
        }
      }
      if (operation === 'check' && Array.isArray(data.issues) && data.issues.length > maxNodes) {
        data = {
          ...data,
          issues: data.issues.slice(0, maxNodes),
          truncated: true,
          budget: { maxNodes, totalIssues: data.issues.length, returnedIssues: maxNodes },
        }
      }
      if (operation === 'dsm') {
        const allNodes = Array.isArray(data.nodes) ? data.nodes.map((item) => String(item)) : []
        const retainedNodes = allNodes.slice(0, maxNodes)
        const kept = new Set(retainedNodes)
        const matrix = Object.fromEntries(
          Object.entries(objectValue(data.matrix))
            .filter(([source]) => kept.has(source))
            .map(([source, targets]) => [
              source,
              Object.fromEntries(
                Object.entries(objectValue(targets)).filter(([target]) => kept.has(target)),
              ),
            ]),
        )
        const returnedEdges = Object.values(matrix).reduce(
          (total, targets) => total + Object.keys(objectValue(targets)).length,
          0,
        )
        data = {
          ...data,
          nodes: retainedNodes,
          matrix,
          truncated: retainedNodes.length < allNodes.length,
          budget: {
            maxNodes,
            totalNodes: allNodes.length,
            returnedNodes: retainedNodes.length,
            omittedNodes: allNodes.length - retainedNodes.length,
            returnedEdges,
          },
        }
      }
      if (!data || typeof data !== 'object' || Array.isArray(data)) {
        return queryFailure(
          operation,
          `ARCHMAP_INVALID_JSON: archmap query ${operation} must return an object`,
          processResult.code,
        )
      }
      const warnings = queryWarnings(operation, data, processResult)
      const truncated = Boolean(data.truncated)
      const text = formatQueryText(operation, data, processResult, truncated)
      return {
        ok: processResult.code === 0,
        text,
        operation,
        truncated,
        warnings,
        data,
      }
    },
  })
}

function requireWorkspacePath(root, value, label) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`ARCHMAP_ARGUMENT_INVALID: ${label} is required for this query`)
  }
  return resolveWorkspacePath(root, value)
}

function positiveInteger(value, fallback) {
  return Number.isInteger(value) && value > 0 ? value : fallback
}

function queryFailure(operation, message, exitCode = null) {
  return {
    ok: false,
    text: String(message || 'ArchMap query failed').trim(),
    operation,
    truncated: false,
    warnings: exitCode === null ? [] : [`exitCode=${exitCode}`],
    data: {},
  }
}

function queryWarnings(operation, data, processResult) {
  const warnings = []
  if (operation === 'check' && Array.isArray(data.issues)) {
    warnings.push(
      ...data.issues
        .filter((issue) => issue?.severity !== 'error')
        .slice(0, 20)
        .map((issue) => `${issue?.code || 'ISSUE'}: ${issue?.message || ''}`),
    )
  }
  if (operation === 'trace' && integerValue(data.unresolvedCount) > 0) {
    warnings.push(
      `${integerValue(data.unresolvedCount)} unresolved reference(s) may concern the trace start; they are low-confidence hints, not call edges`,
    )
  }
  if (operation === 'method' && integerValue(data.unresolvedCallerCount) > 0) {
    warnings.push(
      `${integerValue(data.unresolvedCallerCount)} possible unresolved caller(s); callerCount only includes resolved call sites`,
    )
  }
  if (data.truncated) warnings.push(`${operation} result truncated`)
  const stderr = String(processResult.stderr || '').trim()
  if (stderr) warnings.push(stderr.slice(0, 1200))
  return warnings
}

function formatQueryText(operation, data, processResult, truncated) {
  if (operation === 'check') {
    const line = `${integerValue(data.errorCount)} error(s), ${integerValue(data.warningCount)} warning(s), issues=${integerValue(data.issueCount)} returned=${Array.isArray(data.issues) ? data.issues.length : 0} truncated=${truncated}`
    return [line, formatIssues(Array.isArray(data.issues) ? data.issues : [])]
      .filter(Boolean)
      .join('\n')
  }
  if (operation === 'trace') {
    return `trace: nodes=${Array.isArray(data.nodes) ? data.nodes.length : 0} paths=${Array.isArray(data.paths) ? data.paths.length : 0} unresolved=${integerValue(data.unresolvedCount)} truncated=${truncated}`
  }
  if (operation === 'impact') {
    const summary = objectValue(data.summary)
    return `impact: functions=${integerValue(summary.functions)} providers=${integerValue(summary.providers)} apis=${integerValue(summary.apis)} surfaces=${integerValue(summary.surfaces)} total=${integerValue(summary.total)} truncated=${truncated}`
  }
  if (operation === 'surfaces') {
    return `surfaces: total=${integerValue(data.total)} returned=${integerValue(data.returned)} omitted=${integerValue(data.omitted)} truncated=${truncated}`
  }
  if (operation === 'dsm') {
    const stats = objectValue(data.stats)
    const budget = objectValue(data.budget)
    return `dsm: nodes=${integerValue(budget.returnedNodes)}/${integerValue(budget.totalNodes)} edges=${integerValue(budget.returnedEdges)} totalEdges=${integerValue(stats.edges)} truncated=${truncated}`
  }
  if (operation === 'method') {
    return `${stringValue(data.qualifiedName) || stringValue(data.id)} (${stringValue(data.file)}:${integerValue(data.line)}) callers=${integerValue(data.callerCount)} unresolvedCallers=${integerValue(data.unresolvedCallerCount)} callees=${integerValue(data.calleeCount)}`
  }
  const stderr = String(processResult.stderr || '').trim()
  return stderr || `${operation}: ok`
}

function formatIssues(issues, limit = 20) {
  if (!Array.isArray(issues) || issues.length === 0) return ''
  const lines = ['issues:']
  for (const issue of issues.slice(0, limit)) {
    const severity = String(issue?.severity || 'info').toUpperCase()
    const code = String(issue?.code || 'ISSUE')
    const location = [issue?.file, issue?.line].filter((part) => part !== undefined && part !== '').join(':')
    const suffix = location ? ` [${location}]` : ''
    lines.push(`${severity} ${code}${suffix}: ${String(issue?.message || '')}`)
  }
  if (issues.length > limit) lines.push(`... ${issues.length - limit} more issue(s)`)
  return lines.join('\n')
}

function summarizeIssues(issues) {
  const counts = new Map()
  for (const issue of issues) {
    const code = String(issue?.code || 'ISSUE')
    counts.set(code, (counts.get(code) || 0) + 1)
  }
  return [...counts.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([code, count]) => ({ code, count }))
}

function buildNextActions(issues) {
  const codes = new Set(
    issues.flatMap((issue) => [issue?.code, issue?.sourceCode].map((code) => String(code || ''))),
  )
  const messages = issues.map((issue) => String(issue?.message || '')).join('\n')
  const actions = []
  if (
    [...codes].some(
      (code) => code.includes('CONFIG') || code.includes('PROVIDER_') || code.includes('API_EXPOSURE'),
    ) ||
    /PROVIDER_ROLE|API_EXPOSURE|CONFIG_|contract\./i.test(messages)
  ) {
    actions.push('Inspect archmap.config.json target keys and rerun archmap_query check after correcting them.')
  }
  if ([...codes].some((code) => code.includes('POLYMORPHIC') || code.includes('CALL_'))) {
    actions.push('Inspect unresolved call sites with archmap_query trace; preserve intended abstractions and use dispatch hints or explicit incomplete evidence instead of deleting them.')
  }
  if ([...codes].some((code) => code.includes('MISSING') || code.includes('DUPLICATE') || code.includes('SCHEMA'))) {
    actions.push('Run archmap_query check on the written bundle and fix structural references before rerunning build.')
  }
  if (actions.length === 0 && issues.length > 0) {
    actions.push('Run archmap_query check with --json semantics to inspect the complete issue list.')
  }
  return actions
}

async function readValidationIssues(config, root, bundlePath, exec) {
  if (!(await fileExists(bundlePath))) return { issues: [] }
  try {
    const result = await runPython(config, root, ['check', bundlePath, '--json'], exec)
    const payload = parseJsonStdout(result.stdout, 'archmap check')
    return { issues: Array.isArray(payload.issues) ? payload.issues : [] }
  } catch (error) {
    return {
      issues: [
        {
          severity: 'error',
          code: 'CHECK_FAILED',
          message: error instanceof Error ? error.message : String(error),
        },
      ],
    }
  }
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

function parseJsonStdoutValue(stdout, label) {
  const text = String(stdout || '').trim()
  if (!text) throw new Error(`ARCHMAP_INVALID_JSON: ${label} returned no output`)
  try {
    return JSON.parse(text)
  } catch (error) {
    throw new Error(`ARCHMAP_INVALID_JSON: ${label} returned invalid JSON: ${error.message}`)
  }
}

function parseJsonStdout(stdout, label) {
  const value = parseJsonStdoutValue(stdout, label)
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
    totalCandidates: 0,
    eligibleCount: 0,
    selectedCount: 0,
    remainingCount: 0,
    missingCount: 0,
    freshCount: 0,
    staleCount: 0,
    manualPreservedCount: 0,
    truncated: false,
    durationMs: 0,
    batchDurationsMs: [],
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
    durationMs: 0,
    bundleBytes: 0,
    htmlBytes: 0,
  }
}

async function artifactSizes(jsonPath, htmlPath) {
  const [jsonBytes, htmlBytes] = await Promise.all(
    [jsonPath, htmlPath].map(async (path) => {
      try {
        return (await stat(path)).size
      } catch {
        return 0
      }
    }),
  )
  return { jsonBytes, htmlBytes }
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
