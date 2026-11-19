import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { dirname, join, relative, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { parseJsonLoose, resolveHostRoute } from '../../lib/host-llm.js'
import { apply } from '../../lib/index.js'

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const FIXTURE = join(REPO_ROOT, 'tests', 'fixtures', 'student_demo')

function makeContext(root, llm = emptyLlm()) {
  const tools = []
  const skillProviderFactories = []
  const ctx = {
    tools: {
      register(tool) {
        tools.push(tool)
      },
    },
    skills: {
      registerProvider(create) {
        skillProviderFactories.push(create)
      },
    },
    llm,
    workingDirectory: {
      async ensure() {
        return root
      },
    },
  }
  return { ctx, tools, skillProviderFactories }
}

function emptyLlm() {
  return {
    listProviders() {
      return []
    },
    async listModels() {
      return []
    },
  }
}

function createMockAnnotationLlm() {
  const calls = []
  return {
    calls,
    llm: {
      listProviders() {
        return []
      },
      async listModels() {
        return []
      },
      async prepareCall(request, _signal, configure) {
        calls.push(request)
        const controls = configure ? configure({}, {}) : request
        const config = {
          provider: request.provider,
          model: request.model,
          ...controls,
        }
        return {
          config,
          stream(options) {
            const payload = JSON.parse(options.messages[0].content[0].text)
            const nodes = payload.nodes.map((node) => ({
              nodeId: node.nodeId,
              summary: `模型摘要：${node.name}`,
              details: `模型详情：${node.name}。`,
              sourceHash: 'sha256:' + '0'.repeat(64),
            }))
            return (async function* () {
              yield { type: 'text-delta', index: 0, text: JSON.stringify({ nodes }) }
              yield { type: 'finish', reason: { kind: 'stop' } }
            })()
          },
        }
      },
    },
  }
}

async function pluginTools(root, config, llm) {
  const made = makeContext(root, llm)
  await apply(made.ctx, config)
  return made
}

function createRepairingAnnotationLlm() {
  let attempt = 0
  let sawRepair = false
  return {
    get attempt() {
      return attempt
    },
    get sawRepair() {
      return sawRepair
    },
    llm: {
      listProviders() {
        return []
      },
      async listModels() {
        return []
      },
      async prepareCall(request, _signal, configure) {
        const controls = configure ? configure({}, {}) : request
        return {
          config: { provider: request.provider, model: request.model, ...controls },
          stream(options) {
            attempt += 1
            const payload = JSON.parse(options.messages[0].content[0].text)
            sawRepair ||= Boolean(payload.repair)
            const currentAttempt = attempt
            return (async function* () {
              if (currentAttempt === 1) {
                yield { type: 'text-delta', index: 0, text: 'not valid json' }
              } else {
                const nodes = payload.nodes.map((node) => ({
                  nodeId: node.nodeId,
                  summary: `修复摘要：${node.name}`,
                  details: `修复详情：${node.name}。`,
                }))
                yield { type: 'text-delta', index: 0, text: JSON.stringify({ nodes }) }
              }
              yield { type: 'finish', reason: { kind: 'stop' } }
            })()
          },
        }
      },
    },
  }
}

test('plugin registers build/annotate tools and both bundled Skills', async () => {
  const { tools, skillProviderFactories } = await pluginTools(REPO_ROOT, {
    pythonPath: process.env.ARCHMAP_PYTHON || 'python3',
    defaultOutputDir: '.archmap',
    toolTimeoutMs: 120000,
  })

  assert.deepEqual(
    tools.map((tool) => tool.name).sort(),
    ['archmap_annotate', 'archmap_build', 'archmap_guide', 'archmap_query'],
  )
  const build = tools.find((tool) => tool.name === 'archmap_build')
  assert.equal(build.parameters.required.includes('projectPath'), true)
  const guide = tools.find((tool) => tool.name === 'archmap_guide')
  const guideResult = await guide.execute({ topic: 'code-conventions' })
  assert.equal(guideResult.ok, true, guideResult.text)
  assert.ok(guideResult.charCount > 1000)
  assert.match(guideResult.text, /ArchMap 代码约定/)

  assert.equal(skillProviderFactories.length, 1)
  const provider = skillProviderFactories[0]({
    signal: new AbortController().signal,
    invalidate() {},
  })
  const candidates = await provider.list({ signal: new AbortController().signal })
  assert.deepEqual(candidates.map((item) => item.name).sort(), [
    'archmap-code-conventions',
    'archmap-config-generation',
  ])
  const configSkill = await provider.get(
    candidates.find((item) => item.name === 'archmap-config-generation'),
    { signal: new AbortController().signal },
  )
  assert.equal(configSkill.name, 'archmap-config-generation')
  assert.ok(configSkill.content.length > 100)
  assert.equal(configSkill.provider, 'archmap')
  assert.equal(configSkill.source, 'bundled')
})

test('archmap_build uses the bundled Python core', async () => {
  const outputRoot = await mkdtemp(join(REPO_ROOT, '.dsh-archmap-test-'))
  try {
    const { tools } = await pluginTools(REPO_ROOT, {
      pythonPath: process.env.ARCHMAP_PYTHON || 'python3',
      defaultOutputDir: '.archmap',
      toolTimeoutMs: 120000,
    })
    const tool = tools.find((item) => item.name === 'archmap_build')
    const result = await tool.execute(
      {
        projectPath: relative(REPO_ROOT, FIXTURE),
        outDir: relative(REPO_ROOT, outputRoot),
      },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )

    assert.equal(result.ok, true, result.text)
    assert.equal(result.project, 'student_demo')
    assert.equal(result.moduleCount, 3)
    assert.equal(result.functionCount, 5)
    assert.ok(result.executionFlowCount >= 1)
    assert.ok(result.callSiteCount >= 1)
    assert.equal(result.diagnostics.error, 0)
    assert.match(result.fingerprint, /^sha256:[0-9a-f]{64}$/)
    const bundle = JSON.parse(await readFile(result.jsonPath, 'utf8'))
    assert.equal(bundle.kind, 'archmap.bundle')
    assert.match(await readFile(result.htmlPath, 'utf8'), /ArchMap/)
  } finally {
    await rm(outputRoot, { recursive: true, force: true })
  }
})

test('archmap_annotate uses the host model and Python-owned source hashes', async () => {
  const outputRoot = await mkdtemp(join(REPO_ROOT, '.dsh-archmap-test-'))
  const mock = createMockAnnotationLlm()
  try {
    const made = await pluginTools(
      REPO_ROOT,
      {
        pythonPath: process.env.ARCHMAP_PYTHON || 'python3',
        defaultOutputDir: '.archmap',
        toolTimeoutMs: 120000,
        provider: 'mock-provider',
        model: 'mock-model',
        llmMaxTokens: 1024,
        annotationBatchSize: 2,
        annotationMaxNodes: 5,
        annotationMaxCharsPerNode: 4000,
        includeSourceInAnnotations: true,
      },
      mock.llm,
    )
    const build = made.tools.find((item) => item.name === 'archmap_build')
    const annotated = made.tools.find((item) => item.name === 'archmap_annotate')
    const buildResult = await build.execute(
      {
        projectPath: relative(REPO_ROOT, FIXTURE),
        outDir: relative(REPO_ROOT, outputRoot),
      },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    assert.equal(buildResult.ok, true, buildResult.text)

    const result = await annotated.execute(
      {
        bundlePath: relative(REPO_ROOT, buildResult.jsonPath),
        scope: 'functions',
        maxNodes: 1,
        force: false,
      },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    assert.equal(result.ok, true, result.text)
    assert.equal(result.applied, 1)
    assert.equal(result.provider, 'mock-provider')
    assert.equal(result.model, 'mock-model')
    assert.equal(mock.calls.length, 1)

    const sidecar = JSON.parse(await readFile(result.annotationsPath, 'utf8'))
    const [nodeId] = Object.keys(sidecar.nodes)
    assert.match(nodeId, /^fn:/)
    assert.match(sidecar.nodes[nodeId].summary, /^模型摘要：/)
    assert.match(sidecar.nodes[nodeId].sourceHash, /^sha256:[0-9a-f]{64}$/)
    assert.notEqual(sidecar.nodes[nodeId].sourceHash, 'sha256:' + '0'.repeat(64))
    assert.match(await readFile(result.htmlPath, 'utf8'), /模型摘要：/)
  } finally {
    await rm(outputRoot, { recursive: true, force: true })
  }
})

test('archmap_annotate repairs one invalid model response', async () => {
  const outputRoot = await mkdtemp(join(REPO_ROOT, '.dsh-archmap-test-'))
  const mock = createRepairingAnnotationLlm()
  try {
    const made = await pluginTools(
      REPO_ROOT,
      {
        pythonPath: process.env.ARCHMAP_PYTHON || 'python3',
        provider: 'mock-provider',
        model: 'mock-model',
      },
      mock.llm,
    )
    const build = made.tools.find((item) => item.name === 'archmap_build')
    const annotated = made.tools.find((item) => item.name === 'archmap_annotate')
    const buildResult = await build.execute(
      {
        projectPath: relative(REPO_ROOT, FIXTURE),
        outDir: relative(REPO_ROOT, outputRoot),
      },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    const result = await annotated.execute(
      {
        bundlePath: relative(REPO_ROOT, buildResult.jsonPath),
        scope: 'functions',
        maxNodes: 1,
      },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )

    assert.equal(result.ok, true, result.text)
    assert.equal(result.applied, 1)
    assert.equal(mock.attempt, 2)
    assert.equal(mock.sawRepair, true)
    const sidecar = JSON.parse(await readFile(result.annotationsPath, 'utf8'))
    assert.match(Object.values(sidecar.nodes)[0].summary, /^修复摘要：/)
  } finally {
    await rm(outputRoot, { recursive: true, force: true })
  }
})

test('archmap_query exposes check and trace without shelling out', async () => {
  const outputRoot = await mkdtemp(join(REPO_ROOT, '.dsh-archmap-test-'))
  try {
    const { tools } = await pluginTools(REPO_ROOT, {
      pythonPath: process.env.ARCHMAP_PYTHON || 'python3',
      toolTimeoutMs: 120000,
    })
    const build = tools.find((item) => item.name === 'archmap_build')
    const query = tools.find((item) => item.name === 'archmap_query')
    const buildResult = await build.execute(
      {
        projectPath: relative(REPO_ROOT, FIXTURE),
        outDir: relative(REPO_ROOT, outputRoot),
      },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    assert.equal(buildResult.ok, true, buildResult.text)
    const bundlePath = relative(REPO_ROOT, buildResult.jsonPath)

    const checked = await query.execute(
      { operation: 'check', bundlePath },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    assert.equal(checked.ok, true, checked.text)
    assert.equal(checked.operation, 'check')
    assert.equal(checked.data.errorCount, 0)
    assert.equal(checked.data.issueCount, 0)

    const traced = await query.execute(
      { operation: 'trace', bundlePath, start: 'fn:app.main.main' },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    assert.equal(traced.ok, true, traced.text)
    assert.equal(traced.operation, 'trace')
    assert.ok(traced.data.nodes.length > 1)
    assert.ok(traced.data.paths.length > 0)
    assert.match(traced.text, /nodes=/)

    const surfaces = await query.execute(
      { operation: 'surfaces', bundlePath },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    assert.equal(surfaces.ok, true, surfaces.text)
    assert.ok(Array.isArray(surfaces.data.items))
    assert.equal(surfaces.data.total, surfaces.data.items.length)

    const dsm = await query.execute(
      { operation: 'dsm', bundlePath, level: 'module' },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    assert.equal(dsm.ok, true, dsm.text)
    assert.ok(dsm.data.stats.nodes > 0)

    const method = await query.execute(
      { operation: 'method', projectPath: relative(REPO_ROOT, FIXTURE), function: 'main' },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    assert.equal(method.ok, true, method.text)
    assert.equal(method.data.name, 'main')
  } finally {
    await rm(outputRoot, { recursive: true, force: true })
  }
})

test('archmap_build returns actionable validation diagnostics', async () => {
  const projectRoot = await mkdtemp(join(REPO_ROOT, '.dsh-archmap-bad-'))
  try {
    await writeFile(join(projectRoot, 'app.py'), 'def main():\n    print("hello")\n', 'utf8')
    await writeFile(
      join(projectRoot, 'archmap.config.json'),
      JSON.stringify({
        projectName: 'bad-project',
        include: ['**/*.py'],
        entrypoints: ['app:main'],
        contract: { providerRoles: { missing: 'adapter' } },
      }),
      'utf8',
    )
    const { tools } = await pluginTools(REPO_ROOT, {
      pythonPath: process.env.ARCHMAP_PYTHON || 'python3',
      toolTimeoutMs: 120000,
    })
    const build = tools.find((item) => item.name === 'archmap_build')
    const result = await build.execute(
      { projectPath: relative(REPO_ROOT, projectRoot) },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    assert.equal(result.ok, false)
    assert.ok(result.issues.length >= 1)
    assert.match(result.text, /PROVIDER_ROLE_TARGET_UNRESOLVED/)
    assert.ok(result.issues.some((issue) => issue.sourceCode === 'PROVIDER_ROLE_TARGET_UNRESOLVED'))
    assert.ok(result.nextActions.some((item) => /config/i.test(item)))
  } finally {
    await rm(projectRoot, { recursive: true, force: true })
  }
})

test('archmap_annotate supports missing then stale refresh modes', async () => {
  const outputRoot = await mkdtemp(join(REPO_ROOT, '.dsh-archmap-test-'))
  const mock = createMockAnnotationLlm()
  try {
    const made = await pluginTools(
      REPO_ROOT,
      {
        pythonPath: process.env.ARCHMAP_PYTHON || 'python3',
        provider: 'mock-provider',
        model: 'mock-model',
        annotationBatchSize: 2,
        annotationMaxNodes: 10,
      },
      mock.llm,
    )
    const build = made.tools.find((item) => item.name === 'archmap_build')
    const annotated = made.tools.find((item) => item.name === 'archmap_annotate')
    const buildResult = await build.execute(
      {
        projectPath: relative(REPO_ROOT, FIXTURE),
        outDir: relative(REPO_ROOT, outputRoot),
      },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    const bundlePath = relative(REPO_ROOT, buildResult.jsonPath)
    const first = await annotated.execute(
      { bundlePath, scope: 'functions', maxNodes: 10, refreshMode: 'missing' },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    assert.equal(first.ok, true, first.text)
    assert.ok(first.applied > 0)
    assert.equal(first.remainingCount, 0)
    assert.equal(first.truncated, false)
    const callsAfterFirst = mock.calls.length

    const second = await annotated.execute(
      { bundlePath, scope: 'functions', maxNodes: 10, refreshMode: 'missing' },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    assert.equal(second.ok, true, second.text)
    assert.equal(second.applied, 0)
    assert.equal(second.selectedCount, 0)
    assert.equal(mock.calls.length, callsAfterFirst)

    const bundle = JSON.parse(await readFile(buildResult.jsonPath, 'utf8'))
    const target = bundle.functionDetails[0]
    target.sourceHash = 'sha256:' + '1'.repeat(64)
    await writeFile(buildResult.jsonPath, JSON.stringify(bundle), 'utf8')

    const stale = await annotated.execute(
      { bundlePath, scope: 'functions', maxNodes: 10, refreshMode: 'stale' },
      { agent: { id: 'test' }, signal: new AbortController().signal },
    )
    assert.equal(stale.ok, true, stale.text)
    assert.equal(stale.applied, 1)
    assert.equal(stale.staleCount, 1)
    assert.equal(mock.calls.length, callsAfterFirst + 1)
  } finally {
    await rm(outputRoot, { recursive: true, force: true })
  }
})

test('bridge rejects paths outside the DSH workspace', async () => {
  const { tools } = await pluginTools(REPO_ROOT, {
    pythonPath: process.env.ARCHMAP_PYTHON || 'python3',
  })
  const tool = tools.find((item) => item.name === 'archmap_build')

  await assert.rejects(
    () =>
      tool.execute(
        { projectPath: '../outside-workspace' },
        { agent: { id: 'test' }, signal: new AbortController().signal },
      ),
    /ARCHMAP_PATH_ESCAPE/,
  )
})

test('host route precedence is config, session, then discovered provider', async () => {
  const explicit = await resolveHostRoute(
    { llm: emptyLlm() },
    { provider: 'configured', model: 'configured-model' },
    {},
  )
  assert.equal(explicit.provider, 'configured')
  assert.equal(explicit.source, 'config')

  const session = await resolveHostRoute(
    { llm: emptyLlm() },
    {},
    {
      agent: {
        model: {
          current() {
            return { provider: 'session-provider', model: 'session-model' }
          },
        },
      },
    },
  )
  assert.equal(session.provider, 'session-provider')
  assert.equal(session.source, 'session')

  const discovered = await resolveHostRoute(
    {
      llm: {
        listProviders() {
          return [{ id: 'first-provider', name: 'First' }]
        },
        async listModels() {
          return [{ id: 'first-model', name: 'First model' }]
        },
      },
    },
    {},
    {},
  )
  assert.equal(discovered.provider, 'first-provider')
  assert.equal(discovered.model, 'first-model')
  assert.equal(discovered.source, 'discovered')
})

test('model JSON parser accepts a fenced object and rejects arrays', () => {
  assert.deepEqual(parseJsonLoose('```json\n{"nodes":[]}\n```'), { nodes: [] })
  assert.throws(() => parseJsonLoose('[]'), /JSON root must be an object/)
})
