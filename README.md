# Folio

Reusable Django 6 UI engine, typed page pattern contracts, source-linked element catalogue, deterministic static release bundler, and static/Playwright verifier for the SK Design System (`ADR 0020`).

## Features

- **Packaged Django app**: Add `"folio"` to `INSTALLED_APPS` to discover templates (`APP_DIRS = True`) and static assets (`sk-design-system.css`, `folio.js`, Bootstrap 5.3.9, self-hosted IBM Plex F3 fonts, and licences).
- **Typed immutable pattern contracts**: `Launchpad`, `Homepage`, `Reading`, `Dashboard`, `SearchIndex`, `WorkJournal`, and `WorkQueue` with fail-fast validation.
- **Dual rendering adapters**: `folio.render(request, page)` for Django / HTMX views and `folio.render_static(page)` for standalone HTML generation.
- **Single-source catalogue**: All 6 Bootstrap-aligned element groups and 7 page pattern inventories linked to one shared Django template partial per entry.
- **Deterministic release bundler & verifier**: `build_release()` emits repeatable `dist/` bundles with SHA-256 `manifest.json`; `verify_target()` runs static + headless Playwright checks.

## Two-door Launchpad and session dialog

Use `Launchpad(layout="two-door", cards=(acquire, review))` for two equally sized
activity doors that stack on narrow screens (the default layout remains available).
Add `header_actions=(HeaderAction("Switch context and sync", "session-tools"),)`
and `dialogs=(Dialog("session-tools", "Session tools", "app/session_tools.html"),)`.
Import `Dialog` and `HeaderAction` from `folio`. Dialog IDs must be unique and
every header trigger must reference a declared dialog.

The reusable `folio/includes/dialog.html` template uses native `<dialog class="sk-dialog">`
modal semantics, Escape and backdrop dismissal, and an explicit close button. `folio.js`
opens it with `showModal()` and wraps `Tab` and `Shift+Tab` between visible enabled
controls. Consumer templates receive the rendering context and own context selection,
secondary links, CSRF-protected forms, and sync state.

## Retrieval, tutorial turns, and offline Mermaid diagrams

Set `Reading.study_markdown` to plain text using this study dialect:

````text
sk: This is my explanation of the concept.

> [!tutor] sonnet 5.5:
> What evidence supports your explanation?

```quiz
id: recall-001
question: "What should you do when an automated check fails?"
options:
  A: "Ignore the warning."
  B: "Inspect the cause before proceeding."
  C: "Delete the failing test."
  D: "Disable verification."
answer: B
explanation: "Inspecting the root cause preserves correctness without silent regressions."
```

```mermaid
flowchart LR
  Read --> Recall
  Recall --> Defend
```
````

- **Retrieval quiz (`quiz`)**: Structured YAML-like block (`id`, `question`,
  `options` `A:`–`D:`, `answer`, `explanation`) rendered as an accessible
  multiple-choice `<fieldset class="sk-quiz">` with immediate deterministic
  client-side grading in `folio.js` (score counter, `.is-correct`/`.is-wrong`
  feedback, `.sk-quiz-explanation` reveal, and reset) with zero runtime LLM
  or network calls.
- **Strategy 3 tutorial turns (`sk:` / `> [!tutor]`)**: Learner and tutor turns
  (including optional tutor labels such as `> [!tutor] sonnet 5.5:`) carry
  explicit labels as well as distinct styling, and all text is escaped.
- **Offline Mermaid diagrams (`mermaid`)**: `Reading.study_markdown` (` ```mermaid `)
  and `Reading.body_html` (`.sk-mermaid` / `.mermaid` / `pre > code.language-mermaid`)
  render offline via vendored `vendor/mermaid.min.js` with zero external CDN requests
  and sync Mermaid's `neutral` vs `dark` theme automatically with `[data-bs-theme]`
  (with synchronous `@media print` contrast adjustment for dark-mode diagrams).
