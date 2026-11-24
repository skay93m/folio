# folio Agent Guide

`folio` is the SK Design System Django 6 UI engine, typed pattern contract library, element catalogue, static release bundler, and static/Playwright verifier. Normative governance and accepted ADRs live in `~/Home` (`ADR 0002`, Lex Superior; `ADR 0020`, SK Design System; `ADR 0021`, Public Git Opsec); repository invariants live in [CODING_STANDARDS.md](CODING_STANDARDS.md).

## Module layout

- `src/folio/__init__.py`: public package API, `__version__`, and alphabetically sorted `__all__` exports.
- `src/folio/contracts.py`: immutable page pattern dataclasses (`Launchpad`, `Homepage`, `Reading`, `Dashboard`, `SearchIndex`, `WorkJournal`, `WorkQueue`) and construction-time validators.
- `src/folio/renderer.py`: dual rendering adapters (`render` for Django/HTMX, `render_static` for standalone HTML) and standalone Django setup.
- `src/folio/catalogue.py`: six Bootstrap-aligned element groups, seven pattern inventories, CSS class index (`build_class_index`), and template/contract validation (`validate_catalogue`).
- `src/folio/fixtures.py`: Git-tracked sample fixtures for all seven page patterns.
- `src/folio/navigation.py`: canonical pattern keys, legacy aliases, and gallery navigation context builder.
- `src/folio/bundle.py`: deterministic `dist/` release bundler (`build_release`), `BuildManifest`, and Obsidian bundle staging.
- `src/folio/obsidian.py`: one-way CSS token parser, WCAG AA contrast check, F3 font embedder, and Obsidian theme builder, sync, and vault drift verifier.
- `src/folio/verifier.py`: unified static and headless Playwright verifier (`verify_target`) for HTML files, URLs, and Obsidian vaults.
- `src/folio/server.py`: loopback HTTP prototype server (`start_prototype_server`) serving prototype directories and `/assets/`.
- `src/folio/views.py`, `src/folio/urls.py`, `src/folio/apps.py`: Django app configuration, reference gallery views, and URL routes.
- `src/folio/templates/`, `src/folio/static/folio/`: SK Design System templates, `sk-design-system.css`, `folio.js`, Bootstrap 5.3.9, and IBM Plex F3 fonts.
- `folio_site/`: standalone Django project settings and root URLs for local gallery and test runs.

## Verification commands

- Static lint: `uv run --frozen ruff check src tests`
- Format check: `uv run --frozen ruff format --check src tests`
- Full test suite: `uv run --frozen pytest -q`

## Conventions

- Run Python, lint, and tests through `uv run --frozen`.
- Keep `skay93m/folio` strictly public (`ADR 0021`); see [CODING_STANDARDS.md](CODING_STANDARDS.md) for opsec, exports, contrast, and TDD rules.
- Follow British English, zero em dashes, and zero body horizontal dividing lines in documentation and comments.
- Land code changes via branches and pull requests referencing `skay93m/home#<issue>`.
