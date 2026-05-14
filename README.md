# App assessment-app
Boilerplate for the assessment app

# Project architecture
Follow these instructions to setup the project architecture

## Setup folder structure
Setup this folder structure
```
assessment-app/
├── .github
└── workflows/
        ├── backend-deploy.yml
        └── frontend-deploy.yml 
├── backend/
│   ├── models/
│   ├── tests/
├── frontend/
│   ├── src/
├── memory/
├── scripts/
├── .env
├── .env.pipeline
├── README.md
```

# Setup the application #

## Setup the repo ##
Setup the repository for development

### Setup locally ###
1. Run `git init`
2. touch README.md
3. Run `git add .`
4. Run `git commit -m "Initial commit"`
5. Create the repo repo on GitHub
6. Run `git remote add origin https://github.com/<user>/assessment-app.git`
7. Run `git branch -M main`
8. Run `git push -u origin main`

### Setup from remote ###
1. Create the repo repo on GitHub
2. Run `git clone https://github.com/<user>/assessment-app.git`
3. Run `git commit -m "Initial commit"`
4. Run `git push`

## Prerequisites ##
- Make sure python 3.12 is installed
- Make sure uv is installed
-Make sure node and npm is installed

## Setup the app ##
Run these commands to setup the application locally

### Setup the backend ###
1. Create a folder 'backend' and `cd backend`
2. Create a file requirements.txt and add python libraries
3. Run `uv init`
4. Run `uv add -r requirements.txt`

### Setup the frontend ###
1. Run `npm create next-app` from the root
2. Add project name 'frontend'
3. Choose the options for your next React app

## Run the application ##
Use these commands to run the application locally

### Setup environment ###
- Create .env file
- Add the environment vars 

### Run the backend ###
- Run `cd backend`
- Run `uv run uvicorn main:app --reload` to start the backend app in dev mode

### Test the backend ###
- Run `cd backend`
- Run `uv run flake8`
- Run `uv run mypy`
- Run `uv run python -m unittest discover -s tests -v`

### Run the frontend ###
- Run `cd frontend`
- Run `npm run dev` to start the frontend app in dev mode

### Test the frontend ###
- Run `cd frontend`
- Run `npm run lint`
- Run `npm run check-types`
- Run `npm run test`
 
# Deploy the application
Run these commands to setup the deployment

## Deploy to Azure ##
Run these commands to deploy the backend and frontend to Azure using Github workflows

### Prerequisites ###
1. Install Azure `curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash`
2. Login to Azure `az login`

### Create Azure App Service ###
1. Run `source ./scripts/azure-backend-deployment.sh` to create the resources on Azure
If using Publish Profile
2. Go to GitHub Repository → Settings → Secrets and variables → Actions
3. Add Azure secret AZURE_WEBAPP_PUBLISH_PROFILE with the xml from the sh command
If using OIDC
3. Run `source ./scripts/azure-oidc-login.sh` to create the resources on Azure
4. Go to GitHub Repository → Settings → Secrets and variables → Actions
5. Add AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID secrets  

### Run backend deployment ###
- Commit code and have ./github/workflows/backend-deploy.yml running the backend deployment

### Run frontend deployment ###
- Commit code and have ./github/workflows/frontend-deploy.yml running the frontend deployment

### Check Azure ###
- Check the Azure Resource Group 