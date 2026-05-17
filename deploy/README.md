# Build Service Deployment Manifests

Deployment manifests for the Context Foundry build service (`foundry serve`).
Two targets:

- [`compose/`](compose/docker-compose.yml) -- a Docker Compose stack for the
  homelab (Postgres + service + Caddy).
- [`azure/`](azure/main.bicep) -- a Bicep template + `az` wrapper for Azure
  Container Apps.

For operations (env reference, key rotation, failure playbooks, retention)
see the [operator runbook](../docs/build-service-runbook.md). For the API
contract see the [API contract](../docs/build-service-api.md).

## Local / homelab (Docker Compose)

```bash
cp deploy/compose/example.env deploy/compose/.env   # then edit
docker compose -f deploy/compose/docker-compose.yml up -d
```

The default `.env` runs the `mock` build backend: no Anthropic key, no real
builds. For real builds set `FOUNDRY_SERVICE_BUILD_BACKEND=local_docker` and a
real `ANTHROPIC_API_KEY` in `.env`.

Validate the manifest before bringing it up:

```bash
docker compose -f deploy/compose/docker-compose.yml config
```

## Azure Container Apps

```bash
# 1. Build the daemon image with the azure feature and push it to ACR.
cargo build --release --features azure
#    docker build / az acr build, then push to <acr>.azurecr.io/foundry-service:latest

# 2. Fill in the deploy env.
cp deploy/azure/example.env deploy/azure/.env       # then edit

# 3. Validate the template.
az bicep build --file deploy/azure/main.bicep

# 4. Deploy.
bash deploy/azure/deploy.sh <resource-group> <location>
```

`deploy.sh` runs `az group create`, `az bicep build`, `az deployment group
validate`, then `az deployment group create`, and prints the outputs.

**Operator follow-up:** add an Azure Storage lifecycle-management rule on the
`foundry-jobs` blob container to delete blobs older than 30 days. This is the
artifact/diagnostics retention policy from the runbook -- the template
provisions the container but does not set the lifecycle rule.

## Validation

Each command is a no-op where its tool is absent:

| Target | Command |
|--------|---------|
| Compose | `docker compose -f deploy/compose/docker-compose.yml config` |
| Caddyfile | `caddy validate --config deploy/compose/Caddyfile --adapter caddyfile` |
| Bicep | `az bicep build --file deploy/azure/main.bicep` |
| Shell | `bash -n deploy/azure/deploy.sh` |

## See also

- [Operator runbook](../docs/build-service-runbook.md)
- [API contract](../docs/build-service-api.md)
