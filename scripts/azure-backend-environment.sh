RESOURCE_GROUP=assessment-app-rg
APP_NAME=assessment-app-2026

az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --settings \
    DATABASE_URL="your-db-url" \
    SECRET_KEY="your-secret"