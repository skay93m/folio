# Folio

Reusable Django 6 UI engine, typed page pattern contracts, source-linked element catalogue, deterministic static release bundler, and static/Playwright verifier for the SK Design System (`ADR 0020`).

## Features

- **Packaged Django app**: Add `"folio"` to `INSTALLED_APPS` to discover templates (`APP_DIRS = True`) and static assets (`sk-design-system.css`, `folio.js`, Bootstrap 5.3.9, self-hosted IBM Plex F3 fonts, and licences).
- **Typed immutable pattern contracts**: `Launchpad`, `Homepage`, `Reading`, `Dashboard`, `SearchIndex`, `WorkJournal`, and `WorkQueue` with fail-fast validation.
- **Dual rendering adapters**: `folio.render(request, page)` for Django / HTMX views and `folio.render_static(page)` for standalone HTML generation.
- **Single-source catalogue**: All 6 Bootstrap-aligned element groups and 7 page pattern inventories linked to one shared Django template partial per entry.
- **Deterministic release bundler & verifier**: `build_release()` emits repeatable `dist/` bundles with SHA-256 `manifest.json`; `verify_target()` runs static + headless Playwright checks.
