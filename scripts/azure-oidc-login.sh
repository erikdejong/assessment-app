az ad app create \
  --display-name github-actions-assessment

az ad sp create --id <APP_ID>

az ad app federated-credential create \
  --id <APP_ID> \
  --parameters '{
    "name": "github-actions",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:erikdejong/assessment-app:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

az role assignment create \
  --assignee <APP_ID> \
  --role "Contributor" \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP