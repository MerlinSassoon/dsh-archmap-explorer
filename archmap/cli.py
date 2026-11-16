from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .pipeline import build_architecture
from .render import render_html
from .validate import validate_bundle


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
    for flow in bundle["functionFlows"]:
        safe = flow["id"].replace(":", "_").replace("/", "_").replace(".", "_")
        (functions_dir / f"{safe}.json").write_text(json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_build(args: argparse.Namespace) -> int:
    project_root = Path(args.project).resolve()
    if not project_root.is_dir():
        print(f"error: project root is not a directory: {project_root}", file=sys.stderr)
        return 2
    config_path = Path(args.config).resolve() if args.config else None
    out_dir = Path(args.out).resolve() if args.out else project_root / ".archmap"
    bundle = build_architecture(project_root, config_path)
    try:
        bundle["project"]["root"] = Path(
            __import__("os").path.relpath(project_root, out_dir)
        ).as_posix()
    except Exception:
        bundle["project"]["root"] = "."
    issues = validate_bundle(bundle)
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
    html_path.write_text(render_html(bundle, annotations), encoding="utf-8")
    if args.split:
        _write_split(bundle, out_dir)
    if annotations_path:
        print(f"annotations: {annotations_path}")
    print(f"project:   {bundle['project']['name']}")
    print(f"modules:   {bundle['stats']['modules']}")
    print(f"functions: {bundle['stats']['functions']}")
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
    issues = validate_bundle(bundle)
    if not issues:
        print("OK: schema, cross references, function invariants and layout are valid")
        return 0
    _print_issues(issues)
    return 1 if any(issue.get("severity") == "error" for issue in issues) else 0


def cmd_flow(args: argparse.Namespace) -> int:
    project_root = Path(args.project).resolve()
    config_path = Path(args.config).resolve() if args.config else None
    bundle = build_architecture(project_root, config_path)
    target_file = Path(args.file).name if args.file else None
    candidates = bundle["functionFlows"]
    if target_file:
        candidates = [flow for flow in candidates if Path(flow["file"]).name == target_file]
    if args.function:
        candidates = [
            flow
            for flow in candidates
            if flow["name"] == args.function or flow["qualifiedName"].endswith("." + args.function)
        ]
    if not candidates:
        print("error: no matching function flow", file=sys.stderr)
        return 1
    flow = candidates[0]
    if args.json:
        print(json.dumps(flow, ensure_ascii=False, indent=2))
    else:
        print(f"{flow['qualifiedName']} ({flow['file']}:{flow['line']})")
        print(f"nodes={len(flow['nodes'])} edges={len(flow['edges'])} canvas={flow['layout']['canvas']}")
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
    before_flows = {flow["id"] for flow in before.get("functionFlows", [])}
    after_flows = {flow["id"] for flow in after.get("functionFlows", [])}
    for added in sorted(after_flows - before_flows):
        print(f"+ {added}")
    for removed in sorted(before_flows - after_flows):
        print(f"- {removed}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archmap", description="ArchMap v3 module-first architecture analysis")
    parser.add_argument("--version", action="version", version="archmap 1.0.0")
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

    flow = sub.add_parser("flow", help="inspect a single generated function flow")
    flow.add_argument("project", nargs="?", default=".")
    flow.add_argument("--config")
    flow.add_argument("--file")
    flow.add_argument("--function")
    flow.add_argument("--json", action="store_true")
    flow.set_defaults(func=cmd_flow)

    serve = sub.add_parser("serve", help="serve generated artifacts locally")
    serve.add_argument("directory", nargs="?", default=".archmap")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(func=cmd_serve)

    diff = sub.add_parser("diff", help="compare two architecture bundles")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.set_defaults(func=cmd_diff)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
