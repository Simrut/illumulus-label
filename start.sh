#!/bin/bash
source /workspace/venv/bin/activate
gunicorn --bind 0.0.0.0:8000 app:app
