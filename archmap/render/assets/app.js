(() => {
  "use strict";

  const DATA = window.__ARCHMAP_DATA__;
  if (!DATA) throw new Error("ArchMap data missing");

  const projectGraph = DATA.projectGraph;
  const moduleGraphs = DATA.moduleGraphs || [];
  const functionFlows = DATA.functionFlows || [];
  const annotations = DATA.annotations || { version: 1, nodes: {} };
  const moduleGraphById = new Map(moduleGraphs.map(item => [item.moduleId, item]));
  const flowById = new Map(functionFlows.map(item => [item.id, item]));
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
  const singleModeBtn = $("singleModeBtn");
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
    suppressClickUntil: 0,
    pageKind: "project",
    pageEdges: [],
    nodes: new Map(),
    sizes: new Map(),
    moduleId: null,
    functionId: null,
  };

  let override = loadOverrides();

  function defaultOverride() {
    return {
      version: OVERRIDE_VERSION,
      geometryVersion: GEOMETRY_VERSION,
      project: { nodes: {}, miniNodes: {}, expanded: {}, singleModule: false },
      modules: {},
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
    const padTop = state.pageKind === "function" ? 26 : 64;
    const padBottom = 46;
    const scale = Math.min(
      (rect.width - padX * 2) / Math.max(1, width),
      (rect.height - padTop - padBottom) / Math.max(1, height),
      1
    );
    const minScale = state.pageKind === "function" ? .5 : .2;
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
    if (kind === "input") return `<span class="legend-item"><span class="legend-swatch"></span>${escapeHtml(text)}</span>`;
    if (kind === "output") return `<span class="legend-item"><span class="legend-swatch out"></span>${escapeHtml(text)}</span>`;
    if (kind === "dashed") return `<span class="legend-item"><span class="legend-line dashed"></span>${escapeHtml(text)}</span>`;
    return `<span class="legend-item"><span class="legend-line"></span>${escapeHtml(text)}</span>`;
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
      const inputs = projectGraph.boundaryNodes.filter(node => node.kind === "input").map(node => node.label);
      const outputs = projectGraph.boundaryNodes.filter(node => node.kind === "output").map(node => node.label);
      detailScroll.innerHTML = `<div class="eyebrow">Project page</div>
        <h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(DATA.project.name)}</h2>
        <div class="detail-note">项目页仅展示逻辑模块。模块保留人工备注、输入与输出；文件路径只作为函数节点的源码证据。</div>
        <div class="port-detail"><span>项目输入 <b>${escapeHtml(inputs.join(" / ") || "—")}</b></span><span>项目输出 <b>${escapeHtml(outputs.join(" / ") || "—")}</b></span></div>
        ${annotationBlock(DATA.project.name)}
        <div class="empty-hint">单击节点查看备注与 LLM 语义占位；双击模块或点击 ↗ 进入独立模块页面。</div>`;
      return;
    }
    if (state.route.kind === "module") {
      const module = moduleGraphById.get(state.route.moduleId);
      if (!module) return;
      detailScroll.innerHTML = `<div class="detail-head" style="--mc:${module.color}"><div class="detail-color"></div><div>
          <div class="eyebrow">Module node</div><h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(module.name)}</h2>
          <div class="detail-module">module://${escapeHtml(module.moduleId)}</div></div></div>
        <div class="detail-note">${escapeHtml(module.note || "暂无模块备注")}</div>
        <div class="port-detail"><span>输入 <b>${escapeHtml(module.inputs.map(item => item.label).join(" / "))}</b></span><span>输出 <b>${escapeHtml(module.outputs.map(item => item.label).join(" / "))}</b></span></div>
        ${annotationBlock(module.moduleId)}
        <div class="empty-hint">双击函数节点进入真实执行流页面。</div>`;
      return;
    }
    const flow = flowById.get(state.route.functionId);
    if (!flow) return;
    const module = projectModuleById.get(flow.moduleId);
    detailScroll.innerHTML = `<div class="detail-head" style="--mc:${module?.color || "#60a5fa"}"><div class="detail-color"></div><div>
        <div class="eyebrow">Function execution flow</div><h2 class="detail-name">${escapeHtml(flow.name)}</h2>
        <div class="detail-module">${escapeHtml(module?.name || flow.moduleId)} · ${escapeHtml(flow.module)}</div></div></div>
      <div class="detail-note">${escapeHtml(flow.note || "暂无函数备注")}</div>
      <div class="source-line">${escapeHtml(flow.file)}:${flow.line} · ${escapeHtml(flow.signature)}</div>
      ${annotationBlock(flow.id, flow.sourceHash)}
      <div class="empty-hint">单击执行流节点查看步骤、源码位置与调用目标。</div>`;
  }

  function renderSelectionDetail(uid) {
    const macroNode = state.nodes.get(uid);
    if (macroNode) {
      if (macroNode.kind === "input" || macroNode.kind === "output") {
        detailScroll.innerHTML = `<div class="eyebrow">Boundary node</div>
          <h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(macroNode.label)}</h2>
          <div class="detail-note">${escapeHtml(macroNode.note || "")}</div>
          <div class="port-detail"><span>类型 <b>${macroNode.kind === "input" ? "输入" : "输出"}</b></span></div>
          ${annotationBlock(uid)}`;
        return;
      }
      if (macroNode.kind === "module") {
        const graph = moduleGraphById.get(uid);
        detailScroll.innerHTML = `<div class="detail-head" style="--mc:${macroNode.color}"><div class="detail-color"></div><div>
            <div class="eyebrow">Module node</div><h2 class="detail-name" style="font-family:var(--font);font-size:18px">${escapeHtml(macroNode.name)}</h2>
            <div class="detail-module">module://${escapeHtml(uid)}</div></div></div>
          <div class="detail-note">${escapeHtml(macroNode.note || "暂无模块备注")}</div>
          <div class="port-detail"><span>输入 <b>${escapeHtml((macroNode.inputs || []).map(item => item.label).join(" / "))}</b></span><span>输出 <b>${escapeHtml((macroNode.outputs || []).map(item => item.label).join(" / "))}</b></span></div>
          <div class="source-line">${escapeHtml((macroNode.sourceFiles || []).join("\n"))}</div>
          ${annotationBlock(uid)}
          <div class="detail-actions"><button class="detail-action" type="button" data-open-module-detail="${escapeHtml(uid)}">打开模块页面</button></div>`;
        detailScroll.querySelector("[data-open-module-detail]")?.addEventListener("click", () => navigate({ kind: "module", moduleId: uid }));
        return;
      }
      if (macroNode.kind === "function") {
        const flow = flowById.get(macroNode.functionFlowId);
        detailScroll.innerHTML = `<div class="detail-head" style="--mc:${macroNode.color || "#60a5fa"}"><div class="detail-color"></div><div>
            <div class="eyebrow">Function node</div><h2 class="detail-name">${escapeHtml(macroNode.name)}</h2>
            <div class="detail-module">${escapeHtml(macroNode.qualifiedName || "")}</div></div></div>
          <div class="detail-note">${escapeHtml(macroNode.note || "暂无函数备注")}</div>
          <div class="source-line">${escapeHtml(macroNode.file)}:${macroNode.line}</div>
          ${annotationBlock(macroNode.functionFlowId, flow?.sourceHash)}
          <div class="detail-actions"><button class="detail-action" type="button" data-open-flow-detail="${escapeHtml(macroNode.functionFlowId)}">打开函数执行流</button></div>`;
        detailScroll.querySelector("[data-open-flow-detail]")?.addEventListener("click", () => {
          const target = flowById.get(macroNode.functionFlowId);
          if (target) navigate({ kind: "function", moduleId: target.moduleId, functionId: target.id });
        });
        return;
      }
    }
    if (state.route.kind === "function") {
      const flow = flowById.get(state.route.functionId);
      const node = flow?.nodes.find(item => item.id === uid);
      if (flow && node) {
        const call = node.call;
        detailScroll.innerHTML = `<div class="eyebrow">${escapeHtml(String(node.stepType || node.type).toUpperCase())}</div>
          <h2 class="detail-name" style="font-family:var(--mono);font-size:14px">${escapeHtml(node.code || node.id)}</h2>
          <div class="source-line">${node.file ? `${escapeHtml(node.file)}:${node.line}` : "synthetic node"}</div>
          <div class="detail-code">${escapeHtml(node.code || "")}</div>
          ${call ? `<div class="port-detail"><span>调用 <b>${escapeHtml(call.qualifiedName || call.name)}</b></span><span>${call.resolved ? "已解析" : call.external ? "外部" : "未解析"}</span></div>` : ""}
          ${node.data ? `<div class="port-detail"><span>defs <b>${escapeHtml((node.data.defs || []).join(", ") || "—")}</b></span><span>uses <b>${escapeHtml((node.data.uses || []).join(", ") || "—")}</b></span></div>` : ""}
          ${call?.resolved && call.targetFunctionId && flowById.has(call.targetFunctionId) ? `<div class="detail-actions"><button class="detail-action" type="button" data-open-call-target="${escapeHtml(call.targetFunctionId)}">打开调用目标</button></div>` : ""}`;
        detailScroll.querySelector("[data-open-call-target]")?.addEventListener("click", () => {
          const target = flowById.get(call.targetFunctionId);
          if (target) navigate({ kind: "function", moduleId: target.moduleId, functionId: target.id });
        });
        return;
      }
    }
    renderDefaultDetail();
  }

  function updateChrome(kind) {
    const module = state.route.moduleId ? projectModuleById.get(state.route.moduleId) : null;
    const flow = state.route.functionId ? flowById.get(state.route.functionId) : null;
    if (kind === "project") {
      canvasKicker.textContent = "Project topology";
      canvasTitle.textContent = DATA.project.name;
      canvasSub.textContent = "模块是项目页的节点 · 拖拽调整布局 · 双击进入模块页面";
      breadcrumb.innerHTML = `<b>${escapeHtml(DATA.project.name)}</b>`;
      legend.innerHTML = legendItem("line", "模块调用/数据关系") + legendItem("input", "用户输入") + legendItem("output", "用户输出");
    } else if (kind === "module") {
      canvasKicker.textContent = "Module topology";
      canvasTitle.textContent = module?.name || state.route.moduleId;
      canvasSub.textContent = "函数节点展示名称与人工备注 · 双击进入真实执行流";
      breadcrumb.innerHTML = `<button type="button" data-nav="project">${escapeHtml(DATA.project.name)}</button><span class="slash">/</span><b>${escapeHtml(module?.name || state.route.moduleId)}</b>`;
      legend.innerHTML = legendItem("line", "函数调用/数据关系") + legendItem("input", "模块输入") + legendItem("output", "模块输出");
    } else {
      canvasKicker.textContent = "Function execution flow";
      canvasTitle.textContent = flow?.name || state.route.functionId;
      canvasSub.textContent = "ENTRY → 步骤 / 分支 / 循环 → EXIT · 双击调用步骤可跳转目标";
      breadcrumb.innerHTML = `<button type="button" data-nav="project">${escapeHtml(DATA.project.name)}</button><span class="slash">/</span><button type="button" data-nav="module" data-module="${escapeHtml(state.route.moduleId)}">${escapeHtml(module?.name || state.route.moduleId)}</button><span class="slash">/</span><b>${escapeHtml(flow?.name || state.route.functionId)}</b>`;
      legend.innerHTML = legendItem("line", "控制流") + legendItem("dashed", "回边 / 异常") + legendItem("input", "数据依赖");
    }
    breadcrumb.querySelectorAll("[data-nav]").forEach(button => {
      button.addEventListener("click", () => {
        if (button.dataset.nav === "project") navigate({ kind: "project" });
        if (button.dataset.nav === "module") navigate({ kind: "module", moduleId: button.dataset.module });
      });
    });
    $("pageHint").textContent = kind === "project" ? "项目页" : kind === "module" ? "模块页" : "执行流页";
    searchWrap.classList.toggle("is-disabled", kind === "function");
    if (kind === "function") searchInput.value = "";
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
    updateChrome("project");
    world.innerHTML = "";
    world.classList.remove("page-enter");
    const visibleModuleIds = state.singleModule && projectGraph.modules.length
      ? [projectGraph.modules[0].id]
      : projectGraph.modules.map(item => item.id);
    state.nodes = new Map();
    projectGraph.boundaryNodes.forEach(node => state.nodes.set(node.id, { ...node }));
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
    state.pageEdges = projectGraph.edges.filter(edge => state.nodes.has(edge.from) && state.nodes.has(edge.to));
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
      if (node.kind === "input" || node.kind === "output") {
        renderProjectBoundary(nodeId, node);
      } else {
        renderProjectModule(nodeId, node);
      }
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

  function renderProjectBoundary(nodeId, node) {
    const position = state.positions.get(nodeId);
    const element = document.createElement("article");
    element.className = `node-card boundary-node ${node.kind === "output" ? "output" : "input"}`;
    element.dataset.uid = nodeId;
    element.style.left = `${position.x}px`;
    element.style.top = `${position.y}px`;
    element.style.width = `${position.w}px`;
    element.style.height = `${position.h}px`;
    element.innerHTML = `<div class="boundary-kicker">${node.kind === "input" ? "USER INPUT / PROJECT INPUT" : "USER OUTPUT / PROJECT OUTPUT"}</div>
      <div class="boundary-name">${escapeHtml(node.label)}</div>
      <div class="boundary-note">${escapeHtml(node.note || "")}</div>`;
    world.appendChild(element);
    bindNodeHover(element, nodeId);
    element.addEventListener("click", () => selectUid(nodeId));
    attachDrag(element, element, {
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
  }

  function renderProjectModule(nodeId, module) {
    const position = state.positions.get(nodeId);
    const expanded = projectNodeExpanded(nodeId);
    const size = state.sizes.get(nodeId);
    const element = document.createElement("article");
    element.className = `node-card module-node${expanded ? " is-expanded" : ""}`;
    element.dataset.uid = nodeId;
    element.style.left = `${position.x}px`;
    element.style.top = `${position.y}px`;
    element.style.width = `${size.w}px`;
    element.style.height = `${size.h}px`;
    element.style.setProperty("--mc", module.color || "#f59e0b");
    element.style.setProperty("--mc-rgb", rgbFromHex(module.color || "#f59e0b"));
    element.innerHTML = `<header class="module-header">
        <div class="module-title-row">
          <span class="module-dot"></span><span class="module-kind">MODULE</span>
          <span class="module-title">${escapeHtml(module.name)}</span>
          <div class="module-actions">
            <button class="mini-action" type="button" data-expand="${escapeHtml(nodeId)}" aria-label="${expanded ? "收起模块" : "展开模块"}" title="${expanded ? "收起" : "展开"}">${expanded ? "−" : "+"}</button>
            <button class="mini-action" type="button" data-open-module="${escapeHtml(nodeId)}" aria-label="打开模块页面" title="打开独立模块页面">↗</button>
          </div>
        </div>
        <div class="module-note">${escapeHtml(module.note || "暂无模块备注")}</div>
        <div class="module-ports">${(module.inputs || []).map(port => `<span class="port-pill in"><i></i>IN <b>${escapeHtml(port.label)}</b></span>`).join("")}${(module.outputs || []).map(port => `<span class="port-pill out"><i></i>OUT <b>${escapeHtml(port.label)}</b></span>`).join("")}</div>
      </header>`;
    if (expanded) {
      const mini = document.createElement("div");
      mini.className = "module-mini";
      mini.dataset.moduleId = nodeId;
      element.appendChild(mini);
    }
    world.appendChild(element);
    bindNodeHover(element, nodeId);
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
    const functions = graph.nodes.filter(node => node.kind === "function");
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
    graph.nodes.filter(node => node.kind === "function").forEach(node => {
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
    const edges = graph.edges.filter(edge => edge.role === "internal");
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
    graph.nodes.filter(node => node.kind === "function").forEach(node => {
      const pos = getMiniPosition(moduleId, node.id, defaults);
      const element = document.createElement("article");
      element.className = "mini-node node-card";
      element.dataset.uid = node.id;
      element.style.left = `${pos.x}px`;
      element.style.top = `${pos.y}px`;
      element.style.width = "176px";
      element.style.height = "76px";
      element.innerHTML = `<div class="mini-title">${escapeHtml(node.name)}</div><div class="mini-note">${escapeHtml(node.note || "暂无备注")}</div>`;
      host.appendChild(element);
      bindNodeHover(element, node.id);
      element.addEventListener("click", event => {
        event.stopPropagation();
        state.nodes.set(node.id, { ...node, kind: "function", color: graph.color });
        selectUid(node.id);
      });
      element.addEventListener("dblclick", event => {
        event.stopPropagation();
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
    return node.kind === "function" ? { w: node.w || 210, h: node.h || 98 } : { w: node.w || 190, h: node.h || 96 };
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
    updateChrome("module");
    world.innerHTML = "";
    world.classList.remove("page-enter");
    state.nodes = new Map();
    graph.nodes.forEach(node => {
      if (node.kind === "function") {
        state.nodes.set(node.id, { ...node, kind: "function", color: graph.color });
      } else {
        state.nodes.set(node.id, { ...node, kind: node.kind === "input" ? "input" : "output" });
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
      else renderModuleBoundary(moduleId, nodeId, node);
    });
    updateModuleWorldSize(moduleId);
    refreshModuleEdges();
    world.classList.add("page-enter");
    requestAnimationFrame(() => {
      applyTransform();
      fitView();
      renderDefaultDetail();
      if (state.search) applySearch();
    });
  }

  function renderModuleBoundary(moduleId, nodeId, node) {
    const pos = state.positions.get(nodeId);
    const element = document.createElement("article");
    element.className = `node-card boundary-node ${node.kind === "output" ? "output" : "input"}`;
    element.dataset.uid = nodeId;
    element.style.left = `${pos.x}px`;
    element.style.top = `${pos.y}px`;
    element.style.width = `${pos.w}px`;
    element.style.height = `${pos.h}px`;
    element.innerHTML = `<div class="boundary-kicker">${node.kind === "input" ? "MODULE INPUT" : "MODULE OUTPUT"}</div>
      <div class="boundary-name">${node.kind === "input" ? "模块输入" : "模块输出"}</div>
      <div class="boundary-note">${escapeHtml(node.label)}</div>`;
    world.appendChild(element);
    bindNodeHover(element, nodeId);
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
    element.innerHTML = `<div class="fn-node-top"><span class="fn-node-icon">ƒ</span><span class="fn-node-kind">FUNCTION</span></div>
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

  const FLOW_COLORS = {
    next: "#475569", true: "#16a34a", false: "#dc2626", loop_body: "#2563eb",
    loop_exit: "#64748b", back: "#f59e0b", break: "#f59e0b", continue: "#f59e0b",
    return: "#7c3aed", exception: "#dc2626", merge: "#94a3b8", data_dep: "#a855f7",
  };

  function flowEdgeColor(edge) {
    if (edge.type === "data_dep") return FLOW_COLORS.data_dep;
    return FLOW_COLORS[edge.flow] || FLOW_COLORS.next;
  }

  function flowDash(edge) {
    if (edge.type === "data_dep") return "5 4";
    if (["back", "break", "continue", "exception"].includes(edge.flow)) return "6 4";
    return "";
  }

  function flowMarkerId(edge) {
    if (edge.type === "data_dep") return "arrow-data";
    return `arrow-${edge.flow || "next"}`;
  }

  function renderFlowSvg(flow) {
    const layout = flow.layout;
    const width = layout.canvas.width;
    const height = layout.canvas.height;
    const nodeMap = new Map(flow.nodes.map(node => [node.id, node]));
    const colorSet = new Set(["next", "true", "false", "loop_body", "loop_exit", "back", "break", "continue", "return", "exception", "merge", "data_dep"]);
    const defs = [...colorSet].map(key => {
      const color = FLOW_COLORS[key] || FLOW_COLORS.next;
      return `<marker id="arrow-${key}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0 0 L8 4 L0 8 Z" fill="${color}"></path></marker>`;
    }).join("");
    const edges = [...flow.edges].sort((a, b) => {
      const priority = edge => edge.type === "data_dep" ? 0 : 1;
      return priority(a) - priority(b);
    });
    const edgeMarkup = edges.map(edge => {
      if (!edge.d) return "";
      const color = flowEdgeColor(edge);
      const dash = flowDash(edge);
      const opacity = edge.type === "data_dep" ? ".78" : ".92";
      const dashAttr = dash ? ` stroke-dasharray="${dash}"` : "";
      const label = edge.label || edge.variable || "";
      const labelPos = layout.edges?.[edge.id]?.label;
      const labelMarkup = label && labelPos
        ? `<text class="flow-label" x="${labelPos.x}" y="${labelPos.y}" text-anchor="start" fill="${color}">${escapeXml(truncate(label, 26))}</text>`
        : "";
      return `<path d="${edge.d}" data-from="${escapeXml(edge.from)}" data-to="${escapeXml(edge.to)}" data-edge-type="${escapeXml(edge.type)}" fill="none" stroke="${color}" stroke-width="${edge.type === "data_dep" ? 1.4 : 1.6}" stroke-linecap="round" stroke-linejoin="round"${dashAttr} opacity="${opacity}" marker-end="url(#${flowMarkerId(edge)})"></path>${labelMarkup}`;
    }).join("");
    const nodeMarkup = flow.nodes.map(node => {
      const rect = layout.nodes[node.id];
      const x = rect.x, y = rect.y, w = rect.w, h = rect.h;
      const common = `class="flow-node" data-uid="${escapeXml(node.id)}" tabindex="0" role="button" style="pointer-events:all;cursor:pointer"`;
      if (node.type === "entry" || node.type === "exit") {
        const isEntry = node.type === "entry";
        return `<g ${common} aria-label="${isEntry ? "ENTRY" : "EXIT"}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${h / 2}" fill="${isEntry ? "#ecfdf5" : "#fff1f2"}" stroke="${isEntry ? "#059669" : "#e11d48"}" stroke-width="1.5"></rect><text x="${x + w / 2}" y="${y + h / 2 + 4}" text-anchor="middle" class="flow-node-title" fill="${isEntry ? "#047857" : "#be123c"}" letter-spacing=".08em">${isEntry ? "ENTRY" : "EXIT"}</text></g>`;
      }
      if (node.type === "branch") {
        return `<g ${common} aria-label="${escapeXml(truncate(node.code, 60))}"><polygon points="${x + 16},${y} ${x + w - 16},${y} ${x + w},${y + h / 2} ${x + w - 16},${y + h} ${x + 16},${y + h} ${x},${y + h / 2}" fill="#fffbeb" stroke="#f59e0b" stroke-width="1.5"></polygon><text x="${x + w / 2}" y="${y + h / 2 + 4}" text-anchor="middle" class="flow-node-code" fill="#334155">${escapeXml(truncate(node.code, 34))}</text></g>`;
      }
      if (node.type === "loop") {
        return `<g ${common} aria-label="${escapeXml(truncate(node.code, 60))}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10" fill="#eff6ff" stroke="#2563eb" stroke-width="1.5"></rect><text x="${x + 14}" y="${y + h / 2 + 4}" class="flow-node-code" fill="#1d4ed8">↻ ${escapeXml(truncate(node.code, 31))}</text></g>`;
      }
      if (node.type === "merge") {
        return `<g ${common} aria-label="汇合节点"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${h / 2}" fill="#f1f5f9" stroke="#94a3b8"></rect><text x="${x + w / 2}" y="${y + h / 2 + 4}" text-anchor="middle" style="font-size:10px" fill="#64748b">汇合</text></g>`;
      }
      const stepType = String(node.stepType || "step").toUpperCase();
      const accent = {
        assign: "#0ea5e9", aug_assign: "#0ea5e9", ann_assign: "#0ea5e9",
        call: "#2563eb", await: "#0891b2", return: "#7c3aed", yield: "#7c3aed",
        raise: "#dc2626", try: "#64748b", match: "#64748b", read: "#f59e0b",
        write: "#ea580c", emit: "#db2777", consume: "#db2777", break: "#f59e0b",
        continue: "#f59e0b", with: "#64748b", assert: "#64748b", delete: "#dc2626", pass: "#94a3b8",
      }[node.stepType] || "#64748b";
      const badge = node.call?.recursive ? "↺" : node.call?.external ? "↗" : node.call && !node.call.resolved ? "?" : "";
      return `<g ${common} aria-label="${escapeXml(stepType + " " + truncate(node.code, 60))}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="#ffffff" stroke="#cbd5e1"></rect><rect x="${x}" y="${y}" width="4" height="${h}" rx="2" fill="${accent}"></rect><text x="${x + 14}" y="${y + 19}" style="font-size:10px;letter-spacing:.05em" fill="${accent}" font-weight="700">${escapeXml(stepType)}${badge ? ` ${escapeXml(badge)}` : ""}</text><text x="${x + 14}" y="${y + 39}" class="flow-node-code" fill="#1e293b">${escapeXml(truncate(node.code, 28))}</text></g>`;
    }).join("");
    return `<svg class="function-flow-svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg"><defs>${defs}</defs><g class="flow-edges">${edgeMarkup}</g><g class="flow-nodes">${nodeMarkup}</g></svg>`;
  }

  function flowFocus(uid) {
    const flow = flowById.get(state.route.functionId);
    if (!flow) return;
    const neighbor = new Set([uid]);
    flow.edges.forEach(edge => {
      if (edge.from === uid || edge.to === uid) {
        neighbor.add(edge.from);
        neighbor.add(edge.to);
      }
    });
    world.querySelectorAll(".flow-node").forEach(node => {
      node.style.opacity = neighbor.has(node.dataset.uid) ? "1" : ".22";
    });
    world.querySelectorAll(".flow-edges path").forEach(path => {
      path.style.opacity = path.dataset.from === uid || path.dataset.to === uid ? "1" : ".12";
    });
  }

  function clearFlowFocus() {
    world.querySelectorAll(".flow-node").forEach(node => { node.style.opacity = "1"; });
    world.querySelectorAll(".flow-edges path").forEach(path => { path.style.opacity = ""; });
  }

  function renderFunctionPage(moduleId, functionId) {
    const flow = flowById.get(functionId);
    if (!flow) {
      navigate({ kind: "module", moduleId }, false);
      return;
    }
    state.pageKind = "function";
    state.moduleId = moduleId;
    state.functionId = functionId;
    viewport.classList.add("is-light");
    updateChrome("function");
    world.innerHTML = renderFlowSvg(flow);
    const svg = world.querySelector(".function-flow-svg");
    world.style.width = `${flow.layout.canvas.width}px`;
    world.style.height = `${flow.layout.canvas.height}px`;
    if (svg) {
      svg.style.width = `${flow.layout.canvas.width}px`;
      svg.style.height = `${flow.layout.canvas.height}px`;
    }
    world.classList.remove("page-enter");
    world.querySelectorAll(".flow-node").forEach(element => {
      element.addEventListener("click", () => {
        selectUid(element.dataset.uid);
        flowFocus(element.dataset.uid);
      });
      element.addEventListener("dblclick", () => {
        const node = flow.nodes.find(item => item.id === element.dataset.uid);
        const target = node?.call?.targetFunctionId;
        const targetFlow = target ? flowById.get(target) : null;
        if (targetFlow) navigate({ kind: "function", moduleId: targetFlow.moduleId, functionId: targetFlow.id });
      });
    });
    requestAnimationFrame(() => {
      applyTransform();
      fitView();
      renderDefaultDetail();
    });
  }

  function renderRoute() {
    state.selectedUid = null;
    state.hoveredUid = null;
    state.search = "";
    searchInput.value = "";
    const route = parseRoute();
    state.route = route;
    if (route.kind === "function") renderFunctionPage(route.moduleId, route.functionId);
    else if (route.kind === "module") renderModulePage(route.moduleId);
    else renderProjectPage();
  }

  function applySearch() {
    const query = state.search.trim().toLowerCase();
    if (!query || state.pageKind === "function") {
      world.querySelectorAll(".node-card, .mini-node").forEach(node => node.classList.remove("is-search-dim"));
      world.querySelectorAll(".macro-edge").forEach(edge => edge.classList.remove("is-search-dim"));
      return;
    }
    if (state.pageKind === "project") {
      state.nodes.forEach((node, uid) => {
        if (node.kind !== "module") return;
        const graph = moduleGraphById.get(uid);
        const haystack = [
          node.name, node.note, ...(node.inputs || []).map(item => item.label), ...(node.outputs || []).map(item => item.label),
          ...(graph?.nodes || []).filter(item => item.kind === "function").flatMap(item => [item.name, item.note]),
        ].join(" ").toLowerCase();
        world.querySelector(`.module-node[data-uid="${cssEscape(uid)}"]`)?.classList.toggle("is-search-dim", !haystack.includes(query));
      });
      world.querySelectorAll(".boundary-node").forEach(node => node.classList.remove("is-search-dim"));
    } else if (state.pageKind === "module") {
      state.nodes.forEach((node, uid) => {
        if (node.kind !== "function") return;
        const haystack = [node.name, node.note].join(" ").toLowerCase();
        world.querySelector(`.function-node[data-uid="${cssEscape(uid)}"]`)?.classList.toggle("is-search-dim", !haystack.includes(query));
      });
    }
  }

  // Global controls.
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
    if (event.target.closest(".detail-panel")) return;
    event.preventDefault();
    zoomAt(Math.exp(-event.deltaY * .0015), event.clientX, event.clientY);
  }, { passive: false });

  let panning = false;
  let panStart = null;
  viewport.addEventListener("pointerdown", event => {
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
    if (event.target.closest(".node-card, button, input")) return;
    fitView();
  });

  window.addEventListener("keydown", event => {
    if (event.target.matches("input, textarea")) return;
    if (event.key === "0") fitView();
    if (event.key === "+" || event.key === "=") zoomAt(1.16);
    if (event.key === "-") zoomAt(1 / 1.16);
    if (event.key === "Escape") {
      state.selectedUid = null;
      clearSelection();
      clearFlowFocus();
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
