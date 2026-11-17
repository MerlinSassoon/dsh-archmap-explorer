(() => {
  "use strict";

  const DATA = window.__ARCHMAP_DATA__;
  if (!DATA) throw new Error("ArchMap data missing");

  const projectGraph = DATA.projectGraph;
  const moduleGraphs = DATA.moduleGraphs || [];
  const functionDetails = DATA.functionDetails || [];
  const annotations = DATA.annotations || { version: 1, nodes: {} };
  const moduleGraphById = new Map(moduleGraphs.map(item => [item.moduleId, item]));
  const functionDetailById = new Map(functionDetails.map(item => [item.id, item]));
  const projectModuleById = new Map((projectGraph.modules || []).map(item => [item.id, item]));
  const STORAGE_KEY = "archmap-v3-layout-v1";
  const OVERRIDE_VERSION = 1;
  const GEOMETRY_VERSION = 1;

  const $ = id => document.getElementById(id);
  const viewport = $("viewport");
  const world = $("world");
  const detailScroll = $("detailScroll");
  const breadcrumb = $("breadcrumb");
  const backBtn = $("backBtn");
  const searchInput = $("searchInput");
  const searchWrap = $("searchWrap");
  const legend = $("legend");
  const canvasKicker = $("canvasKicker");
  const canvasTitle = $("canvasTitle");
  const canvasSub = $("canvasSub");
  const zoomValue = $("zoomValue");
  const saveState = $("saveState");
  const relationModeBtn = $("relationModeBtn");
  const singleModeBtn = $("singleModeBtn");
  const moduleContracts = $("moduleContracts");
  const projectNameEl = $("projectName");
  const projectLanguageEl = $("projectLanguage");
  const toastEl = $("toast");

  const state = {
    route: { kind: "project" },
    scale: .75,
    x: 0,
    y: 0,
    selectedUid: null,
    hoveredUid: null,
    search: "",
    singleModule: false,
    showProjectRelations: false,
    pendingSelectUid: null,
    suppressClickUntil: 0,
    pageKind: "project",
    pageEdges: [],
    nodes: new Map(),
    sizes: new Map(),
    moduleId: null,
    functionId: null,
    flowId: null,
    mainView: "flow",
  };

  let override = loadOverrides();

  function defaultOverride() {
    return {
      version: OVERRIDE_VERSION,
      geometryVersion: GEOMETRY_VERSION,
      project: { nodes: {}, miniNodes: {}, expanded: {}, singleModule: false },
      modules: {},
      functions: {},
    };
  }

  function normalizeOverride(value) {
    const base = defaultOverride();
    if (!value || typeof value !== "object") return base;
    if (Number(value.version) !== OVERRIDE_VERSION) return base;
    base.project.nodes = value.project?.nodes && typeof value.project.nodes === "object" ? value.project.nodes : {};
    base.project.miniNodes = value.project?.miniNodes && typeof value.project.miniNodes === "object" ? value.project.miniNodes : {};
    base.project.expanded = value.project?.expanded && typeof value.project.expanded === "object" ? value.project.expanded : {};
    base.project.singleModule = Boolean(value.project?.singleModule);
    base.modules = value.modules && typeof value.modules === "object" ? value.modules : {};
    base.functions = value.functions && typeof value.functions === "object" ? value.functions : {};
    return base;
  }

  function loadOverrides() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? normalizeOverride(JSON.parse(raw)) : defaultOverride();
    } catch (error) {
      return defaultOverride();
    }
  }

  function persistOverride() {
    override.geometryVersion = GEOMETRY_VERSION;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(override));
    const now = new Date();
    saveState.textContent = `已保存 ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  }

  function resetOverride() {
    localStorage.removeItem(STORAGE_KEY);
    override = defaultOverride();
    state.singleModule = false;
    saveState.textContent = "布局已重置";
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[ch]);
  }

  function escapeXml(value) {
    return escapeHtml(value).replaceAll("'", "&apos;");
  }

  function truncate(value, max) {
    const text = String(value ?? "").replace(/\s+/g, " ").trim();
    return text.length > max ? text.slice(0, Math.max(0, max - 1)) + "…" : text;
  }

  function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === "function") return window.CSS.escape(String(value));
    return String(value).replace(/["\\]/g, "\\$&");
  }

  function rgbFromHex(hex) {
    const value = String(hex || "#6ea8ff").replace("#", "");
    const full = value.length === 3 ? value.split("").map(ch => ch + ch).join("") : value.padEnd(6, "0").slice(0, 6);
    const num = parseInt(full, 16);
    return `${(num >> 16) & 255},${(num >> 8) & 255},${num & 255}`;
  }

  function showToast(message) {
    toastEl.textContent = message;
    toastEl.classList.add("is-visible");
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => toastEl.classList.remove("is-visible"), 1800);
  }

  function parseRoute() {
    const hash = location.hash.replace(/^#\/?/, "");
    const parts = hash.split("/").filter(Boolean).map(part => {
      try { return decodeURIComponent(part); } catch (error) { return part; }
    });
    if (parts[0] === "module" && parts[1]) {
      if (parts[2] === "function" && parts[3]) {
        return { kind: "function", moduleId: parts[1], functionId: parts[3] };
      }
      return { kind: "module", moduleId: parts[1] };
    }
    return { kind: "project" };
  }

  function routeHash(route) {
    if (route.kind === "module") return `#/module/${encodeURIComponent(route.moduleId)}`;
    if (route.kind === "function") {
      return `#/module/${encodeURIComponent(route.moduleId)}/function/${encodeURIComponent(route.functionId)}`;
    }
    return "#/project";
  }

  function navigate(route, push = true) {
    const nextHash = routeHash(route);
    if (push && location.hash !== nextHash) history.pushState(route, "", nextHash);
    else if (!push) history.replaceState(route, "", nextHash);
    state.route = route;
    renderRoute();
  }

  function focusPage() {
    const nodes = [...world.querySelectorAll(".node-card")];
    const edges = [...world.querySelectorAll(".graph-edge, .macro-edge")];
    const focusUid = state.hoveredUid || state.selectedUid;
    nodes.forEach(node => node.classList.toggle("is-selected", node.dataset.uid === focusUid));
    if (!focusUid) {
      nodes.forEach(node => node.classList.remove("is-dim", "is-highlight"));
      edges.forEach(edge => edge.classList.remove("is-dim", "is-highlight"));
      world.querySelectorAll(".mini-node").forEach(node => node.classList.remove("is-dim", "is-selected"));
      return;
    }
    // Capability cards are siblings, not a dependency neighbourhood.  Without
    // the optional relation view, selecting one module must not dim the rest.
    if (state.pageKind === "project" && !state.showProjectRelations) {
      nodes.forEach(node => node.classList.remove("is-dim", "is-highlight"));
      edges.forEach(edge => edge.classList.remove("is-dim", "is-highlight"));
      return;
    }
    const neighborUids = new Set([focusUid]);
    state.pageEdges.forEach(edge => {
      if (edge.from === focusUid || edge.to === focusUid) {
        neighborUids.add(edge.from);
        neighborUids.add(edge.to);
      }
    });
    nodes.forEach(node => {
      const uid = node.dataset.uid;
      node.classList.toggle("is-dim", !neighborUids.has(uid));
      node.classList.toggle("is-highlight", uid === focusUid);
    });
    edges.forEach(edge => {
      const highlighted = edge.dataset.from === focusUid || edge.dataset.to === focusUid;
      edge.classList.toggle("is-highlight", highlighted);
      edge.classList.toggle("is-dim", !highlighted);
    });
    world.querySelectorAll(".mini-node").forEach(node => {
      node.classList.toggle("is-dim", node.dataset.uid !== focusUid && ![...neighborUids].includes(node.dataset.uid));
    });
  }

  function selectUid(uid) {
    if (Date.now() < state.suppressClickUntil) return;
    state.selectedUid = uid;
    state.hoveredUid = null;
    focusPage();
    renderSelectionDetail(uid);
  }

  function clearSelection() {
    state.selectedUid = null;
    state.hoveredUid = null;
    focusPage();
    renderDefaultDetail();
  }

  function bindNodeHover(element, uid) {
    element.addEventListener("mouseenter", () => { state.hoveredUid = uid; focusPage(); });
    element.addEventListener("mouseleave", () => { state.hoveredUid = null; focusPage(); });
  }

  function applyTransform() {
    world.style.transform = `translate(${state.x}px, ${state.y}px) scale(${state.scale})`;
    zoomValue.textContent = `${Math.round(state.scale * 100)}%`;
  }

  function fitView(animate = false) {
    const width = world.offsetWidth || Number(world.style.width.replace("px", "")) || 900;
    const height = world.offsetHeight || Number(world.style.height.replace("px", "")) || 700;
    const rect = viewport.getBoundingClientRect();
    const padX = 58;
    const padTop = state.pageKind === "module" ? 122 : state.pageKind === "method" ? 26 : 64;
    const padBottom = 46;
    const scale = Math.min(
      (rect.width - padX * 2) / Math.max(1, width),
      (rect.height - padTop - padBottom) / Math.max(1, height),
      1
    );
    const minScale = state.pageKind === "method" ? .5 : .2;
    state.scale = Math.max(minScale, Math.min(1, scale));
    const availableW = rect.width - padX * 2;
    const availableH = rect.height - padTop - padBottom;
    state.x = width * state.scale <= availableW
      ? (rect.width - width * state.scale) / 2
      : padX;
    state.y = height * state.scale <= availableH
      ? padTop + (availableH - height * state.scale) / 2
      : padTop;
    applyTransform();
  }

  function screenToWorld(clientX, clientY) {
    const rect = viewport.getBoundingClientRect();
    return { x: (clientX - rect.left - state.x) / state.scale, y: (clientY - rect.top - state.y) / state.scale };
  }

  function zoomAt(factor, clientX, clientY) {
    const rect = viewport.getBoundingClientRect();
    const px = clientX == null ? rect.width / 2 : clientX - rect.left;
    const py = clientY == null ? rect.height / 2 : clientY - rect.top;
    const oldScale = state.scale;
    const nextScale = Math.max(.2, Math.min(2.4, oldScale * factor));
    const wx = (px - state.x) / oldScale;
    const wy = (py - state.y) / oldScale;
    state.scale = nextScale;
    state.x = px - wx * nextScale;
    state.y = py - wy * nextScale;
    applyTransform();
  }

  function curvePath(from, to) {
    const fromRight = to.x >= from.x;
    const sx = fromRight ? from.x + from.w : from.x;
    const sy = from.y + from.h / 2;
    const tx = fromRight ? to.x : to.x + to.w;
    const ty = to.y + to.h / 2;
    const bend = Math.max(52, Math.min(190, Math.abs(tx - sx) * .46));
    const sign = tx >= sx ? 1 : -1;
    return `M ${sx.toFixed(2)} ${sy.toFixed(2)} C ${(sx + sign * bend).toFixed(2)} ${sy.toFixed(2)} ${(tx - sign * bend).toFixed(2)} ${ty.toFixed(2)} ${tx.toFixed(2)} ${ty.toFixed(2)}`;
  }

  function makeSvg(width, height, className) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", className);
    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    return svg;
  }

  function macroEdgeClass(edge) {
    if (edge.primaryType === "data") return "macro-edge type-data";
    if (edge.primaryType === "control") return "macro-edge type-control";
    return "macro-edge";
  }

  function attachDrag(handle, element, options) {
    let dragging = false;
    let moved = false;
    let start = null;
    let origin = null;

    handle.addEventListener("pointerdown", event => {
      if (event.button !== 0 || event.target.closest("button")) return;
      event.preventDefault();
      event.stopPropagation();
      dragging = true;
      moved = false;
      start = { x: event.clientX, y: event.clientY };
      origin = options.getPosition();
      element.classList.add("is-dragging");
      try { handle.setPointerCapture(event.pointerId); } catch (error) {}
    });

    handle.addEventListener("pointermove", event => {
      if (!dragging) return;
      const dx = (event.clientX - start.x) / state.scale;
      const dy = (event.clientY - start.y) / state.scale;
      if (!moved && Math.abs(dx) + Math.abs(dy) < 3) return;
      moved = true;
      const bounds = options.bounds ? options.bounds() : { w: 2200, h: 1600 };
      const x = Math.max(0, Math.min(bounds.w, origin.x + dx));
      const y = Math.max(0, Math.min(bounds.h, origin.y + dy));
      options.setPosition(x, y);
      element.style.left = `${x}px`;
      element.style.top = `${y}px`;
      options.onMove?.();
    });

    const finish = event => {
      if (!dragging) return;
      dragging = false;
      element.classList.remove("is-dragging");
      try { handle.releasePointerCapture(event.pointerId); } catch (error) {}
      if (moved) {
        state.suppressClickUntil = Date.now() + 220;
        options.onEnd?.();
      }
    };
    handle.addEventListener("pointerup", finish);
    handle.addEventListener("pointercancel", finish);
  }

  function legendItem(kind, text) {
    if (kind === "card") return `<span class="legend-item"><span class="legend-swatch"></span>${escapeHtml(text)}</span>`;
    if (kind === "dashed") return `<span class="legend-item"><span class="legend-line dashed"></span>${escapeHtml(text)}</span>`;
    if (kind === "entry") return `<span class="legend-item"><span class="legend-swatch entry"></span>${escapeHtml(text)}</span>`;
    if (kind === "function") return `<span class="legend-item"><span class="legend-swatch function"></span>${escapeHtml(text)}</span>`;
    if (kind === "interface") return `<span class="legend-item"><span class="legend-swatch interface"></span>${escapeHtml(text)}</span>`;
    if (kind === "dispatch") return `<span class="legend-item"><span class="legend-swatch dispatch"></span>${escapeHtml(text)}</span>`;
    return `<span class="legend-item"><span class="legend-line"></span>${escapeHtml(text)}</span>`;
  }

  function moduleRoleLabel(role) {
    return ({
      main: "MAIN",
      service: "SERVICE",
      adapter: "ADAPTER",
      test: "TEST",
      other: "MODULE",
    }[role] || "MODULE");
  }

  function providerRoleLabel(role) {
    return ({
      config: "CONFIG",
      model: "MODEL",
      manager: "MANAGER",
      entry: "ENTRY",
      adapter: "ADAPTER",
      component: "COMPONENT",
      contract: "CONTRACT",
      utility: "UTILITY",
    }[role] || "PROVIDER");
  }

  function providerRoleBadge(role) {
    return `<span class="provider-role-badge role-${escapeHtml(role || "utility")}">${escapeHtml(providerRoleLabel(role))}</span>`;
  }

  function roleCountChips(counts, limit = 8) {
    const entries = Object.entries(counts || {}).filter(([, count]) => Number(count) > 0).slice(0, limit);
    if (!entries.length) return `<span class="role-count-empty">暂无 Provider</span>`;
    return entries.map(([role, count]) => `<span class="role-count-chip role-${escapeHtml(role)}">${escapeHtml(providerRoleLabel(role))}<b>${Number(count)}</b></span>`).join("");
  }

  function isHiddenProvider(node) {
    return node.providerVisibility === "internal" || node.providerRole === "utility";
  }

  function visibleProviderNodes(graph) {
    return (graph?.nodes || []).filter(node => (node.kind === "class" || node.kind === "function") && !isHiddenProvider(node));
  }

  function visibleRoleCounts(graph) {
    if (graph?.publicProviderRoleCounts && typeof graph.publicProviderRoleCounts === "object") {
      return graph.publicProviderRoleCounts;
    }
    const counts = {};
    visibleProviderNodes(graph).forEach(node => {
      const role = node.providerRole || "utility";
      counts[role] = (counts[role] || 0) + 1;
    });
    return counts;
  }

  function visibleComposition(graph) {
    if (graph?.publicModuleComposition && typeof graph.publicModuleComposition === "object") {
      return graph.publicModuleComposition;
    }
    const visibleIds = new Set(visibleProviderNodes(graph).map(node => node.id));
    const composition = {};
    Object.entries(graph?.moduleComposition || {}).forEach(([role, ids]) => {
      const visible = (ids || []).filter(id => visibleIds.has(id));
      if (visible.length) composition[role] = visible;
    });
    return composition;
  }

  function typeFieldChips(summary, limit = 3) {
    const fields = summary?.fields || [];
    if (!fields.length) return `<span class="type-field-empty">暂无字段摘要</span>`;
    const chips = fields.slice(0, limit).map(field => {
      const suffix = field.default ? ` = ${truncate(field.default, 14)}` : "";
      const annotation = field.annotation ? `: ${truncate(field.annotation, 15)}` : "";
      return `<span class="type-field-chip" title="${escapeHtml(field.name + annotation + suffix)}">${escapeHtml(field.name)}${escapeHtml(annotation)}${escapeHtml(suffix)}</span>`;
    }).join("");
    const more = fields.length > limit ? `<span class="type-field-chip more">+${fields.length - limit}</span>` : "";
    return chips + more;
  }

  function typeFieldList(summary) {
    const fields = summary?.fields || [];
    if (!fields.length) return `<div class="class-method-empty">暂无字段摘要</div>`;
    return `<div class="type-field-list">${fields.map(field => `<div class="type-field-row">
        <span class="type-field-name">${escapeHtml(field.name)}</span>
        <span class="type-field-annotation">${escapeHtml(field.annotation || "—")}</span>
        <span class="type-field-default">${escapeHtml(field.default || "—")}</span>
        <span class="type-field-kind">${escapeHtml(field.kind || "")}</span>
      </div>`).join("")}</div>`;
  }

  function roleCompositionBlock(graph) {
    const composition = visibleComposition(graph);
    const counts = visibleRoleCounts(graph);
    const entries = Object.entries(composition).filter(([, ids]) => Array.isArray(ids) && ids.length);
    if (!entries.length) return `<div class="class-method-empty">暂无公开 Provider</div>`;
    return `<div class="module-composition">${entries.map(([role, ids]) => `<div class="composition-row">
      ${providerRoleBadge(role)}
      <span class="composition-count">${Number(counts?.[role] ?? ids.length)}</span>
      <span class="composition-ids">${ids.slice(0, 5).map(id => `<code>${escapeHtml(id.split(/[.:]/).pop())}</code>`).join("")}${ids.length > 5 ? `<em>+${ids.length - 5}</em>` : ""}</span>
    </div>`).join("")}</div>`;
  }

  function apiDisplayName(api) {
    if (!api) return "";
    return api.display || api.signature || api.name || "";
  }

  function apiExposureBadge(api) {
    if (!api) return "";
    if (api.inherited) return `inherited · ${api.declaredInProviderId ? String(api.declaredInProviderId).split(".").pop() : "base"}`;
    if (api.overridesCapabilityId) return "override";
    if (api.isEntry) return "entry";
    if (api.exposureSource === "protocol") return "protocol";
    if (api.exposureSource === "naming") return "inferred";
    return api.exposure || "public";
  }

  function typeRelationLabel(kind) {
    return kind === "implements" ? "implements" : "inherits";
  }

  function classHierarchyBlock(node) {
    const bases = node.baseClassIds || [];
    const subclasses = node.subclassIds || [];
    const unresolved = node.unresolvedBases || [];
    if (!bases.length && !subclasses.length && !unresolved.length) {
      return `<div class="class-method-empty">无已解析的继承/实现关系</div>`;
    }
    const list = (ids, empty) => ids.length ? ids.map(id => `<code>${escapeHtml(String(id).split(".").pop())}</code>`).join("") : `<span class="class-hierarchy-empty">${empty}</span>`;
    return `<div class="class-hierarchy">
      <div class="hierarchy-row"><span>BASES</span><div>${list(bases, "—")}</div></div>
      <div class="hierarchy-row"><span>SUBCLASSES</span><div>${list(subclasses, "—")}</div></div>
      ${unresolved.length ? `<div class="hierarchy-row is-unresolved"><span>UNRESOLVED</span><div>${unresolved.map(item => `<code>${escapeHtml(item)}</code>`).join("")}</div></div>` : ""}
    </div>`;
  }

  function typeRelationChips(graph, limit = 8) {
    const relations = graph?.typeRelations || [];
    if (!relations.length) return `<span class="contracts-empty">暂无继承/实现关系</span>`;
    const short = id => String(id || "").split(".").pop();
    return relations.slice(0, limit).map(relation => `<span class="type-relation-chip kind-${escapeHtml(relation.kind)}" title="${escapeHtml(`${relation.fromClassId} ${typeRelationLabel(relation.kind)} ${relation.toClassId}`)}">
      <b>${escapeHtml(short(relation.fromClassId))}</b><em>${escapeHtml(typeRelationLabel(relation.kind))}</em><span>${escapeHtml(short(relation.toClassId))}</span>
    </span>`).join("") + (relations.length > limit ? `<span class="type-relation-chip more">+${relations.length - limit}</span>` : "");
  }

  function polymorphicCallList(entries, emptyText) {
    if (!entries || !entries.length) return `<div class="method-call-empty">${escapeHtml(emptyText)}</div>`;
    return entries.map(entry => {
      const candidates = entry.candidates || [];
      const targetNames = candidates.map(id => String(id).split(".").slice(-2).join("."));
      return `<div class="method-call-item is-polymorphic">
        <span class="method-call-name">${escapeHtml(entry.calleeText || entry.qualifiedName || "polymorphic call")}</span>
        <span class="method-call-meta">${escapeHtml(entry.file || "")}:${entry.line || "—"} · ${candidates.length} candidate${candidates.length === 1 ? "" : "s"}</span>
        <span class="method-call-kind">polymorphic</span>
        ${targetNames.length ? `<span class="method-call-candidates">${targetNames.map(name => `<code>${escapeHtml(name)}</code>`).join("")}</span>` : ""}
      </div>`;
    }).join("");
  }

  function apiButtonAttrs(api) {
    return [
      `data-api-id="${escapeHtml(api.id)}"`,
      `data-api-kind="${escapeHtml(api.kind)}"`,
      `data-provider-id="${escapeHtml(api.providerId || "")}"`,
      `data-provider-kind="${escapeHtml(api.providerKind || "")}"`,
      `data-module-id="${escapeHtml(api.moduleId || "")}"`,
      api.functionId ? `data-function-id="${escapeHtml(api.functionId)}"` : "",
    ].filter(Boolean).join(" ");
  }

  function apiChips(apis, limit, options = {}) {
    const items = (apis || []).slice(0, limit);
    if (!items.length) {
      return `<div class="module-api-empty">暂无公开接口</div>`;
    }
    const chips = items.map(api => {
      const label = apiDisplayName(api);
      const classes = ["module-api-chip", api.isEntry ? "is-entry" : "", api.kind.includes("context") || api.kind === "callable" || api.kind === "iterable" ? "is-protocol" : ""].filter(Boolean).join(" ");
      return `<button class="${classes}" type="button" ${apiButtonAttrs(api)} title="${escapeHtml(api.signature || label)}">${escapeHtml(label)}</button>`;
    }).join("");
    const more = (apis || []).length > items.length && options.showMore !== false
      ? `<span class="module-api-chip more">+${apis.length - items.length}</span>`
      : "";
    return chips + more;
  }

  function apiDetailList(apis) {
    if (!apis || !apis.length) return `<div class="class-method-empty">暂无公开接口</div>`;
    return apis.map(api => `<button class="detail-api-row" type="button" ${apiButtonAttrs(api)}>
        <span class="detail-api-kind">${escapeHtml(api.kind)}</span>
        <span class="detail-api-name">${escapeHtml(apiDisplayName(api))}</span>
        <span class="detail-api-badge${api.inherited ? " is-inherited" : api.overridesCapabilityId ? " is-override" : ""}">${escapeHtml(apiExposureBadge(api))}</span>
      </button>`).join("");
  }

  function apiProviderList(providers) {
    if (!providers || !providers.length) {
      return `<div class="class-method-empty">暂无公开接口</div>`;
    }
    const groups = [];
    const byRole = new Map();
    providers.forEach(provider => {
      const role = provider.providerRole || "utility";
      if (!byRole.has(role)) {
        const items = [];
        byRole.set(role, items);
        groups.push([role, items]);
      }
      byRole.get(role).push(provider);
    });
    return groups.map(([role, items]) => `<div class="api-role-group">
      <div class="api-role-heading">${providerRoleBadge(role)}<span>${items.length} provider${items.length === 1 ? "" : "s"}</span></div>
      ${items.map(provider => `<div class="api-provider">
        <div class="api-provider-head">
          <span class="api-provider-kind">${escapeHtml(provider.providerKind || "provider")}</span>
          <b>${escapeHtml(provider.providerName || provider.providerId)}</b>
          <em>${provider.apiCount || (provider.apis || []).length}${Number(provider.inheritedApiCount || 0) ? ` · ${Number(provider.inheritedApiCount)} inherited` : ""}</em>
        </div>
        ${apiDetailList(provider.apis || [])}
      </div>`).join("")}
    </div>`).join("");
  }

  function bindApiNavigation(root) {
    root.querySelectorAll("[data-provider-id]").forEach(button => {
      button.addEventListener("click", event => {
        event.stopPropagation();
        const functionId = button.dataset.functionId;
        const kind = button.dataset.apiKind;
        if (functionId && (kind === "method" || kind === "function")) {
          const target = functionDetailById.get(functionId);
          if (target) navigate({ kind: "function", moduleId: target.moduleId, functionId: target.id });
          return;
        }
        const providerId = button.dataset.providerId;
        if (!providerId) return;
        if (state.pageKind === "module" && state.nodes.has(providerId)) {
          selectUid(providerId);
          return;
        }
        const moduleId = button.dataset.moduleId;
        if (!moduleId) return;
        state.pendingSelectUid = providerId;
        navigate({ kind: "module", moduleId });
      });
    });
  }

  function annotationBlock(uid, sourceHash) {
    const annotation = annotations?.nodes?.[uid];
    if (!annotation) {
      return `<div class="llm-placeholder">
        <div class="llm-head"><span class="spark">✦</span><strong>LLM 语义说明</strong><em>占位</em></div>
        <div class="llm-copy">由语言大模型阅读源码后生成，展示职责边界、输入输出、关键约束与异常路径。</div>
        <div class="llm-skeleton">
          <div class="skeleton-row"><span class="skeleton-icon"></span><span class="skeleton-lines"><i></i><i></i></span></div>
          <div class="skeleton-row"><span class="skeleton-icon"></span><span class="skeleton-lines"><i></i><i></i></span></div>
          <div class="skeleton-row"><span class="skeleton-icon"></span><span class="skeleton-lines"><i></i><i></i></span></div>
        </div>
      </div>`;
    }
    const stale = sourceHash && annotation.sourceHash && annotation.sourceHash !== sourceHash;
    return `<div class="llm-placeholder">
      <div class="llm-head"><span class="spark">✦</span><strong>LLM 语义说明</strong><em>${stale ? "过期" : "已加载"}</em></div>
      <div class="llm-copy"><h3>${escapeHtml(annotation.summary || "")}</h3><p>${escapeHtml(annotation.details || "")}</p></div>
      ${stale ? `<div class="llm-stale">源码已变化，当前注解可能已过期。</div>` : ""}
    </div>`;
  }

  function renderDefaultDetail() {
    if (state.route.kind === "project") {
      const mainModule = projectGraph.modules.find(node => node.moduleKind === "main");
      const functionalCount = projectGraph.modules.filter(node => node.moduleKind === "functional").length;
      const flow = currentMainFlow();
      detailScroll.innerHTML = `<div class="eyebrow">Project composition map</div>
        <h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(DATA.project.name)}</h2>
        <div class="detail-note">项目页展示主模块与功能模块能力。主模块承载程序主流程；功能模块只暴露能力，不再拥有僵硬的输入输出端口。</div>
        <div class="port-detail"><span>模块 <b>${projectGraph.modules.length}</b></span><span>主模块 <b>${escapeHtml(mainModule?.name || "—")}</b></span><span>功能模块 <b>${functionalCount}</b></span><span>类型关系 <b>${(projectGraph.typeRelations || []).length}</b></span><span>主流程节点 <b>${flow?.nodeCount || 0}</b></span></div>
        ${annotationBlock(DATA.project.name)}
        <div class="empty-hint">双击主模块查看主流程；双击功能模块查看 Provider 与提供接口。</div>`;
      return;
    }
    if (state.route.kind === "module") {
      const module = moduleGraphById.get(state.route.moduleId);
      if (!module) return;
      const apis = module.providedApis || [];
      const providers = module.apiProviders || [];
      const flow = currentMainFlow();
      const isMain = module.moduleKind === "main";
      detailScroll.innerHTML = `<div class="detail-head" style="--mc:${module.color}"><div class="detail-color"></div><div>
          <div class="eyebrow">${isMain ? "Main flow" : "Module capability"}</div><h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(module.name)}</h2>
          <div class="detail-module">module://${escapeHtml(module.moduleId)} · ${escapeHtml(moduleRoleLabel(module.role))}</div></div></div>
        <div class="detail-note">${escapeHtml(module.note || "暂无模块备注")}</div>
        <div class="port-detail"><span>类型 <b>${isMain ? "主模块" : "功能模块"}</b></span><span>Provider <b>${providers.length}</b></span><span>接口 <b>${apis.length}</b></span><span>类型关系 <b>${(module.typeRelations || []).length}</b></span><span>流程节点 <b>${isMain ? (flow?.nodeCount || 0) : "—"}</b></span></div>
        <div class="class-method-section"><div class="class-method-heading">Module composition</div>${roleCompositionBlock(module)}</div>
        <div class="class-method-section"><div class="class-method-heading">Providing API</div>${apiProviderList(providers)}</div>
        ${annotationBlock(module.moduleId)}
        <div class="empty-hint">${isMain ? "主流程节点可点击查看语义，双击进入方法详情。" : "双击自由函数进入方法详情；类节点右栏展示其提供接口。"}</div>`;
      bindApiNavigation(detailScroll);
      return;
    }
    const detail = functionDetailById.get(state.route.functionId);
    if (!detail) return;
    const module = projectModuleById.get(detail.moduleId);
    detailScroll.innerHTML = `<div class="detail-head" style="--mc:${module?.color || "#60a5fa"}"><div class="detail-color"></div><div>
        <div class="eyebrow">Method detail</div><h2 class="detail-name">${escapeHtml(detail.name)}</h2>
        <div class="detail-module">${escapeHtml(module?.name || detail.moduleId)} · ${escapeHtml(detail.module)}</div></div></div>
      <div class="detail-note">${escapeHtml(detail.note || "暂无函数备注")}</div>
      <div class="source-line">${escapeHtml(detail.file)}:${detail.line} · ${escapeHtml(detail.signature)}</div>
      ${annotationBlock(detail.id, detail.sourceHash)}
      <div class="empty-hint">左侧查看源码和调用关系；点击调用者/被调用者继续下钻。</div>`;
  }

  function renderSelectionDetail(uid) {
    const macroNode = state.nodes.get(uid);
    if (macroNode) {
      if (macroNode.flowRole) {
        const isDispatch = macroNode.kind === "dispatch";
        const module = projectModuleById.get(macroNode.moduleId);
        const functionId = macroNode.functionId;
        const detail = functionId ? functionDetailById.get(functionId) : null;
        detailScroll.innerHTML = `<div class="detail-head" style="--mc:${macroNode.color || module?.color || "#60a5fa"}"><div class="detail-color"></div><div>
            <div class="eyebrow">Main flow · ${escapeHtml(String(macroNode.flowRole || macroNode.kind).toUpperCase())}</div>
            <h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(macroNode.label || macroNode.providerName || macroNode.id)}</h2>
            <div class="detail-module">${escapeHtml(module?.name || macroNode.moduleName || macroNode.moduleId)}${macroNode.providerName ? ` · ${escapeHtml(macroNode.providerName)}` : ""}</div></div></div>
          <div class="detail-note">${escapeHtml(macroNode.note || "主流程组合节点")}</div>
          <div class="port-detail"><span>节点类型 <b>${escapeHtml(macroNode.kind)}</b></span><span>模块 <b>${escapeHtml(module?.name || macroNode.moduleId)}</b></span><span>边界 <b>${macroNode.flowBoundary ? "功能模块接口" : "主模块编排"}</b></span>${macroNode.signature ? `<span>签名 <b>${escapeHtml(macroNode.signature)}</b></span>` : ""}</div>
          ${isDispatch ? `<div class="llm-stale">${macroNode.candidateSource === "polymorphic" ? "多态分发边界：按已解析的本地实现候选生成低置信度 composition 连线。" : "动态分发边界：候选连线使用低置信度 composition 语义"}，${macroNode.candidateSetComplete ? "候选集已声明完整" : "候选集未声明完整"}。</div>
            <div class="source-line">表达式：${escapeHtml(macroNode.expression || macroNode.label || "")} · 候选：${Number(macroNode.candidateCount || 0)} · 来源：${escapeHtml(macroNode.candidateSource || "unknown")}</div>` : ""}
          ${detail ? `<div class="source-line">${escapeHtml(detail.file)}:${detail.line} · ${escapeHtml(detail.signature)}</div>` : ""}
          ${annotationBlock(functionId || uid, detail?.sourceHash)}
          <div class="detail-actions">${functionId ? `<button class="detail-action" type="button" data-open-flow-method="${escapeHtml(functionId)}">打开方法详情</button>` : ""}${module ? `<button class="detail-action" type="button" data-open-flow-module="${escapeHtml(module.id)}">打开模块页面</button>` : ""}</div>`;
        detailScroll.querySelector("[data-open-flow-method]")?.addEventListener("click", () => {
          const target = functionDetailById.get(functionId);
          if (target) navigate({ kind: "function", moduleId: target.moduleId, functionId: target.id });
        });
        detailScroll.querySelector("[data-open-flow-module]")?.addEventListener("click", () => navigate({ kind: "module", moduleId: module.id }));
        return;
      }
      if (macroNode.kind === "module") {
        const graph = moduleGraphById.get(uid);
        const apis = graph?.providedApis || [];
        const providers = graph?.apiProviders || [];
        detailScroll.innerHTML = `<div class="detail-head" style="--mc:${macroNode.color}"><div class="detail-color"></div><div>
            <div class="eyebrow">Module capability · ${escapeHtml(moduleRoleLabel(macroNode.role))}</div><h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(macroNode.name)}</h2>
            <div class="detail-module">module://${escapeHtml(uid)}</div></div></div>
          <div class="detail-note">${escapeHtml(macroNode.note || "暂无模块备注")}</div>
          <div class="port-detail"><span>类型 <b>${escapeHtml(macroNode.moduleKind === "main" ? "主模块" : "功能模块")}</b></span><span>Provider <b>${providers.length}</b></span><span>接口 <b>${apis.length}</b></span></div>
          <div class="class-method-section"><div class="class-method-heading">Module composition</div>${roleCompositionBlock(graph)}</div>
          <div class="class-method-section"><div class="class-method-heading">Providing API</div>${apiProviderList(providers)}</div>
          <div class="source-line">${escapeHtml((macroNode.sourceFiles || []).join("\n"))}</div>
          ${annotationBlock(uid)}
          <div class="detail-actions"><button class="detail-action" type="button" data-open-module-detail="${escapeHtml(uid)}">打开模块页面</button></div>`;
        bindApiNavigation(detailScroll);
        detailScroll.querySelector("[data-open-module-detail]")?.addEventListener("click", () => navigate({ kind: "module", moduleId: uid }));
        return;
      }
      if (macroNode.kind === "class") {
        const apis = macroNode.providedApis || [];
        const usage = macroNode.usage || {};
        const typeSummary = macroNode.typeSummary || usage.typeSummary || null;
        const isTypeCard = macroNode.providerRole === "config" || macroNode.providerRole === "model";
        const constructorSignature = usage.constructor?.signature || `${macroNode.name}()`;
        const protocols = usage.protocols || [];
        const internalCount = Number(macroNode.internalMethodCount || 0);
        detailScroll.innerHTML = `<div class="detail-head" style="--mc:${macroNode.color || "#60a5fa"}"><div class="detail-color"></div><div>
            <div class="eyebrow">${isTypeCard ? "Type provider" : "Class provider"}${macroNode.isAbstract ? " · contract" : ""}</div>
            <h2 class="detail-name">${escapeHtml(macroNode.name)}</h2>
            <div class="detail-module">${escapeHtml(macroNode.qualifiedName || "")}</div></div></div>
          <div class="detail-note">${escapeHtml(macroNode.note || "暂无类备注")}</div>
          <div class="port-detail"><span>角色 <b>${escapeHtml(providerRoleLabel(macroNode.providerRole))}</b></span><span>类型 <b>${escapeHtml(macroNode.classKind || "class")}</b></span><span>接口 <b>${apis.length}</b></span>${protocols.length ? `<span>协议 <b>${escapeHtml(protocols.join(" / "))}</b></span>` : ""}</div>
          <div class="source-line">角色来源：${escapeHtml(macroNode.roleSource || "structure")} · ${escapeHtml(macroNode.roleConfidence || "medium")}</div>
          ${isTypeCard ? "" : `<div class="source-line">用法：${escapeHtml(constructorSignature)}</div>`}
          <div class="source-line">${escapeHtml(macroNode.file || "")}:${macroNode.line || "—"}</div>
          <div class="port-detail"><span>声明接口 <b>${Number(macroNode.declaredApiCount || apis.filter(api => !api.inherited).length)}</b></span><span>继承接口 <b>${Number(macroNode.inheritedApiCount || apis.filter(api => api.inherited).length)}</b></span></div>
          ${macroNode.isAbstract ? `<div class="llm-stale">抽象类/接口是契约节点，不进入主流程执行节点。</div>` : ""}
          <div class="class-method-section"><div class="class-method-heading">Type hierarchy</div>${classHierarchyBlock(macroNode)}</div>
          ${isTypeCard ? `<div class="class-method-section"><div class="class-method-heading">Type fields · ${Number(typeSummary?.fieldCount || 0)}</div>${typeFieldList(typeSummary)}</div>` : `<div class="class-method-section"><div class="class-method-heading">提供接口</div>${apiDetailList(apis)}</div>`}
          <div class="class-method-section"><div class="class-method-heading">内部实现</div><div class="class-method-empty">${internalCount} 个内部方法，不在契约视图展示。</div></div>`;
        bindApiNavigation(detailScroll);
        return;
      }
      if (macroNode.kind === "function") {
        const detail = functionDetailById.get(macroNode.functionDetailId);
        detailScroll.innerHTML = `<div class="detail-head" style="--mc:${macroNode.color || "#60a5fa"}"><div class="detail-color"></div><div>
            <div class="eyebrow">Function provider</div><h2 class="detail-name">${escapeHtml(macroNode.name)}</h2>
            <div class="detail-module">${escapeHtml(macroNode.qualifiedName || "")}</div></div></div>
          <div class="detail-note">${escapeHtml(macroNode.note || "暂无函数备注")}</div>
          <div class="port-detail"><span>角色 <b>${escapeHtml(providerRoleLabel(macroNode.providerRole))}</b></span><span>暴露 <b>${escapeHtml(detail?.apiExposure || macroNode.apiExposure || "public")}</b></span><span>来源 <b>${escapeHtml(detail?.apiExposureSource || macroNode.apiExposureSource || "naming")}</b></span></div>
          <div class="source-line">角色来源：${escapeHtml(macroNode.roleSource || "structure")} · ${escapeHtml(macroNode.roleConfidence || "medium")}</div>
          <div class="source-line">${escapeHtml(macroNode.file)}:${macroNode.line}</div>
          ${annotationBlock(macroNode.functionDetailId, detail?.sourceHash)}
          <div class="detail-actions"><button class="detail-action" type="button" data-open-method-detail="${escapeHtml(macroNode.functionDetailId)}">打开方法详情</button></div>`;
        detailScroll.querySelector("[data-open-method-detail]")?.addEventListener("click", () => {
          const target = functionDetailById.get(macroNode.functionDetailId);
          if (target) navigate({ kind: "function", moduleId: target.moduleId, functionId: target.id });
        });
        return;
      }
    }
    renderDefaultDetail();
  }

  function currentMainFlow() {
    const flows = projectGraph.mainFlows || [];
    if (!flows.length) return null;
    const wanted = state.flowId || projectGraph.primaryFlowId;
    return flows.find(flow => flow.id === wanted) || flows[0];
  }

  function renderModuleContracts(moduleId) {
    if (!moduleContracts) return;
    const graph = moduleGraphById.get(moduleId);
    const apis = graph?.providedApis || [];
    if (!graph) {
      moduleContracts.innerHTML = "";
      moduleContracts.classList.remove("is-visible");
      return;
    }
    const flows = projectGraph.mainFlows || [];
    const flowSwitcher = graph.moduleKind === "main"
      ? `<div class="flow-switcher"><span>MAIN MODULE</span>
          <button type="button" data-main-view="flow" class="${state.mainView === "flow" ? "is-active" : ""}">主流程</button>
          <button type="button" data-main-view="capabilities" class="${state.mainView === "capabilities" ? "is-active" : ""}">能力视图</button>
          ${flows.map(flow => `<button type="button" data-flow-id="${escapeHtml(flow.id)}" class="${state.mainView === "flow" && flow.id === currentMainFlow()?.id ? "is-active" : ""}">${escapeHtml(flow.name || flow.entrypointId)}</button>`).join("")}
        </div>`
      : "";
    moduleContracts.style.setProperty("--mc-rgb", rgbFromHex(graph.color || "#60a5fa"));
    moduleContracts.innerHTML = `${flowSwitcher}<div class="contracts-main">
        <div class="contracts-label">PROVIDED API</div>
        <div class="contracts-track">${apis.length ? apiChips(apis, 8, { showMore: true }) : `<span class="contracts-empty">该模块暂无公开接口</span>`}</div>
        <div class="contracts-count">${apis.length} apis</div>
      </div>
      <div class="contracts-roles">${roleCountChips(visibleRoleCounts(graph))}</div>
      <div class="contracts-types"><div class="contracts-label">TYPE RELATIONS</div><div class="type-relation-track">${typeRelationChips(graph)}</div><div class="contracts-count">${(graph.typeRelations || []).length} relations</div></div>`;
    moduleContracts.classList.add("is-visible");
    bindApiNavigation(moduleContracts);
    moduleContracts.querySelectorAll("[data-main-view]").forEach(button => {
      button.addEventListener("click", event => {
        event.stopPropagation();
        state.mainView = button.dataset.mainView === "capabilities" ? "capabilities" : "flow";
        renderModulePage(moduleId);
      });
    });
    moduleContracts.querySelectorAll("[data-flow-id]").forEach(button => {
      button.addEventListener("click", event => {
        event.stopPropagation();
        state.flowId = button.dataset.flowId;
        state.mainView = "flow";
        renderModulePage(moduleId);
      });
    });
  }

  function updateChrome(kind) {
    const module = state.route.moduleId ? projectModuleById.get(state.route.moduleId) : null;
    const detail = state.route.functionId ? functionDetailById.get(state.route.functionId) : null;
    relationModeBtn.style.display = kind === "project" ? "" : "none";
    relationModeBtn.setAttribute("aria-pressed", String(state.showProjectRelations));
    relationModeBtn.textContent = state.showProjectRelations ? "隐藏关系" : "关系";
    if (kind === "project") {
      canvasKicker.textContent = "Project composition map";
      canvasTitle.textContent = DATA.project.name;
      canvasSub.textContent = "主模块 + 功能模块能力卡片 · 双击进入模块页面";
      breadcrumb.innerHTML = `<b>${escapeHtml(DATA.project.name)}</b>`;
      legend.innerHTML = state.showProjectRelations
        ? legendItem("line", "模块调用/数据关系") + legendItem("card", "模块能力卡片")
        : legendItem("card", "模块能力卡片") + legendItem("entry", "主模块");
    } else if (kind === "module") {
      const isMain = module?.moduleKind === "main";
      canvasKicker.textContent = isMain ? "Main flow" : "Module capability";
      canvasTitle.textContent = module?.name || state.route.moduleId;
      canvasSub.textContent = isMain
        ? "入口 → 主模块编排 → 功能模块接口 · 实线 call · 虚线 composition"
        : "提供接口 · 类/自由函数 · 内部调用 · 双击进入详情";
      breadcrumb.innerHTML = `<button type="button" data-nav="project">${escapeHtml(DATA.project.name)}</button><span class="slash">/</span><b>${escapeHtml(module?.name || state.route.moduleId)}</b>`;
      legend.innerHTML = isMain
        ? legendItem("entry", "入口") + legendItem("function", "主模块编排") + legendItem("interface", "功能接口") + legendItem("dashed", "composition / low")
        : legendItem("line", "模块内部调用关系");
    } else {
      const ownerClass = detail?.ownerClassId
        ? (moduleGraphById.get(detail.moduleId)?.nodes || []).find(node => node.id === detail.ownerClassId)
        : null;
      const owner = ownerClass ? `<button type="button" data-nav="module" data-module="${escapeHtml(state.route.moduleId)}">${escapeHtml(ownerClass.name)}</button><span class="slash">/</span>` : "";
      canvasKicker.textContent = "Method detail";
      canvasTitle.textContent = detail?.name || state.route.functionId;
      canvasSub.textContent = "源码 + 人类备注 + LLM 语义 + 调用关系";
      breadcrumb.innerHTML = `<button type="button" data-nav="project">${escapeHtml(DATA.project.name)}</button><span class="slash">/</span><button type="button" data-nav="module" data-module="${escapeHtml(state.route.moduleId)}">${escapeHtml(module?.name || state.route.moduleId)}</button><span class="slash">/</span>${owner}<b>${escapeHtml(detail?.name || state.route.functionId)}</b>`;
      legend.innerHTML = legendItem("line", "调用关系") + legendItem("input", "源码证据");
    }
    breadcrumb.querySelectorAll("[data-nav]").forEach(button => {
      button.addEventListener("click", () => {
        if (button.dataset.nav === "project") navigate({ kind: "project" });
        if (button.dataset.nav === "module") navigate({ kind: "module", moduleId: button.dataset.module });
      });
    });
    $("pageHint").textContent = kind === "project" ? "项目页" : kind === "module" ? "模块页" : "方法详情";
    searchWrap.classList.toggle("is-disabled", kind === "method");
    if (kind === "method") searchInput.value = "";
    backBtn.disabled = kind === "project" && history.length <= 1;
  }

  function projectNodeExpanded(moduleId) {
    if (Object.prototype.hasOwnProperty.call(override.project.expanded, moduleId)) {
      return Boolean(override.project.expanded[moduleId]);
    }
    return false;
  }

  function projectNodeSize(node) {
    if (node.kind === "module") {
      return projectNodeExpanded(node.id)
        ? { w: node.expandedW || 560, h: node.expandedH || 360 }
        : { w: node.w || 270, h: node.h || 140 };
    }
    return { w: node.w || 190, h: node.h || 96 };
  }

  function projectNodeDefaultPosition(nodeId) {
    return projectGraph.layout?.nodes?.[nodeId] || { x: 80, y: 120, w: 270, h: 140 };
  }

  function getProjectPosition(nodeId) {
    const custom = override.project.nodes[nodeId];
    const base = projectNodeDefaultPosition(nodeId);
    return { x: Number(custom?.x ?? base.x ?? 0), y: Number(custom?.y ?? base.y ?? 0) };
  }

  function setProjectPosition(nodeId, x, y) {
    override.project.nodes[nodeId] = { x: Math.round(x), y: Math.round(y) };
  }

  function updateProjectWorldSize() {
    let width = 900, height = 640;
    state.nodes.forEach((node, nodeId) => {
      const position = getProjectPosition(nodeId);
      const size = state.sizes.get(nodeId) || projectNodeSize(node);
      width = Math.max(width, position.x + size.w + 90);
      height = Math.max(height, position.y + size.h + 100);
    });
    world.style.width = `${width}px`;
    world.style.height = `${height}px`;
    const svg = world.querySelector(".world-edges");
    if (svg) {
      svg.setAttribute("width", String(width));
      svg.setAttribute("height", String(height));
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    }
    return { width, height };
  }

  function refreshProjectEdges() {
    world.querySelectorAll(".macro-edge").forEach(path => {
      const from = state.positions.get(path.dataset.from);
      const to = state.positions.get(path.dataset.to);
      if (!from || !to) {
        path.style.display = "none";
        return;
      }
      path.style.display = "";
      path.setAttribute("d", curvePath(from, to));
    });
  }

  function renderProjectPage() {
    state.pageKind = "project";
    state.moduleId = null;
    state.functionId = null;
    viewport.classList.remove("is-light");
    viewport.classList.remove("is-detail");
    setGraphChromeVisible(true);
    updateChrome("project");
    if (moduleContracts) {
      moduleContracts.innerHTML = "";
      moduleContracts.classList.remove("is-visible");
    }
    world.innerHTML = "";
    world.classList.remove("page-enter");
    const visibleModuleIds = state.singleModule && projectGraph.modules.length
      ? [projectGraph.modules[0].id]
      : projectGraph.modules.map(item => item.id);
    state.nodes = new Map();
    // The project page is a module capability board.  Main-flow and dependency
    // evidence stay in the bundle; the main module page renders the curated
    // composition flow.
    projectGraph.modules.forEach(module => {
      if (visibleModuleIds.includes(module.id)) {
        state.nodes.set(module.id, { ...module, kind: "module" });
      }
    });
    state.sizes = new Map();
    state.positions = new Map();
    state.nodes.forEach((node, nodeId) => {
      const size = projectNodeSize(node);
      state.sizes.set(nodeId, size);
      const position = getProjectPosition(nodeId);
      state.positions.set(nodeId, { x: position.x, y: position.y, w: size.w, h: size.h });
    });
    const width = 1200, height = 800;
    const svg = makeSvg(width, height, "world-edges");
    world.appendChild(svg);
    state.pageEdges = state.showProjectRelations
      ? projectGraph.edges.filter(edge => edge.role === "internal" && state.nodes.has(edge.from) && state.nodes.has(edge.to))
      : [];
    state.pageEdges.forEach(edge => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("class", macroEdgeClass(edge));
      path.setAttribute("data-from", edge.from);
      path.setAttribute("data-to", edge.to);
      path.setAttribute("data-edge-id", edge.id);
      path.setAttribute("data-edge-count", String((edge.evidence || []).length));
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${edge.primaryType} · ${(edge.evidence || []).length} evidence`;
      path.appendChild(title);
      const from = state.positions.get(edge.from);
      const to = state.positions.get(edge.to);
      path.setAttribute("d", curvePath(from, to));
      svg.appendChild(path);
    });
    state.nodes.forEach((node, nodeId) => {
      renderProjectModule(nodeId, node);
    });
    updateProjectWorldSize();
    refreshProjectEdges();
    world.classList.add("page-enter");
    requestAnimationFrame(() => {
      applyTransform();
      fitView();
      renderDefaultDetail();
      if (state.search) applySearch();
    });
  }

  function renderProjectModule(nodeId, module) {
    const position = state.positions.get(nodeId);
    const expanded = projectNodeExpanded(nodeId);
    const size = state.sizes.get(nodeId);
    const graph = moduleGraphById.get(nodeId);
    const apis = graph?.providedApis || [];
    const role = module.role || graph?.role || "service";
    const isMain = role === "main";
    const visibleClasses = visibleProviderNodes(graph).filter(node => node.kind === "class").length;
    const classCount = Number(visibleClasses || 0);
    const providerCount = Number((graph?.apiProviders || []).length);
    const apiCount = Number(module.providedApiCount ?? apis.length);
    const element = document.createElement("article");
    element.className = `node-card module-node${expanded ? " is-expanded" : ""}${isMain ? " is-main" : ""}`;
    element.dataset.uid = nodeId;
    element.style.left = `${position.x}px`;
    element.style.top = `${position.y}px`;
    element.style.width = `${size.w}px`;
    element.style.height = `${size.h}px`;
    element.style.setProperty("--mc", module.color || "#f59e0b");
    element.style.setProperty("--mc-rgb", rgbFromHex(module.color || "#f59e0b"));
    element.innerHTML = `<header class="module-header">
        <div class="module-title-row">
          <span class="module-dot"></span><span class="module-kind">${escapeHtml(moduleRoleLabel(role))}</span>
          <span class="module-title">${escapeHtml(module.name)}</span>
          <div class="module-actions">
            <button class="mini-action" type="button" data-expand="${escapeHtml(nodeId)}" aria-label="${expanded ? "收起模块" : "展开模块"}" title="${expanded ? "收起" : "展开"}">${expanded ? "−" : "+"}</button>
            <button class="mini-action" type="button" data-open-module="${escapeHtml(nodeId)}" aria-label="打开模块页面" title="打开独立模块页面">↗</button>
          </div>
        </div>
        <div class="module-note">${escapeHtml(module.note || "暂无模块备注")}</div>
        <div class="module-api-section">
          <div class="module-api-heading"><span>PROVIDED API</span><b>${apiCount}</b></div>
          <div class="module-api-chips">${apiChips(apis, isMain ? 4 : 3)}</div>
        </div>
        <div class="module-role-counts">${roleCountChips(visibleRoleCounts(graph))}</div>
        <div class="module-metrics">
          <span>${classCount} class${classCount === 1 ? "" : "es"}</span>
          <span>${providerCount} provider${providerCount === 1 ? "" : "s"}</span>
          <span class="${apiCount ? "has-apis" : ""}">${apiCount} api${apiCount === 1 ? "" : "s"}</span>
          ${module.moduleKind === "main" ? `<span class="has-apis">main flow${module.mainFlowId ? "" : " · empty"}</span>` : ""}
        </div>
      </header>`;
    if (expanded) {
      const mini = document.createElement("div");
      mini.className = "module-mini";
      mini.dataset.moduleId = nodeId;
      element.appendChild(mini);
    }
    world.appendChild(element);
    bindNodeHover(element, nodeId);
    bindApiNavigation(element);
    const header = element.querySelector(".module-header");
    header.addEventListener("click", event => {
      if (event.target.closest("button")) return;
      selectUid(nodeId);
    });
    header.addEventListener("dblclick", event => {
      if (event.target.closest("button")) return;
      navigate({ kind: "module", moduleId: nodeId });
    });
    element.querySelector("[data-open-module]")?.addEventListener("click", event => {
      event.stopPropagation();
      navigate({ kind: "module", moduleId: nodeId });
    });
    element.querySelector("[data-expand]")?.addEventListener("click", event => {
      event.stopPropagation();
      override.project.expanded[nodeId] = !expanded;
      persistOverride();
      renderProjectPage();
    });
    attachDrag(header, element, {
      getPosition: () => ({ x: parseFloat(element.style.left), y: parseFloat(element.style.top) }),
      setPosition: (x, y) => {
        const pos = state.positions.get(nodeId);
        pos.x = x; pos.y = y;
        setProjectPosition(nodeId, x, y);
      },
      bounds: () => ({ w: 2600, h: 1800 }),
      onMove: refreshProjectEdges,
      onEnd: () => { persistOverride(); updateProjectWorldSize(); },
    });
    if (expanded) renderModuleMini(element.querySelector(".module-mini"), nodeId);
  }

  function miniDefaultPositions(moduleId) {
    const graph = moduleGraphById.get(moduleId);
    if (!graph) return new Map();
    const functions = visibleProviderNodes(graph);
    if (!functions.length) return new Map();
    const layout = graph.layout?.nodes || {};
    const rects = functions.map(node => {
      const rect = layout[node.id] || { x: 0, y: 0, w: node.w || 210, h: node.h || 98 };
      return { id: node.id, x: Number(rect.x || 0), y: Number(rect.y || 0) };
    });
    const minX = Math.min(...rects.map(item => item.x));
    const maxX = Math.max(...rects.map(item => item.x));
    const minY = Math.min(...rects.map(item => item.y));
    const maxY = Math.max(...rects.map(item => item.y));
    const areaW = 540, areaH = 218, nodeW = 176, nodeH = 76;
    const spanX = Math.max(1, maxX - minX + 210);
    const spanY = Math.max(1, maxY - minY + 98);
    const scale = Math.min((areaW - nodeW - 20) / spanX, (areaH - nodeH - 18) / spanY, 1);
    const offsetX = (areaW - spanX * scale) / 2;
    const offsetY = (areaH - spanY * scale) / 2;
    const result = new Map();
    rects.forEach(item => {
      result.set(item.id, {
        x: Math.max(8, Math.min(areaW - nodeW - 8, offsetX + (item.x - minX) * scale)),
        y: Math.max(8, Math.min(areaH - nodeH - 8, offsetY + (item.y - minY) * scale)),
      });
    });
    return result;
  }

  function getMiniPosition(moduleId, functionId, defaults) {
    const custom = override.project.miniNodes?.[moduleId]?.[functionId];
    const base = defaults.get(functionId) || { x: 16, y: 20 };
    return { x: Number(custom?.x ?? base.x), y: Number(custom?.y ?? base.y) };
  }

  function setMiniPosition(moduleId, functionId, x, y) {
    if (!override.project.miniNodes[moduleId]) override.project.miniNodes[moduleId] = {};
    override.project.miniNodes[moduleId][functionId] = { x: Math.round(x), y: Math.round(y) };
  }

  function refreshMiniEdges(moduleId) {
    const host = world.querySelector(`.module-mini[data-module-id="${cssEscape(moduleId)}"]`);
    if (!host) return;
    const svg = host.querySelector(".mini-edges");
    if (!svg) return;
    const graph = moduleGraphById.get(moduleId);
    const defaults = miniDefaultPositions(moduleId);
    const positionMap = new Map();
    visibleProviderNodes(graph).forEach(node => {
      const element = host.querySelector(`.mini-node[data-uid="${cssEscape(node.id)}"]`);
      if (!element) return;
      positionMap.set(node.id, {
        x: parseFloat(element.style.left),
        y: parseFloat(element.style.top),
        w: 176,
        h: 76,
      });
    });
    svg.querySelectorAll(".graph-edge").forEach(path => {
      const from = positionMap.get(path.dataset.from);
      const to = positionMap.get(path.dataset.to);
      if (from && to) path.setAttribute("d", curvePath(from, to));
    });
  }

  function renderModuleMini(host, moduleId) {
    const graph = moduleGraphById.get(moduleId);
    if (!host || !graph) return;
    const defaults = miniDefaultPositions(moduleId);
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "mini-edges");
    svg.setAttribute("width", "540");
    svg.setAttribute("height", "218");
    svg.setAttribute("viewBox", "0 0 540 218");
    host.appendChild(svg);
    const visibleIds = new Set(visibleProviderNodes(graph).map(node => node.id));
    const edges = graph.edges.filter(edge => edge.role === "internal" && visibleIds.has(edge.from) && visibleIds.has(edge.to));
    edges.forEach(edge => {
      const fromPos = getMiniPosition(moduleId, edge.from, defaults);
      const toPos = getMiniPosition(moduleId, edge.to, defaults);
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("class", "graph-edge");
      path.setAttribute("data-from", edge.from);
      path.setAttribute("data-to", edge.to);
      path.setAttribute("d", curvePath({ ...fromPos, w: 176, h: 76 }, { ...toPos, w: 176, h: 76 }));
      path.setAttribute("stroke", graph.color || "#f59e0b");
      path.setAttribute("opacity", ".42");
      svg.appendChild(path);
    });
    visibleProviderNodes(graph).forEach(node => {
      const pos = getMiniPosition(moduleId, node.id, defaults);
      const element = document.createElement("article");
      element.className = `mini-node node-card${node.kind === "class" ? " mini-class" : ""}`;
      element.dataset.uid = node.id;
      element.style.left = `${pos.x}px`;
      element.style.top = `${pos.y}px`;
      element.style.width = "176px";
      element.style.height = "76px";
      const prefix = node.kind === "class" ? "C · " : "";
      element.innerHTML = `<div class="mini-title">${escapeHtml(prefix + node.name)}</div><div class="mini-note">${escapeHtml(node.note || (node.kind === "class" ? `${node.methodCount || 0} methods` : "暂无备注"))}</div>`;
      host.appendChild(element);
      bindNodeHover(element, node.id);
      element.addEventListener("click", event => {
        event.stopPropagation();
        state.nodes.set(node.id, { ...node, kind: node.kind, color: graph.color });
        selectUid(node.id);
      });
      element.addEventListener("dblclick", event => {
        event.stopPropagation();
        if (node.kind === "class") {
          navigate({ kind: "module", moduleId });
          return;
        }
        navigate({ kind: "function", moduleId, functionId: node.id });
      });
      attachDrag(element, element, {
        getPosition: () => ({ x: parseFloat(element.style.left), y: parseFloat(element.style.top) }),
        setPosition: (x, y) => setMiniPosition(moduleId, node.id, x, y),
        bounds: () => ({ w: 540 - 176, h: 218 - 76 }),
        onMove: () => refreshMiniEdges(moduleId),
        onEnd: persistOverride,
      });
    });
  }

  function modulePagePositionDefault(moduleId, nodeId) {
    return moduleGraphById.get(moduleId)?.layout?.nodes?.[nodeId] || { x: 80, y: 120, w: 210, h: 98 };
  }

  function getModulePagePosition(moduleId, nodeId) {
    const custom = override.modules?.[moduleId]?.nodes?.[nodeId];
    const base = modulePagePositionDefault(moduleId, nodeId);
    return { x: Number(custom?.x ?? base.x ?? 0), y: Number(custom?.y ?? base.y ?? 0) };
  }

  function setModulePagePosition(moduleId, nodeId, x, y) {
    if (!override.modules[moduleId]) override.modules[moduleId] = { nodes: {} };
    if (!override.modules[moduleId].nodes) override.modules[moduleId].nodes = {};
    override.modules[moduleId].nodes[nodeId] = { x: Math.round(x), y: Math.round(y) };
  }

  function moduleNodeSize(node) {
    if (node.kind === "class") return { w: node.w || 280, h: node.h || 170 };
    if (node.kind === "function") return { w: node.w || 210, h: node.h || 98 };
    return { w: node.w || 190, h: node.h || 96 };
  }

  function updateModuleWorldSize(moduleId) {
    let width = 860, height = 640;
    state.nodes.forEach((node, nodeId) => {
      const pos = state.positions.get(nodeId);
      const size = state.sizes.get(nodeId);
      width = Math.max(width, pos.x + size.w + 90);
      height = Math.max(height, pos.y + size.h + 100);
    });
    world.style.width = `${width}px`;
    world.style.height = `${height}px`;
    const svg = world.querySelector(".world-edges");
    if (svg) {
      svg.setAttribute("width", String(width));
      svg.setAttribute("height", String(height));
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    }
  }

  function refreshModuleEdges() {
    world.querySelectorAll(".macro-edge").forEach(path => {
      const from = state.positions.get(path.dataset.from);
      const to = state.positions.get(path.dataset.to);
      if (from && to) path.setAttribute("d", curvePath(from, to));
    });
  }

  function flowEdgeClass(edge) {
    const kind = edge.kind || "call";
    return `macro-edge graph-edge flow-edge kind-${escapeHtml(kind)}${edge.confidence === "low" ? " is-low" : ""}`;
  }

  function getFlowPosition(moduleId, nodeId, flow) {
    const custom = override.modules?.[moduleId]?.nodes?.[nodeId];
    const base = flow?.layout?.nodes?.[nodeId] || { x: 80, y: 100 };
    return { x: Number(custom?.x ?? base.x ?? 0), y: Number(custom?.y ?? base.y ?? 0) };
  }

  function renderMainFlowNode(moduleId, nodeId, node) {
    const pos = state.positions.get(nodeId);
    const element = document.createElement("article");
    const kind = node.kind || "orchestrator";
    const badges = [
      kind === "dispatch" ? `${Number(node.candidateCount || 0)} candidates` : "",
      kind === "dispatch" && node.candidateSetComplete ? "complete" : "",
      kind === "dispatch" && !node.candidateSetComplete ? "partial" : "",
      node.capabilityKind || "",
      node.flowBoundary ? "module boundary" : "",
    ].filter(Boolean);
    element.className = `node-card main-flow-node flow-${escapeHtml(kind)}${kind === "dispatch" ? " is-dispatch" : ""}`;
    element.dataset.uid = nodeId;
    element.style.left = `${pos.x}px`;
    element.style.top = `${pos.y}px`;
    element.style.width = `${pos.w}px`;
    element.style.height = `${pos.h}px`;
    element.style.setProperty("--mc", node.color || "#60a5fa");
    element.style.setProperty("--mc-rgb", rgbFromHex(node.color || "#60a5fa"));
    const icon = kind === "entry" ? "▶" : kind === "dispatch" ? "⑂" : kind === "provider" ? "C" : kind === "interface" ? "I" : "ƒ";
    element.innerHTML = `<div class="flow-node-top">
        <span class="flow-node-icon">${icon}</span>
        <span class="flow-node-kind">${escapeHtml(kind.toUpperCase())}</span>
        <span class="flow-node-module">${escapeHtml(node.moduleName || node.moduleId || "")}</span>
      </div>
      <div class="flow-node-label">${escapeHtml(node.label || node.providerName || node.id)}</div>
      <div class="flow-node-note">${escapeHtml(node.note || node.signature || "主流程组合节点")}</div>
      ${badges.length ? `<div class="flow-node-badges">${badges.map(item => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : ""}`;
    world.appendChild(element);
    bindNodeHover(element, nodeId);
    element.addEventListener("click", event => {
      event.stopPropagation();
      selectUid(nodeId);
    });
    element.addEventListener("dblclick", event => {
      event.stopPropagation();
      if (node.functionId && functionDetailById.has(node.functionId)) {
        const detail = functionDetailById.get(node.functionId);
        navigate({ kind: "function", moduleId: detail.moduleId, functionId: detail.id });
      }
    });
    attachDrag(element, element, {
      getPosition: () => ({ x: parseFloat(element.style.left), y: parseFloat(element.style.top) }),
      setPosition: (x, y) => {
        const item = state.positions.get(nodeId);
        item.x = x; item.y = y;
        setModulePagePosition(moduleId, nodeId, x, y);
      },
      bounds: () => ({ w: 3000, h: 2200 }),
      onMove: refreshModuleEdges,
      onEnd: () => { persistOverride(); updateModuleWorldSize(moduleId); },
    });
  }

  function renderMainFlowPage(moduleId, graph) {
    const flow = currentMainFlow();
    world.innerHTML = "";
    world.classList.remove("page-enter");
    state.nodes = new Map();
    state.sizes = new Map();
    state.positions = new Map();
    if (!flow) {
      world.style.width = "760px";
      world.style.height = "420px";
      world.innerHTML = `<div class="main-flow-empty"><div class="eyebrow">Main flow</div><h2>暂无可解析入口</h2><p>主模块已建立，但当前项目没有可用的 entrypoint 或主流程入口。</p></div>`;
      updateModuleWorldSize(moduleId);
      requestAnimationFrame(() => { applyTransform(); fitView(); renderDefaultDetail(); });
      return;
    }
    state.flowId = flow.id;
    flow.nodes.forEach(node => {
      state.nodes.set(node.id, { ...node, color: node.color || graph.color });
      state.sizes.set(node.id, { w: Number(node.w || 244), h: Number(node.h || 108) });
      const pos = getFlowPosition(moduleId, node.id, flow);
      state.positions.set(node.id, { x: pos.x, y: pos.y, w: Number(node.w || 244), h: Number(node.h || 108) });
    });
    const canvas = flow.layout?.canvas || { width: 1200, height: 800 };
    const svg = makeSvg(Number(canvas.width || 1200), Number(canvas.height || 800), "world-edges");
    world.appendChild(svg);
    state.pageEdges = flow.edges || [];
    state.pageEdges.forEach(edge => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("class", flowEdgeClass(edge));
      path.setAttribute("data-from", edge.from);
      path.setAttribute("data-to", edge.to);
      path.setAttribute("data-edge-id", edge.id);
      path.setAttribute("data-edge-kind", edge.kind || "call");
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${edge.kind || "call"} · ${edge.confidence || "medium"}${edge.branchLabel ? ` · ${edge.branchLabel}` : ""}`;
      path.appendChild(title);
      const from = state.positions.get(edge.from);
      const to = state.positions.get(edge.to);
      if (from && to) path.setAttribute("d", curvePath(from, to));
      svg.appendChild(path);
    });
    state.nodes.forEach((node, nodeId) => renderMainFlowNode(moduleId, nodeId, node));
    updateModuleWorldSize(moduleId);
    refreshModuleEdges();
    world.classList.add("page-enter");
    requestAnimationFrame(() => {
      applyTransform();
      fitView();
      renderDefaultDetail();
      const pendingUid = state.pendingSelectUid;
      state.pendingSelectUid = null;
      if (pendingUid && state.nodes.has(pendingUid)) selectUid(pendingUid);
      if (state.search) applySearch();
    });
  }

  function renderModulePage(moduleId) {
    const graph = moduleGraphById.get(moduleId);
    if (!graph) {
      navigate({ kind: "project" }, false);
      return;
    }
    state.pageKind = "module";
    state.moduleId = moduleId;
    state.functionId = null;
    viewport.classList.remove("is-light");
    viewport.classList.remove("is-detail");
    setGraphChromeVisible(true);
    updateChrome("module");
    renderModuleContracts(moduleId);
    if (graph.moduleKind === "main" && state.mainView !== "capabilities") {
      renderMainFlowPage(moduleId, graph);
      return;
    }
    world.innerHTML = "";
    world.classList.remove("page-enter");
    state.nodes = new Map();
    graph.nodes.forEach(node => {
      if ((node.kind === "class" || node.kind === "function") && isHiddenProvider(node)) {
        return;
      }
      if (node.kind === "class") {
        state.nodes.set(node.id, { ...node, kind: "class", color: graph.color });
      } else if (node.kind === "function") {
        state.nodes.set(node.id, { ...node, kind: "function", color: graph.color });
      }
    });
    state.sizes = new Map();
    state.positions = new Map();
    state.nodes.forEach((node, nodeId) => {
      const size = moduleNodeSize(node);
      const position = getModulePagePosition(moduleId, nodeId);
      state.sizes.set(nodeId, size);
      state.positions.set(nodeId, { x: position.x, y: position.y, w: size.w, h: size.h });
    });
    const svg = makeSvg(1200, 800, "world-edges");
    world.appendChild(svg);
    state.pageEdges = graph.edges.filter(edge => state.nodes.has(edge.from) && state.nodes.has(edge.to));
    state.pageEdges.forEach(edge => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("class", macroEdgeClass(edge));
      path.setAttribute("data-from", edge.from);
      path.setAttribute("data-to", edge.to);
      path.setAttribute("data-edge-id", edge.id);
      const from = state.positions.get(edge.from);
      const to = state.positions.get(edge.to);
      path.setAttribute("d", curvePath(from, to));
      svg.appendChild(path);
    });
    state.nodes.forEach((node, nodeId) => {
      if (node.kind === "function") renderModuleFunctionNode(moduleId, nodeId, node);
      else if (node.kind === "class") renderModuleClassNode(moduleId, nodeId, node);
    });
    updateModuleWorldSize(moduleId);
    refreshModuleEdges();
    world.classList.add("page-enter");
    requestAnimationFrame(() => {
      applyTransform();
      fitView();
      renderDefaultDetail();
      const pendingUid = state.pendingSelectUid;
      state.pendingSelectUid = null;
      if (pendingUid && state.nodes.has(pendingUid)) selectUid(pendingUid);
      if (state.search) applySearch();
    });
  }

  function renderModuleFunctionNode(moduleId, nodeId, node) {
    const pos = state.positions.get(nodeId);
    const graph = moduleGraphById.get(moduleId);
    const element = document.createElement("article");
    element.className = "node-card function-node";
    element.dataset.uid = nodeId;
    element.style.left = `${pos.x}px`;
    element.style.top = `${pos.y}px`;
    element.style.width = `${pos.w}px`;
    element.style.height = `${pos.h}px`;
    element.style.setProperty("--mc", graph?.color || "#f59e0b");
    element.style.setProperty("--mc-rgb", rgbFromHex(graph?.color || "#f59e0b"));
    element.innerHTML = `<div class="fn-node-top"><span class="fn-node-icon">ƒ</span><span class="fn-node-kind">${escapeHtml(providerRoleLabel(node.providerRole))}</span>${providerRoleBadge(node.providerRole)}</div>
      <div class="fn-node-name">${escapeHtml(node.name)}</div>
      <div class="fn-node-note">${escapeHtml(node.note || "暂无备注")}</div>`;
    world.appendChild(element);
    bindNodeHover(element, nodeId);
    element.addEventListener("click", () => selectUid(nodeId));
    element.addEventListener("dblclick", () => navigate({ kind: "function", moduleId, functionId: node.id }));
    attachDrag(element, element, {
      getPosition: () => ({ x: parseFloat(element.style.left), y: parseFloat(element.style.top) }),
      setPosition: (x, y) => {
        const item = state.positions.get(nodeId);
        item.x = x; item.y = y;
        setModulePagePosition(moduleId, nodeId, x, y);
      },
      bounds: () => ({ w: 2200, h: 1600 }),
      onMove: refreshModuleEdges,
      onEnd: () => { persistOverride(); updateModuleWorldSize(moduleId); },
    });
  }

  function renderModuleClassNode(moduleId, nodeId, node) {
    const pos = state.positions.get(nodeId);
    const graph = moduleGraphById.get(moduleId);
    const methods = Array.isArray(node.methods) ? node.methods : [];
    const apis = Array.isArray(node.providedApis) ? node.providedApis : [];
    const usage = node.usage || {};
    const typeSummary = node.typeSummary || usage.typeSummary || null;
    const isTypeCard = node.providerRole === "config" || node.providerRole === "model";
    const constructorSignature = usage.constructor?.signature || `${node.name}()`;
    const inheritanceText = (node.baseClassIds || []).length ? ` · ${node.baseClassIds.length} base` : "";
    const inheritedText = Number(node.inheritedApiCount || 0) ? ` · ${Number(node.inheritedApiCount)} inherited` : "";
    const bodySummary = isTypeCard
      ? `<div class="class-usage">${Number(typeSummary?.fieldCount || 0)} fields · type contract${inheritanceText}</div>`
      : `<div class="class-usage">${escapeHtml(constructorSignature)}${escapeHtml(inheritanceText + inheritedText)}</div>`;
    const chips = isTypeCard
      ? `<div class="class-method-chips type-fields">${typeFieldChips(typeSummary, 2)}</div>`
      : `<div class="class-method-chips">${apiChips(apis, 2)}</div>`;
    const element = document.createElement("article");
    element.className = `node-card class-node${node.isAbstract ? " is-abstract" : ""}${isTypeCard ? " is-type-card" : ""} role-${escapeHtml(node.providerRole || "utility")}`;
    element.dataset.uid = nodeId;
    element.style.left = `${pos.x}px`;
    element.style.top = `${pos.y}px`;
    element.style.width = `${pos.w}px`;
    element.style.height = `${pos.h}px`;
    element.style.setProperty("--mc", graph?.color || "#60a5fa");
    element.style.setProperty("--mc-rgb", rgbFromHex(graph?.color || "#60a5fa"));
    element.innerHTML = `<div class="class-node-top">
        <span class="class-node-icon">C</span>
        <span class="class-node-kind">${escapeHtml(providerRoleLabel(node.providerRole))}</span>
        ${providerRoleBadge(node.providerRole)}
        <span class="class-node-count">${isTypeCard ? `${Number(typeSummary?.fieldCount || 0)} fields` : `${apis.length} apis`}</span>
      </div>
      <div class="class-node-name">${escapeHtml(node.name)}</div>
      ${bodySummary}
      <div class="class-node-note">${escapeHtml(node.note || "暂无类备注")}</div>
      ${chips}`;
    world.appendChild(element);
    bindNodeHover(element, nodeId);
    bindApiNavigation(element);
    element.addEventListener("click", () => selectUid(nodeId));
    attachDrag(element, element, {
      getPosition: () => ({ x: parseFloat(element.style.left), y: parseFloat(element.style.top) }),
      setPosition: (x, y) => {
        const item = state.positions.get(nodeId);
        item.x = x; item.y = y;
        setModulePagePosition(moduleId, nodeId, x, y);
      },
      bounds: () => ({ w: 2200, h: 1600 }),
      onMove: refreshModuleEdges,
      onEnd: () => { persistOverride(); updateModuleWorldSize(moduleId); },
    });
  }

  function setGraphChromeVisible(visible) {
    const zoombar = document.querySelector(".zoombar");
    if (zoombar) zoombar.style.display = visible ? "" : "none";
    legend.style.display = visible ? "" : "none";
  }

  function methodCallList(entries, emptyText) {
    if (!entries || !entries.length) {
      return `<div class="method-call-empty">${escapeHtml(emptyText)}</div>`;
    }
    return entries.map(entry => {
      const name = entry.qualifiedName || entry.name || entry.calleeText || "unknown";
      const meta = `${entry.file || ""}:${entry.line || "—"}`;
      const clickable = Boolean(entry.functionId && functionDetailById.has(entry.functionId));
      const content = `<span class="method-call-name">${escapeHtml(name)}</span>
        <span class="method-call-meta">${escapeHtml(meta)}</span>
        <span class="method-call-kind">${entry.polymorphic ? `polymorphic ×${(entry.candidates || []).length}` : entry.resolved === false ? (entry.external ? "external" : "unresolved") : "detail ↗"}</span>`;
      return clickable
        ? `<button class="method-call-item" type="button" data-goto-method="${escapeHtml(entry.functionId)}">${content}</button>`
        : `<div class="method-call-item is-static">${content}</div>`;
    }).join("");
  }

  function renderMethodPage(moduleId, functionId) {
    const detail = functionDetailById.get(functionId);
    if (!detail) {
      navigate({ kind: "module", moduleId }, false);
      return;
    }
    state.pageKind = "method";
    state.moduleId = moduleId;
    state.functionId = functionId;
    viewport.classList.add("is-light");
    viewport.classList.add("is-detail");
    updateChrome("method");
    setGraphChromeVisible(false);
    if (moduleContracts) {
      moduleContracts.innerHTML = "";
      moduleContracts.classList.remove("is-visible");
    }

    const source = detail.source || {};
    const sourceStart = Number(source.startLine || detail.line || 1);
    const calleeLines = new Set(
      (detail.callees || []).map(item => Number(item.line)).filter(line => Number.isFinite(line))
    );
    const sourceRows = String(source.text || "").split("\n").map((line, index) => {
      const lineNumber = sourceStart + index;
      const isCall = calleeLines.has(lineNumber);
      return `<div class="method-source-line${isCall ? " is-call-site" : ""}">
        <span class="method-source-ln">${lineNumber}</span>
        <span class="method-source-code">${escapeHtml(line || " ")}</span>
        ${isCall ? `<span class="method-source-call">call</span>` : ""}
      </div>`;
    }).join("");

    const ownerClass = detail.ownerClassId
      ? (moduleGraphById.get(detail.moduleId)?.nodes || []).find(node => node.id === detail.ownerClassId)
      : null;
    const module = projectModuleById.get(detail.moduleId);
    const providerRole = detail.providerRole || ownerClass?.providerRole || "";
    const badges = [
      detail.methodKind || "function",
      providerRole ? `role:${providerRole}` : "",
      detail.visibility || "public",
      `api:${detail.apiExposure || "public"}`,
      detail.apiExposureSource ? `source:${detail.apiExposureSource}` : "",
      detail.isAsync ? "async" : "",
      detail.isAbstract ? "abstract" : "",
      detail.overrideOfFunctionId ? "override" : "",
      Number(detail.polymorphicCallerCount || 0) ? `poly-callers:${detail.polymorphicCallerCount}` : "",
    ].filter(Boolean);

    world.innerHTML = `<div class="method-page">
      <header class="method-page-head">
        <div class="eyebrow">Method detail</div>
        <h1 class="method-page-title">${escapeHtml(detail.name)}<span>()</span></h1>
        <div class="method-signature">${escapeHtml(detail.signature || "")}</div>
        <div class="method-badges">${badges.map(item => `<span class="method-badge">${escapeHtml(item)}</span>`).join("")}</div>
        <div class="method-location">${escapeHtml(detail.file || "")}:${detail.line || "—"}${ownerClass ? ` · ${escapeHtml(ownerClass.name)}` : ""}${module ? ` · ${escapeHtml(module.name)}` : ""}</div>
      </header>
      <div class="method-page-grid">
        <section class="method-source-panel">
          <div class="method-panel-heading"><span>Source</span><em>${escapeHtml(source.language || "python")} · ${source.startLine || detail.line}-${source.endLine || detail.endLine}${source.truncated ? " · truncated" : ""}</em></div>
          <div class="method-source">${sourceRows || `<div class="method-call-empty">源码不可用</div>`}</div>
        </section>
        <aside class="method-calls-panel">
          <section>
            <div class="method-panel-heading"><span>Callers</span><em>${detail.callerCount || 0}</em></div>
            ${methodCallList(detail.callers || [], "暂无调用者")}
          </section>
          <section>
            <div class="method-panel-heading"><span>Callees</span><em>${detail.calleeCount || 0}</em></div>
            ${methodCallList(detail.callees || [], "暂无被调用者")}
          </section>
          ${(detail.polymorphicCallers || []).length ? `<section>
            <div class="method-panel-heading"><span>Polymorphic callers</span><em>${detail.polymorphicCallerCount || 0}</em></div>
            ${polymorphicCallList(detail.polymorphicCallers, "暂无多态调用者")}
          </section>` : ""}
          ${(detail.polymorphicCallees || []).length ? `<section>
            <div class="method-panel-heading"><span>Polymorphic callees</span><em>${detail.polymorphicCalleeCount || 0}</em></div>
            ${polymorphicCallList(detail.polymorphicCallees, "暂无多态候选")}
          </section>` : ""}
        </aside>
      </div>
    </div>`;
    world.style.width = "100%";
    world.style.height = "100%";
    world.classList.remove("page-enter");
    state.scale = 1;
    state.x = 0;
    state.y = 0;
    applyTransform();

    const ownerLine = ownerClass
      ? `<div class="source-line">owner: ${escapeHtml(ownerClass.qualifiedName || ownerClass.name)}</div>`
      : "";
    detailScroll.innerHTML = `<div class="eyebrow">Semantic contract</div>
      <h2 class="detail-name" style="font-family:var(--mono);font-size:15px">${escapeHtml(detail.qualifiedName)}</h2>
      <div class="detail-note">${escapeHtml(detail.note || "暂无函数备注")}</div>
      <div class="port-detail"><span>API <b>${escapeHtml(detail.apiExposure || "public")}</b></span><span>来源 <b>${escapeHtml(detail.apiExposureSource || "naming")}</b></span><span>返回 <b>${escapeHtml(detail.returns || "—")}</b></span><span>异常 <b>${escapeHtml((detail.raises || []).join(" / ") || "—")}</b></span></div>
      ${ownerLine}
      ${detail.overrideOfFunctionId ? `<div class="source-line">override of <code>${escapeHtml(detail.overrideOfFunctionId)}</code></div>` : ""}
      ${(detail.overriddenByFunctionIds || []).length ? `<div class="source-line">overridden by ${detail.overriddenByFunctionIds.map(id => `<code>${escapeHtml(id)}</code>`).join(" ")}</div>` : ""}
      <div class="source-line">${escapeHtml(detail.file)}:${detail.line}</div>
      ${annotationBlock(detail.id, detail.sourceHash)}`;

    world.querySelectorAll("[data-goto-method]").forEach(button => {
      button.addEventListener("click", () => {
        const target = functionDetailById.get(button.dataset.gotoMethod);
        if (target) navigate({ kind: "function", moduleId: target.moduleId, functionId: target.id });
      });
    });
  }

  function renderRoute() {
    state.selectedUid = null;
    state.hoveredUid = null;
    state.search = "";
    searchInput.value = "";
    const route = parseRoute();
    state.route = route;
    if (route.kind === "function") renderMethodPage(route.moduleId, route.functionId);
    else if (route.kind === "module") renderModulePage(route.moduleId);
    else renderProjectPage();
  }

  function applySearch() {
    const query = state.search.trim().toLowerCase();
    if (!query || state.pageKind === "method") {
      world.querySelectorAll(".node-card, .mini-node").forEach(node => node.classList.remove("is-search-dim"));
      world.querySelectorAll(".macro-edge").forEach(edge => edge.classList.remove("is-search-dim"));
      return;
    }
    if (state.pageKind === "project") {
      state.nodes.forEach((node, uid) => {
        if (node.kind !== "module") return;
        const graph = moduleGraphById.get(uid);
        const haystack = [
          node.name, node.note,
          ...(graph?.nodes || []).flatMap(item => {
            if (item.kind === "class") return [item.name, item.note, ...(item.methods || []).flatMap(method => [method.name, method.note])];
            if (item.kind === "function") return [item.name, item.note];
            return [];
          }),
          ...(graph?.providedApis || []).flatMap(api => [api.display, api.providerName, api.signature, api.note]),
        ].join(" ").toLowerCase();
        world.querySelector(`.module-node[data-uid="${cssEscape(uid)}"]`)?.classList.toggle("is-search-dim", !haystack.includes(query));
      });
    } else if (state.pageKind === "module") {
      state.nodes.forEach((node, uid) => {
        if (node.flowRole) {
          const haystack = [node.label, node.note, node.providerName, node.moduleName, node.capabilityKind, node.expression]
            .filter(Boolean).join(" ").toLowerCase();
          world.querySelector(`.main-flow-node[data-uid="${cssEscape(uid)}"]`)?.classList.toggle("is-search-dim", !haystack.includes(query));
          return;
        }
        if (node.kind !== "function" && node.kind !== "class") return;
        const haystack = node.kind === "class"
          ? [node.name, node.note, ...(node.providedApis || []).flatMap(api => [api.display, api.kind, api.signature])].join(" ").toLowerCase()
          : [node.name, node.note, node.apiExposure].join(" ").toLowerCase();
        const selector = node.kind === "class" ? ".class-node" : ".function-node";
        world.querySelector(`${selector}[data-uid="${cssEscape(uid)}"]`)?.classList.toggle("is-search-dim", !haystack.includes(query));
      });
    }
  }

  // Global controls.
  relationModeBtn.addEventListener("click", () => {
    state.showProjectRelations = !state.showProjectRelations;
    if (state.pageKind === "project") renderProjectPage();
    else updateChrome(state.pageKind);
  });
  $("saveBtn").addEventListener("click", () => { persistOverride(); showToast("布局已保存到浏览器"); });
  $("resetBtn").addEventListener("click", () => { resetOverride(); renderRoute(); showToast("已恢复默认布局"); });
  $("fitBtn").addEventListener("click", () => fitView());
  $("zoomIn").addEventListener("click", () => zoomAt(1.16));
  $("zoomOut").addEventListener("click", () => zoomAt(1 / 1.16));
  singleModeBtn.addEventListener("click", () => {
    state.singleModule = !state.singleModule;
    override.project.singleModule = state.singleModule;
    singleModeBtn.setAttribute("aria-pressed", String(state.singleModule));
    persistOverride();
    if (state.pageKind === "project") renderProjectPage();
    else navigate({ kind: "project" });
  });
  $("exportBtn").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(override, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "layout-overrides.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 500);
    showToast("布局覆盖已导出");
  });
  $("importBtn").addEventListener("click", () => $("importFile").click());
  $("importFile").addEventListener("change", event => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        override = normalizeOverride(JSON.parse(String(reader.result)));
        state.singleModule = Boolean(override.project.singleModule);
        persistOverride();
        renderRoute();
        showToast("布局覆盖已导入");
      } catch (error) {
        showToast("导入失败：不是有效的布局 JSON");
      }
    };
    reader.readAsText(file);
    event.target.value = "";
  });
  backBtn.addEventListener("click", () => {
    if (location.hash && location.hash !== "#/project") history.back();
    else navigate({ kind: "project" }, false);
  });
  searchInput.addEventListener("input", () => { state.search = searchInput.value; applySearch(); });
  window.addEventListener("hashchange", renderRoute);

  viewport.addEventListener("wheel", event => {
    if (state.pageKind === "method" || event.target.closest(".detail-panel")) return;
    event.preventDefault();
    zoomAt(Math.exp(-event.deltaY * .0015), event.clientX, event.clientY);
  }, { passive: false });

  let panning = false;
  let panStart = null;
  viewport.addEventListener("pointerdown", event => {
    if (state.pageKind === "method") return;
    if (event.button !== 0 || event.target.closest(".node-card, button, input, .detail-panel")) return;
    panning = true;
    panStart = { x: event.clientX - state.x, y: event.clientY - state.y };
    viewport.classList.add("is-panning");
    viewport.setPointerCapture(event.pointerId);
  });
  viewport.addEventListener("pointermove", event => {
    if (!panning) return;
    state.x = event.clientX - panStart.x;
    state.y = event.clientY - panStart.y;
    applyTransform();
  });
  const endPan = () => { panning = false; viewport.classList.remove("is-panning"); };
  viewport.addEventListener("pointerup", endPan);
  viewport.addEventListener("pointercancel", endPan);
  viewport.addEventListener("dblclick", event => {
    if (state.pageKind === "method") return;
    if (event.target.closest(".node-card, button, input")) return;
    fitView();
  });

  window.addEventListener("keydown", event => {
    if (event.target.matches("input, textarea")) return;
    if (state.pageKind !== "method" && event.key === "0") fitView();
    if (state.pageKind !== "method" && (event.key === "+" || event.key === "=")) zoomAt(1.16);
    if (state.pageKind !== "method" && event.key === "-") zoomAt(1 / 1.16);
    if (event.key === "Escape") {
      state.selectedUid = null;
      clearSelection();
    }
  });

  projectNameEl.textContent = DATA.project.name;
  projectLanguageEl.textContent = DATA.project.language === "python" ? "Python" : DATA.project.language;
  state.singleModule = Boolean(override.project.singleModule);
  singleModeBtn.setAttribute("aria-pressed", String(state.singleModule));
  if (!location.hash) history.replaceState({ kind: "project" }, "", "#/project");
  applyTransform();
  renderRoute();
})();
