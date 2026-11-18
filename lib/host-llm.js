/**
 * DSH host-model adapter for ArchMap annotation generation.
 *
 * This module never reads API keys and never calls provider HTTP endpoints
 * directly. Every model request goes through the mounted DSH `ctx.llm` service.
 */

import { BlockAssembler } from '@deepseek-ai/dsh-llm'

/**
 * Resolve the host-model route using the documented precedence:
 * explicit plugin config, current session selection, first usable provider.
 *
 * @param {import('@deepseek-ai/cordis').Context} ctx
 * @param {{ provider?: string, model?: string }} config
 * @param {{ agent?: { model?: { current?: () => { provider?: string, model?: string, reasoningEffort?: string } | undefined } }, signal?: AbortSignal }} exec
 * @returns {Promise<{ provider: string, model: string, reasoningEffort?: string, source: 'config' | 'session' | 'discovered' }>}
 */
export async function resolveHostRoute(ctx, config, exec) {
  const configuredProvider = String(config?.provider || '').trim()
  const configuredModel = String(config?.model || '').trim()
  if (Boolean(configuredProvider) !== Boolean(configuredModel)) {
    throw new Error('HOST_MODEL_UNAVAILABLE: provider and model must be configured together')
  }
  if (configuredProvider && configuredModel) {
    return {
      provider: configuredProvider,
      model: configuredModel,
      source: 'config',
    }
  }

  const selection = exec?.agent?.model?.current?.()
  if (selection?.provider && selection?.model) {
    return {
      provider: String(selection.provider),
      model: String(selection.model),
      ...(selection.reasoningEffort ? { reasoningEffort: String(selection.reasoningEffort) } : {}),
      source: 'session',
    }
  }

  if (!ctx?.llm || typeof ctx.llm.listProviders !== 'function') {
    throw new Error('HOST_MODEL_UNAVAILABLE: DSH llm service is not available')
  }
  for (const provider of ctx.llm.listProviders()) {
    if (!provider?.id || typeof ctx.llm.listModels !== 'function') continue
    let models
    try {
      models = await ctx.llm.listModels(provider.id)
    } catch {
      continue
    }
    const model = Array.isArray(models) ? models.find((item) => item?.id) : undefined
    if (model?.id) {
      return {
        provider: String(provider.id),
        model: String(model.id),
        source: 'discovered',
      }
    }
  }

  throw new Error(
    'HOST_MODEL_UNAVAILABLE: no configured provider/model, session model, or listable provider model',
  )
}

/**
 * Parse one strictly-shaped JSON object from model text. Markdown fences and
 * surrounding prose are tolerated only as a transport wrapper, never as a
 * substitute for valid JSON.
 *
 * @param {string} text
 * @returns {Record<string, unknown>}
 */
export function parseJsonLoose(text) {
  let value = String(text || '').trim()
  if (!value) throw new Error('HOST_MODEL_EMPTY_RESPONSE: model returned empty text')
  if (value.startsWith('```')) {
    value = value.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '')
  }
  const first = value.indexOf('{')
  const last = value.lastIndexOf('}')
  if (first >= 0 && last > first) value = value.slice(first, last + 1)
  const parsed = JSON.parse(value)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('HOST_MODEL_INVALID_JSON: model JSON root must be an object')
  }
  return parsed
}

/**
 * Run one host-model JSON call through `ctx.llm`.
 *
 * @param {import('@deepseek-ai/cordis').Context} ctx
 * @param {{ signal?: AbortSignal, agent?: unknown }} exec
 * @param {{ provider?: string, model?: string }} config
 * @param {{ system: string, payload: unknown, maxTokens: number }} request
 * @returns {Promise<{ route: { provider: string, model: string, source: string }, text: string, json: Record<string, unknown> }>}
 */
export async function hostJson(ctx, exec, config, { system, payload, maxTokens }) {
  if (
    !ctx?.llm ||
    (typeof ctx.llm.stream !== 'function' && typeof ctx.llm.prepareCall !== 'function')
  ) {
    throw new Error('HOST_MODEL_UNAVAILABLE: DSH llm service is not available')
  }
  const route = await resolveHostRoute(ctx, config, exec)
  const signal = exec?.signal
  if (signal?.aborted) throw abortError()

  // Prepare and dispatch must use one frozen call config. DSH compares every
  // control field at dispatch, so decide controls inside configure() and send
  // the exact resolved config back with the request.
  const requested = { maxTokens, temperature: 0.1 }
  if (route.reasoningEffort !== undefined) requested.reasoningEffort = route.reasoningEffort

  let prepared
  if (typeof ctx.llm.prepareCall === 'function') {
    prepared = await ctx.llm.prepareCall(
      { provider: route.provider, model: route.model, ...requested },
      signal,
      (controls, _model) => ({ ...controls, ...requested }),
    )
  }

  let resolvedConfig = prepared?.config
  if (!resolvedConfig) {
    resolvedConfig =
      typeof ctx.llm.resolveCallConfig === 'function'
        ? await ctx.llm.resolveCallConfig(
            { provider: route.provider, model: route.model, ...requested },
            signal,
          )
        : { provider: route.provider, model: route.model, ...requested }
  }

  const options = {
    ...resolvedConfig,
    system,
    messages: [
      {
        role: 'user',
        content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }],
      },
    ],
    signal,
  }

  const assembler = new BlockAssembler()
  let stream
  if (prepared?.stream) {
    stream = prepared.stream(options)
  } else if (typeof ctx.llm.stream === 'function') {
    stream = ctx.llm.stream(options)
  } else {
    throw new Error('HOST_MODEL_UNAVAILABLE: DSH llm stream entry point is not available')
  }
  for await (const chunk of stream) {
    if (signal?.aborted) throw abortError()
    assembler.push(chunk)
  }

  const finish = assembler.finish
  if (finish?.kind === 'error') {
    throw new Error(
      `HOST_MODEL_FAILED: ${finish.failure?.code || finish.failure?.message || 'unknown model failure'}`,
    )
  }
  if (finish?.kind === 'aborted') throw abortError()
  if (finish?.kind === 'max-tokens') {
    throw new Error('HOST_MODEL_TRUNCATED: model response reached the output limit')
  }

  const text = assembler
    .blocks()
    .filter((block) => block.type === 'text')
    .map((block) => block.text)
    .join('')
    .trim()
  if (!text) throw new Error('HOST_MODEL_EMPTY_RESPONSE: model returned no text blocks')

  try {
    return { route, text, json: parseJsonLoose(text) }
  } catch (error) {
    const wrapped = new Error(`HOST_MODEL_INVALID_JSON: ${error.message}`)
    wrapped.rawText = text
    throw wrapped
  }
}

function abortError() {
  const error = new Error('ARCHMAP_ABORTED: model annotation was cancelled')
  error.name = 'AbortError'
  return error
}
