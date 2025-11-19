# Copilot Instructions

## Architecture Snapshot
- `start_services.py` is the only supported entrypoint: it clones `supabase/` (sparse checkout), copies the root `.env` into `supabase/docker/.env`, generates a SearXNG secret, then starts the Supabase stack before the local AI stack so dependent services (n8n, Langfuse) always see healthy databases.
- `docker-compose.yml` uses `include: ./supabase/docker/docker-compose.yml`, so both stacks share the same `localai` project name and can be controlled together with `docker compose -p localai ...`.
- Major services: n8n (with `n8n-import` bootstrap), Open WebUI, Flowise, CPU-only Ollama, Qdrant, Neo4j, Langfuse (web + worker backed by Postgres/ClickHouse/MinIO/Valkey), SearXNG, and Caddy for TLS/front-door routing.
- This fork standardizes on the CPU profile and the private environment; other upstream compose profiles still exist but are not used during development or deployment here.
- `n8n/backup/workflows/*.json` and `n8n/backup/credentials` mount into `n8n-import`, which runs `n8n import:*` before the main `n8n` container starts; update those JSON files if you want new defaults shipped with the stack.
- `shared/` is bind-mounted to `/data/shared` inside n8n for local file triggers/read-write nodes; keep automations that need filesystem access inside this folder.
- Flowise and Open WebUI ship pre-baked integrations: Flowise tool JSONs live under `flowise/`, while `n8n_pipe.py` is the function Open WebUI expects (Workspace → Functions) to call back into n8n webhooks.

## Running & Updating the Stack
- Bring everything up with `python start_services.py --profile cpu --environment private`; the script applies `docker-compose.override.private.yml` so all service ports stay bound to `127.0.0.1`.
- `--profile cpu` keeps Ollama on the standard image without GPU runtime assumptions, ensuring consistent behavior across developer machines and CI boxes.
- `--environment private` exposes only localhost ports; avoid mixing in the public overrides unless you intend to reconfigure Caddy for external access.
- Upgrades follow the README recipe: `docker compose -p localai -f docker-compose.yml --profile cpu down`, `docker compose ... pull`, then rerun `start_services.py --profile cpu --environment private`; don’t rely on the Python script alone to pull images.
- When toggling domains, set the `*HOSTNAME` vars in `.env`; Caddy references them via placeholders and auto-enables Let’s Encrypt if they look like real domains (still relevant even in private mode if you front with real DNS).

## Development Conventions & Gotchas
- Any change to Supabase secrets must be mirrored in both the root `.env` and the generated `supabase/docker/.env` (the script overwrites it each run), so treat the root `.env` as the source of truth.
- If you edit `searxng/settings.yml`, keep `settings-base.yml` untouched—`start_services.py` only copies the file when `settings.yml` is missing. Re-running the script will not regenerate the file once it exists.
- The script may temporarily comment out `cap_drop: - ALL` for SearXNG on first boot; don’t delete the marker comment or the auto-reenable logic will fail.
- Langfuse expects ClickHouse, MinIO, Redis, and Postgres to share the same secrets defined in `.env`; missing `LANGFUSE_*` values will block the web UI even if the container is up.
- Open WebUI’s `n8n_pipe` function requires a production webhook URL (`n8n_url`) and optional bearer token; the JSON payload uses `input_field`/`response_field` keys that must match the n8n workflow you expose.
- `n8n-tool-workflows/*.json` and `flowise/*` are sample automations exposed via n8n’s “Use workflow” import or Flowise’s tool loader—keep their IDs stable if other services call them via HTTP paths embedded in the JSON.
- Shared credentials (e.g., Slack OAuth IDs) inside the workflow JSONs are placeholders; prompt the user to configure them through the n8n UI instead of editing JSON unless you’re preparing a new default export.

## Debugging Tips
- Most “service unavailable” errors trace back to Supabase env mismatches; confirm `POSTGRES_PASSWORD` doesn’t contain `@` (per README) and that Docker Desktop exposes the daemon on `tcp://localhost:2375` when running on macOS/Windows.
- If SearXNG restarts on first boot, ensure `chmod 755 searxng` (per README) completed so it can write `uwsgi.ini`; the generated secret lives inside `searxng/settings.yml`.
- `n8n` won’t start until `n8n-import` finishes; check its logs first whenever imports hang.
- Use `docker compose -p localai logs -f <service>` for targeted debugging; all services share the same project namespace so container names match the entries in `docker-compose.yml`.
