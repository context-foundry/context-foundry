#!/usr/bin/env bash
# deploy.sh -- validate and deploy the Context Foundry build service to Azure.
#
# Usage:
#   bash deploy/azure/deploy.sh <resource-group> [<location>]
#
# Prereqs:
#   - the `az` CLI, logged in (`az login`)
#   - an existing resource group, or permission to create one
#   - cp deploy/azure/example.env deploy/azure/.env  and fill it in
#     (this script sources deploy/azure/.env when present)
#
# Build the daemon image with `cargo build --release --features azure` and
# push it to ACR before the Container App can start. See deploy/README.md.
set -euo pipefail

command -v az >/dev/null 2>&1 || {
  echo "deploy.sh: the 'az' CLI is required -- install it and run 'az login'" >&2
  exit 1
}

RG="${1:?resource group required -- usage: bash deploy/azure/deploy.sh <resource-group> [<location>]}"
LOC="${2:-eastus}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
# shellcheck disable=SC1090
[[ -f "$ENV_FILE" ]] && source "$ENV_FILE"

ACR_NAME="${ACR_NAME:?ACR_NAME required -- set it in deploy/azure/.env}"
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:?STORAGE_ACCOUNT required -- set it in deploy/azure/.env}"
SERVICE_IMAGE="${SERVICE_IMAGE:?SERVICE_IMAGE required -- set it in deploy/azure/.env}"
API_KEYS="${API_KEYS:?API_KEYS required -- set it in deploy/azure/.env}"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY required -- set it in deploy/azure/.env}"

TEMPLATE="$SCRIPT_DIR/main.bicep"

echo "deploy.sh: ensuring resource group $RG in $LOC"
az group create --name "$RG" --location "$LOC" >/dev/null

echo "deploy.sh: compiling $TEMPLATE"
az bicep build --file "$TEMPLATE"

echo "deploy.sh: validating the deployment"
az deployment group validate \
  --resource-group "$RG" \
  --template-file "$TEMPLATE" \
  --parameters \
    acrName="$ACR_NAME" \
    storageAccountName="$STORAGE_ACCOUNT" \
    serviceImage="$SERVICE_IMAGE" \
    apiKeys="$API_KEYS" \
    anthropicApiKey="$ANTHROPIC_API_KEY" >/dev/null

echo "deploy.sh: creating the deployment"
az deployment group create \
  --resource-group "$RG" \
  --template-file "$TEMPLATE" \
  --parameters \
    acrName="$ACR_NAME" \
    storageAccountName="$STORAGE_ACCOUNT" \
    serviceImage="$SERVICE_IMAGE" \
    apiKeys="$API_KEYS" \
    anthropicApiKey="$ANTHROPIC_API_KEY" \
  --query properties.outputs

echo
echo "deploy.sh: done. Next: add an Azure Storage lifecycle-management rule on"
echo "the 'foundry-jobs' container to delete blobs older than 30 days -- see the"
echo "'Diagnostics and artifact retention' section of docs/build-service-runbook.md."
