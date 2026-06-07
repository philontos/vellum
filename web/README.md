# Vellum web

Single eternal conversation UI for Vellum.

## Dev
1. Start the API (from `../api`, with `.env` configured — LLM + embedding key):
   `.venv/bin/python -m uvicorn app.main:app --port 18080`
2. Start the web dev server: `pnpm install && pnpm dev` → http://localhost:5173
   (Vite proxies `/chat`, `/history`, `/health` to the API.)

## Build
`pnpm build` → static assets in `dist/`. For a single-service deploy, have the API
serve `dist/` as static files (not wired by default).

## Test
`pnpm test` — vitest, covers the SSE parser.
