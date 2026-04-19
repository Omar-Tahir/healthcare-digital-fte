# ADR-010: HTMX for Coder Review UI

**Status:** ACCEPTED
**Date:** 2026-04-02
**Decision makers:** Engineering team
**Constitution references:** Article III.8 (FastAPI),
Article II.4 (HIPAA), Article IV.3 (HIM Director as Champion)

---

## Context

The coder review UI (DESIGN-006) requires dynamic interactions:
- Accept/reject toggles that update DRG calculations without
  full page reloads
- Worklist auto-refresh every 60 seconds
- Evidence quote highlighting and scroll synchronization
- Approval confirmation modals

We must choose a frontend technology that supports these
interactions while maintaining security, simplicity, and
maintainability in a healthcare environment.

---

## Decision

**Use HTMX with Jinja2 server-rendered HTML templates.
No React, no npm, no Node.js, no frontend build step.**

Implementation:
1. **HTMX** (vendored, not CDN) provides partial page updates,
   form submissions, polling, and event-driven UI changes
2. **Jinja2** templates rendered server-side by FastAPI
3. **Single CSS file** — no preprocessor, no Tailwind build
4. **Minimal custom JavaScript** — only for evidence quote
   scroll synchronization (not achievable with HTMX alone)
5. **HTMX vendored into static assets** — no external CDN
   dependency (healthcare networks may restrict internet)

---

## Alternatives Considered

### Alternative 1: React SPA

Full React single-page application with API backend.

**Rejected because:**
- Adds npm, Node.js, and a build step to the project —
  increases supply chain attack surface in a HIPAA environment
- Client-side state management for PHI-containing data creates
  additional security surface (browser memory, DevTools,
  localStorage)
- Requires separate frontend and backend developer skill sets
  — our team is Python-first
- React SPA complexity is disproportionate to the UI needs
  (form-based workflow, not a complex interactive application)
- Bundle size and load time higher than server-rendered HTML
- Server-rendered HTML is inherently more secure — PHI never
  stored in client-side state management

### Alternative 2: Vue.js or Svelte

Lighter SPA frameworks with smaller bundle sizes.

**Rejected because:**
- Still requires npm and a build step
- Still introduces client-side state management concerns
- Same skill set mismatch (JavaScript framework expertise
  needed alongside Python)
- Marginal improvement over React for our specific use case

### Alternative 3: Server-Rendered HTML Only (No HTMX)

Pure Jinja2 templates with full page reloads for every action.

**Rejected because:**
- Accept/reject toggles would cause full page reloads —
  disruptive to coder workflow (they lose scroll position
  in the clinical note panel)
- Worklist polling requires JavaScript anyway
- DRG recalculation on toggle change requires either
  JavaScript or full page reload
- HTMX adds the specific interactivity needed with minimal
  complexity (single <script> tag, HTML attributes only)

### Alternative 4: Alpine.js + HTMX

HTMX for server communication + Alpine.js for client-side
interactivity.

**Deferred (not rejected):**
- Could be useful if client-side interactivity needs grow
- Currently unnecessary — evidence scroll is the only
  client-side interaction, handled by ~20 lines of vanilla JS
- Can be added later without architectural change

---

## Consequences

### Positive

1. **No build step** — `uv run uvicorn` serves the complete
   application including UI. No npm install, no webpack, no
   build pipeline.
2. **PHI security** — all rendering is server-side; PHI never
   stored in client-side JavaScript state, localStorage, or
   framework stores
3. **Python-only stack** — entire application maintained by
   Python developers. No JavaScript framework expertise needed.
4. **Small dependency footprint** — HTMX is a single 14KB
   file vendored into the project. No transitive dependencies.
5. **Works offline** — HTMX vendored locally; no CDN calls.
   Works in hospital networks with restricted internet.
6. **Fast page loads** — server-rendered HTML loads faster
   than SPA bootstrap (no JS framework initialization)

### Negative

1. **Limited client-side interactivity** — complex animations,
   drag-and-drop, or rich text editing would be difficult.
   Mitigation: the coder review UI does not need these.
2. **HTMX is less mainstream** than React — smaller talent
   pool and community. Mitigation: HTMX is HTML-attribute
   based; any developer who knows HTML can learn it in hours.
3. **Server load increases** — every interaction hits the
   server (no client-side caching/computation). Mitigation:
   partial HTML responses are small; FastAPI handles 50+
   concurrent users per instance easily.
4. **Testing** — no established frontend testing ecosystem
   like React Testing Library. Mitigation: test at the route
   level (FastAPI TestClient) and verify HTML attributes.

---

## References

- Constitution Article III.8 (FastAPI)
- Constitution Article II.4 (HIPAA)
- DESIGN-006 (Coder Review UI Specification)
- HTMX documentation (htmx.org)
