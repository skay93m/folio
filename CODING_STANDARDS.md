# Coding Standards (`folio`)

Reviewer-focused invariants for `skay93m/folio`. Every PR is checked against these rules.

## 1. Public-Repository Opsec (`ADR 0021`)

- Keep `skay93m/folio` strictly limited to generic SK Design System code, tokens, fonts, templates, and generic fixtures (for example `SK Editorial`).
- Keep private workstation paths, vault names or allowlists, personal identifiers, planning specs, clinical/academic notes, and downstream private app codenames in private repositories (`skay93m/home` and private vaults).
- Require callers to pass target vault paths or configuration explicitly at runtime rather than hardcoding local filesystem paths.

## 2. Public API Exports & Version Source (`src/folio/__init__.py`)

- Export the curated public package API from `src/folio/__init__.py` and list every exported symbol in alphabetically sorted `__all__`, keeping internal module helpers module-scoped.
- Maintain `__version__` as the single in-package version string aligned with `pyproject.toml` and include `"__version__"` in `__all__`.
- Fail fast at dataclass construction (`__post_init__`) on invalid themes, print modes, semantic roles, empty required strings, all-caps headings, or faux Serif tags (`<em>`, `<strong>`, `<i>`, `<b>`).

## 3. Tokens, WCAG 2.2 AA Contrast & F3 Typography (`ADR 0020`)

- Derive downstream surface themes (including the Obsidian theme) one way from `sk-design-system.css` light `:root` tokens rather than duplicating colour literals.
- Enforce WCAG 2.2 AA contrast (`>= 4.5:1` for normal text and interactive foreground/background pairs, including `--sk-link` `#9C3028` on light paper and `--sk-on-coral` `#271B24` on `--sk-coral` `#FF4F40`) with automated guards that fail on contrast breaches or unmapped tokens.
- Preserve F3 typography rules: `IBM Plex Sans` `600` sentence-case headings, `IBM Plex Serif` `1rem` / `1.75` prose with `font-synthesis: none` faux-style guards, and `IBM Plex Mono` `0.85rem` metadata and code.

## 4. Deep Modules & Shared Helper Reuse

- Design focused, deep modules behind narrow public seams (`render`, `render_static`, `build_release`, `verify_target`, `build_obsidian_theme`, `sync_obsidian_theme`, `verify_obsidian_vault`, `start_prototype_server`) rather than leaking internal parsing or file-layout logic across callers.
- Reuse shared helpers across modules (`iter_css_blocks` in `folio.catalogue`, `ensure_django_setup` in `folio.renderer`, `resolve_pattern_key` in `folio.navigation`) instead of duplicating CSS block parsers, Django setup, or navigation builders.
- Remove unused dataclasses, parameters, imports, and speculative abstractions before opening a PR.

## 5. TDD Verification & Boundary Testing

- Develop new features, adapters, and bug fixes red-to-green: write a failing test at the public function, Django view, or Playwright browser seam, verify it fails, then implement the minimal change to pass.
- Test real token stylesheets, rendered templates, `dist/` bundle determinism, and WCAG contrast guards directly rather than mocking away core invariants.
- Run `uv sync --frozen`, `uv run --frozen ruff check src tests`, `uv run --frozen ruff format --check src tests`, and `uv run --frozen pytest -q` before opening or merging a PR.
