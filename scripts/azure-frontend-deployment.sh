RESOURCE_GROUP=assessment-app-rg
LOCATION=westeurope
STATIC_APP_NAME=assessment-app-frontend-2026

az staticwebapp create \
  --name $STATIC_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

  az staticwebapp secrets list \
  --name $STATIC_APP_NAME \
  --resource-group $RESOURCE_GROUP