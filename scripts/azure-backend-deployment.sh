RESOURCE_GROUP=assessment-app-rg
LOCATION=westeurope
APP_NAME=assessment-app-2026-backend
PLAN_NAME=assessment-app-plan

az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION

az appservice plan create \
  --name $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --sku B1 \
  --is-linux

az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $PLAN_NAME \
  --name $APP_NAME \
  --runtime "PYTHON|3.11"

az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --startup-file "startup.sh"

az webapp deployment list-publishing-profiles \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --xml