# Contributing

Thanks for taking a look. This project optimizes for **honest static facts** over
impressive-looking guesses: a relation that cannot be resolved is reported as
unresolved, never fabricated. Please keep that contract when changing analysis
or the UI.

## Setup

```bash
git clone https://github.com/MerlinSassoon/dsh-archmap-explorer
cd dsh-archmap-explorer

python3 -m pytest -q          # Python core
npm install && npm test       # DSH plugin
```

## Before opening a pull request

```bash
python3 -m pytest -q
python3 -m archmap build . --config examples/archmap_v3.archmap.json --out .archmap/self
python3 -m archmap check .archmap/self/architecture.json

npm run prepack
npm test
```

Browser smoke test (optional, needs a local Chromium):

```bash
ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py
```

## What kind of changes are welcome

- **Resolution accuracy**: property chains, `cast`, Protocol with a single
  implementation, conditional imports. This is the highest-value area.
- **Diagnostics quality**: errors that tell the user what to do next.
- **Layout and readability** on dense graphs.
- **Configuration validation**: unknown keys should never fail silently.

## What needs a design discussion first

Open an issue before writing code for: bundle schema changes, new node kinds,
new execution-flow semantics, or anything that changes what counts as a
"capability surface". Those contracts are documented in
[docs/archmap-v3-design.md](docs/archmap-v3-design.md) and
[docs/archmap-architecture-spec.md](docs/archmap-architecture-spec.md) — the docs
and the code have to move together.

## Style

- Python 3.10+, no third-party runtime dependencies.
- The HTML output must stay self-contained: no CDN, no external fonts, no
  network requests.
- User-visible strings are currently Chinese; keep new strings consistent with
  the surrounding UI until the English UI lands.
- Add a test for every behaviour change; `tests/` mirrors `archmap/` by module.

## Reporting bugs

Include the command, the configuration, `archmap --version`, and either a
screenshot or `archmap check --json` output. "The graph is wrong" reports are
welcome — say what you expected and what the code actually does.
