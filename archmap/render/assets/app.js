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
  function visibleProjectModules() {
    return (projectGraph.modules || []).filter(
      module => module.capabilitySurface?.hasProviders !== false
    );
  }
  const STORAGE_KEY = "archmap-v3-layout-v1";
  const OVERRIDE_VERSION = 1;
  // Bump whenever default card geometry or layout namespaces change.  Old
  // saved coordinates are ignored instead of being applied to the new grid.
  const GEOMETRY_VERSION = 4;
  const DETAIL_PANEL_STORAGE_KEY = "archmap-detail-panel-width-v1";
  const DETAIL_PANEL_DEFAULT_WIDTH = 420;
  const DETAIL_PANEL_MIN_WIDTH = 360;
  const DETAIL_PANEL_MAX_WIDTH = 720;

  const $ = id => document.getElementById(id);
  const viewport = $("viewport");
  const world = $("world");
  const detailPanel = $("detailPanel");
  const detailResizer = $("detailResizer");
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
  const moduleContracts = $("moduleContracts");
  const flowPicker = $("flowPicker");
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
    pendingSelectUid: null,
    suppressClickUntil: 0,
    pageKind: "project",
    pageEdges: [],
    nodes: new Map(),
    sizes: new Map(),
    moduleId: null,
    functionId: null,
    executionFlowId: null,
    executionScopeId: null,
    executionEdgeLayouts: {},
    executionEdgeLabels: new Map(),
    moduleContractsExpanded: false,
  };

  let override = loadOverrides();

  function defaultOverride() {
    return {
      version: OVERRIDE_VERSION,
      geometryVersion: GEOMETRY_VERSION,
      project: { nodes: {} },
      modules: {},
      functions: {},
      executions: {},
    };
  }

  function normalizeOverride(value) {
    const base = defaultOverride();
    if (!value || typeof value !== "object") return base;
    if (Number(value.version) !== OVERRIDE_VERSION) return base;
    if (Number(value.geometryVersion) !== GEOMETRY_VERSION) return base;
    base.project.nodes = value.project?.nodes && typeof value.project.nodes === "object" ? value.project.nodes : {};
    base.modules = value.modules && typeof value.modules === "object" ? value.modules : {};
    base.functions = value.functions && typeof value.functions === "object" ? value.functions : {};
    base.executions = value.executions && typeof value.executions === "object" ? value.executions : {};
    return base;
  }

  function loadOverrides() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return defaultOverride();
      const stored = JSON.parse(raw);
      const normalized = normalizeOverride(stored);
      // Remove stale coordinates so they cannot be reapplied on every load.
      if (Number(stored?.version) !== OVERRIDE_VERSION || Number(stored?.geometryVersion) !== GEOMETRY_VERSION) {
        localStorage.removeItem(STORAGE_KEY);
      }
      return normalized;
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
    saveState.textContent = "布局已重置";
  }

  function detailPanelWidthBounds() {
    const viewportMax = Math.max(
      DETAIL_PANEL_MIN_WIDTH,
      Math.floor(window.innerWidth * 0.55)
    );
    return {
      min: DETAIL_PANEL_MIN_WIDTH,
      max: Math.max(DETAIL_PANEL_MIN_WIDTH, Math.min(DETAIL_PANEL_MAX_WIDTH, viewportMax)),
    };
  }

  function clampDetailPanelWidth(value) {
    const bounds = detailPanelWidthBounds();
    const parsed = Number(value);
    const fallback = DETAIL_PANEL_DEFAULT_WIDTH;
    return Math.max(bounds.min, Math.min(bounds.max, Number.isFinite(parsed) ? parsed : fallback));
  }

  function loadDetailPanelWidth() {
    try {
      const stored = localStorage.getItem(DETAIL_PANEL_STORAGE_KEY);
      return clampDetailPanelWidth(stored === null ? DETAIL_PANEL_DEFAULT_WIDTH : stored);
    } catch (error) {
      return clampDetailPanelWidth(DETAIL_PANEL_DEFAULT_WIDTH);
    }
  }

  let detailPanelFitFrame = 0;
  function scheduleDetailPanelRefit() {
    if (detailPanelFitFrame) cancelAnimationFrame(detailPanelFitFrame);
    detailPanelFitFrame = requestAnimationFrame(() => {
      detailPanelFitFrame = 0;
      fitView(false);
    });
  }

  function applyDetailPanelWidth(value, options = {}) {
    const width = clampDetailPanelWidth(value);
    detailPanel.style.width = `${width}px`;
    detailPanel.style.flexBasis = `${width}px`;
    detailPanel.style.setProperty("--detail-panel-width", `${width}px`);
    if (options.persist) {
      try {
        localStorage.setItem(DETAIL_PANEL_STORAGE_KEY, String(width));
      } catch (error) {
        // Browser storage may be unavailable; resizing still works for this session.
      }
    }
    if (options.refit !== false) scheduleDetailPanelRefit();
    return width;
  }

  applyDetailPanelWidth(loadDetailPanelWidth(), { refit: false });

  let detailResizeDrag = null;
  detailResizer.addEventListener("pointerdown", event => {
    if (event.button !== 0 || window.innerWidth <= 860) return;
    event.preventDefault();
    event.stopPropagation();
    const width = detailPanel.getBoundingClientRect().width;
    detailResizeDrag = { pointerId: event.pointerId, startX: event.clientX, startWidth: width };
    try {
      detailResizer.setPointerCapture(event.pointerId);
    } catch (error) {
      // Synthetic pointer events may not own a native capture target.
    }
    document.body.classList.add("is-resizing-detail");
  });
  detailResizer.addEventListener("pointermove", event => {
    if (!detailResizeDrag || event.pointerId !== detailResizeDrag.pointerId) return;
    const next = detailResizeDrag.startWidth + (detailResizeDrag.startX - event.clientX);
    applyDetailPanelWidth(next, { persist: false, refit: true });
  });
  const finishDetailResize = event => {
    if (!detailResizeDrag) return;
    if (event?.pointerId !== undefined && event.pointerId !== detailResizeDrag.pointerId) return;
    const width = detailPanel.getBoundingClientRect().width;
    detailResizeDrag = null;
    document.body.classList.remove("is-resizing-detail");
    applyDetailPanelWidth(width, { persist: true, refit: true });
  };
  detailResizer.addEventListener("pointerup", finishDetailResize);
  detailResizer.addEventListener("pointercancel", finishDetailResize);
  detailResizer.addEventListener("dblclick", event => {
    event.preventDefault();
    applyDetailPanelWidth(DETAIL_PANEL_DEFAULT_WIDTH, { persist: true, refit: true });
  });
  detailResizer.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "Home"].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "Home") {
      applyDetailPanelWidth(DETAIL_PANEL_DEFAULT_WIDTH, { persist: true, refit: true });
      return;
    }
    const delta = event.key === "ArrowLeft" ? -16 : 16;
    applyDetailPanelWidth(detailPanel.getBoundingClientRect().width + delta, {
      persist: true,
      refit: true,
    });
  });
  window.addEventListener("resize", () => {
    applyDetailPanelWidth(detailPanel.getBoundingClientRect().width, {
      persist: false,
      refit: true,
    });
  });

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
    if (parts[0] === "flow") {
      if (parts[2] === "scope" && parts[3]) {
        return { kind: "scope", flowId: parts[1] || null, nodeId: parts[3] };
      }
      if (parts[2] === "dispatch" && parts[3]) {
        return {
          kind: "dispatch",
          flowId: parts[1] || null,
          nodeId: parts[3],
          candidateScopeId: parts[4] === "candidate" && parts[5] ? parts[5] : null,
        };
      }
      return { kind: "flow", flowId: parts[1] || null };
    }
    return { kind: "project" };
  }

  function routeHash(route) {
    if (route.kind === "module") return `#/module/${encodeURIComponent(route.moduleId)}`;
    if (route.kind === "function") {
      return `#/module/${encodeURIComponent(route.moduleId)}/function/${encodeURIComponent(route.functionId)}`;
    }
    if (route.kind === "flow") {
      return route.flowId ? `#/flow/${encodeURIComponent(route.flowId)}` : "#/flow";
    }
    if (route.kind === "scope") {
      return `#/flow/${encodeURIComponent(route.flowId)}/scope/${encodeURIComponent(route.nodeId)}`;
    }
    if (route.kind === "dispatch") {
      const base = `#/flow/${encodeURIComponent(route.flowId)}/dispatch/${encodeURIComponent(route.nodeId)}`;
      return route.candidateScopeId
        ? `${base}/candidate/${encodeURIComponent(route.candidateScopeId)}`
        : base;
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
    const edges = [...world.querySelectorAll(".graph-edge, .macro-edge, .execution-edge")];
    const focusUid = state.selectedUid || state.hoveredUid;
    nodes.forEach(node => node.classList.toggle("is-selected", node.dataset.uid === focusUid));
    if (!focusUid) {
      nodes.forEach(node => node.classList.remove("is-dim", "is-highlight"));
      edges.forEach(edge => edge.classList.remove("is-dim", "is-highlight"));
      return;
    }
    // Capability cards are siblings, not a dependency neighbourhood.
    if (state.pageKind === "project") {
      nodes.forEach(node => node.classList.remove("is-dim", "is-highlight"));
      edges.forEach(edge => edge.classList.remove("is-dim", "is-highlight"));
      return;
    }
    const isFlowPage = Boolean(world.querySelector(".execution-node"));
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
      if (isFlowPage) edge.classList.remove("is-dim");
      else edge.classList.toggle("is-dim", !highlighted);
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

  function contentBounds() {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    if (state.positions) {
      state.positions.forEach((position, nodeId) => {
        const size = state.sizes?.get(nodeId) || { w: position.w || 190, h: position.h || 96 };
        const x = Number(position.x) || 0;
        const y = Number(position.y) || 0;
        const w = Number(size.w) || 190;
        const h = Number(size.h) || 96;
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x + w);
        maxY = Math.max(maxY, y + h);
      });
    }
    if (!Number.isFinite(minX)) {
      return { minX: 0, minY: 0, maxX: 900, maxY: 640, width: 900, height: 640 };
    }
    return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
  }

  function updateWorldExtent(minWidth = 900, minHeight = 640, pad = 90) {
    const bounds = contentBounds();
    const width = Math.max(minWidth, bounds.maxX + pad);
    const height = Math.max(minHeight, bounds.maxY + pad);
    const svgX = bounds.minX - pad;
    const svgY = bounds.minY - pad;
    const svgWidth = Math.max(1, bounds.width + pad * 2);
    const svgHeight = Math.max(1, bounds.height + pad * 2);
    world.style.width = `${width}px`;
    world.style.height = `${height}px`;
    const svg = world.querySelector(".world-edges");
    if (svg) {
      svg.style.left = `${svgX}px`;
      svg.style.top = `${svgY}px`;
      svg.setAttribute("width", String(svgWidth));
      svg.setAttribute("height", String(svgHeight));
      svg.setAttribute("viewBox", `${svgX} ${svgY} ${svgWidth} ${svgHeight}`);
    }
    return { width, height, ...bounds };
  }

  function overlayTopPadding(fallback = 122) {
    const panels = [moduleContracts, flowPicker].filter(panel => panel?.classList.contains("is-visible"));
    if (!panels.length) return fallback;
    const viewportRect = viewport.getBoundingClientRect();
    const bottom = Math.max(...panels.map(panel => panel.getBoundingClientRect().bottom - viewportRect.top));
    return Math.max(fallback, bottom + 26);
  }

  function fitView(animate = false) {
    const bounds = contentBounds();
    const rect = viewport.getBoundingClientRect();
    const padX = 58;
    const basePadTop = state.pageKind === "module" ? 122 : state.pageKind === "method" ? 26 : state.pageKind === "flow" ? 72 : 64;
    const padTop = overlayTopPadding(basePadTop);
    const padBottom = 46;
    const availableW = rect.width - padX * 2;
    const availableH = rect.height - padTop - padBottom;
    const scale = Math.min(
      availableW / Math.max(1, bounds.width),
      availableH / Math.max(1, bounds.height),
      1
    );
    const minScale = state.pageKind === "method" ? .5 : .2;
    state.scale = Math.max(minScale, Math.min(1, scale));
    state.x = bounds.width * state.scale <= availableW
      ? (rect.width - bounds.width * state.scale) / 2 - bounds.minX * state.scale
      : padX - bounds.minX * state.scale;
    state.y = bounds.height * state.scale <= availableH
      ? padTop + (availableH - bounds.height * state.scale) / 2 - bounds.minY * state.scale
      : padTop - bounds.minY * state.scale;
    applyTransform();
  }

  function focusExecutionStart(flow) {
    if (!flow) return;
    const incoming = new Set((flow.edges || []).map(edge => edge.to));
    const entry = (flow.nodes || []).find(node => !incoming.has(node.id)) || flow.nodes[0];
    const pos = entry ? state.positions.get(entry.id) : null;
    if (!pos) return;
    const rect = viewport.getBoundingClientRect();
    const padTop = overlayTopPadding(148);
    state.scale = Math.max(.78, Math.min(1, state.scale));
    state.x = 72 - pos.x * state.scale;
    state.y = padTop - pos.y * state.scale;
    // Keep a little breathing room without hiding the whole graph offscreen.
    if (rect.width > 900) state.x += 18;
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
      const x = origin.x + dx;
      const y = origin.y + dy;
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
      main: "Main",
      service: "Service",
      adapter: "Adapter",
      test: "Test",
      other: "Module",
    }[role] || "Module");
  }

  function providerRoleLabel(role) {
    return ({
      config: "Config",
      model: "Model",
      manager: "Manager",
      entry: "Entry",
      adapter: "Adapter",
      component: "Component",
      contract: "Contract",
      utility: "Utility",
    }[role] || "Provider");
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

  function apiKindLabel(kind) {
    return ({
      method: "方法",
      function: "函数",
      context_manager: "上下文管理器",
      async_context_manager: "异步上下文管理器",
      callable: "可调用对象",
      iterable: "可迭代对象",
    }[kind] || kind || "接口");
  }

  function providerKindLabel(kind) {
    return ({
      class: "类",
      function: "函数",
      provider: "提供者",
    }[kind] || kind || "提供者");
  }

  function functionNote(functionId) {
    const detail = functionDetailById.get(functionId);
    return String(detail?.note || "").trim();
  }

  function apiHumanNote(api) {
    const direct = String(api?.note || "").trim();
    if (direct) return direct;
    return api?.functionId ? functionNote(api.functionId) : "";
  }

  function humanNoteLine(note) {
    return `<span class="detail-api-note">${escapeHtml(truncate(note || "暂无人类注释", 180))}</span>`;
  }

  function apiExposureBadge(api) {
    if (!api) return "";
    if (api.inherited) return `继承 · ${api.declaredInProviderId ? String(api.declaredInProviderId).split(".").pop() : "基类"}`;
    if (api.overridesCapabilityId) return "覆写";
    if (api.isEntry) return "入口";
    if (api.exposureSource === "protocol") return "协议";
    if (api.exposureSource === "naming") return "推断";
    return api.exposure === "internal" ? "内部" : "公开";
  }

  function typeRelationLabel(kind) {
    return ({
      inherits: "inherits",
      implements: "implements",
      instantiates: "instantiates",
      uses: "uses",
      aggregates: "aggregates",
      composes: "composes",
    }[kind] || kind || "relation");
  }

  function surfaceKindLabel(kind) {
    return ({
      cli_input: "CLI 输入",
      cli_output: "CLI 输出",
      file_io: "文件 IO",
      network_endpoint: "网络监听",
      network_client: "网络连接",
      keyboard_event: "键盘事件",
      http_endpoint: "HTTP",
      tui_menu: "TUI 菜单",
      ui_component: "UI 组件",
    }[kind] || kind || "surface");
  }

  function userSurfaceChips(surfaces, limit = 8) {
    const items = (surfaces || []).slice(0, limit);
    if (!items.length) return `<span class="contracts-empty">暂无用户交互面</span>`;
    return items.map(surface => `<span class="user-surface-chip kind-${escapeHtml(surface.kind)}" title="${escapeHtml(surface.display || surface.id)}">
      <b>${escapeHtml(surfaceKindLabel(surface.kind))}</b><span>${escapeHtml(surface.moduleId || "")}</span>
    </span>`).join("") + ((surfaces || []).length > limit ? `<span class="user-surface-chip more">+${surfaces.length - limit}</span>` : "");
  }

  function structuralRelationsBlock(node, graph) {
    const relations = (graph?.typeRelations || []).filter(relation =>
      relation.fromClassId === node.id || relation.toClassId === node.id
    );
    if (!relations.length) return `<div class="class-method-empty">暂无结构关系</div>`;
    const short = id => String(id || "").split(".").pop();
    return `<div class="structural-relations">${relations.map(relation => `<div class="structural-relation-row">
      <span>${escapeHtml(short(relation.fromClassId))}</span><em>${escapeHtml(typeRelationLabel(relation.kind))}</em><span>${escapeHtml(short(relation.toClassId))}</span>
      <i>${escapeHtml(relation.source || "")}</i>
    </div>`).join("")}</div>`;
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
      <div class="hierarchy-row"><span>基类</span><div>${list(bases, "—")}</div></div>
      <div class="hierarchy-row"><span>子类</span><div>${list(subclasses, "—")}</div></div>
      ${unresolved.length ? `<div class="hierarchy-row is-unresolved"><span>未解析</span><div>${unresolved.map(item => `<code>${escapeHtml(item)}</code>`).join("")}</div></div>` : ""}
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
        <span class="method-call-meta">${escapeHtml(entry.file || "")}:${entry.line || "—"} · ${candidates.length} 个候选</span>
        <span class="method-call-kind">多态</span>
        ${targetNames.length ? `<span class="method-call-candidates">${targetNames.map(name => `<code>${escapeHtml(name)}</code>`).join("")}</span>` : ""}
      </div>`;
    }).join("");
  }

  function dispatchCandidateList(node) {
    const candidates = node?.candidates || [];
    if (!candidates.length) {
      return `<div class="method-call-empty">未解析出候选；请检查 dispatchHints、argparse 注册或静态分发表。</div>`;
    }
    const flow = currentExecutionFlow();
    const group = (flow?.dispatchGroups || []).find(item => item.parentNodeId === node.id);
    const scopeByRoot = new Map((group?.scopes || []).map(scope => [scope.rootFunctionId, scope]));
    return `<div class="method-call-list">${candidates.map(candidateId => {
      const detail = functionDetailById.get(candidateId);
      const name = detail?.qualifiedName || detail?.name || candidateId;
      const candidateScope = scopeByRoot.get(candidateId);
      const actionAttr = candidateScope
        ? `data-open-dispatch-candidate="${escapeHtml(candidateScope.id)}" data-dispatch-node="${escapeHtml(node.id)}"`
        : `data-open-exec-candidate="${escapeHtml(candidateId)}"`;
      return `<button class="detail-api-row" type="button" ${actionAttr}>
        <span class="detail-api-kind">${candidateScope ? "旅程" : "候选"}</span>
        <span class="detail-api-main">
          <span class="detail-api-name">${escapeHtml(name)}</span>
          ${humanNoteLine(detail?.note || "")}
          <span class="detail-api-meta">${escapeHtml(detail?.file || "")}:${escapeHtml(detail?.line || "—")}</span>
        </span>
        <span class="detail-api-badge">${candidateScope ? "打开" : "源码"}</span>
      </button>`;
    }).join("")}</div>`;
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
        <span class="detail-api-kind">${escapeHtml(apiKindLabel(api.kind))}</span>
        <span class="detail-api-main">
          <span class="detail-api-name">${escapeHtml(apiDisplayName(api))}</span>
          ${humanNoteLine(apiHumanNote(api))}
        </span>
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
      <div class="api-role-heading">${providerRoleBadge(role)}<span>${items.length} 个提供者</span></div>
      ${items.map(provider => `<div class="api-provider">
        <div class="api-provider-head">
          <span class="api-provider-kind">${escapeHtml(providerKindLabel(provider.providerKind))}</span>
          <b>${escapeHtml(provider.providerName || provider.providerId)}</b>
          <em>${provider.apiCount || (provider.apis || []).length} 个接口${Number(provider.inheritedApiCount || 0) ? ` · 继承 ${Number(provider.inheritedApiCount)}` : ""}</em>
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
      const executionFlow = currentExecutionFlow();
      const flowCount = (projectGraph.executionFlows || []).length;
      detailScroll.innerHTML = `<div class="eyebrow">项目组成图</div>
        <h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(DATA.project.name)}</h2>
        <div class="detail-note">项目页提供独立主流程入口与模块能力卡片。流程与模块能力分开浏览，互不混用同一页面。</div>
        <div class="port-detail"><span>模块 <b>${visibleProjectModules().length}</b></span><span>执行流 <b>${flowCount}</b></span><span>类型关系 <b>${(projectGraph.typeRelations || []).length}</b></span><span>执行流节点 <b>${executionFlow?.nodeCount || 0}</b></span></div>
        ${annotationBlock(DATA.project.name)}
        <div class="empty-hint">打开主流程入口查看执行流；双击模块卡片查看能力视图。</div>`;
      return;
    }
    if (state.route.kind === "flow") {
      const flow = currentExecutionFlow();
      if (!flow) {
        detailScroll.innerHTML = `<div class="eyebrow">主执行流</div><h2 class="detail-name">暂无可解析主流程</h2><div class="detail-note">请检查 entrypoints 或 executionEntrypoints 配置。</div>`;
        return;
      }
      const scopeCount = (flow.scopes || []).length;
      detailScroll.innerHTML = `<div class="eyebrow">主执行流</div>
        <h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(flow.name || "主流程")}</h2>
        <div class="detail-note">入口函数的静态控制骨架。带 L1 标记的节点可打开一级接口下钻视图；更深实现进入方法详情。</div>
        <div class="port-detail"><span>入口 <b>${escapeHtml(flow.entrypointId || "—")}</b></span><span>节点 <b>${(flow.nodes || []).length}</b></span><span>边 <b>${(flow.edges || []).length}</b></span><span>接口 scope <b>${scopeCount}</b></span></div>
        ${annotationBlock(flow.entrypointId || flow.id)}
        <div class="empty-hint">单节点点击查看接口摘要；L1 按钮进入一级接口流程。</div>`;
      return;
    }
    if (state.route.kind === "scope") {
      const flow = currentExecutionFlow();
      const scope = currentExecutionScope();
      detailScroll.innerHTML = `<div class="eyebrow">一级接口下钻 · L1</div>
        <h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(scope?.name || "接口下钻")}</h2>
        <div class="detail-note">目标函数的一级接口骨架。只展示直接外部能力接口与必要控制结构，不递归展开内部实现。</div>
        <div class="port-detail"><span>来源主流程 <b>${escapeHtml(flow?.name || "—")}</b></span><span>L1 来源 <b>${escapeHtml(drilldownReasonLabel(scope?.reason))}</b></span><span>节点 <b>${Number(scope?.nodeCount || 0)}</b></span><span>边 <b>${Number(scope?.edgeCount || 0)}</b></span><span>外部接口 <b>${(scope?.interfaceSummary || []).length}</b></span></div>
        ${(scope?.interfaceSummary || []).length ? `<div class="class-method-section"><div class="class-method-heading">外部接口</div><div class="exec-interface-list">${scope.interfaceSummary.map(item => `<span class="exec-interface-chip"><b>${escapeHtml(item.moduleName || item.moduleId)}</b>${escapeHtml(item.label)}${Number(item.callCount || 1) > 1 ? ` ×${Number(item.callCount)}` : ""}</span>`).join("")}</div></div>` : ""}
        ${scope?.truncated ? `<div class="llm-stale">该 scope 已触发节点预算收缩，详情以源码与方法详情为准。</div>` : ""}
        <div class="empty-hint">点击节点查看语义；双击打开方法详情 / 源码。</div>`;
      return;
    }
    if (state.route.kind === "dispatch") {
      const flow = currentExecutionFlow();
      const group = currentExecutionDispatchGroup();
      const scope = currentExecutionScope();
      if (!group || !scope) {
        detailScroll.innerHTML = `<div class="eyebrow">分发候选旅程</div><h2 class="detail-name">暂无可解析候选旅程</h2><div class="detail-note">dispatch 节点存在，但没有可用于下钻的候选 scope。</div>`;
        return;
      }
      const truncated = group.truncated || scope.truncated;
      detailScroll.innerHTML = `<div class="eyebrow">分发候选旅程</div>
        <h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(scope.name || "候选旅程")}</h2>
        <div class="detail-note">dispatch 节点保持原子边界；当前候选以一级 callable scope 独立展开，不在主流程画布生成候选控制边。</div>
        <div class="port-detail"><span>表达式 <b>${escapeHtml(group.expression || "—")}</b></span><span>来源 <b>${escapeHtml(dispatchSourceLabel(group.candidateSource))}</b></span><span>候选 <b>${Number(group.candidateCount || 0)}</b></span><span>已生成 <b>${(group.scopes || []).length}</b></span><span>节点 <b>${Number(scope.nodeCount || 0)}</b></span></div>
        ${group.candidateSetComplete ? "" : `<div class="llm-stale">候选集合未声明完整；当前旅程只覆盖已知候选，不代表全部运行时路径。</div>`}
        ${truncated ? `<div class="llm-stale">候选旅程触发预算截断，未生成或已收缩的内容不在此 scope 中展开。</div>` : ""}
        ${(scope.interfaceSummary || []).length ? `<div class="class-method-section"><div class="class-method-heading">外部接口</div><div class="exec-interface-list">${scope.interfaceSummary.map(item => `<span class="exec-interface-chip"><b>${escapeHtml(item.moduleName || item.moduleId)}</b>${escapeHtml(item.label)}${Number(item.callCount || 1) > 1 ? ` ×${Number(item.callCount)}` : ""}</span>`).join("")}</div></div>` : ""}
        <div class="empty-hint">使用顶部候选列表切换旅程；双击节点打开方法详情 / 源码。</div>`;
      return;
    }
    if (state.route.kind === "module") {
      const module = moduleGraphById.get(state.route.moduleId);
      if (!module) return;
      const apis = module.providedApis || [];
      const providers = module.apiProviders || [];
      detailScroll.innerHTML = `<div class="detail-head" style="--mc:${module.color}"><div class="detail-color"></div><div>
          <div class="eyebrow">模块能力</div><h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(module.name)}</h2>
          <div class="detail-module">module://${escapeHtml(module.moduleId)} · ${escapeHtml(moduleRoleLabel(module.role))}</div></div></div>
        <div class="detail-note">${escapeHtml(module.note || "暂无模块备注")}</div>
        <div class="port-detail"><span>角色 <b>${escapeHtml(moduleRoleLabel(module.role || "service"))}</b></span><span>Provider <b>${providers.length}</b></span><span>接口 <b>${apis.length}</b></span><span>类型关系 <b>${(module.typeRelations || []).length}</b></span></div>
        <div class="class-method-section"><div class="class-method-heading">模块组成</div>${roleCompositionBlock(module)}</div>
        <div class="class-method-section"><div class="class-method-heading">提供接口</div>${apiProviderList(providers)}</div>
        ${(module.userSurfaces || []).length ? `<div class="class-method-section"><div class="class-method-heading">用户交互面</div><div class="user-surface-track">${userSurfaceChips(module.userSurfaces || [])}</div></div>` : ""}
        ${annotationBlock(module.moduleId)}
        <div class="empty-hint">双击自由函数进入方法详情；类节点右栏展示其提供接口。</div>`;
      bindApiNavigation(detailScroll);
      return;
    }
    const detail = functionDetailById.get(state.route.functionId);
    if (!detail) return;
    const module = projectModuleById.get(detail.moduleId);
    detailScroll.innerHTML = `<div class="detail-head" style="--mc:${module?.color || "#60a5fa"}"><div class="detail-color"></div><div>
        <div class="eyebrow">方法详情</div><h2 class="detail-name">${escapeHtml(detail.name)}</h2>
        <div class="detail-module">${escapeHtml(module?.name || detail.moduleId)} · ${escapeHtml(detail.module)}</div></div></div>
      <div class="detail-note">${escapeHtml(detail.note || "暂无函数备注")}</div>
      <div class="source-line">${escapeHtml(detail.file)}:${detail.line} · ${escapeHtml(detail.signature)}</div>
      ${annotationBlock(detail.id, detail.sourceHash)}
      <div class="empty-hint">左侧查看源码和调用关系；点击调用者/被调用者继续下钻。</div>`;
  }

  function renderSelectionDetail(uid) {
    const macroNode = state.nodes.get(uid);
    if (macroNode) {
      if (macroNode.kind === "flow") {
        detailScroll.innerHTML = `<div class="detail-head" style="--mc:${macroNode.color || "#f59e0b"}"><div class="detail-color"></div><div>
            <div class="eyebrow">项目主流程</div><h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(macroNode.name || "主流程")}</h2>
            <div class="detail-module">${escapeHtml(macroNode.moduleName || macroNode.moduleId || "")}</div></div></div>
          <div class="detail-note">${escapeHtml(macroNode.note || "项目级主流程入口")}</div>
          <div class="port-detail"><span>入口 <b>${escapeHtml(macroNode.entrypointId || "—")}</b></span><span>节点 <b>${Number(macroNode.nodeCount || 0)}</b></span><span>边 <b>${Number(macroNode.edgeCount || 0)}</b></span></div>
          <div class="detail-actions"><button class="detail-action" type="button" data-open-flow-card-detail="${escapeHtml(macroNode.flowId)}">打开主流程 →</button></div>`;
        detailScroll.querySelector("[data-open-flow-card-detail]")?.addEventListener("click", () => {
          navigate({ kind: "flow", flowId: macroNode.flowId });
        });
        return;
      }
      if (macroNode.execution) {
        const module = projectModuleById.get(macroNode.moduleId);
        const targetId = macroNode.targetFunctionId || (
          ["entry", "free_function", "interface", "dispatch"].includes(macroNode.kind) ? macroNode.functionId : null
        );
        const detail = targetId ? functionDetailById.get(targetId) : null;
        const meta = [];
        if (macroNode.condition) meta.push(`条件：${macroNode.condition}`);
        if (macroNode.loopKind) meta.push(`循环类型：${macroNode.loopKind}`);
        if (macroNode.iterable) meta.push(`迭代对象：${macroNode.iterable}`);
        if (macroNode.loopVariable) meta.push(`循环变量：${macroNode.loopVariable}`);
        if (macroNode.mayExit === false) meta.push("静态判断：循环可能不会退出");
        if ((macroNode.cases || []).length) meta.push(`分支：${macroNode.cases.map(item => item.label).join(" / ")}`);
        if (macroNode.kind === "dispatch") {
          meta.push(`候选：${Number(macroNode.candidateCount || 0)} · ${macroNode.candidateSetComplete ? "完整" : "未声明完整"}`);
          meta.push(`来源：${dispatchSourceLabel(macroNode.candidateSource)}`);
          if (macroNode.drilldown?.kind === "dispatch" && macroNode.drilldown?.status === "available") {
            meta.push(`候选旅程：${Number(macroNode.drilldown.candidateScopeCount || 0)}`);
          }
        }
        detailScroll.innerHTML = `<div class="detail-head" style="--mc:${macroNode.color || module?.color || "#60a5fa"}"><div class="detail-color"></div><div>
            <div class="eyebrow">执行流 · ${escapeHtml(executionKindLabel(macroNode.kind))}</div>
            <h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(macroNode.label || macroNode.id)}</h2>
            <div class="detail-module">${escapeHtml(module?.name || macroNode.moduleName || macroNode.moduleId || "")}</div></div></div>
          <div class="detail-note">${escapeHtml(macroNode.note || "主执行流节点")}</div>
          <div class="port-detail"><span>节点类型 <b>${escapeHtml(macroNode.kind)}</b></span><span>模块 <b>${escapeHtml(module?.name || macroNode.moduleId || "—")}</b></span>${macroNode.drilldown?.reason ? `<span>${macroNode.kind === "dispatch" ? "下钻来源" : "L1 来源"} <b>${escapeHtml(drilldownReasonLabel(macroNode.drilldown.reason))}</b></span>` : ""}${macroNode.capabilityKind ? `<span>能力 <b>${escapeHtml(macroNode.capabilityKind)}</b></span>` : ""}${macroNode.usageKind ? `<span>用法 <b>${escapeHtml(macroNode.usageKind)}</b></span>` : ""}</div>
          ${macroNode.kind === "interface" ? `<div class="empty-hint">功能接口是模块暴露的能力边界，不在主流程中展开内部实现；请打开方法详情或模块能力页查看。</div>` : ""}
          ${meta.length ? `<div class="source-line">${meta.map(item => escapeHtml(item)).join("<br>")}</div>` : ""}
          ${executionArmSummaryDetailHtml(macroNode)}
          ${macroNode.kind === "dispatch" ? `<div class="class-method-section"><div class="class-method-heading">分发候选 · ${Number(macroNode.candidateCount || 0)}</div>${dispatchCandidateList(macroNode)}</div>` : ""}
          ${macroNode.kind !== "interface" && (macroNode.drilldown?.interfaceSummary || []).length ? `<div class="class-method-section"><div class="class-method-heading">L1 外部接口 · ${macroNode.drilldown.interfaceSummary.length}</div><div class="exec-interface-list">${macroNode.drilldown.interfaceSummary.map(item => `<span class="exec-interface-chip"><b>${escapeHtml(item.moduleName || item.moduleId)}</b>${escapeHtml(item.label)}${Number(item.callCount || 1) > 1 ? ` ×${Number(item.callCount)}` : ""}</span>`).join("")}</div></div>` : ""}
          ${(macroNode.interfaceHints || []).length ? `<div class="class-method-section"><div class="class-method-heading">Helper 直接触达接口 · ${macroNode.interfaceHints.length}</div><div class="exec-interface-list">${macroNode.interfaceHints.map(item => `<span class="exec-interface-chip"><b>${escapeHtml(item.moduleName || item.moduleId)}</b>${escapeHtml(item.label)}</span>`).join("")}</div></div>` : ""}
          ${detail ? `<div class="source-line">${escapeHtml(detail.file)}:${detail.line} · ${escapeHtml(detail.signature)}</div>` : ""}
          ${annotationBlock(targetId || uid, detail?.sourceHash)}
          <div class="detail-actions">${macroNode.kind === "dispatch" && macroNode.drilldown?.kind === "dispatch" && macroNode.drilldown?.status === "available" ? `<button class="detail-action" type="button" data-open-dispatch-detail="${escapeHtml(uid)}">打开候选旅程</button>` : ""}${macroNode.kind !== "interface" && macroNode.kind !== "dispatch" && macroNode.drilldown?.status === "available" ? `<button class="detail-action" type="button" data-open-flow-scope="${escapeHtml(macroNode.drilldown.scopeId)}">下钻接口视图 L1</button>` : ""}${targetId ? `<button class="detail-action" type="button" data-open-exec-method="${escapeHtml(targetId)}">打开源码 / 方法详情</button>` : ""}${module ? `<button class="detail-action" type="button" data-open-exec-module="${escapeHtml(module.id)}">打开模块页面</button>` : ""}</div>`;
        detailScroll.querySelector("[data-open-flow-scope]")?.addEventListener("click", () => {
          const flow = currentExecutionFlow();
          if (flow) navigate({ kind: "scope", flowId: flow.id, nodeId: uid });
        });
        detailScroll.querySelector("[data-open-exec-method]")?.addEventListener("click", () => {
          const target = functionDetailById.get(targetId);
          if (target) navigate({ kind: "function", moduleId: target.moduleId, functionId: target.id });
        });
        detailScroll.querySelectorAll("[data-open-exec-candidate]").forEach(button => {
          button.addEventListener("click", () => {
            const target = functionDetailById.get(button.dataset.openExecCandidate);
            if (target) navigate({ kind: "function", moduleId: target.moduleId, functionId: target.id });
          });
        });
        detailScroll.querySelectorAll("[data-open-dispatch-candidate]").forEach(button => {
          button.addEventListener("click", () => {
            navigate({
              kind: "dispatch",
              flowId: currentExecutionFlow()?.id,
              nodeId: button.dataset.dispatchNode || uid,
              candidateScopeId: button.dataset.openDispatchCandidate,
            });
          });
        });
        detailScroll.querySelector("[data-open-dispatch-detail]")?.addEventListener("click", () => {
          navigate({ kind: "dispatch", flowId: currentExecutionFlow()?.id, nodeId: uid });
        });
        detailScroll.querySelector("[data-open-exec-module]")?.addEventListener("click", () => navigate({ kind: "module", moduleId: module.id }));
        return;
      }
      if (macroNode.kind === "module") {
        const graph = moduleGraphById.get(uid);
        const apis = graph?.providedApis || [];
        const providers = graph?.apiProviders || [];
        detailScroll.innerHTML = `<div class="detail-head" style="--mc:${macroNode.color}"><div class="detail-color"></div><div>
            <div class="eyebrow">模块能力 · ${escapeHtml(moduleRoleLabel(macroNode.role))}</div><h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(macroNode.name)}</h2>
            <div class="detail-module">module://${escapeHtml(uid)}</div></div></div>
          <div class="detail-note">${escapeHtml(macroNode.note || "暂无模块备注")}</div>
          <div class="port-detail"><span>角色 <b>${escapeHtml(moduleRoleLabel(macroNode.role || "service"))}</b></span><span>Provider <b>${providers.length}</b></span><span>接口 <b>${apis.length}</b></span></div>
          <div class="class-method-section"><div class="class-method-heading">模块组成</div>${roleCompositionBlock(graph)}</div>
          <div class="class-method-section"><div class="class-method-heading">提供接口</div>${apiProviderList(providers)}</div>
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
            <div class="eyebrow">${isTypeCard ? "类型 Provider" : "类 Provider"}${macroNode.isAbstract ? " · 契约" : ""}</div>
            <h2 class="detail-name">${escapeHtml(macroNode.name)}</h2>
            <div class="detail-module">${escapeHtml(macroNode.qualifiedName || "")}</div></div></div>
          <div class="detail-note">${escapeHtml(macroNode.note || "暂无类备注")}</div>
          <div class="port-detail"><span>角色 <b>${escapeHtml(providerRoleLabel(macroNode.providerRole))}</b></span><span>类型 <b>${escapeHtml(macroNode.classKind || "class")}</b></span><span>接口 <b>${apis.length}</b></span>${protocols.length ? `<span>协议 <b>${escapeHtml(protocols.join(" / "))}</b></span>` : ""}</div>
          <div class="source-line">角色来源：${escapeHtml(macroNode.roleSource || "structure")} · ${escapeHtml(macroNode.roleConfidence || "medium")}</div>
          ${isTypeCard ? "" : `<div class="source-line">用法：${escapeHtml(constructorSignature)}</div>`}
          <div class="source-line">${escapeHtml(macroNode.file || "")}:${macroNode.line || "—"}</div>
          <div class="port-detail"><span>声明接口 <b>${Number(macroNode.declaredApiCount || apis.filter(api => !api.inherited).length)}</b></span><span>继承接口 <b>${Number(macroNode.inheritedApiCount || apis.filter(api => api.inherited).length)}</b></span></div>
          ${macroNode.isAbstract ? `<div class="llm-stale">抽象类/接口是契约节点，不进入主流程执行节点。</div>` : ""}
          <div class="class-method-section"><div class="class-method-heading">类型层级</div>${classHierarchyBlock(macroNode)}</div>
          <div class="class-method-section"><div class="class-method-heading">结构关系</div>${structuralRelationsBlock(macroNode, moduleGraphById.get(state.moduleId))}</div>
          ${isTypeCard ? `<div class="class-method-section"><div class="class-method-heading">类型字段 · ${Number(typeSummary?.fieldCount || 0)}</div>${typeFieldList(typeSummary)}</div>` : `<div class="class-method-section"><div class="class-method-heading">提供接口</div>${apiDetailList(apis)}</div>`}
          <div class="class-method-section"><div class="class-method-heading">内部实现</div><div class="class-method-empty">${internalCount} 个内部方法，不在契约视图展示。</div></div>`;
        bindApiNavigation(detailScroll);
        return;
      }
      if (macroNode.kind === "function") {
        const detail = functionDetailById.get(macroNode.functionDetailId);
        detailScroll.innerHTML = `<div class="detail-head" style="--mc:${macroNode.color || "#60a5fa"}"><div class="detail-color"></div><div>
            <div class="eyebrow">函数 Provider</div><h2 class="detail-name">${escapeHtml(macroNode.name)}</h2>
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

  function currentExecutionFlow() {
    const flows = projectGraph.executionFlows || [];
    if (!flows.length) return null;
    const routeFlowId = ["flow", "scope", "dispatch"].includes(state.route.kind) ? state.route.flowId : null;
    const wanted = routeFlowId || state.executionFlowId || projectGraph.primaryExecutionFlowId;
    return flows.find(flow => flow.id === wanted) || flows.find(flow => flow.id === projectGraph.primaryExecutionFlowId) || flows[0];
  }

  function currentExecutionDispatchGroup() {
    if (state.route.kind !== "dispatch") return null;
    const flow = currentExecutionFlow();
    if (!flow) return null;
    return (flow.dispatchGroups || []).find(group =>
      group.id === state.route.dispatchGroupId || group.parentNodeId === state.route.nodeId
    ) || null;
  }

  function currentExecutionScope() {
    const flow = currentExecutionFlow();
    if (!flow) return null;
    if (state.route.kind === "scope") {
      const wanted = [state.route.nodeId, state.executionScopeId].filter(Boolean);
      return (flow.scopes || []).find(scope =>
        wanted.includes(scope.id) || wanted.includes(scope.parentNodeId)
      ) || null;
    }
    if (state.route.kind === "dispatch") {
      const group = currentExecutionDispatchGroup();
      if (!group) return null;
      return (group.scopes || []).find(scope => scope.id === state.route.candidateScopeId)
        || (group.scopes || [])[0]
        || null;
    }
    return null;
  }

  function executionFlowStorageId(flow) {
    return flow?.id || "primary";
  }

  function getExecutionPosition(flowId, nodeId, base) {
    const custom = override.executions?.[flowId]?.nodes?.[nodeId];
    return {
      x: Number(custom?.x ?? base?.x ?? 0),
      y: Number(custom?.y ?? base?.y ?? 0),
    };
  }

  function setExecutionPosition(flowId, nodeId, x, y) {
    if (!override.executions[flowId]) override.executions[flowId] = { nodes: {} };
    if (!override.executions[flowId].nodes) override.executions[flowId].nodes = {};
    override.executions[flowId].nodes[nodeId] = { x: Math.round(x), y: Math.round(y) };
  }

  function executionPortPoint(nodeId, portName) {
    const pos = state.positions.get(nodeId);
    if (!pos) return { x: 0, y: 0 };
    const spec = pos.ports?.[portName] || pos.ports?.out || pos.ports?.in || { x: 0, y: 0 };
    const nodeElement = world.querySelector(`.execution-node[data-uid="${cssEscape(nodeId)}"]`);
    const portElement = nodeElement
      ? [...nodeElement.querySelectorAll("[data-port]")].find(item => item.dataset.port === portName)
      : null;
    if (nodeElement && portElement) {
      const nodeRect = nodeElement.getBoundingClientRect();
      const portRect = portElement.getBoundingClientRect();
      const scale = Number(state.scale || 1) || 1;
      const side = spec.side || (portElement.classList.contains("is-left") ? "left" : "right");
      return {
        x: Number(pos.x || 0) + (side === "left" ? 0 : Number(pos.w || 0)),
        y: Number(pos.y || 0) + ((portRect.top + portRect.height / 2 - nodeRect.top) / scale),
      };
    }
    return { x: pos.x + Number(spec.x || 0), y: pos.y + Number(spec.y || 0) };
  }

  function executionCurveD(edge) {
    const geometry = state.executionEdgeLayouts?.[edge.id] || {};
    const from = executionPortPoint(edge.from, geometry.fromPort || "out");
    const to = executionPortPoint(edge.to, geometry.toPort || "in");
    const sx = from.x, sy = from.y, tx = to.x, ty = to.y;
    if (geometry.laneY != null) {
      const bottoms = [...state.positions.values()].map(pos => pos.y + pos.h);
      const laneY = Math.max(...bottoms, 0) + 48;
      const left = sx + 34;
      const right = Math.max(left + 18, tx - 34);
      return `M ${sx.toFixed(2)} ${sy.toFixed(2)} C ${left.toFixed(2)} ${sy.toFixed(2)} ${left.toFixed(2)} ${laneY.toFixed(2)} ${(left + 32).toFixed(2)} ${laneY.toFixed(2)} L ${(right - 32).toFixed(2)} ${laneY.toFixed(2)} C ${right.toFixed(2)} ${laneY.toFixed(2)} ${right.toFixed(2)} ${ty.toFixed(2)} ${tx.toFixed(2)} ${ty.toFixed(2)}`;
    }
    const bend = Math.max(42, Math.min(210, Math.abs(tx - sx) * .46));
    return `M ${sx.toFixed(2)} ${sy.toFixed(2)} C ${(sx + bend).toFixed(2)} ${sy.toFixed(2)} ${(tx - bend).toFixed(2)} ${ty.toFixed(2)} ${tx.toFixed(2)} ${ty.toFixed(2)}`;
  }

  function refreshExecutionEdges() {
    const edgesById = new Map((state.pageEdges || []).map(edge => [edge.id, edge]));
    world.querySelectorAll(".execution-edge").forEach(path => {
      const edge = edgesById.get(path.dataset.edgeId);
      if (!edge) return;
      path.setAttribute("d", executionCurveD(edge));
    });
    state.executionEdgeLabels.forEach((element, edgeId) => {
      const edge = edgesById.get(edgeId);
      if (!edge) return;
      const geometry = state.executionEdgeLayouts?.[edgeId] || {};
      const from = executionPortPoint(edge.from, geometry.fromPort || "out");
      const to = executionPortPoint(edge.to, geometry.toPort || "in");
      element.style.left = `${(from.x + to.x) / 2}px`;
      element.style.top = `${(from.y + to.y) / 2 - 14}px`;
    });
  }

  function setModuleContractsExpanded(expanded, targetPanel = "") {
    state.moduleContractsExpanded = Boolean(expanded);
    const drawer = moduleContracts.querySelector("#moduleContractsDrawer");
    const toggle = moduleContracts.querySelector("[data-contracts-toggle]");
    if (!drawer || !toggle) return;
    drawer.hidden = !state.moduleContractsExpanded;
    moduleContracts.classList.toggle("is-expanded", state.moduleContractsExpanded);
    moduleContracts.querySelectorAll("[data-contracts-toggle], [data-contracts-target]").forEach(button => {
      button.setAttribute("aria-expanded", String(state.moduleContractsExpanded));
      button.classList.toggle("is-open", state.moduleContractsExpanded);
    });
    toggle.innerHTML = state.moduleContractsExpanded
      ? `收起概览 <span class="contracts-toggle-icon">▴</span>`
      : `展开概览 <span class="contracts-toggle-icon">▾</span>`;
    if (state.moduleContractsExpanded && targetPanel) {
      const panel = drawer.querySelector(`[data-contracts-panel="${targetPanel}"]`);
      if (panel) {
        requestAnimationFrame(() => panel.scrollIntoView({ block: "nearest", behavior: "smooth" }));
      }
    }
    requestAnimationFrame(() => fitView(false));
  }

  function renderModuleContracts(moduleId) {
    if (!moduleContracts) return;
    const graph = moduleGraphById.get(moduleId);
    if (!graph) {
      moduleContracts.innerHTML = "";
      moduleContracts.classList.remove("is-visible", "is-expanded");
      return;
    }
    const typeRelationCount = (graph.typeRelations || []).length;
    const surfaceCount = (graph.userSurfaces || []).length;
    moduleContracts.style.setProperty("--mc-rgb", rgbFromHex(graph.color || "#60a5fa"));
    moduleContracts.innerHTML = `<div class="contracts-topline">
        <div class="contracts-title-group">
          <span class="contracts-label">模块能力</span>
          <span class="contracts-subtitle">Provider 结构概览</span>
        </div>
        <div class="contracts-roles">${roleCountChips(visibleRoleCounts(graph))}</div>
        <div class="contracts-summary-actions">
          <button class="contracts-count-btn" type="button" data-contracts-target="types" aria-expanded="false" aria-controls="moduleContractsDrawer">类型关系 <b>${typeRelationCount}</b></button>
          <button class="contracts-count-btn" type="button" data-contracts-target="surfaces" aria-expanded="false" aria-controls="moduleContractsDrawer">用户交互面 <b>${surfaceCount}</b></button>
          <button class="contracts-toggle" type="button" data-contracts-toggle aria-expanded="false" aria-controls="moduleContractsDrawer">展开概览 <span class="contracts-toggle-icon">▾</span></button>
        </div>
      </div>
      <div class="contracts-drawer" id="moduleContractsDrawer" hidden>
        <section class="contracts-drawer-section" data-contracts-panel="types">
          <div class="contracts-section-head"><span class="contracts-label">类型关系</span><span class="contracts-count">${typeRelationCount} 条</span></div>
          <div class="contracts-grid type-relation-track">${typeRelationChips(graph, typeRelationCount || 1)}</div>
        </section>
        <section class="contracts-drawer-section" data-contracts-panel="surfaces">
          <div class="contracts-section-head"><span class="contracts-label">用户交互面</span><span class="contracts-count">${surfaceCount} 个</span></div>
          <div class="contracts-grid user-surface-track">${userSurfaceChips(graph.userSurfaces || [], surfaceCount || 1)}</div>
        </section>
      </div>`;
    moduleContracts.classList.add("is-visible");
    moduleContracts.querySelector("[data-contracts-toggle]")?.addEventListener("click", () => {
      setModuleContractsExpanded(!state.moduleContractsExpanded);
    });
    moduleContracts.querySelectorAll("[data-contracts-target]").forEach(button => {
      button.addEventListener("click", () => setModuleContractsExpanded(true, button.dataset.contractsTarget || ""));
    });
    setModuleContractsExpanded(false);
  }

  function renderFlowPicker(selectedFlow) {
    const flows = projectGraph.executionFlows || [];
    const visible = flows.length > 1;
    flowPicker.classList.toggle("is-visible", visible);
    if (!visible) {
      flowPicker.innerHTML = "";
      return;
    }
    flowPicker.innerHTML = `<span>执行流</span>${flows.map(flow =>
      `<button type="button" data-flow-pick="${escapeHtml(flow.id)}" class="${flow.id === selectedFlow?.id ? "is-active" : ""}">${escapeHtml(flow.name || flow.entrypointId)}</button>`
    ).join("")}`;
    flowPicker.querySelectorAll("[data-flow-pick]").forEach(button => {
      button.addEventListener("click", () => navigate({ kind: "flow", flowId: button.dataset.flowPick }));
    });
  }

  function renderDispatchPicker(group, selectedScope) {
    const scopes = group.scopes || [];
    flowPicker.classList.toggle("is-visible", scopes.length > 0);
    if (!scopes.length) {
      flowPicker.innerHTML = "";
      return;
    }
    flowPicker.innerHTML = `<span>分发候选</span>${scopes.map(scope => {
      const detail = functionDetailById.get(scope.rootFunctionId);
      const label = detail?.name || scope.rootFunctionId.split(".").pop();
      return `<button type="button" data-candidate-pick="${escapeHtml(scope.id)}" class="${scope.id === selectedScope?.id ? "is-active" : ""}" title="${escapeHtml(scope.name || label)}">${escapeHtml(label)}</button>`;
    }).join("")}`;
    flowPicker.querySelectorAll("[data-candidate-pick]").forEach(button => {
      button.addEventListener("click", () => navigate({
        kind: "dispatch",
        flowId: currentExecutionFlow()?.id,
        nodeId: group.parentNodeId,
        candidateScopeId: button.dataset.candidatePick,
      }));
    });
  }


  function updateChrome(kind) {
    const module = state.route.moduleId ? projectModuleById.get(state.route.moduleId) : null;
    const detail = state.route.functionId ? functionDetailById.get(state.route.functionId) : null;
    if (kind === "project") {
      canvasKicker.textContent = "项目组成图";
      canvasTitle.textContent = DATA.project.name;
      canvasSub.textContent = "项目级执行流独立展示 · 模块卡片展示能力视图 · 双击进入对应页面";
      breadcrumb.innerHTML = `<b>${escapeHtml(DATA.project.name)}</b>`;
      legend.innerHTML = legendItem("entry", "执行流卡片") + legendItem("card", "模块能力卡片");
    } else if (kind === "flow") {
      const flow = currentExecutionFlow();
      canvasKicker.textContent = "主执行流";
      canvasTitle.textContent = flow?.name || "主流程";
      canvasSub.textContent = "入口函数控制骨架 · 调用目标原子化 · 带 L1 标记的节点可下钻接口视图 · 双击进入源码";
      breadcrumb.innerHTML = `<button type="button" data-nav="project">${escapeHtml(DATA.project.name)}</button><span class="slash">/</span><b>主流程</b>`;
      legend.innerHTML = legendItem("function", "本地调用") + legendItem("interface", "功能接口") + legendItem("entry", "可下钻接口视图") + legendItem("line", "确定的控制/执行边");
    } else if (kind === "scope") {
      const flow = currentExecutionFlow();
      const scope = currentExecutionScope();
      canvasKicker.textContent = "一级接口下钻 · L1";
      canvasTitle.textContent = scope?.name || "接口下钻";
      canvasSub.textContent = "一级接口展开 · 外部模块能力节点与目标函数控制骨架 · 不递归展开 · 双击进入源码";
      breadcrumb.innerHTML = `<button type="button" data-nav="project">${escapeHtml(DATA.project.name)}</button><span class="slash">/</span><button type="button" data-nav="flow">${escapeHtml(flow?.name || "主流程")}</button><span class="slash">/</span><b>${escapeHtml(scope?.name || "接口下钻")}</b>`;
      legend.innerHTML = legendItem("interface", "外部能力接口") + legendItem("function", "内部调用") + legendItem("line", "确定的控制/执行边");
    } else if (kind === "dispatch") {
      const flow = currentExecutionFlow();
      const group = currentExecutionDispatchGroup();
      const scope = currentExecutionScope();
      canvasKicker.textContent = "分发候选旅程";
      canvasTitle.textContent = group?.expression || "候选旅程";
      canvasSub.textContent = "dispatch 保持原子边界 · 候选以独立 callable scope 展开 · 不递归生成新候选旅程 · 双击进入源码";
      breadcrumb.innerHTML = `<button type="button" data-nav="project">${escapeHtml(DATA.project.name)}</button><span class="slash">/</span><button type="button" data-nav="flow">${escapeHtml(flow?.name || "主流程")}</button><span class="slash">/</span><button type="button" data-nav="dispatch">${escapeHtml(group?.expression || "dispatch")}</button><span class="slash">/</span><b>${escapeHtml(scope?.name || "候选旅程")}</b>`;
      legend.innerHTML = legendItem("dispatch", "分发边界") + legendItem("function", "候选步骤") + legendItem("interface", "外部能力接口") + legendItem("line", "确定的控制/执行边");
    } else if (kind === "module") {
      canvasKicker.textContent = "模块能力";
      canvasTitle.textContent = module?.name || state.route.moduleId;
      canvasSub.textContent = "Provider · API · 类型关系 · 双击进入详情";
      breadcrumb.innerHTML = `<button type="button" data-nav="project">${escapeHtml(DATA.project.name)}</button><span class="slash">/</span><b>${escapeHtml(module?.name || state.route.moduleId)}</b>`;
      legend.innerHTML = legendItem("card", "模块能力卡片");
    } else {
      const ownerClass = detail?.ownerClassId
        ? (moduleGraphById.get(detail.moduleId)?.nodes || []).find(node => node.id === detail.ownerClassId)
        : null;
      const owner = ownerClass ? `<button type="button" data-nav="module" data-module="${escapeHtml(state.route.moduleId)}">${escapeHtml(ownerClass.name)}</button><span class="slash">/</span>` : "";
      canvasKicker.textContent = "方法详情";
      canvasTitle.textContent = detail?.name || state.route.functionId;
      canvasSub.textContent = "源码 + 人类备注 + LLM 语义 + 调用关系";
      breadcrumb.innerHTML = `<button type="button" data-nav="project">${escapeHtml(DATA.project.name)}</button><span class="slash">/</span><button type="button" data-nav="module" data-module="${escapeHtml(state.route.moduleId)}">${escapeHtml(module?.name || state.route.moduleId)}</button><span class="slash">/</span>${owner}<b>${escapeHtml(detail?.name || state.route.functionId)}</b>`;
      legend.innerHTML = legendItem("line", "调用关系") + legendItem("input", "源码证据");
    }
    breadcrumb.querySelectorAll("[data-nav]").forEach(button => {
      button.addEventListener("click", () => {
        if (button.dataset.nav === "project") navigate({ kind: "project" });
        if (button.dataset.nav === "flow") navigate({ kind: "flow", flowId: currentExecutionFlow()?.id });
        if (button.dataset.nav === "dispatch") {
          const group = currentExecutionDispatchGroup();
          navigate({
            kind: "dispatch",
            flowId: currentExecutionFlow()?.id,
            nodeId: group?.parentNodeId || state.route.nodeId,
          });
        }
        if (button.dataset.nav === "module") navigate({ kind: "module", moduleId: button.dataset.module });
      });
    });
    $("pageHint").textContent = kind === "project" ? "项目页" : kind === "flow" ? "主流程页" : kind === "scope" ? "接口下钻" : kind === "dispatch" ? "候选旅程" : kind === "module" ? "模块页" : "方法详情";
    searchWrap.classList.toggle("is-disabled", kind === "method");
    if (kind === "method") searchInput.value = "";
    backBtn.disabled = kind === "project" && history.length <= 1;
  }

  function projectNodeSize(node) {
    if (node.kind === "module" || node.kind === "flow") {
      return { w: node.w || 320, h: node.h || 200 };
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
    return updateWorldExtent(900, 640);
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
    flowPicker.classList.remove("is-visible");
    world.innerHTML = "";
    world.classList.remove("page-enter");
    const capabilityModules = visibleProjectModules();
    state.nodes = new Map();
    // The project page is one card grid: project-level flow cards and
    // capability module cards are peers.  Module dependency lines are not
    // projected or rendered.
    (projectGraph.flowCards || []).forEach(card => {
      state.nodes.set(card.id, { ...card, kind: "flow" });
    });
    capabilityModules.forEach(module => {
      state.nodes.set(module.id, { ...module, kind: "module" });
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
    state.pageEdges = [];
    state.nodes.forEach((node, nodeId) => {
      if (node.kind === "flow") renderProjectFlowCard(nodeId, node);
      else renderProjectModule(nodeId, node);
    });
    updateProjectWorldSize();
    world.classList.add("page-enter");
    requestAnimationFrame(() => {
      applyTransform();
      fitView();
      renderDefaultDetail();
      if (state.search) applySearch();
    });
  }

  function renderProjectFlowCard(nodeId, card) {
    const position = state.positions.get(nodeId);
    const size = state.sizes.get(nodeId);
    const element = document.createElement("article");
    element.className = "node-card module-node flow-card-node";
    element.dataset.uid = nodeId;
    element.style.left = `${position.x}px`;
    element.style.top = `${position.y}px`;
    element.style.width = `${size.w}px`;
    element.style.height = `${size.h}px`;
    element.style.setProperty("--mc", card.color || "#f59e0b");
    element.style.setProperty("--mc-rgb", rgbFromHex(card.color || "#f59e0b"));
    element.innerHTML = `<header class="module-header">
        <div class="module-title-row">
          <span class="module-dot"></span><span class="module-kind">主流程</span>
          <span class="module-title">${escapeHtml(card.name || "主流程")}</span>
          <div class="module-actions">
            <button class="mini-action" type="button" data-open-flow-card="${escapeHtml(card.flowId)}" aria-label="打开主流程" title="打开主流程">↗</button>
          </div>
        </div>
        <div class="module-note">${escapeHtml(card.note || "项目级主流程入口")}</div>
        <div class="module-api-section">
          <div class="module-api-heading"><span>入口</span><b>${escapeHtml(card.entrypointReason || "flow")}</b></div>
          <div class="module-api-chips"><span class="module-api-chip is-entry">${escapeHtml(card.entrypointId || "")}</span></div>
        </div>
        <div class="module-metrics">
          <span>${escapeHtml(card.moduleName || card.moduleId || "")}</span>
          <span>${Number(card.nodeCount || 0)} 个节点</span>
          <span>${Number(card.edgeCount || 0)} 条边</span>
        </div>
      </header>`;
    world.appendChild(element);
    bindNodeHover(element, nodeId);
    const header = element.querySelector(".module-header");
    header.addEventListener("click", event => {
      if (event.target.closest("button")) return;
      selectUid(nodeId);
    });
    header.addEventListener("dblclick", event => {
      if (event.target.closest("button")) return;
      navigate({ kind: "flow", flowId: card.flowId });
    });
    element.querySelector("[data-open-flow-card]")?.addEventListener("click", event => {
      event.stopPropagation();
      navigate({ kind: "flow", flowId: card.flowId });
    });
    attachDrag(header, element, {
      getPosition: () => ({ x: parseFloat(element.style.left), y: parseFloat(element.style.top) }),
      setPosition: (x, y) => {
        const pos = state.positions.get(nodeId);
        pos.x = x; pos.y = y;
        setProjectPosition(nodeId, x, y);
      },
      onMove: () => { updateProjectWorldSize(); },
      onEnd: () => { persistOverride(); updateProjectWorldSize(); },
    });
  }

  function renderProjectModule(nodeId, module) {
    const position = state.positions.get(nodeId);
    const size = state.sizes.get(nodeId);
    const graph = moduleGraphById.get(nodeId);
    const apis = graph?.providedApis || [];
    const role = module.role || graph?.role || "service";
    const visibleClasses = visibleProviderNodes(graph).filter(node => node.kind === "class").length;
    const classCount = Number(visibleClasses || 0);
    const providerCount = Number((graph?.apiProviders || []).length);
    const apiCount = Number(module.providedApiCount ?? apis.length);
    const element = document.createElement("article");
    element.className = "node-card module-node";
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
            <button class="mini-action" type="button" data-open-module="${escapeHtml(nodeId)}" aria-label="打开模块页面" title="打开独立模块页面">↗</button>
          </div>
        </div>
        <div class="module-note">${escapeHtml(module.note || "暂无模块备注")}</div>
        <div class="module-api-section">
          <div class="module-api-heading"><span>提供接口</span><b>${apiCount}</b></div>
          <div class="module-api-chips">${apiChips(apis, 3)}</div>
        </div>
        <div class="module-role-counts">${roleCountChips(visibleRoleCounts(graph))}</div>
        <div class="module-metrics">
          <span>${classCount} 个类</span>
          <span>${providerCount} 个提供者</span>
          <span class="${apiCount ? "has-apis" : ""}">${apiCount} 个接口</span>
        </div>
      </header>`;
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
    attachDrag(header, element, {
      getPosition: () => ({ x: parseFloat(element.style.left), y: parseFloat(element.style.top) }),
      setPosition: (x, y) => {
        const pos = state.positions.get(nodeId);
        pos.x = x; pos.y = y;
        setProjectPosition(nodeId, x, y);
      },
      onMove: () => { updateProjectWorldSize(); },
      onEnd: () => { persistOverride(); updateProjectWorldSize(); },
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
    return updateWorldExtent(860, 640);
  }

  function drilldownReasonLabel(reason) {
    return ({
      configured_root: "显式配置",
      execution_only: "executionOnly",
      auto_orchestrator: "自动发现",
      dispatch_candidates: "候选旅程",
      candidate_set_incomplete: "候选不完整",
      no_candidates: "无候选",
      no_resolved_candidates: "无可用候选",
      scope_budget_exhausted: "预算耗尽",
    }[reason] || String(reason || ""));
  }

  function dispatchSourceLabel(source) {
    return ({
      config: "配置声明",
      comment: "源码注释",
      argparse_registry: "argparse 推断",
      static_registry: "静态 registry",
      polymorphic: "多态候选",
      unknown: "未解析来源",
    }[source] || String(source || "未解析来源"));
  }

  function executionKindLabel(kind) {
    return ({
      entry: "入口",
      exit: "结束",
      free_function: "本地调用",
      interface: "功能接口",
      branch: "双分支",
      multi_branch: "多分支",
      loop: "循环",
      break: "跳出循环",
      continue: "继续循环",
      return: "返回",
      dispatch: "动态分发",
    }[kind] || String(kind || "节点"));
  }

  function executionEdgeClass(edge) {
    return `execution-edge kind-${escapeHtml(edge.kind || "next")}`;
  }

  function executionArmSummaryText(summary, emptyText = "") {
    if (!summary || typeof summary !== "object") return emptyText;
    const statements = Array.isArray(summary.statements)
      ? summary.statements.map(item => String(item ?? "").trim()).filter(Boolean)
      : [];
    if (statements.length) return statements.join("; ");
    const next = String(summary.next || "");
    if (next && next !== "fallthrough") return `→ ${next}`;
    return emptyText;
  }

  function executionArmSummaryRows(node) {
    const rows = [];
    const arms = node.armSummaries && typeof node.armSummaries === "object"
      ? node.armSummaries
      : {};
    ["true", "false"].forEach(port => {
      const summary = arms[port];
      const text = executionArmSummaryText(summary, "");
      if (text) rows.push({ label: port === "true" ? "是" : "否", text });
    });
    if (node.implicitNext === "loop_iteration") {
      rows.push({ label: "↻", text: "隐式进入下一轮循环" });
    }
    return rows;
  }

  function executionArmSummaryHtml(node) {
    const rows = executionArmSummaryRows(node);
    if (!rows.length) return "";
    return `<div class="exec-arm-summaries">${rows.map(row =>
      `<div class="exec-arm-row"><b title="${escapeHtml(row.title || row.label)}">${escapeHtml(row.label)}</b><span>${escapeHtml(truncate(row.text, 72))}</span></div>`
    ).join("")}</div>`;
  }

  function executionArmSummaryDetailHtml(node) {
    const rows = executionArmSummaryRows(node);
    const outgoing = (state.pageEdges || [])
      .filter(edge => edge.from === node.id && Array.isArray(edge.statements) && edge.statements.length);
    if (!rows.length && !outgoing.length) return "";
    return `<div class="class-method-section"><div class="class-method-heading">控制臂语义</div>
      <div class="exec-arm-detail">
        ${rows.map(row => `<div class="exec-arm-detail-row"><b>${escapeHtml(row.label)}</b><span>${escapeHtml(row.text)}</span></div>`).join("")}
        ${outgoing.map(edge => `<div class="exec-arm-detail-row"><b>${escapeHtml(edge.kind || "next")}</b><span>${escapeHtml((edge.statements || []).join("; "))}</span></div>`).join("")}
      </div></div>`;
  }

  function executionPortDisplay(node, name, spec) {
    const kind = node.kind;
    const caseMatch = /^case:(\d+)$/.exec(String(name));
    if (name === "in") {
      return {
        label: kind === "loop" ? "进入循环" : (kind === "branch" || kind === "multi_branch") ? "进入分支" : "进入",
        detail: "in",
        className: "port-in",
      };
    }
    if (name === "out") {
      if (kind === "entry") return { label: "开始", detail: "out", className: "port-out" };
      if (kind === "dispatch") return { label: "分发", detail: "out", className: "port-dispatch" };
      return { label: "返回", detail: "out", className: "port-out" };
    }
    if (name === "true") return { label: "是", detail: "true arm", className: "port-true" };
    if (name === "false") return { label: "否", detail: "false arm", className: "port-false" };
    if (name === "default") return { label: "默认", detail: "default", className: "port-default" };
    if (name === "loop_body") return { label: "循环体", detail: "loop body", className: "port-loop_body" };
    if (name === "loop_complete") return { label: "离开循环", detail: "loop exit", className: "port-loop_complete" };
    if (caseMatch) {
      const index = Number(caseMatch[1]);
      const caseItem = (node.cases || [])[index] || {};
      return {
        label: String(caseItem.label || spec.label || `case ${index + 1}`),
        detail: `case ${index + 1}`,
        className: "port-case",
      };
    }
    return {
      label: String(spec.label || name),
      detail: String(name),
      className: "port-out",
    };
  }

  function executionPortGrid(node, pos) {
    const ports = pos.ports || {};
    const left = [];
    const right = [];
    Object.entries(ports).forEach(([name, spec]) => {
      const display = executionPortDisplay(node, name, spec);
      const side = spec.side || (name === "in" ? "left" : "right");
      const item = `<div class="exec-port-item ${side === "left" ? "is-left" : "is-right"} ${display.className}" data-port="${escapeHtml(name)}">
        <span class="exec-port-symbol shape-${escapeHtml(spec.shape || "circle")}" aria-hidden="true"></span>
        <span class="exec-port-copy"><b>${escapeHtml(display.label)}</b><small>${escapeHtml(display.detail)}</small></span>
      </div>`;
      (side === "left" ? left : right).push(item);
    });
    return `<div class="exec-port-grid">
      <div class="exec-port-side is-left">${left.join("") || `<div class="exec-port-empty"></div>`}</div>
      <div class="exec-port-side is-right">${right.join("") || `<div class="exec-port-empty"></div>`}</div>
    </div>`;
  }

  function renderExecutionNode(moduleId, nodeId, node) {
    const pos = state.positions.get(nodeId);
    const kind = node.kind || "free_function";
    const flow = currentExecutionFlow();
    const flowId = ["scope", "dispatch"].includes(state.pageKind)
      ? (state.executionScopeId || state.pageKind)
      : executionFlowStorageId(flow);
    const targetId = node.targetFunctionId || (
      ["entry", "free_function", "interface", "dispatch"].includes(kind) ? node.functionId : null
    );
    const detail = targetId ? functionDetailById.get(targetId) : null;
    const noteText = node.note || detail?.note || "";
    const dispatchCandidateNames = kind === "dispatch"
      ? (node.candidates || []).slice(0, 3).map(candidateId => {
          const candidateDetail = functionDetailById.get(candidateId);
          return candidateDetail?.name || String(candidateId).split(".").pop();
        })
      : [];
    const dispatchCandidatePreview = dispatchCandidateNames.length
      ? `${dispatchCandidateNames.join(" / ")}${(node.candidates || []).length > dispatchCandidateNames.length ? ` / +${(node.candidates || []).length - dispatchCandidateNames.length}` : ""}`
      : "";
    const icon = ({
      entry: "▶", exit: "■", free_function: "ƒ", interface: "I",
      branch: "◇", multi_branch: "⑂", loop: "↻", break: "↩",
      continue: "↪", return: "⤴", dispatch: "⑂",
    }[kind] || "•");
    const meta = [];
    if (node.condition && kind !== "branch" && kind !== "multi_branch" && kind !== "loop") {
      meta.push(`条件：${truncate(node.condition, 46)}`);
    }
    if (kind === "loop" && node.condition) meta.push(`条件：${truncate(node.condition, 46)}`);
    if (kind === "free_function" && node.callableKind) {
      meta.push(node.callableKind === "method" ? `方法 · ${node.ownerClassName || ""}`.trim() : "函数");
    }
    if (kind === "dispatch") {
      meta.push(`候选 ${Number(node.candidateCount || 0)} · ${node.candidateSetComplete ? "完整" : "部分"} · ${dispatchSourceLabel(node.candidateSource)}`);
    }
    if (kind === "loop" && node.mayExit === false) meta.push("可能不退出");
    if (node.usageKind) meta.push(node.usageKind);
    const foot = [];
    if (kind === "dispatch") {
      foot.push(`来源：${dispatchSourceLabel(node.candidateSource)}`);
      if (node.drilldown?.kind === "dispatch" && node.drilldown?.status === "available") {
        foot.push(`候选旅程：${Number(node.drilldown.candidateScopeCount || 0)}`);
      } else if (node.drilldown?.kind === "dispatch" && node.drilldown?.status === "blocked") {
        foot.push(drilldownReasonLabel(node.drilldown.reason));
      } else {
        foot.push(`完整性：${node.candidateSetComplete ? "完整" : "部分"}`);
      }
    }
    if (kind === "loop") {
      foot.push(`循环类型：${node.loopKind || "loop"}`);
      foot.push(`可能退出：${node.mayExit ? "是" : "否"}`);
    }
    const element = document.createElement("article");
    element.className = `node-card execution-node kind-${escapeHtml(kind)}${targetId ? " is-navigable" : ""}`;
    element.dataset.uid = nodeId;
    element.dataset.kind = kind;
    element.style.left = `${pos.x}px`;
    element.style.top = `${pos.y}px`;
    element.style.width = `${pos.w}px`;
    element.style.height = `${pos.h}px`;
    element.style.setProperty("--mc", node.color || "#60a5fa");
    element.style.setProperty("--mc-rgb", rgbFromHex(node.color || "#60a5fa"));
    element.innerHTML = `
      <div class="exec-node-header">
        <span class="exec-node-icon">${icon}</span>
        <span class="exec-node-kind">${escapeHtml(executionKindLabel(kind))}</span>
        <span class="exec-node-module">${escapeHtml(node.moduleName || node.moduleId || "")}</span>
      </div>
      <div class="exec-node-body">
        <div class="exec-copy">
          <div class="exec-node-label" title="${escapeHtml(node.label || "")}">${escapeHtml(node.label || "")}</div>
          ${noteText ? `<div class="exec-node-note" title="${escapeHtml(noteText)}">${escapeHtml(noteText)}</div>` : ""}
          ${meta.length ? `<div class="exec-node-meta">${escapeHtml(meta.join(" · "))}</div>` : ""}
          ${executionArmSummaryHtml(node)}
          ${node.kind !== "interface" && (node.drilldown?.interfaceSummary || []).length ? `<div class="exec-node-interface-hint">外部接口 ${node.drilldown.interfaceSummary.length} · ${node.drilldown.interfaceSummary.slice(0, 2).map(item => escapeHtml(item.label)).join(" / ")}</div>` : ""}
          ${(node.interfaceHints || []).length ? `<div class="exec-node-interface-hint">触达 ${node.interfaceHints.length} 个接口 · ${node.interfaceHints.slice(0, 2).map(item => escapeHtml(item.label)).join(" / ")}</div>` : ""}
          ${dispatchCandidatePreview ? `<div class="exec-node-interface-hint" title="${escapeHtml(dispatchCandidatePreview)}">候选：${escapeHtml(dispatchCandidatePreview)}</div>` : ""}
        </div>
        ${executionPortGrid(node, pos)}
        ${foot.length ? `<div class="exec-foot">${foot.map(item => `<span class="exec-pill">${escapeHtml(item)}</span>`).join("")}</div>` : ""}
        ${node.kind === "dispatch" && node.drilldown?.kind === "dispatch" && node.drilldown?.status === "available" ? `<button class="exec-drilldown-l1" type="button" data-open-dispatch-group="${escapeHtml(nodeId)}" title="打开候选旅程">候选旅程 · ${Number(node.drilldown.candidateScopeCount || 0)}</button>` : ""}
        ${node.kind !== "interface" && node.kind !== "dispatch" && node.drilldown?.status === "available" ? `<button class="exec-drilldown-l1${node.drilldown.reason === "auto_orchestrator" ? " is-auto" : ""}" type="button" data-drilldown-node="${escapeHtml(nodeId)}" title="${escapeHtml(drilldownReasonLabel(node.drilldown.reason))}">L1 · ${node.drilldown.interfaceSummary?.length || 0} 接口${node.drilldown.reason === "auto_orchestrator" ? " · 自动" : ""}</button>` : ""}
      </div>`;
    world.appendChild(element);
    bindNodeHover(element, nodeId);
    element.querySelector("[data-drilldown-node]")?.addEventListener("click", event => {
      event.stopPropagation();
      navigate({ kind: "scope", flowId: currentExecutionFlow()?.id, nodeId });
    });
    element.querySelector("[data-open-dispatch-group]")?.addEventListener("click", event => {
      event.stopPropagation();
      navigate({ kind: "dispatch", flowId: currentExecutionFlow()?.id, nodeId });
    });
    element.addEventListener("click", event => {
      event.stopPropagation();
      selectUid(nodeId);
    });
    element.addEventListener("dblclick", event => {
      event.stopPropagation();
      const target = targetId ? functionDetailById.get(targetId) : null;
      if (target) navigate({ kind: "function", moduleId: target.moduleId, functionId: target.id });
    });
    attachDrag(element, element, {
      getPosition: () => ({ x: parseFloat(element.style.left), y: parseFloat(element.style.top) }),
      setPosition: (x, y) => {
        const item = state.positions.get(nodeId);
        item.x = x; item.y = y;
        setExecutionPosition(flowId, nodeId, x, y);
      },
      onMove: () => { refreshExecutionEdges(); updateModuleWorldSize(moduleId); },
      onEnd: () => { persistOverride(); updateModuleWorldSize(moduleId); },
    });
  }

  function renderFlowPage(
    flowId = null, scopeNodeId = null, dispatchNodeId = null, candidateScopeId = null
  ) {
    state.pageKind = scopeNodeId ? "scope" : dispatchNodeId ? "dispatch" : "flow";
    state.functionId = null;
    viewport.classList.remove("is-light");
    viewport.classList.remove("is-detail");
    setGraphChromeVisible(true);
    if (moduleContracts) {
      moduleContracts.innerHTML = "";
      moduleContracts.classList.remove("is-visible");
    }
    const flows = projectGraph.executionFlows || [];
    let flow = flowId ? flows.find(item => item.id === flowId) : null;
    if (!flow) flow = flows.find(item => item.id === projectGraph.primaryExecutionFlowId) || flows[0] || null;
    if (!flow) {
      flowPicker.classList.remove("is-visible");
      state.moduleId = null;
      updateChrome("flow");
      renderExecutionFlowPage(projectGraph.mainModuleId || "", { color: "#f59e0b" });
      return;
    }
    if (scopeNodeId) {
      const scope = (flow.scopes || []).find(item =>
        item.parentNodeId === scopeNodeId || item.id === scopeNodeId
      );
      if (!scope) {
        navigate({ kind: "flow", flowId: flow.id }, false);
        showToast("该节点没有可用的 L1 接口 scope");
        return;
      }
      state.route = { kind: "scope", flowId: flow.id, nodeId: scopeNodeId };
      const expectedHash = routeHash(state.route);
      if (location.hash !== expectedHash) history.replaceState(state.route, "", expectedHash);
      state.executionFlowId = flow.id;
      state.executionScopeId = scope.id;
      state.moduleId = flow.moduleId;
      flowPicker.classList.remove("is-visible");
      updateChrome("scope");
      const graph = moduleGraphById.get(flow.moduleId) || { color: "#f59e0b" };
      renderExecutionFlowPage(flow.moduleId, graph);
      return;
    }
    if (dispatchNodeId) {
      const group = (flow.dispatchGroups || []).find(item => item.parentNodeId === dispatchNodeId);
      if (!group || !(group.scopes || []).length) {
        navigate({ kind: "flow", flowId: flow.id }, false);
        showToast("该 dispatch 节点没有可用的候选旅程");
        return;
      }
      const candidateScope = (group.scopes || []).find(item => item.id === candidateScopeId)
        || (group.scopes || [])[0];
      state.route = {
        kind: "dispatch",
        flowId: flow.id,
        nodeId: dispatchNodeId,
        candidateScopeId: candidateScope.id,
      };
      const expectedHash = routeHash(state.route);
      if (location.hash !== expectedHash) history.replaceState(state.route, "", expectedHash);
      state.executionFlowId = flow.id;
      state.executionScopeId = candidateScope.id;
      state.moduleId = flow.moduleId;
      updateChrome("dispatch");
      renderDispatchPicker(group, candidateScope);
      const graph = moduleGraphById.get(flow.moduleId) || { color: "#f59e0b" };
      renderExecutionFlowPage(flow.moduleId, graph);
      return;
    }
    state.route = { kind: "flow", flowId: flow.id };
    const expectedHash = routeHash(state.route);
    if (location.hash !== expectedHash) history.replaceState(state.route, "", expectedHash);
    state.executionFlowId = flow.id;
    state.executionScopeId = null;
    state.moduleId = flow.moduleId;
    updateChrome("flow");
    renderFlowPicker(flow);
    const graph = moduleGraphById.get(flow.moduleId) || { color: "#f59e0b" };
    renderExecutionFlowPage(flow.moduleId, graph);
  }

  function renderExecutionFlowPage(moduleId, graph) {
    const flow = currentExecutionFlow();
    const scope = currentExecutionScope();
    const executionView = scope || flow;
    world.innerHTML = "";
    world.classList.remove("page-enter");
    state.nodes = new Map();
    state.sizes = new Map();
    state.positions = new Map();
    state.executionEdgeLabels = new Map();
    state.executionEdgeLayouts = {};
    if (!flow || !executionView) {
      world.style.width = "760px";
      world.style.height = "420px";
      world.innerHTML = `<div class="flow-empty"><div class="eyebrow">执行流</div><h2>暂无可解析主流程</h2><p>请检查 entrypoints 或 executionEntrypoints 配置。</p></div>`;
      updateModuleWorldSize(moduleId);
      requestAnimationFrame(() => { applyTransform(); fitView(); renderDefaultDetail(); });
      return;
    }
    state.executionFlowId = flow.id;
    state.executionScopeId = scope?.id || null;
    state.executionEdgeLayouts = executionView.layout?.edges || {};
    const flowId = scope ? scope.id : executionFlowStorageId(flow);
    executionView.nodes.forEach(node => {
      const base = executionView.layout?.nodes?.[node.id] || { x: 80, y: 100, w: 250, h: 92, ports: {} };
      const position = getExecutionPosition(flowId, node.id, base);
      const item = { ...node, execution: true, color: node.color || graph.color, ports: base.ports || {} };
      state.nodes.set(node.id, item);
      state.sizes.set(node.id, { w: Number(base.w || node.w || 250), h: Number(base.h || node.h || 92) });
      state.positions.set(node.id, {
        x: Number(position.x || 0), y: Number(position.y || 0),
        w: Number(base.w || node.w || 250), h: Number(base.h || node.h || 92),
        ports: base.ports || {},
      });
    });
    const canvas = executionView.layout?.canvas || { width: 1200, height: 800 };
    const svg = makeSvg(Number(canvas.width || 1200), Number(canvas.height || 800), "world-edges execution-edges");
    world.appendChild(svg);
    state.pageEdges = executionView.edges || [];
    state.pageEdges.forEach(edge => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("class", executionEdgeClass(edge));
      path.setAttribute("data-from", edge.from);
      path.setAttribute("data-to", edge.to);
      path.setAttribute("data-edge-id", edge.id);
      path.setAttribute("data-edge-kind", edge.kind || "next");
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${edge.kind || "next"}${edge.label ? ` · ${edge.label}` : ""}`;
      path.appendChild(title);
      path.setAttribute("d", executionCurveD(edge));
      svg.appendChild(path);
      if (Array.isArray(edge.statements) && edge.statements.length) {
        const note = document.createElement("div");
        note.className = "execution-edge-note";
        note.dataset.edgeId = edge.id;
        note.textContent = edge.statements.join("; ");
        world.appendChild(note);
        state.executionEdgeLabels.set(edge.id, note);
      }
    });
    state.nodes.forEach((node, nodeId) => renderExecutionNode(moduleId, nodeId, node));
    refreshExecutionEdges();
    updateModuleWorldSize(moduleId);
    world.classList.add("page-enter");
    requestAnimationFrame(() => {
      applyTransform();
      fitView();
      if (state.scale < .78) focusExecutionStart(executionView);
      renderDefaultDetail();
      const pendingUid = state.pendingSelectUid;
      state.pendingSelectUid = null;
      if (pendingUid && state.nodes.has(pendingUid)) selectUid(pendingUid);
      if (state.search) applySearch();
    });
  }

  function renderModulePage(moduleId) {
    const graph = moduleGraphById.get(moduleId);
    const projectModule = projectModuleById.get(moduleId);
    if (!graph || projectModule?.capabilitySurface?.hasProviders === false) {
      navigate({ kind: "project" }, false);
      if (graph) showToast("该模块仅承载执行流，无能力视图");
      return;
    }
    state.pageKind = "module";
    state.moduleId = moduleId;
    state.functionId = null;
    viewport.classList.remove("is-light");
    viewport.classList.remove("is-detail");
    setGraphChromeVisible(true);
    flowPicker.classList.remove("is-visible");
    updateChrome("module");
    renderModuleContracts(moduleId);
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
    state.pageEdges = [];
    state.nodes.forEach((node, nodeId) => {
      if (node.kind === "function") renderModuleFunctionNode(moduleId, nodeId, node);
      else if (node.kind === "class") renderModuleClassNode(moduleId, nodeId, node);
    });
    updateModuleWorldSize(moduleId);
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
      onMove: () => { updateModuleWorldSize(moduleId); },
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
    const inheritanceText = (node.baseClassIds || []).length ? ` · ${node.baseClassIds.length} 个基类` : "";
    const inheritedText = Number(node.inheritedApiCount || 0) ? ` · 继承 ${Number(node.inheritedApiCount)} 个接口` : "";
    const bodySummary = isTypeCard
      ? `<div class="class-usage">${Number(typeSummary?.fieldCount || 0)} 个字段 · 类型契约${inheritanceText}</div>`
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
        <span class="class-node-count">${isTypeCard ? `${Number(typeSummary?.fieldCount || 0)} 字段` : `${apis.length} 个接口`}</span>
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
      onMove: () => { updateModuleWorldSize(moduleId); },
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
    flowPicker.classList.remove("is-visible");
    if (moduleContracts) moduleContracts.classList.remove("is-visible");
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
        ${isCall ? `<span class="method-source-call">调用</span>` : ""}
      </div>`;
    }).join("");

    const ownerClass = detail.ownerClassId
      ? (moduleGraphById.get(detail.moduleId)?.nodes || []).find(node => node.id === detail.ownerClassId)
      : null;
    const module = projectModuleById.get(detail.moduleId);
    const executionOnly = detail.isExecutionOnly === true;
    const nonCapabilitySurface = detail.functionSurface === "execution" || detail.functionSurface === "internal";
    const providerRole = nonCapabilitySurface ? "" : (detail.providerRole || ownerClass?.providerRole || "");
    const executionRole = detail.executionRole
      ? `execution:${detail.executionRole}`
      : executionOnly ? "execution:orchestrator" : "";
    const surfaceBadge = detail.functionSurface && !executionOnly
      ? `surface:${detail.functionSurface}`
      : "";
    const badges = [
      detail.methodKind || "function",
      executionRole,
      surfaceBadge,
      providerRole ? `role:${providerRole}` : "",
      detail.visibility || "public",
      `api:${detail.apiExposure || "public"}`,
      detail.apiExposureSource ? `source:${detail.apiExposureSource}` : "",
      detail.isAsync ? "async" : "",
      detail.isAbstract ? "abstract" : "",
      detail.overrideOfFunctionId ? "override" : "",
      ...(detail.userSurfaceKinds || []).map(kind => `surface:${kind}`),
      Number(detail.polymorphicCallerCount || 0) ? `poly-callers:${detail.polymorphicCallerCount}` : "",
      Number(detail.unresolvedCallerCount || 0) ? `unresolved-callers:${detail.unresolvedCallerCount}` : "",
    ].filter(Boolean);

    world.innerHTML = `<div class="method-page">
      <header class="method-page-head">
        <div class="eyebrow">方法详情</div>
        <h1 class="method-page-title">${escapeHtml(detail.name)}<span>()</span></h1>
        <div class="method-signature">${escapeHtml(detail.signature || "")}</div>
        <div class="method-badges">${badges.map(item => `<span class="method-badge">${escapeHtml(item)}</span>`).join("")}</div>
        <div class="method-location">${escapeHtml(detail.file || "")}:${detail.line || "—"}${ownerClass ? ` · ${escapeHtml(ownerClass.name)}` : ""}${module ? ` · ${escapeHtml(module.name)}` : ""}</div>
      </header>
      <div class="method-page-grid">
        <section class="method-source-panel">
          <div class="method-panel-heading"><span>源码</span><em>${escapeHtml(source.language || "python")} · ${source.startLine || detail.line}-${source.endLine || detail.endLine}${source.truncated ? " · 已截断" : ""}</em></div>
          <div class="method-source">${sourceRows || `<div class="method-call-empty">源码不可用</div>`}</div>
        </section>
        <aside class="method-calls-panel">
          <section>
            <div class="method-panel-heading"><span>调用者</span><em>${detail.callerCount || 0}</em></div>
            ${methodCallList(detail.callers || [], "暂无调用者")}
          </section>
          <section>
            <div class="method-panel-heading"><span>被调用者</span><em>${detail.calleeCount || 0}</em></div>
            ${methodCallList(detail.callees || [], "暂无被调用者")}
          </section>
          ${(detail.unresolvedCallers || []).length ? `<section>
            <div class="method-panel-heading"><span>可能的未解析调用者</span><em>${detail.unresolvedCallerCount || 0}</em></div>
            ${methodCallList(detail.unresolvedCallers, "暂无未解析调用者")}
          </section>` : ""}
          ${(detail.polymorphicCallers || []).length ? `<section>
            <div class="method-panel-heading"><span>多态调用者</span><em>${detail.polymorphicCallerCount || 0}</em></div>
            ${polymorphicCallList(detail.polymorphicCallers, "暂无多态调用者")}
          </section>` : ""}
          ${(detail.polymorphicCallees || []).length ? `<section>
            <div class="method-panel-heading"><span>多态被调用者</span><em>${detail.polymorphicCalleeCount || 0}</em></div>
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
      ? `<div class="source-line">所属类：${escapeHtml(ownerClass.qualifiedName || ownerClass.name)}</div>`
      : "";
    detailScroll.innerHTML = `<div class="eyebrow">语义契约</div>
      <h2 class="detail-name" style="font-family:var(--mono);font-size:15px">${escapeHtml(detail.qualifiedName)}</h2>
      <div class="detail-note">${escapeHtml(detail.note || "暂无函数备注")}</div>
      <div class="port-detail"><span>API <b>${escapeHtml(detail.apiExposure || "public")}</b></span><span>来源 <b>${escapeHtml(detail.apiExposureSource || "naming")}</b></span><span>返回 <b>${escapeHtml(detail.returns || "—")}</b></span><span>异常 <b>${escapeHtml((detail.raises || []).join(" / ") || "—")}</b></span></div>
      ${ownerLine}
      ${detail.overrideOfFunctionId ? `<div class="source-line">覆写自 <code>${escapeHtml(detail.overrideOfFunctionId)}</code></div>` : ""}
      ${(detail.overriddenByFunctionIds || []).length ? `<div class="source-line">被覆写：${detail.overriddenByFunctionIds.map(id => `<code>${escapeHtml(id)}</code>`).join(" ")}</div>` : ""}
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
    else if (route.kind === "flow") renderFlowPage(route.flowId);
    else if (route.kind === "scope") renderFlowPage(route.flowId, route.nodeId);
    else if (route.kind === "dispatch") {
      renderFlowPage(route.flowId, null, route.nodeId, route.candidateScopeId);
    }
    else renderProjectPage();
  }

  function applySearch() {
    const query = state.search.trim().toLowerCase();
    if (!query || state.pageKind === "method") {
      world.querySelectorAll(".node-card").forEach(node => node.classList.remove("is-search-dim"));
      world.querySelectorAll(".macro-edge, .execution-edge").forEach(edge => edge.classList.remove("is-search-dim"));
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
    } else if (state.pageKind === "flow" || state.pageKind === "scope" || state.pageKind === "dispatch") {
      state.nodes.forEach((node, uid) => {
        const haystack = [node.label, node.note, node.condition, node.loopKind, node.iterable, node.loopVariable, node.moduleName, node.capabilityKind, node.usageKind, node.expression, node.callableKind, node.ownerClassName]
          .filter(Boolean).join(" ").toLowerCase();
        world.querySelector(`.execution-node[data-uid="${cssEscape(uid)}"]`)?.classList.toggle("is-search-dim", !haystack.includes(query));
      });
    } else if (state.pageKind === "module") {
      state.nodes.forEach((node, uid) => {
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
  $("saveBtn").addEventListener("click", () => { persistOverride(); showToast("布局已保存到浏览器"); });
  $("resetBtn").addEventListener("click", () => { resetOverride(); renderRoute(); showToast("已恢复默认布局"); });
  $("fitBtn").addEventListener("click", () => fitView());
  $("zoomIn").addEventListener("click", () => zoomAt(1.16));
  $("zoomOut").addEventListener("click", () => zoomAt(1 / 1.16));
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
  let panOrigin = null;
  let suppressBackgroundClick = false;
  viewport.addEventListener("pointerdown", event => {
    if (state.pageKind === "method") return;
    if (event.button !== 0 || event.target.closest(".node-card, button, input, .detail-panel")) return;
    panning = true;
    panOrigin = { x: event.clientX, y: event.clientY };
    panStart = { x: event.clientX - state.x, y: event.clientY - state.y };
    suppressBackgroundClick = false;
    viewport.classList.add("is-panning");
    viewport.setPointerCapture(event.pointerId);
  });
  viewport.addEventListener("pointermove", event => {
    if (!panning) return;
    if (panOrigin && Math.hypot(event.clientX - panOrigin.x, event.clientY - panOrigin.y) > 4) {
      suppressBackgroundClick = true;
    }
    state.x = event.clientX - panStart.x;
    state.y = event.clientY - panStart.y;
    applyTransform();
  });
  const endPan = () => { panning = false; viewport.classList.remove("is-panning"); };
  viewport.addEventListener("pointerup", endPan);
  viewport.addEventListener("pointercancel", endPan);
  viewport.addEventListener("click", event => {
    if (state.pageKind === "method") return;
    if (event.target.closest(".node-card, button, input, .detail-panel")) return;
    if (suppressBackgroundClick) {
      suppressBackgroundClick = false;
      return;
    }
    if (state.selectedUid || state.hoveredUid) clearSelection();
  });
  viewport.addEventListener("dblclick", event => {
    if (state.pageKind === "method") return;
    if (event.target.closest(".node-card, button, input, .detail-panel")) return;
    if (state.selectedUid || state.hoveredUid) clearSelection();
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
  if (!location.hash) history.replaceState({ kind: "project" }, "", "#/project");
  applyTransform();
  renderRoute();
})();
