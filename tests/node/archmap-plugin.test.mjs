import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
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
    ['archmap_annotate', 'archmap_build'],
  )
  const build = tools.find((tool) => tool.name === 'archmap_build')
  assert.equal(build.parameters.required.includes('projectPath'), true)

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
