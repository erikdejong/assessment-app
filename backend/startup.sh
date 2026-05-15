#!/bin/bash

pip install -r requirements.txt

.venv/bin/activate

playwright install

python -m database.create_tables
python -m database.seed_admin_user
python -m vector_store

gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app