"""Internal CLI command implementations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .. import __version__
from ..managers.pipeline_manager import PipelineManager
from ..managers.render_manager import RenderManager
from ..managers.validate_manager import ValidationManager
from .query_utility import build_dsm, build_impact, build_trace


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_annotations(path: Path | None) -> dict[str, Any] | None:
    if path and path.exists():
        data = _read_json(path)
        if not isinstance(data, dict):
            raise ValueError("annotations file must contain a JSON object")
        data.setdefault("version", 1)
        data.setdefault("nodes", {})
        return data
    return None


def _print_issues(issues: list[dict[str, Any]]) -> None:
    for issue in issues:
        location = ""
        if issue.get("functionId"):
            location += f" [{issue['functionId']}]"
        if issue.get("nodeId"):
            location += f" [{issue['nodeId']}]"
        print(f"{issue.get('severity', 'info').upper():7} {issue.get('code', 'ISSUE'):24}{location} {issue.get('message', '')}")


def _write_split(bundle: dict[str, Any], out_dir: Path) -> None:
    split = out_dir / "split"
    split.mkdir(parents=True, exist_ok=True)
    (split / "project.json").write_text(
        json.dumps(bundle["projectGraph"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    modules_dir = split / "modules"
    functions_dir = split / "functions"
    modules_dir.mkdir(exist_ok=True)
    functions_dir.mkdir(exist_ok=True)
    for graph in bundle["moduleGraphs"]:
        safe = graph["moduleId"].replace("/", "_")
        (modules_dir / f"{safe}.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    for detail in bundle["functionDetails"]:
        safe = detail["id"].replace(":", "_").replace("/", "_").replace(".", "_")
        (functions_dir / f"{safe}.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
    (split / "call-sites.json").write_text(
        json.dumps(bundle["callSites"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
def cmd_build(args: argparse.Namespace) -> int:
    project_root = Path(args.project).resolve()
    if not project_root.is_dir():
        print(f"error: project root is not a directory: {project_root}", file=sys.stderr)
        return 2
    config_path = Path(args.config).resolve() if args.config else None
    out_dir = Path(args.out).resolve() if args.out else project_root / ".archmap"
    bundle = PipelineManager().build_architecture(project_root, config_path)
    try:
        bundle["project"]["root"] = Path(
            __import__("os").path.relpath(project_root, out_dir)
        ).as_posix()
    except Exception:
        bundle["project"]["root"] = "."
    issues = ValidationManager().validate(bundle)
    errors = [issue for issue in issues if issue.get("severity") == "error"]
    warnings = [issue for issue in issues if issue.get("severity") != "error"]
    if args.json:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))
        if warnings:
            print(f"warning: {len(warnings)} validation warning(s)", file=sys.stderr)
        return 1 if errors else 0
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "architecture.json"
    json_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    annotations_path = Path(args.annotations).resolve() if args.annotations else None
    if annotations_path is None:
        for candidate in (out_dir / "llm-annotations.json", project_root / ".archmap" / "llm-annotations.json"):
            if candidate.exists():
                annotations_path = candidate
                break
    annotations = _load_annotations(annotations_path)
    html_path = out_dir / "architecture.html"
    if errors:
        print(f"wrote {json_path}", file=sys.stderr)
        print(f"skipped HTML because {len(errors)} validation error(s) occurred", file=sys.stderr)
        _print_issues(errors)
        if warnings:
            _print_issues(warnings[:20])
        return 1
    html_path.write_text(RenderManager().render(bundle, annotations), encoding="utf-8")
    if args.split:
        _write_split(bundle, out_dir)
    if annotations_path:
        print(f"annotations: {annotations_path}")
    print(f"project:   {bundle['project']['name']}")
    print(f"modules:   {bundle['stats']['modules']}")
    print(f"functions: {bundle['stats']['functions']}")
    print(f"call sites: {bundle['stats']['callSites']}")
    print(f"json:      {json_path}")
    print(f"html:      {html_path}")
    if warnings:
        _print_issues(warnings[:20])
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    path = Path(args.bundle).resolve()
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    try:
        bundle = _read_json(path)
    except Exception as exc:
        print(f"error: cannot read JSON: {exc}", file=sys.stderr)
        return 2
    issues = ValidationManager().validate(bundle)
    if not issues:
        print("OK: schema, cross references, function details and call sites are valid")
        return 0
    _print_issues(issues)
    return 1 if any(issue.get("severity") == "error" for issue in issues) else 0


def cmd_method(args: argparse.Namespace) -> int:
    project_root = Path(args.project).resolve()
    config_path = Path(args.config).resolve() if args.config else None
    bundle = PipelineManager().build_architecture(project_root, config_path)
    target_file = Path(args.file).name if args.file else None
    candidates = bundle["functionDetails"]
    if target_file:
        candidates = [detail for detail in candidates if Path(detail["file"]).name == target_file]
    if args.function:
        candidates = [
            detail
            for detail in candidates
            if detail["name"] == args.function or detail["qualifiedName"].endswith("." + args.function)
        ]
    if not candidates:
        print("error: no matching function detail", file=sys.stderr)
        return 1
    detail = candidates[0]
    if args.json:
        print(json.dumps(detail, ensure_ascii=False, indent=2))
    else:
        print(f"{detail['qualifiedName']} ({detail['file']}:{detail['line']})")
        print(f"signature={detail['signature']}")
        print(f"callers={detail['callerCount']} callees={detail['calleeCount']} sourceLines={detail['source']['endLine'] - detail['source']['startLine'] + 1}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import http.server
    import socketserver

    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        print(f"error: directory not found: {directory}", file=sys.stderr)
        return 2
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(directory), **kw)
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"serving {directory} at http://127.0.0.1:{args.port}/architecture.html")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    before = _read_json(Path(args.before).resolve())
    after = _read_json(Path(args.after).resolve())
    fp_before = before.get("project", {}).get("fingerprint")
    fp_after = after.get("project", {}).get("fingerprint")
    print(f"before: {fp_before}")
    print(f"after:  {fp_after}")
    if fp_before == fp_after:
        print("no semantic changes")
        return 0
    print("semantic changes detected")
    before_functions = {detail["id"] for detail in before.get("functionDetails", [])}
    after_functions = {detail["id"] for detail in after.get("functionDetails", [])}
    for added in sorted(after_functions - before_functions):
        print(f"+ {added}")
    for removed in sorted(before_functions - after_functions):
        print(f"- {removed}")
    return 1


def cmd_impact(args: argparse.Namespace) -> int:
    before = _read_json(Path(args.before).resolve())
    after = _read_json(Path(args.after).resolve())
    result = build_impact(
        before,
        after,
        max_depth=max(1, int(args.max_depth)),
        max_nodes=max(1, int(args.max_nodes)),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    summary = result["summary"]
    print(f"before: {result['beforeFingerprint']}")
    print(f"after:  {result['afterFingerprint']}")
    print(f"seeds:  {len(result['seeds'])}")
    print(
        "impact: "
        f"functions={summary['functions']} providers={summary['providers']} "
        f"apis={summary['apis']} surfaces={summary['surfaces']} total={summary['total']}"
    )
    for item in result["impacts"][:40]:
        print(f"{item['nodeKind']:9} {item['change']:26} {item['nodeId']}")
    if result["truncated"]:
        print("warning: impact result truncated", file=sys.stderr)
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    bundle = _read_json(Path(args.bundle).resolve())
    try:
        result = build_trace(
            bundle,
            args.start,
            direction=args.direction,
            max_depth=max(1, int(args.max_depth)),
            max_nodes=max(1, int(args.max_nodes)),
            include_internal=bool(args.include_internal),
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"trace: {result['startId']} ({result['direction']})")
    print(f"nodes: {len(result['nodes'])} paths: {len(result['paths'])}")
    for path in result["paths"][:40]:
        kinds = " -> ".join(edge["kind"] for edge in path["edges"])
        print(f"depth={path['depth']} {path['to']} [{kinds}]")
    if result["truncated"]:
        print("warning: trace result truncated", file=sys.stderr)
    return 0


def cmd_surfaces(args: argparse.Namespace) -> int:
    bundle = _read_json(Path(args.bundle).resolve())
    surfaces = bundle.get("projectGraph", {}).get("userSurfaces", [])
    if args.module:
        surfaces = [item for item in surfaces if item.get("moduleId") == args.module]
    if args.json:
        print(json.dumps(surfaces, ensure_ascii=False, indent=2))
        return 0
    for item in surfaces:
        entrypoints = ", ".join(item.get("entrypointIds") or []) or "—"
        print(
            f"{item.get('kind', 'surface'):18} {item.get('moduleId', '—'):14} "
            f"{item.get('display', item.get('id'))} -> {entrypoints}"
        )
    print(f"total: {len(surfaces)}")
    return 0


def cmd_dsm(args: argparse.Namespace) -> int:
    bundle = _read_json(Path(args.bundle).resolve())
    try:
        result = build_dsm(bundle, level=args.level, include_internal=bool(args.include_internal))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    for source, targets in result["matrix"].items():
        for target, payload in targets.items():
            kinds = ", ".join(f"{kind}:{count}" for kind, count in payload["kinds"].items())
            print(f"{source} -> {target}: {payload['count']} ({kinds})")
    print(f"nodes: {result['stats']['nodes']} edges: {result['stats']['edges']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archmap", description="ArchMap v3 module-first architecture analysis")
    parser.add_argument("--version", action="version", version=f"archmap {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="analyze a Python project and write architecture.json/html")
    build.add_argument("project", nargs="?", default=".")
    build.add_argument("--out")
    build.add_argument("--config")
    build.add_argument("--json", action="store_true", help="print bundle JSON to stdout only")
    build.add_argument("--split", action="store_true")
    build.add_argument("--annotations")
    build.set_defaults(func=cmd_build)

    check = sub.add_parser("check", help="validate an architecture bundle")
    check.add_argument("bundle")
    check.set_defaults(func=cmd_check)

    method = sub.add_parser("method", help="inspect a generated function/method detail")
    method.add_argument("project", nargs="?", default=".")
    method.add_argument("--config")
    method.add_argument("--file")
    method.add_argument("--function")
    method.add_argument("--json", action="store_true")
    method.set_defaults(func=cmd_method)

    serve = sub.add_parser("serve", help="serve generated artifacts locally")
    serve.add_argument("directory", nargs="?", default=".archmap")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(func=cmd_serve)

    diff = sub.add_parser("diff", help="compare two architecture bundles")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.set_defaults(func=cmd_diff)

    impact = sub.add_parser("impact", help="compute reverse impact between two bundles")
    impact.add_argument("before")
    impact.add_argument("after")
    impact.add_argument("--json", action="store_true")
    impact.add_argument("--max-depth", type=int, default=6)
    impact.add_argument("--max-nodes", type=int, default=200)
    impact.set_defaults(func=cmd_impact)

    trace = sub.add_parser("trace", help="trace call and polymorphic paths from one symbol")
    trace.add_argument("bundle")
    trace.add_argument("--from", dest="start", required=True)
    trace.add_argument("--direction", choices=["outbound", "inbound"], default="outbound")
    trace.add_argument("--max-depth", type=int, default=8)
    trace.add_argument("--max-nodes", type=int, default=200)
    trace.add_argument("--include-internal", action="store_true", default=True)
    trace.add_argument("--exclude-internal", action="store_false", dest="include_internal")
    trace.add_argument("--json", action="store_true")
    trace.set_defaults(func=cmd_trace)

    surfaces = sub.add_parser("surfaces", help="list user surface records")
    surfaces.add_argument("bundle")
    surfaces.add_argument("--module")
    surfaces.add_argument("--json", action="store_true")
    surfaces.set_defaults(func=cmd_surfaces)

    dsm = sub.add_parser("dsm", help="build a module/provider dependency structure matrix")
    dsm.add_argument("bundle")
    dsm.add_argument("--level", choices=["module", "provider"], default="module")
    dsm.add_argument("--include-internal", action="store_true")
    dsm.add_argument("--json", action="store_true")
    dsm.set_defaults(func=cmd_dsm)
    return parser
