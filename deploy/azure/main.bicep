// Context Foundry build service -- Azure deployment.
//
// Provisions: ACR, a Storage account + blob container, an ACA managed
// environment, the daemon Container App, a user-assigned managed identity,
// and the role assignments the daemon needs to run builds and previews.
//
// Build the daemon image with: cargo build --release --features azure
// This template provisions infrastructure only. The secrets `apiKeys` and
// `anthropicApiKey` are passed at deploy time and are never committed.
//
// See deploy/README.md and ../../docs/build-service-runbook.md.

targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Prefix for generated resource names.')
param namePrefix string = 'foundry'

@description('Globally unique ACR name (5-50 alphanumeric chars).')
param acrName string

@description('Globally unique Storage account name (3-24 lowercase alphanumeric chars).')
param storageAccountName string

@description('ACA managed environment name.')
param acaEnvName string = '${namePrefix}-aca-env'

@description('Blob container for per-job artifacts, logs, and diagnostics.')
param containerName string = 'foundry-jobs'

@description('Daemon image reference in ACR, e.g. <acr>.azurecr.io/foundry-service:latest')
param serviceImage string

@description('Comma-separated /v1 bearer API keys.')
@secure()
param apiKeys string

@description('Real Anthropic API key held by the auth proxy.')
@secure()
param anthropicApiKey string

// Well-known role-definition GUIDs.
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var acrPushRoleId = '8311e382-0749-4cb8-b61a-304f252e45ec'
var blobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var contributorRoleId = 'b24988ac-6180-42a0-ab88-20f7382dd24c'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource jobsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}

// The daemon's user-assigned managed identity -- no static cloud credentials.
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-mi'
  location: location
}

resource acaEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: acaEnvName
  location: location
  properties: {}
}

resource daemon 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-service'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: acaEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8787
        transport: 'auto'
      }
      // Secrets are supplied at deploy time. FOUNDRY_SERVICE_AZURE_STORAGE_KEY
      // is taken from the storage account's listKeys() and held as a secret.
      secrets: [
        {
          name: 'api-keys'
          value: apiKeys
        }
        {
          name: 'anthropic-api-key'
          value: anthropicApiKey
        }
        {
          name: 'storage-key'
          value: storage.listKeys().keys[0].value
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'foundry-service'
          image: serviceImage
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'FOUNDRY_SERVICE_BUILD_BACKEND', value: 'azure_container_apps' }
            { name: 'FOUNDRY_SERVICE_UPSTREAM_AUTH', value: 'api_key' }
            { name: 'FOUNDRY_SERVICE_BIND', value: '0.0.0.0:8787' }
            { name: 'FOUNDRY_SERVICE_PROXY_BIND', value: '0.0.0.0:8788' }
            { name: 'FOUNDRY_SERVICE_AZURE_SUBSCRIPTION_ID', value: subscription().subscriptionId }
            { name: 'FOUNDRY_SERVICE_AZURE_RESOURCE_GROUP', value: resourceGroup().name }
            { name: 'FOUNDRY_SERVICE_AZURE_LOCATION', value: location }
            { name: 'FOUNDRY_SERVICE_AZURE_STORAGE_ACCOUNT', value: storageAccountName }
            { name: 'FOUNDRY_SERVICE_AZURE_ACR_NAME', value: acrName }
            { name: 'FOUNDRY_SERVICE_AZURE_ACA_ENVIRONMENT', value: acaEnvName }
            { name: 'FOUNDRY_SERVICE_AZURE_STORAGE_CONTAINER', value: containerName }
            { name: 'FOUNDRY_SERVICE_AZURE_MI_CLIENT_ID', value: identity.properties.clientId }
            { name: 'FOUNDRY_SERVICE_API_KEYS', secretRef: 'api-keys' }
            { name: 'ANTHROPIC_API_KEY', secretRef: 'anthropic-api-key' }
            { name: 'FOUNDRY_SERVICE_AZURE_STORAGE_KEY', secretRef: 'storage-key' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

// AcrPull + AcrPush on the ACR: pull the daemon image and push the build
// context for ACR image builds.
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, acrPullRoleId)
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource acrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, acrPushRoleId)
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPushRoleId)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Blob Data Contributor on the storage account: read/write per-job
// artifacts, logs, and diagnostics.
resource blobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, blobDataContributorRoleId)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributorRoleId)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Contributor on the resource group: the daemon creates ACA Jobs (builds) and
// Container Apps (previews) at runtime. For a tighter posture, replace this
// with a custom role limited to Microsoft.App/jobs and
// Microsoft.App/containerApps write/delete.
resource rgContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, identity.id, contributorRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', contributorRoleId)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output acrLoginServer string = acr.properties.loginServer
output storageAccountName string = storage.name
output acaEnvironmentId string = acaEnv.id
output managedIdentityClientId string = identity.properties.clientId
output containerAppFqdn string = daemon.properties.configuration.ingress.fqdn
