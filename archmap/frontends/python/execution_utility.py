"""Python entrypoint execution-flow skeleton extraction for P5.

The P5 execution view is intentionally bounded.  It expands only the control
structure of the selected entrypoint.  Main-module free functions and
functional-module public capabilities remain opaque execution steps; normal
statements, external IO calls, list operations and exception paths are not
projected into nodes.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from ...model.analysis_model import AnalysisResult, FunctionInfo
from ...model.call_model import CallSite


@dataclass
class _Endpoint:
    node_id: str
    kind: str = "next"
    label: str = ""
    # Opaque, non-control statement summaries accumulated since the last
    # visible execution node.  They are attached to the next outgoing edge.
    pending: list[dict[str, Any]] = field(default_factory=list)


def _unparse(node: ast.AST | None, limit: int = 140) -> str:
    if node is None:
        return ""
    try:
        text = ast.unparse(node)
    except Exception:
        text = type(node).__name__
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _is_effective_statement(stmt: ast.stmt) -> bool:
    return not isinstance(stmt, ast.Pass)


class ExecutionSkeletonBuilder:
    """Build one bounded execution skeleton for a single Python entrypoint."""

    def __init__(
        self,
        *,
        analysis: AnalysisResult,
        call_sites: Iterable[CallSite],
        entry: FunctionInfo,
        flow_id: str,
        flow_key: str,
        resolve_target: Callable[[CallSite], dict[str, Any] | None],
        module_meta: dict[str, dict[str, Any]],
    ) -> None:
        self.analysis = analysis
        self.entry = entry
        self.flow_id = flow_id
        self.flow_key = flow_key
        self.resolve_target = resolve_target
        self.module_meta = module_meta
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.diagnostics: list[dict[str, Any]] = []
        self._node_seq = 0
        self._edge_seq = 0
        self._loop_stack: list[dict[str, Any]] = []
        self._exit_created = False
        self._try_diagnostic_emitted = False
        self._calls_by_position: dict[tuple[int, int], CallSite] = {}
        for site in call_sites:
            if site.from_function_id == entry.id:
                self._calls_by_position[(site.line, site.column)] = site
        self._entry_module = module_meta.get(entry.module_id, {})
        self._exit_id = f"exec:{flow_key}:exit"
        self._entry_id = f"exec:{flow_key}:entry:{entry.id}"
        self._add_node(
            node_id=self._entry_id,
            kind="entry",
            label=f"{entry.name}()",
            line=entry.line,
            end_line=entry.end_line,
            data={
                "functionId": entry.id,
                "targetFunctionId": entry.id,
                "moduleId": entry.module_id,
                "moduleName": self._entry_module.get("name", entry.module_id),
                "color": self._entry_module.get("color", "#f59e0b"),
                "signature": entry.signature,
                "note": entry.note,
                "ports": ["out"],
                "expandable": False,
                "execution": True,
                "flowId": flow_id,
            },
        )

    # ------------------------------------------------------------------
    # Node/edge helpers
    # ------------------------------------------------------------------
    def _next_node_id(self, kind: str, line: int, column: int = 0) -> str:
        self._node_seq += 1
        return f"exec:{self.flow_key}:{kind}:{line}:{column}:{self._node_seq}"

    def _add_node(
        self,
        *,
        node_id: str,
        kind: str,
        label: str,
        line: int,
        end_line: int,
        data: dict[str, Any],
        column: int = 0,
    ) -> str:
        order = len(self.nodes)
        payload = {
            "id": node_id,
            "kind": kind,
            "label": label,
            "moduleId": data.get("moduleId") or self.entry.module_id,
            "order": order,
            **data,
            "file": data.get("file") or self.entry.file,
            "line": line,
            "endLine": end_line,
        }
        self.nodes.append(payload)
        return node_id

    def _add_edge(
        self,
        from_node: str,
        to_node: str,
        kind: str,
        *,
        label: str = "",
        evidence: list[dict[str, Any]] | None = None,
        case_index: int | None = None,
        branch_order: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not from_node or not to_node or from_node == to_node:
            return
        if any(
            edge.get("from") == from_node
            and edge.get("to") == to_node
            and edge.get("kind") == kind
            for edge in self.edges
        ):
            return
        self._edge_seq += 1
        edge: dict[str, Any] = {
            "id": f"exec-edge:{self.flow_key}:{self._edge_seq}",
            "from": from_node,
            "to": to_node,
            "kind": kind,
            "label": label,
            "confidence": "high",
            "evidence": list(evidence or []),
        }
        if case_index is not None:
            edge["caseIndex"] = case_index
        if branch_order is not None:
            edge["branchOrder"] = branch_order
        if extra:
            edge.update(extra)
        self.edges.append(edge)

    def _connect(
        self,
        endpoints: list[_Endpoint],
        target: str,
        *,
        default_kind: str = "next",
        force_kind: str | None = None,
        label: str = "",
    ) -> None:
        for endpoint in endpoints:
            kind = force_kind or endpoint.kind or default_kind
            extra: dict[str, Any] = {}
            if endpoint.pending:
                statements = [str(item.get("text") or "") for item in endpoint.pending if item.get("text")]
                lines = [int(item.get("line") or 0) for item in endpoint.pending if item.get("line")]
                if statements:
                    extra["statements"] = statements
                    extra["statementLines"] = lines
            self._add_edge(
                endpoint.node_id,
                target,
                kind,
                label=label or endpoint.label,
                extra=extra,
            )

    def _endpoint(self, node_id: str, kind: str = "next", label: str = "") -> _Endpoint:
        return _Endpoint(node_id=node_id, kind=kind, label=label)

    def _append_pending(
        self,
        endpoints: list[_Endpoint],
        summary: dict[str, Any],
    ) -> list[_Endpoint]:
        """Carry an opaque statement summary on every live endpoint."""

        return [
            _Endpoint(
                node_id=endpoint.node_id,
                kind=endpoint.kind,
                label=endpoint.label,
                pending=[*endpoint.pending, summary],
            )
            for endpoint in endpoints
        ]

    def _opaque_statement_summary(self, stmt: ast.stmt) -> dict[str, Any] | None:
        """Return a compact summary for a statement that has no visible node."""

        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            text = _unparse(stmt)
        elif isinstance(stmt, ast.Expr) and not isinstance(stmt.value, ast.Constant):
            if any(isinstance(child, ast.Call) for child in ast.walk(stmt.value)):
                return None
            text = _unparse(stmt.value)
        else:
            return None
        if not text:
            return None
        return {"text": text, "line": int(getattr(stmt, "lineno", 0) or 0)}

    def _pending_statement_summaries(
        self, endpoints: list[_Endpoint]
    ) -> tuple[list[str], list[int]]:
        """Collect unique opaque statements from a set of endpoints."""

        seen: set[tuple[str, int]] = set()
        statements: list[str] = []
        lines: list[int] = []
        for endpoint in endpoints:
            for item in endpoint.pending:
                key = (str(item.get("text") or ""), int(item.get("line") or 0))
                if not key[0] or key in seen:
                    continue
                seen.add(key)
                statements.append(key[0])
                lines.append(key[1])
        return statements, lines

    def _arm_next_kind(
        self, body: list[ast.stmt], endpoints: list[_Endpoint]
    ) -> str:
        """Describe how one control arm leaves its body."""

        if endpoints:
            return "fallthrough"
        if not body:
            return "empty"
        last = body[-1]
        if isinstance(last, ast.Continue):
            return "continue"
        if isinstance(last, ast.Break):
            return "break"
        if isinstance(last, ast.Return):
            return "return"
        if isinstance(last, ast.Raise):
            return "raise"
        return "terminal"

    def _arm_summary(
        self, body: list[ast.stmt], endpoints: list[_Endpoint]
    ) -> dict[str, Any]:
        statements, lines = self._pending_statement_summaries(endpoints)
        return {
            "statements": statements,
            "sourceLines": lines,
            "next": self._arm_next_kind(body, endpoints),
        }

    def _update_node(self, node_id: str, updates: dict[str, Any]) -> None:
        for node in self.nodes:
            if str(node.get("id") or "") == node_id:
                node.update(updates)
                return

    def _module_payload(self, module_id: str) -> dict[str, Any]:
        meta = self.module_meta.get(module_id, {})
        return {
            "moduleId": module_id,
            "moduleName": meta.get("name", module_id),
            "color": meta.get("color", "#60a5fa"),
        }

    # ------------------------------------------------------------------
    # Entrypoint traversal
    # ------------------------------------------------------------------
    def _ensure_exit(self) -> str:
        """Create the shared terminal anchor only when a path needs it."""

        if self._exit_created:
            return self._exit_id
        self._exit_created = True
        self._add_node(
            node_id=self._exit_id,
            kind="exit",
            label="结束",
            line=self.entry.end_line,
            end_line=self.entry.end_line,
            data={
                "functionId": self.entry.id,
                "moduleId": self.entry.module_id,
                "moduleName": self._entry_module.get("name", self.entry.module_id),
                "color": self._entry_module.get("color", "#f59e0b"),
                "ports": ["in"],
                "expandable": False,
                "execution": True,
                "flowId": self.flow_id,
            },
        )
        return self._exit_id

    def build(self) -> dict[str, Any]:
        entry_node = self.nodes[0]
        endpoints = self._visit_stmts(
            list(self.entry.node.body), [self._endpoint(self._entry_id)]
        )
        # A return is already a terminal sink.  The shared exit anchor exists
        # only for implicit fall-through or other real paths that reach it.
        if endpoints:
            self._connect(endpoints, self._ensure_exit())
            entry_node["exitNodeId"] = self._exit_id
        return {
            "kind": "archmap.execution-flow",
            "id": self.flow_id,
            "moduleId": self.entry.module_id,
            "entrypointId": self.entry.id,
            "entrypointReason": "",
            "name": f"{self.entry.name}()",
            "nodes": self.nodes,
            "edges": self.edges,
            "diagnostics": self.diagnostics,
            "truncated": False,
        }

    def _visit_stmts(self, stmts: list[ast.stmt], incoming: list[_Endpoint]) -> list[_Endpoint]:
        current = incoming
        for stmt in stmts:
            if not current:
                break
            current = self._visit_stmt(stmt, current)
        return current

    def _visit_stmt(self, stmt: ast.stmt, incoming: list[_Endpoint]) -> list[_Endpoint]:
        if isinstance(stmt, ast.If):
            return self._visit_if(stmt, incoming)
        if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            return self._visit_loop(stmt, incoming)
        if isinstance(stmt, ast.Match):
            return self._visit_match(stmt, incoming)
        if isinstance(stmt, (ast.With, ast.AsyncWith)):
            current = self._process_calls(
                self._calls_in_nodes([item.context_expr for item in stmt.items]),
                incoming,
            )
            return self._visit_stmts(list(stmt.body), current)
        if isinstance(stmt, ast.Try):
            self._emit_exception_diagnostic(stmt)
            return self._visit_stmts(list(stmt.body), incoming)
        if isinstance(stmt, ast.Return):
            current = self._process_calls(self._calls_in_statement(stmt), incoming)
            if not current:
                return []
            return_id = self._next_node_id("return", stmt.lineno, stmt.col_offset + 1)
            self._add_node(
                node_id=return_id,
                kind="return",
                label=f"return {_unparse(stmt.value)}".strip(),
                line=stmt.lineno,
                end_line=getattr(stmt, "end_lineno", stmt.lineno) or stmt.lineno,
                column=stmt.col_offset + 1,
                data={
                    "functionId": self.entry.id,
                    "moduleId": self.entry.module_id,
                    "moduleName": self._entry_module.get("name", self.entry.module_id),
                    "color": self._entry_module.get("color", "#f59e0b"),
                    "ports": ["in"],
                    "expandable": False,
                    "execution": True,
                    "flowId": self.flow_id,
                    "terminalKind": "return",
                },
            )
            self._connect(current, return_id)
            return []
        if isinstance(stmt, ast.Raise):
            self._connect(incoming, self._ensure_exit(), force_kind="next", label="raise")
            return []
        if isinstance(stmt, ast.Break):
            return self._visit_break(stmt, incoming)
        if isinstance(stmt, ast.Continue):
            return self._visit_continue(stmt, incoming)
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return incoming
        # P10.2: simple assignments / non-call expressions do not create nodes.
        # If they contain no resolved project call, retain a compact summary on
        # the live endpoint so the next edge can expose the state change.
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr)):
            before = len(self.nodes)
            current = self._process_calls(self._calls_in_statement(stmt), incoming)
            if len(self.nodes) == before:
                summary = self._opaque_statement_summary(stmt)
                if summary is not None:
                    return self._append_pending(current, summary)
            return current
        # All remaining statements are opaque unless they contain a direct
        # project call.  This is the anti-slip rule: no per-statement actions.
        return self._process_calls(self._calls_in_statement(stmt), incoming)

    def _calls_in_statement(self, stmt: ast.stmt) -> list[CallSite]:
        return self._calls_in_nodes([stmt])

    def _calls_in_nodes(self, roots: list[ast.AST]) -> list[CallSite]:
        found: dict[str, CallSite] = {}
        for root in roots:
            for child in ast.walk(root):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    continue
                if not isinstance(child, ast.Call):
                    continue
                line = int(getattr(child, "lineno", 0) or 0)
                column = int(getattr(child, "col_offset", -1) or -1) + 1
                site = self._calls_by_position.get((line, column))
                if site is not None:
                    found[site.id] = site
        return sorted(found.values(), key=lambda item: (item.line, item.column, item.id))

    def _process_calls(self, sites: list[CallSite], incoming: list[_Endpoint]) -> list[_Endpoint]:
        current = incoming
        for site in sites:
            resolved = self.resolve_target(site)
            if resolved is None:
                continue
            node_id = self._next_node_id(str(resolved["kind"]), site.line, site.column)
            data = {
                **resolved,
                "callSiteId": site.id,
                "usageKind": site.usage_kind,
                "ports": ["in", "out"],
                "expandable": False,
                "execution": True,
                "flowId": self.flow_id,
            }
            data.setdefault("file", site.file)
            self._add_node(
                node_id=node_id,
                kind=str(resolved["kind"]),
                label=str(resolved["label"]),
                line=site.line,
                end_line=int(getattr(site, "line", 0) or site.line),
                column=site.column,
                data=data,
            )
            self._connect(current, node_id)
            current = [self._endpoint(node_id)]
        return current

    # ------------------------------------------------------------------
    # Control structures
    # ------------------------------------------------------------------
    def _visit_if(self, stmt: ast.If, incoming: list[_Endpoint]) -> list[_Endpoint]:
        conditions: list[tuple[ast.expr, list[ast.stmt], int]] = []
        cursor: ast.If | None = stmt
        while cursor is not None:
            conditions.append((cursor.test, list(cursor.body), cursor.lineno))
            if len(cursor.orelse) == 1 and isinstance(cursor.orelse[0], ast.If):
                cursor = cursor.orelse[0]
            else:
                cursor = None

        # Recover the terminal else body from the last chain node.
        cursor = stmt
        while len(cursor.orelse) == 1 and isinstance(cursor.orelse[0], ast.If):
            cursor = cursor.orelse[0]
        else_body = list(cursor.orelse)

        control_id = self._next_node_id("multi_branch" if len(conditions) > 1 else "branch", stmt.lineno, stmt.col_offset + 1)
        if len(conditions) > 1:
            label = _unparse(stmt.test)
            cases = [
                {"key": f"case:{index + 1}", "label": _unparse(condition)}
                for index, (condition, _, _) in enumerate(conditions)
            ]
            node_kind = "multi_branch"
            data = {
                "functionId": self.entry.id,
                "moduleId": self.entry.module_id,
                "moduleName": self._entry_module.get("name", self.entry.module_id),
                "color": self._entry_module.get("color", "#f59e0b"),
                "condition": label,
                "cases": cases,
                "ports": ["in", *[item["key"] for item in cases], "default"],
                "expandable": False,
                "execution": True,
                "flowId": self.flow_id,
            }
        else:
            label = _unparse(conditions[0][0])
            node_kind = "branch"
            data = {
                "functionId": self.entry.id,
                "moduleId": self.entry.module_id,
                "moduleName": self._entry_module.get("name", self.entry.module_id),
                "color": self._entry_module.get("color", "#f59e0b"),
                "condition": label,
                "ports": ["in", "true", "false"],
                "expandable": False,
                "execution": True,
                "flowId": self.flow_id,
            }
        self._add_node(
            node_id=control_id,
            kind=node_kind,
            label=label or "if",
            line=stmt.lineno,
            end_line=getattr(stmt, "end_lineno", stmt.lineno) or stmt.lineno,
            column=stmt.col_offset + 1,
            data=data,
        )
        self._connect(incoming, control_id)

        # P5.1: no synthetic merge node.  Each continuing arm returns its own
        # endpoint; the next real statement (or exit) becomes the fan-in target.
        # P10.2: opaque statements inside each arm are retained as compact
        # summaries; they never become statement-level execution nodes.
        if len(conditions) == 1:
            true_body = conditions[0][1]
            true_endpoints = self._visit_stmts(
                true_body,
                [self._endpoint(control_id, "true", "是")],
            )
            false_endpoints = self._visit_stmts(
                else_body,
                [self._endpoint(control_id, "false", "否")],
            )
            self._update_node(
                control_id,
                {
                    "armSummaries": {
                        "true": self._arm_summary(true_body, true_endpoints),
                        "false": self._arm_summary(else_body, false_endpoints),
                    }
                },
            )
            endpoints = [*true_endpoints, *false_endpoints]
        else:
            endpoints: list[_Endpoint] = []
            case_summaries: list[dict[str, Any]] = []
            for case in cases:
                case["summary"] = {}
            for index, (condition, body, _) in enumerate(conditions):
                arm_endpoints = self._visit_stmts(
                    body,
                    [self._endpoint(control_id, "case", _unparse(condition))],
                )
                summary = self._arm_summary(body, arm_endpoints)
                case_summaries.append(summary)
                if index < len(cases):
                    cases[index]["summary"] = summary
                endpoints.extend(arm_endpoints)
            default_endpoints = self._visit_stmts(
                else_body,
                [self._endpoint(control_id, "default", "默认")],
            )
            self._update_node(
                control_id,
                {
                    "cases": cases,
                    "caseSummaries": case_summaries,
                    "defaultSummary": self._arm_summary(else_body, default_endpoints),
                },
            )
            endpoints.extend(default_endpoints)
        return endpoints

    def _visit_match(self, stmt: ast.Match, incoming: list[_Endpoint]) -> list[_Endpoint]:
        control_id = self._next_node_id("multi_branch", stmt.lineno, stmt.col_offset + 1)
        cases = [
            {"key": f"case:{index + 1}", "label": _unparse(case.pattern)}
            for index, case in enumerate(stmt.cases)
        ]
        has_default = any(
            isinstance(case.pattern, ast.MatchAs) and case.pattern.name is None
            for case in stmt.cases
        )
        self._add_node(
            node_id=control_id,
            kind="multi_branch",
            label=_unparse(stmt.subject),
            line=stmt.lineno,
            end_line=getattr(stmt, "end_lineno", stmt.lineno) or stmt.lineno,
            column=stmt.col_offset + 1,
            data={
                "functionId": self.entry.id,
                "moduleId": self.entry.module_id,
                "moduleName": self._entry_module.get("name", self.entry.module_id),
                "color": self._entry_module.get("color", "#f59e0b"),
                "condition": _unparse(stmt.subject),
                "cases": cases,
                "ports": ["in", *[item["key"] for item in cases], *([] if has_default else ["default"])],
                "expandable": False,
                "execution": True,
                "flowId": self.flow_id,
            },
        )
        self._connect(incoming, control_id)

        # Direct fan-in: every case body returns endpoints unchanged.  If there
        # is no wildcard/default arm, the unmatched path itself is an endpoint
        # that will connect to the next real statement or exit.
        endpoints: list[_Endpoint] = []
        for index, case in enumerate(stmt.cases):
            endpoints.extend(
                self._visit_stmts(
                    list(case.body),
                    [self._endpoint(control_id, "case", _unparse(case.pattern))],
                )
            )
        if not has_default:
            endpoints.append(self._endpoint(control_id, "default", "默认"))
        return endpoints

    def _visit_loop(self, stmt: ast.For | ast.AsyncFor | ast.While, incoming: list[_Endpoint]) -> list[_Endpoint]:
        loop_id = self._next_node_id("loop", stmt.lineno, stmt.col_offset + 1)
        if isinstance(stmt, ast.While):
            loop_kind = "while"
            label = f"while {_unparse(stmt.test)}"
            condition = _unparse(stmt.test)
            iterable = ""
            loop_variable = ""
        elif isinstance(stmt, ast.AsyncFor):
            loop_kind = "async_for"
            label = f"async for {_unparse(stmt.target)} in {_unparse(stmt.iter)}"
            condition = ""
            iterable = _unparse(stmt.iter)
            loop_variable = _unparse(stmt.target)
        else:
            loop_kind = "for"
            label = f"for {_unparse(stmt.target)} in {_unparse(stmt.iter)}"
            condition = ""
            iterable = _unparse(stmt.iter)
            loop_variable = _unparse(stmt.target)
        self._add_node(
            node_id=loop_id,
            kind="loop",
            label=label,
            line=stmt.lineno,
            end_line=getattr(stmt, "end_lineno", stmt.lineno) or stmt.lineno,
            column=stmt.col_offset + 1,
            data={
                "functionId": self.entry.id,
                "moduleId": self.entry.module_id,
                "moduleName": self._entry_module.get("name", self.entry.module_id),
                "color": self._entry_module.get("color", "#f59e0b"),
                "loopKind": loop_kind,
                "condition": condition,
                "iterable": iterable,
                "loopVariable": loop_variable,
                "mayExit": False,
                "hasBreak": False,
                "ports": ["in", "loop_body", "loop_complete"],
                "expandable": False,
                "execution": True,
                "flowId": self.flow_id,
            },
        )
        self._connect(incoming, loop_id)
        loop_context: dict[str, Any] = {"node_id": loop_id, "break_nodes": []}
        self._loop_stack.append(loop_context)
        try:
            body_endpoints = self._visit_stmts(
                list(stmt.body),
                [self._endpoint(loop_id, "loop_body", "循环体")],
            )
            for endpoint in body_endpoints:
                self._update_node(
                    endpoint.node_id,
                    {"implicitNext": "loop_iteration"},
                )
        finally:
            self._loop_stack.pop()

        if stmt.orelse:
            self.diagnostics.append(
                {
                    "severity": "info",
                    "code": "LOOP_ELSE_SIMPLIFIED",
                    "message": "P5 v1 does not model loop else branches; the loop complete path continues directly.",
                    "file": self.entry.file,
                    "line": stmt.lineno,
                }
            )
        has_break = bool(loop_context["break_nodes"])
        if isinstance(stmt, ast.While):
            try:
                may_complete = _unparse(stmt.test).strip() not in {"True", "1"}
            except Exception:
                may_complete = True
        else:
            may_complete = True
        may_exit = may_complete or has_break
        for node in self.nodes:
            if node.get("id") == loop_id:
                node["mayExit"] = may_exit
                node["hasBreak"] = has_break
                node["breakCount"] = len(loop_context["break_nodes"])
                break

        # break / continue are internal loop terminal markers.  The loop node
        # is the single structured boundary: any path that leaves the loop,
        # whether by normal completion or by break, continues from its
        # loop_complete port.
        if not may_exit:
            return []
        return [self._endpoint(loop_id, "loop_complete", "离开循环")]

    def _visit_break(self, stmt: ast.Break, incoming: list[_Endpoint]) -> list[_Endpoint]:
        if not self._loop_stack:
            self.diagnostics.append(
                {
                    "severity": "warning",
                    "code": "BREAK_OUTSIDE_LOOP",
                    "message": "break encountered outside a modeled loop.",
                    "file": self.entry.file,
                    "line": stmt.lineno,
                }
            )
            return []
        break_id = self._next_node_id("break", stmt.lineno, stmt.col_offset + 1)
        self._add_node(
            node_id=break_id,
            kind="break",
            label="break",
            line=stmt.lineno,
            end_line=getattr(stmt, "end_lineno", stmt.lineno) or stmt.lineno,
            column=stmt.col_offset + 1,
            data={
                "functionId": self.entry.id,
                "moduleId": self.entry.module_id,
                "moduleName": self._entry_module.get("name", self.entry.module_id),
                "color": self._entry_module.get("color", "#f59e0b"),
                "loopId": self._loop_stack[-1]["node_id"],
                "ports": ["in"],
                "expandable": False,
                "execution": True,
                "flowId": self.flow_id,
            },
        )
        self._connect(incoming, break_id)
        self._loop_stack[-1]["break_nodes"].append(break_id)
        return []

    def _visit_continue(self, stmt: ast.Continue, incoming: list[_Endpoint]) -> list[_Endpoint]:
        if not self._loop_stack:
            self.diagnostics.append(
                {
                    "severity": "warning",
                    "code": "CONTINUE_OUTSIDE_LOOP",
                    "message": "continue encountered outside a modeled loop.",
                    "file": self.entry.file,
                    "line": stmt.lineno,
                }
            )
            return []
        continue_id = self._next_node_id("continue", stmt.lineno, stmt.col_offset + 1)
        self._add_node(
            node_id=continue_id,
            kind="continue",
            label="continue",
            line=stmt.lineno,
            end_line=getattr(stmt, "end_lineno", stmt.lineno) or stmt.lineno,
            column=stmt.col_offset + 1,
            data={
                "functionId": self.entry.id,
                "moduleId": self.entry.module_id,
                "moduleName": self._entry_module.get("name", self.entry.module_id),
                "color": self._entry_module.get("color", "#f59e0b"),
                "loopId": self._loop_stack[-1]["node_id"],
                "ports": ["in"],
                "expandable": False,
                "execution": True,
                "flowId": self.flow_id,
            },
        )
        self._connect(incoming, continue_id)
        # The compact loop model does not draw a back lane.  ``continue`` is a
        # terminal marker inside the body; iteration is implicit in the loop
        # node's ``loop_body`` port.
        return []

    def _emit_exception_diagnostic(self, stmt: ast.Try) -> None:
        if self._try_diagnostic_emitted:
            return
        self._try_diagnostic_emitted = True
        self.diagnostics.append(
            {
                "severity": "info",
                "code": "EXCEPTION_CONTROL_SIMPLIFIED",
                "message": "P5 v1 does not model try/except/finally control paths; try body is projected as normal sequence.",
                "file": self.entry.file,
                "line": stmt.lineno,
            }
        )


def build_entry_execution_skeleton(
    analysis: AnalysisResult,
    call_sites: Iterable[CallSite],
    entry: FunctionInfo,
    *,
    flow_id: str,
    flow_key: str,
    resolve_target: Callable[[CallSite], dict[str, Any] | None],
    module_meta: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build one bounded execution skeleton for a Python entrypoint."""

    return ExecutionSkeletonBuilder(
        analysis=analysis,
        call_sites=call_sites,
        entry=entry,
        flow_id=flow_id,
        flow_key=flow_key,
        resolve_target=resolve_target,
        module_meta=module_meta,
    ).build()
