// 画像生成 MCP（slide-image-gen）が使う、1 リージョン分の Foundry（AI Services）アカウント、
// gpt-image-2 のデプロイ、ロール割り当て。deploy.py がリージョンごとに、リソースグループ単位で実行する。
// 複数リージョンを 1 回のデプロイにまとめないのは、クォータ不足などで 1 リージョンが失敗しても
// 全体を失敗させず、デプロイできたリージョンだけを使うため。

@description('リージョン')
param location string

@description('アカウント名（= カスタムサブドメイン）。Azure 全体で一意である必要がある')
@minLength(2)
@maxLength(64)
param accountName string

@description('モデル名')
param modelName string = 'gpt-image-2'

@description('モデルのバージョン')
param modelVersion string = '2026-04-21'

@description('デプロイ名（全リージョン共通）')
param deploymentName string = modelName

@description('GlobalStandard の capacity。クォータの空きの範囲で deploy.py が決める')
@minValue(1)
param capacity int = 2

@description('Cognitive Services User を付与する principal の objectId。空ならロール割り当てを作成しない')
param principalId string = ''

@description('ロール割り当て対象の種別')
@allowed([
  'User'
  'ServicePrincipal'
  'Group'
])
param principalType string = 'User'

@description('アカウントに付けるタグ')
param tags object = {}

// AI Services（Foundry）アカウント。Entra ID 認証を前提とするためカスタムサブドメインを付与する
resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  tags: tags
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    // Entra ID（キーレス）を推奨。API キーを完全に無効化したい場合は disableLocalAuth: true にする
  }
}

// gpt-image-2 を GlobalStandard でデプロイする
resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: deploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

// Cognitive Services User ロール。データプレーンの操作（Microsoft.CognitiveServices/*）を許可し、画像の生成と編集の両方を呼べる
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(account.id, principalId, cognitiveServicesUserRoleId)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
    principalId: principalId
    principalType: principalType
  }
}

@description('OpenAI 互換エンドポイント。クライアントが末尾に /openai/v1 を付加する')
output endpoint string = account.properties.endpoint
