# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Factory Inventory Management System demo with GitHub integration. Full-stack app: Vue 3 frontend, Python FastAPI backend, in-memory mock data (no database). `client/CLAUDE.md` and `server/CLAUDE.md` hold per-side conventions.

> ⚠️ **This repository and any fork you create are PUBLIC.** Do not commit credentials, internal hostnames, or private registry URLs. `client/.npmrc` pins the public npm registry and `client/package-lock.json` is gitignored to prevent locally-configured registries from leaking into commits — leave both in place.

## Commands

Requires `uv` (backend, Python >=3.11) and Node `^20.19.0 || >=22.12.0` (frontend, Vite 8).

```bash
# Start both servers (installs deps on first run; logs in /tmp/inventory-*.log)
./scripts/start.sh          # stop with ./scripts/stop.sh

# Backend: http://localhost:8001 (docs at /docs)
cd server && uv sync && uv run python main.py

# Frontend: http://localhost:3000
cd client && npm install && npm run dev
cd client && npm run build   # -> client/dist/
```

**Tests** (backend only; there are no frontend tests and no linter configured). Run from `server/`, because pytest and the other dev dependencies live in the server's uv environment. `cd tests && uv run pytest` (as written in `tests/README.md`) fails, since `tests/` has no uv project.

```bash
cd server
uv run pytest ../tests                                    # all tests (config: tests/pytest.ini)
uv run pytest ../tests/backend/test_inventory.py          # one file
uv run pytest ../tests/backend/test_inventory.py::TestInventoryEndpoints::test_get_all_inventory
uv run pytest ../tests -k "warehouse"                     # by name
```

`tests/backend/conftest.py` puts `server/` on `sys.path` and imports `main.app` directly into a `TestClient`, so no server needs to be running.

## Architecture

**Data flow:** Vue filters → `client/src/api.js` → FastAPI → in-memory filtering → Pydantic `response_model` validation → computed properties in views.

### Backend (`server/`)
- `mock_data.py` loads every `server/data/*.json` file once at import time into module-level lists. Any mutation lives only until restart.
- `main.py` is the entire API: Pydantic models, two shared filter helpers, and all routes.
  - `apply_filters()` handles `warehouse` (exact match), `category` and `status` (case-insensitive). The value `'all'` or a missing param means no filter.
  - `filter_by_month()` substring-matches `month` (e.g. `2025-03`) against `order_date`, or expands `Q1-2025`…`Q4-2025` via the hardcoded `QUARTER_MAP`. Only 2025 quarters exist.
- The Pydantic models are the response schema. Fields missing from a model are silently dropped from responses, so update the model whenever the JSON shape changes.
- `generate_data.py` regenerates and **overwrites** `data/orders.json` with random data (run from `server/`).

### Frontend (`client/src/`)
- Routes are defined in `main.js` (Dashboard, Inventory, Orders, Demand, Spending, Reports). `views/Backlog.vue` exists but is not routed.
- `composables/useFilters.js` keeps filter state in **module-level refs** (a singleton shared by every view). `getCurrentFilters()` maps `selectedLocation` → `warehouse` and `selectedPeriod` → `month`. Views watch these refs and refetch.
- `api.js` hardcodes `http://localhost:8001/api` and drops any filter whose value is `'all'`.
- i18n: `composables/useI18n.js` with `locales/en.js` and `locales/ja.js` (persisted in `localStorage` as `app-locale`). Every new UI string needs a key in **both** locale files. Locale also drives currency: `ja` → JPY via `utils/currency.js` (fixed rate of 150). Format money through `formatCurrency` rather than formatting by hand.
- `composables/useAuth.js` is a mock user (no real auth).

### Known gaps
- `api.js` calls `/api/tasks` (GET/POST/PATCH/DELETE, used by `App.vue`) and `/api/purchase-orders`, but the backend implements neither. The `PurchaseOrder` models in `main.py` exist only to compute `has_purchase_order` on `/api/backlog`.
- `tests/README.md` lists a `test_orders.py` and test counts that don't match what's in `tests/backend/`.

## API Endpoints
- `GET /api/inventory`, `/api/inventory/{id}`. Filters: warehouse, category.
- `GET /api/orders`, `/api/orders/{id}`. Filters: warehouse, category, status, month.
- `GET /api/dashboard/summary`. All filters.
- `GET /api/demand`, `/api/backlog`. No filters.
- `GET /api/spending/{summary,monthly,categories,transactions}`.
- `GET /api/reports/{quarterly,monthly-trends}`. Computed from orders.
- `GET /api/restock-orders` (newest first), `POST /api/restock-orders` with body `{budget, items: [{sku, quantity}]}`. These store orders in memory and are separate from `/api/orders`. The server recomputes prices from `demand_forecasts.json` (`unit_cost`, `lead_time_days`), rejects orders over budget with a 400, and sets the order's lead time to its slowest item.

## Restocking
The Restocking tab (`views/Restocking.vue`) recommends items with `client/src/utils/restock.js`. Items are ranked by trend (increasing, then stable, then decreasing), then by demand gap. Each item asks for its full `forecasted_demand`, and the budget is filled greedily, so an item may get a partial quantity. Submitted orders appear in the "Submitted Orders" section of the Orders tab.

## Critical Tool Usage Rules

### Subagents
Use the Agent tool with these project subagents (defined in `.claude/agents/`):

- **vue-expert**: Vue 3 frontend features, UI components, styling, and client-side functionality.
  - **MANDATORY RULE: ANY time you need to create or significantly modify a .vue file, you MUST delegate to vue-expert.**
- **code-reviewer**: Use after writing significant code.
- **security-auditor**: Security reviews.
- **Explore**: Understanding codebase structure and searching for patterns.

### Skills
- **backend-api-test**: Use when writing or modifying tests in `tests/backend/`.

### MCP Tools (`.mcp.json`)
- **ALWAYS use GitHub MCP tools** (`mcp__github__*`) for ALL GitHub operations.
  - Exception: for local branches, use `git checkout -b` instead of `mcp__github__create_branch`.
- **ALWAYS use Playwright MCP tools** (`mcp__playwright__*`) for browser testing, against `http://localhost:3000` (frontend) and `http://localhost:8001` (API).

## Code Conventions
- Always document non-obvious logic changes with comments.

## Common Issues
1. Use unique keys in `v-for` (not `index`). Use `sku`, `month`, etc.
2. Validate dates before `.getMonth()` calls.
3. Update Pydantic models when changing JSON data structure.
4. Inventory has no time dimension, so the month filter doesn't apply to it.
5. Revenue goals: $800K/month for a single month, $9.6M YTD for all months.

## Design System
- Colors: slate/gray (#0f172a, #64748b, #e2e8f0). Global styles in `client/src/App.vue`.
- Status colors: green/blue/yellow/red.
- Charts: custom SVG (no chart library). CSS Grid for layouts.
- No emojis in the UI.
