# LiteLLM Admin UI demo (trainer laptop)

Purpose: show the LiteLLM configuration in its web UI during Day 2. The CAI LiteLLM Application has no database, so its UI cannot
log in. This runs the same gateway with a Postgres database on your laptop. **Participants do not use it**: Lab 10 keeps calling the
LiteLLM Application in CAI. Nothing here changes the workshop architecture, and nothing is deployed to CAI.

## Start

```bash
cd docs/trainer/litellm-ui-demo
cp .env.example .env            # then edit .env: master key, database password, vLLM address
docker compose up -d
docker compose logs -f litellm  # wait for "Uvicorn running on http://0.0.0.0:4000"
```

Open `http://localhost:4000/ui`. Sign in with username `admin` and the master key from `.env`. The models of `config/litellm.yaml`
(`qwen-primary`, `training-fallback`) are listed. Keys, teams and budgets can be created there (they live in the demo database only).

## Show

Models, the alias to model mapping, the retry and fallback settings, the keys page, and the request logs.

## Stop and clean up

```bash
docker compose down        # keeps the demo database
docker compose down -v     # also deletes it
```

## Notes

- Showing the configuration does not need a connection to the model. Only a test request from the UI needs `VLLM_BASE_URL` to be reachable
  from your laptop (Application addresses are usually reachable only from the BNI network or VPN).
- The port is published on `127.0.0.1` only, so nobody else on the network can reach the UI.
- Use a demo master key. Do not reuse the key of the CAI Application, and never paste either key into a slide or a chat.
- The image defaults to `ghcr.io/berriai/litellm:main-stable`. Pin a released tag in `.env` (`LITELLM_IMAGE`) for a repeatable demo.
  This demo was not started here: the compose file was only validated with `docker compose config`.
