# Random Garden Auto-Battler Plan

## Summary
- Build a browser-first, Python-backed auto-battler inspired by Hearthstone Battlegrounds, but starting with a deterministic combat-only engine.
- First milestone: two boards fight automatically with max 7 cards per side, no grid, stats-only cards, seeded RNG, replayable event logs, and strong tests.
- Long-term target: eight-player match structure, browser client first, Telegram Mini App later.
- Frontend default: SvelteKit + TypeScript + PixiJS. Use Three.js only later if the game becomes meaningfully 3D.

## Core Architecture
- Keep `game/` as a pure Python domain engine with no FastAPI, database, Telegram, or frontend imports.
- Use `services/` for backend adapters: FastAPI HTTP/WebSocket APIs, guest sessions, serialization, and future matchmaking.
- Use `frontend/` for SvelteKit + PixiJS: Svelte owns UI/state panels, PixiJS owns animated board/combat rendering.
- Treat `db/` as future-only until persistence is needed; guest browser sessions are enough during engine/browser prototyping.
- Use Python 3.11+, Poetry, Pydantic v2 for API/data validation, pytest for unit tests, Hypothesis-style property tests where combat invariants matter, Ruff + mypy for quality gates.

## Engine V0
- Define typed Python models for card definitions, card instances, board state, combat request, combat result, combat events, and deterministic RNG state.
- Board rules: max 7 cards per side, left-to-right ordering, no positioning grid, no economy, no shop, no player damage yet.
- Combat rules:
  - First attacker is chosen by seeded coinflip.
  - Turns alternate between sides.
  - The active side attacks with its next living card in left-to-right order.
  - Target is BG-style random among living enemy cards, using the seeded RNG.
  - Damage is simultaneous between attacker and defender.
  - Combat ends when one side has no living cards, both sides have no living cards, or a defensive max-step guard trips.
- Output a complete event log, not just the winner, so tests, frontend replay, debugging, and future spectator tools all share one truth.
- Include extension points for future effects, but do not implement effects in V0. Reserve lifecycle hooks such as combat start, before attack, after damage, death, summon, and combat end.

## API And Frontend
- Initial Python API: `simulate_combat(input) -> CombatResult`, callable directly by tests and a CLI/dev harness.
- First backend endpoint later: `POST /api/combat/simulations`, returning the same combat result/event schema.
- Add WebSockets only once live browser replay or match sessions need server push; FastAPI is a good fit because it supports WebSocket endpoints directly.
- Frontend V0 should render combat replays from event logs, not duplicate combat rules in TypeScript.
- PixiJS should handle cards, movement, hit flashes, death removal, and replay timing; SvelteKit should handle shell UI, controls, history, seed input, debug panels, and responsive layout.
- Telegram is postponed, but frontend should remain WebView-friendly: mobile-first layout, no browser-only assumptions, and future adapter for Telegram init data.

## SOLID And DRY Rules
- Single Responsibility: combat resolution, content registry, API serialization, and rendering stay separate.
- Open/Closed: new card effects are added through hooks/registered effect classes, not giant `if card_id == ...` branches.
- Liskov/Interface Segregation: effect hooks stay narrow so simple effects do not implement irrelevant methods.
- Dependency Inversion: backend and frontend consume engine results/contracts; the engine does not depend on FastAPI, DB, or PixiJS.
- DRY: combat event schema is the shared source for tests, API responses, replay viewer, and debugging.
- Avoid premature abstractions, but design the first effect-free engine so adding battlecries/deathrattles later does not require rewriting combat flow.

## Roadmap
- Phase 0: confirm edit-by-edit workflow, scaffold tooling, tests, and repo layout without touching gameplay complexity.
- Phase 1: implement deterministic combat engine, event log, fixtures, and exhaustive tests.
- Phase 2: add CLI/dev simulation harness for quick seed-based combat inspection.
- Phase 3: add FastAPI simulation endpoint and schema validation.
- Phase 4: create SvelteKit/PixiJS browser replay viewer for seeded combat results.
- Phase 5: expand toward eight-player match shell: seats, pairings, round history, eliminations, and bot placeholders.
- Phase 6: add basic original economy with familiar buy/reroll/upgrade-style decisions, but custom numbers and modular decision handling.
- Phase 7: add first modular effects and richer typed content.
- Phase 8: prepare Telegram Mini App integration after browser UX and backend contracts stabilize.

## Test Plan
- Same seed and same boards always produce identical event logs and final result.
- Different seeds can produce different legal targets without violating deterministic replay.
- Max 7 cards per board is enforced.
- Empty board vs board, empty vs empty, one-card lethal trades, and full-board fights are covered.
- Attack alternation and seeded first attacker are tested directly.
- Random targeting never selects dead or missing cards.
- Event replay reconstructs the same final board state as direct simulation.
- Property tests guard against infinite combat, negative health drift, invalid card references, and non-terminating loops.
- API tests verify request validation and response schema once FastAPI is added.
- Frontend tests verify replay ordering, board rendering from event logs, mobile layout, and no duplicated combat logic.

## Assumptions
- No repo edits happen without direct user confirmation for each edit.
- V0 content is typed Python, not YAML/JSON.
- V0 identity is guest sessions only.
- V0 is combat-only; economy and eight-player match flow are architectural targets, not first implementation work.
- Sources used for stack choices: [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/), [SvelteKit docs](https://svelte.dev/docs/kit/introduction), [PixiJS docs](https://pixijs.download/release/docs/index.html), [Pydantic docs](https://docs.pydantic.dev/latest/), [Telegram Mini Apps docs](https://docs.telegram-mini-apps.com/platform/about).
