from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Iterable

from .analysis import AnalysisResult, FunctionInfo
from .callresolver import CallResolver, ResolvedCall


NODE_SIZES = {
    "entry": (132, 36),
    "exit": (132, 36),
    "step": (240, 56),
    "branch": (260, 64),
    "loop": (260, 64),
    "merge": (72, 28),
}


@dataclass
class PlanNode:
    node_id: str
    falls_through: bool = True


@dataclass
class IfPlan:
    branch_id: str
    block_id: str
    then_plan: "SequencePlan"
    else_plan: "SequencePlan | None"
    merge_id: str | None
    falls_through: bool


@dataclass
class LoopPlan:
    loop_id: str
    block_id: str
    body_plan: "SequencePlan"


@dataclass
class SequencePlan:
    block_id: str
    items: list[Any] = field(default_factory=list)
    falls_through: bool = True


@dataclass
class LoopContext:
    loop_id: str
    break_target: str | None


def _compact(source: str) -> str:
    return " ".join(source.strip().split())


class FunctionFlowBuilder:
    def __init__(self, analysis: AnalysisResult, fn: FunctionInfo) -> None:
        self.analysis = analysis
        self.fn = fn
        self.nodes: list[dict[str, Any]] = []
        self.node_by_id: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self.blocks: list[dict[str, Any]] = []
        self.block_by_id: dict[str, dict[str, Any]] = {}
        self.diagnostics: list[dict[str, Any]] = []
        self._node_ordinal = 0
        self._merge_ordinal = 0
        self._block_ordinal = 0
        self._order = 0
        self._edge_ordinal = 0
        self._loop_depth = 0
        self.sequence_plans: dict[str, SequencePlan] = {}
        self.resolver = CallResolver(analysis)
        self.entry_id = self._add_node(
            node_type="entry",
            code="ENTRY",
            synthetic=True,
            block_id="",
        )
        self.exit_id = self._add_node(
            node_type="exit",
            code="EXIT",
            synthetic=True,
            block_id="",
        )
        self.root_block_id = self._add_block("sequence", None, items=[])
        self.node_by_id[self.entry_id]["blockId"] = self.root_block_id
        self.node_by_id[self.exit_id]["blockId"] = self.root_block_id

    # ------------------------------------------------------------------ ids
    def _new_node_id(self) -> str:
        self._node_ordinal += 1
        return f"n:{self.fn.id}:{self._node_ordinal}"

    def _new_merge_id(self) -> str:
        self._merge_ordinal += 1
        return f"n:{self.fn.id}:m{self._merge_ordinal}"

    def _new_block_id(self, kind: str) -> str:
        self._block_ordinal += 1
        return f"b:{self.fn.id}:{kind}{self._block_ordinal}"

    def _add_block(self, kind: str, parent_id: str | None, **extra: Any) -> str:
        block_id = f"b:{self.fn.id}:root" if kind == "sequence" and parent_id is None else self._new_block_id(kind)
        block = {"id": block_id, "kind": kind, "parentId": parent_id}
        block.update(extra)
        if "items" not in block and kind == "sequence":
            block["items"] = []
        self.blocks.append(block)
        self.block_by_id[block_id] = block
        return block_id

    def _add_node(
        self,
        node_type: str,
        code: str,
        synthetic: bool,
        block_id: str,
        *,
        step_type: str | None = None,
        line: int | None = None,
        end_line: int | None = None,
        data: dict[str, list[str]] | None = None,
        call: dict[str, Any] | None = None,
        loop_kind: str | None = None,
        merge_of: str | None = None,
    ) -> str:
        node_id = self._new_node_id()
        width, height = NODE_SIZES[node_type]
        node: dict[str, Any] = {
            "id": node_id,
            "type": node_type,
            "code": code,
            "synthetic": synthetic,
            "blockId": block_id,
            "w": width,
            "h": height,
        }
        if not synthetic:
            node["file"] = self.fn.file
            node["line"] = int(line or self.fn.line)
            node["endLine"] = int(end_line or line or self.fn.line)
        if node_type == "step":
            node["stepType"] = step_type or "pass"
            self._order += 1
            node["order"] = self._order
            node["data"] = data or {"defs": [], "uses": []}
        if call is not None:
            node["call"] = call
        if node_type == "loop":
            node["loopKind"] = loop_kind or "while"
            self._order += 1
            node["order"] = self._order
        if node_type == "branch":
            self._order += 1
            node["order"] = self._order
        if node_type == "merge":
            node["mergeOf"] = merge_of or ""
        self.nodes.append(node)
        self.node_by_id[node_id] = node
        return node_id

    def _add_edge(
        self,
        from_id: str,
        to_id: str,
        *,
        edge_type: str = "next_step",
        flow: str | None = "next",
        label: str | None = None,
        variable: str | None = None,
        resolution: str | None = None,
        confidence: str = "high",
    ) -> None:
        if not from_id or not to_id:
            return
        if any(
            edge["from"] == from_id
            and edge["to"] == to_id
            and edge["type"] == edge_type
            and edge.get("flow") == flow
            and edge.get("variable") == variable
            for edge in self.edges
        ):
            return
        self._edge_ordinal += 1
        edge: dict[str, Any] = {
            "id": f"e:{self.fn.id}:{self._edge_ordinal}",
            "from": from_id,
            "to": to_id,
            "type": edge_type,
            "flow": flow,
            "confidence": confidence,
        }
        if label:
            edge["label"] = label
        if variable is not None:
            edge["variable"] = variable
        if resolution is not None:
            edge["resolution"] = resolution
        self.edges.append(edge)

    # --------------------------------------------------------------- source
    def _snippet(self, node: ast.AST, limit: int = 240) -> str:
        lines = self.analysis.line_cache.get(self.fn.file, [])
        start = max(1, int(getattr(node, "lineno", 1)))
        end = max(start, int(getattr(node, "end_lineno", start) or start))
        text = " ".join(line.strip() for line in lines[start - 1 : end] if line.strip())
        if len(text) > limit:
            text = text[: limit - 1] + "…"
        return text

    def _header(self, node: ast.AST) -> str:
        lines = self.analysis.line_cache.get(self.fn.file, [])
        idx = max(0, int(getattr(node, "lineno", 1)) - 1)
        if idx < len(lines):
            return _compact(lines[idx])
        return self._snippet(node)

    def _names_from_expr(self, node: ast.AST | None) -> list[str]:
        if node is None:
            return []
        result: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                result.add(child.id)
            elif isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
                result.add(child.value.id)
        return sorted(result)

    def _target_names(self, node: ast.AST) -> list[str]:
        result: set[str] = set()
        if isinstance(node, ast.Name):
            result.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for child in node.elts:
                result.update(self._target_names(child))
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            result.add(f"{node.value.id}.{node.attr}")
        return sorted(result)

    def _data_for_statement(self, stmt: ast.stmt) -> dict[str, list[str]]:
        defs: set[str] = set()
        uses: set[str] = set()
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                defs.update(self._target_names(target))
            uses.update(self._names_from_expr(stmt.value))
        elif isinstance(stmt, ast.AnnAssign):
            defs.update(self._target_names(stmt.target))
            uses.update(self._names_from_expr(stmt.value))
            uses.update(self._names_from_expr(stmt.annotation))
        elif isinstance(stmt, ast.AugAssign):
            defs.update(self._target_names(stmt.target))
            uses.update(self._target_names(stmt.target))
            uses.update(self._names_from_expr(stmt.value))
        elif isinstance(stmt, ast.For):
            defs.update(self._target_names(stmt.target))
            uses.update(self._names_from_expr(stmt.iter))
        elif isinstance(stmt, ast.AsyncFor):
            defs.update(self._target_names(stmt.target))
            uses.update(self._names_from_expr(stmt.iter))
        elif isinstance(stmt, ast.While):
            uses.update(self._names_from_expr(stmt.test))
        elif isinstance(stmt, ast.Return):
            uses.update(self._names_from_expr(stmt.value))
        elif isinstance(stmt, ast.Raise):
            uses.update(self._names_from_expr(stmt.exc))
        elif isinstance(stmt, ast.Expr):
            uses.update(self._names_from_expr(stmt.value))
        elif isinstance(stmt, ast.Assert):
            uses.update(self._names_from_expr(stmt.test))
        elif isinstance(stmt, ast.If):
            uses.update(self._names_from_expr(stmt.test))
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                uses.update(self._names_from_expr(item.context_expr))
        return {"defs": sorted(defs), "uses": sorted(uses)}

    def _step_type(self, stmt: ast.stmt) -> str:
        if isinstance(stmt, ast.Assign):
            return "call" if isinstance(stmt.value, (ast.Call, ast.Await)) else "assign"
        if isinstance(stmt, ast.AnnAssign):
            return "call" if isinstance(stmt.value, (ast.Call, ast.Await)) else "ann_assign"
        if isinstance(stmt, ast.AugAssign):
            return "aug_assign"
        if isinstance(stmt, ast.Return):
            return "return"
        if isinstance(stmt, ast.Raise):
            return "raise"
        if isinstance(stmt, (ast.Break,)):
            return "break"
        if isinstance(stmt, (ast.Continue,)):
            return "continue"
        if isinstance(stmt, ast.Assert):
            return "assert"
        if isinstance(stmt, ast.Delete):
            return "delete"
        if isinstance(stmt, ast.Pass):
            return "pass"
        if isinstance(stmt, ast.With):
            return "with"
        if isinstance(stmt, ast.AsyncWith):
            return "with"
        if isinstance(stmt, ast.Try):
            return "try"
        if isinstance(stmt, ast.Match):
            return "match"
        if isinstance(stmt, ast.Expr):
            if isinstance(stmt.value, ast.Await):
                return "await"
            if isinstance(stmt.value, ast.Yield) or isinstance(stmt.value, ast.YieldFrom):
                return "yield"
            if isinstance(stmt.value, ast.Call):
                return "call"
        return "pass"

    def _call_from_stmt(self, stmt: ast.stmt) -> dict[str, Any] | None:
        call_node: ast.Call | None = None
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call_node = stmt.value
        elif isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            call_node = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.value, ast.Call):
            call_node = stmt.value
        elif isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call):
            call_node = stmt.value
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                if isinstance(item.context_expr, ast.Call):
                    call_node = item.context_expr
                    break
        if call_node is None:
            return None
        resolved: ResolvedCall = self.resolver.resolve(call_node, self.fn)
        return resolved.as_dict()

    def _add_step_for_stmt(self, stmt: ast.stmt, block_id: str) -> str:
        step_type = self._step_type(stmt)
        data = self._data_for_statement(stmt)
        call = self._call_from_stmt(stmt)
        code = self._snippet(stmt)
        return self._add_node(
            "step",
            code,
            False,
            block_id,
            step_type=step_type,
            line=getattr(stmt, "lineno", self.fn.line),
            end_line=getattr(stmt, "end_lineno", getattr(stmt, "lineno", self.fn.line)),
            data=data,
            call=call,
        )

    # ---------------------------------------------------------------- planning
    def plan_sequence(
        self,
        statements: Iterable[ast.stmt],
        parent_block_id: str,
        *,
        create_block: bool = True,
    ) -> SequencePlan:
        block_id = self._add_block("sequence", parent_block_id, items=[]) if create_block else parent_block_id
        plan = SequencePlan(block_id=block_id, items=[], falls_through=True)
        for stmt in statements:
            if not plan.falls_through:
                self.diagnostics.append(
                    {
                        "severity": "warning",
                        "code": "UNREACHABLE_CODE",
                        "message": "检测到终止语句后的不可达代码，已从执行流中剔除",
                        "functionId": self.fn.id,
                        "file": self.fn.file,
                        "line": getattr(stmt, "lineno", self.fn.line),
                    }
                )
                break
            items, falls = self.plan_statement(stmt, block_id)
            plan.items.extend(items)
            plan.falls_through = falls
        if not plan.items:
            node_id = self._add_node(
                "step",
                "pass",
                False,
                block_id,
                step_type="pass",
                line=self.fn.line,
                end_line=self.fn.line,
                data={"defs": [], "uses": []},
            )
            plan.items.append(PlanNode(node_id))
        if create_block:
            self.sequence_plans[block_id] = plan
        return plan

    def plan_statement(self, stmt: ast.stmt, parent_block_id: str) -> tuple[list[Any], bool]:
        if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return [], True

        if isinstance(stmt, ast.If):
            branch_id = self._add_node(
                "branch",
                self._header(stmt),
                False,
                parent_block_id,
                line=stmt.lineno,
                end_line=getattr(stmt, "end_lineno", stmt.lineno),
            )
            if_block_id = self._add_block(
                "if",
                parent_block_id,
                ownerId=branch_id,
                then="",
                merge=None,
            )
            then_plan = self.plan_sequence(stmt.body, if_block_id)
            else_plan = (
                self.plan_sequence(stmt.orelse, if_block_id) if stmt.orelse else None
            )
            merge_id: str | None = None
            falls = then_plan.falls_through or (else_plan.falls_through if else_plan else True)
            if else_plan is not None and then_plan.falls_through and else_plan.falls_through:
                merge_id = self._add_node(
                    "merge",
                    "",
                    True,
                    if_block_id,
                    merge_of=branch_id,
                )
            if_block = self.block_by_id[if_block_id]
            if_block["then"] = then_plan.block_id
            if_block["else"] = else_plan.block_id if else_plan else None
            if_block["merge"] = merge_id
            return [IfPlan(branch_id, if_block_id, then_plan, else_plan, merge_id, falls)], falls

        if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            if isinstance(stmt, ast.While):
                loop_kind = "while"
            elif isinstance(stmt, ast.AsyncFor):
                loop_kind = "async_for"
            else:
                loop_kind = "for"
            loop_id = self._add_node(
                "loop",
                self._header(stmt),
                False,
                parent_block_id,
                line=stmt.lineno,
                end_line=getattr(stmt, "end_lineno", stmt.lineno),
                loop_kind=loop_kind,
            )
            loop_block_id = self._add_block(
                "loop",
                parent_block_id,
                ownerId=loop_id,
                body="",
            )
            body_plan = self.plan_sequence(stmt.body, loop_block_id)
            self.block_by_id[loop_block_id]["body"] = body_plan.block_id
            return [LoopPlan(loop_id, loop_block_id, body_plan)], True

        if isinstance(stmt, (ast.With, ast.AsyncWith)):
            node_id = self._add_step_for_stmt(stmt, parent_block_id)
            child_plan = self.plan_sequence(stmt.body, parent_block_id, create_block=False)
            return [PlanNode(node_id)] + list(child_plan.items), child_plan.falls_through

        if isinstance(stmt, ast.Try):
            node_id = self._add_step_for_stmt(stmt, parent_block_id)
            self.diagnostics.append(
                {
                    "severity": "info",
                    "code": "TRY_SIMPLIFIED",
                    "message": "try/except/finally 在 v1 中仅顺序展开主 body",
                    "functionId": self.fn.id,
                    "file": self.fn.file,
                    "line": stmt.lineno,
                }
            )
            child_plan = self.plan_sequence(stmt.body, parent_block_id, create_block=False)
            return [PlanNode(node_id)] + list(child_plan.items), child_plan.falls_through

        if isinstance(stmt, ast.Match):
            node_id = self._add_step_for_stmt(stmt, parent_block_id)
            self.diagnostics.append(
                {
                    "severity": "info",
                    "code": "MATCH_UNSUPPORTED",
                    "message": "match 分支在 v1 中不展开",
                    "functionId": self.fn.id,
                    "file": self.fn.file,
                    "line": stmt.lineno,
                }
            )
            return [PlanNode(node_id)], True

        terminal = isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue))
        node_id = self._add_step_for_stmt(stmt, parent_block_id)
        return [PlanNode(node_id, falls_through=not terminal)], not terminal

    # ------------------------------------------------------------------ wiring
    def wire_sequence(
        self,
        plan: SequencePlan,
        next_target: str | None,
        exit_flow: str,
        loop_ctx: LoopContext | None,
    ) -> str | None:
        target = next_target
        flow = exit_flow
        entry: str | None = None
        for item in reversed(plan.items):
            entry = self.wire_item(item, target, flow, loop_ctx)
            target = entry
            flow = "next"
        return entry

    def wire_item(
        self,
        item: Any,
        target: str | None,
        flow: str,
        loop_ctx: LoopContext | None,
    ) -> str | None:
        if isinstance(item, PlanNode):
            node = self.node_by_id[item.node_id]
            node_type = node["type"]
            if node_type == "merge":
                if any(edge["from"] == item.node_id for edge in self.edges):
                    return item.node_id
                self._add_edge(item.node_id, target or self.exit_id, flow=flow)
                return item.node_id
            step_type = node.get("stepType")
            if step_type == "return":
                self._add_edge(item.node_id, self.exit_id, flow="return", label=_compact(node["code"]))
                return item.node_id
            if step_type == "raise":
                self._add_edge(item.node_id, self.exit_id, flow="exception", label="raise")
                return item.node_id
            if step_type == "break":
                break_target = loop_ctx.break_target if loop_ctx else self.exit_id
                self._add_edge(item.node_id, break_target or self.exit_id, flow="break", label="break")
                return item.node_id
            if step_type == "continue":
                continue_target = loop_ctx.loop_id if loop_ctx else self.exit_id
                self._add_edge(item.node_id, continue_target, flow="continue", label="continue")
                return item.node_id
            if target:
                self._add_edge(item.node_id, target, flow=flow)
            return item.node_id

        if isinstance(item, IfPlan):
            branch_id = item.branch_id
            then_target = item.merge_id or target
            else_target = item.merge_id or target
            then_entry = None
            else_entry = None
            if item.then_plan.items:
                then_entry = self.wire_sequence(
                    item.then_plan,
                    then_target,
                    "merge" if item.merge_id else flow,
                    loop_ctx,
                )
            if item.else_plan and item.else_plan.items:
                else_entry = self.wire_sequence(
                    item.else_plan,
                    else_target,
                    "merge" if item.merge_id else flow,
                    loop_ctx,
                )
            self._add_edge(
                branch_id,
                then_entry or item.merge_id or target or self.exit_id,
                flow="true",
                label="true",
            )
            if item.else_plan:
                self._add_edge(
                    branch_id,
                    else_entry or item.merge_id or target or self.exit_id,
                    flow="false",
                    label="false",
                )
            else:
                self._add_edge(
                    branch_id,
                    item.merge_id or target or self.exit_id,
                    flow="false",
                    label="false",
                )
            if item.merge_id:
                self._add_edge(item.merge_id, target or self.exit_id, flow=flow)
            return branch_id

        if isinstance(item, LoopPlan):
            inner_ctx = LoopContext(loop_id=item.loop_id, break_target=target)
            body_entry = self.wire_sequence(item.body_plan, item.loop_id, "back", inner_ctx)
            self._add_edge(item.loop_id, body_entry or item.loop_id, flow="loop_body", label="循环体")
            self._add_edge(item.loop_id, target or self.exit_id, flow="loop_exit", label="退出")
            return item.loop_id

        return None

    # ---------------------------------------------------------------- dataflow
    def _node_enclosing_loop(self, node_id: str) -> set[str]:
        node = self.node_by_id[node_id]
        result: set[str] = set()
        block = self.block_by_id.get(node.get("blockId", ""))
        while block:
            if block["kind"] == "loop":
                result.add(block["ownerId"])
            block = self.block_by_id.get(block.get("parentId") or "")
        return result

    def add_data_dependencies(self) -> None:
        control_edges = [edge for edge in self.edges if edge["type"] == "next_step"]
        preds: dict[str, list[str]] = {node["id"]: [] for node in self.nodes}
        for edge in control_edges:
            if edge["to"] in preds:
                preds[edge["to"]].append(edge["from"])

        env_in: dict[str, dict[str, set[str]]] = {node["id"]: {} for node in self.nodes}
        env_out: dict[str, dict[str, set[str]]] = {node["id"]: {} for node in self.nodes}
        limited_nodes = [node for node in self.nodes if node["type"] not in {"entry", "exit"}]
        iterations = max(2, len(limited_nodes) * 2 + 4)
        for _ in range(iterations):
            changed = False
            for node in self.nodes:
                if node["type"] == "exit":
                    continue
                merged: dict[str, set[str]] = {}
                for pred in preds[node["id"]]:
                    for var, producers in env_out.get(pred, {}).items():
                        merged.setdefault(var, set()).update(producers)
                if merged != env_in[node["id"]]:
                    env_in[node["id"]] = merged
                    changed = True
                out = {var: set(producers) for var, producers in merged.items()}
                data = node.get("data") or {}
                for var in data.get("defs", []):
                    out[var] = {node["id"]}
                if out != env_out[node["id"]]:
                    env_out[node["id"]] = out
                    changed = True
            if not changed:
                break

        count = 0
        for node in self.nodes:
            if node["type"] in {"entry", "exit", "merge"}:
                continue
            data = node.get("data") or {}
            for var in data.get("uses", []):
                producers = sorted(env_in[node["id"]].get(var, set()))
                for producer in producers:
                    if producer == node["id"]:
                        continue
                    producer_node = self.node_by_id.get(producer)
                    if not producer_node or producer_node["type"] in {"entry", "exit", "merge"}:
                        continue
                    resolution = "exact" if len(producers) == 1 else "union"
                    loops_a = self._node_enclosing_loop(producer)
                    loops_b = self._node_enclosing_loop(node["id"])
                    if loops_a and loops_b and loops_a.intersection(loops_b):
                        resolution = "loop"
                    if "." in var:
                        resolution = "approximate"
                    self._add_edge(
                        producer,
                        node["id"],
                        edge_type="data_dep",
                        flow=None,
                        variable=var,
                        resolution=resolution,
                        confidence="high" if resolution == "exact" else "medium",
                    )
                    count += 1
                    if count >= self.analysis.config.max_data_deps:
                        self.diagnostics.append(
                            {
                                "severity": "warning",
                                "code": "DATA_DEP_TRUNCATED",
                                "message": f"数据依赖超过上限 {self.analysis.config.max_data_deps}，已截断",
                                "functionId": self.fn.id,
                            }
                        )
                        return

    # ------------------------------------------------------------------- build
    def build(self) -> dict[str, Any]:
        root_plan = self.plan_sequence(self.fn.node.body, self.root_block_id, create_block=False)
        if len(self.nodes) > self.analysis.config.max_steps + 2:
            self.diagnostics.append(
                {
                    "severity": "warning",
                    "code": "WORKFLOW_TRUNCATED",
                    "message": f"函数步骤超过上限 {self.analysis.config.max_steps}，已截断",
                    "functionId": self.fn.id,
                }
            )
        root_entry = self.wire_sequence(root_plan, self.exit_id, "next", None)
        self._add_edge(self.entry_id, root_entry or self.exit_id, flow="next")
        self.add_data_dependencies()
        self.block_by_id[self.root_block_id]["items"] = self._collect_block_items(root_plan)
        for block_id, plan in self.sequence_plans.items():
            self.block_by_id[block_id]["items"] = self._collect_block_items(plan)
        return {
            "id": self.fn.id,
            "kind": "archmap.function-flow",
            "name": self.fn.name,
            "qualifiedName": f"{self.fn.module_name}.{self.fn.qualname}",
            "module": self.fn.module_name,
            "moduleId": self.fn.module_id,
            "ownerClassId": (
                f"cls:{self.fn.module_name}.{self.fn.class_name}"
                if self.fn.class_name else None
            ),
            "methodKind": self.fn.method_kind,
            "visibility": self.fn.visibility,
            "isAbstract": self.fn.is_abstract,
            "file": self.fn.file,
            "line": self.fn.line,
            "endLine": self.fn.end_line,
            "signature": self.fn.signature,
            "isAsync": self.fn.is_async,
            "note": self.fn.note,
            "rootBlockId": self.root_block_id,
            "entryNodeId": self.entry_id,
            "exitNodeId": self.exit_id,
            "nodes": self.nodes,
            "edges": self.edges,
            "blocks": self.blocks,
            "diagnostics": self.diagnostics,
        }

    def _collect_block_items(self, plan: SequencePlan) -> list[str]:
        items: list[str] = []
        for item in plan.items:
            if isinstance(item, PlanNode):
                if item.node_id not in items:
                    items.append(item.node_id)
            elif isinstance(item, IfPlan):
                items.append(item.block_id)
            elif isinstance(item, LoopPlan):
                items.append(item.block_id)
        return items


def build_function_flows(analysis: AnalysisResult) -> list[dict[str, Any]]:
    flows: list[dict[str, Any]] = []
    for fn in sorted(analysis.functions, key=lambda item: (item.file, item.line, item.id)):
        builder = FunctionFlowBuilder(analysis, fn)
        flows.append(builder.build())
    return flows
