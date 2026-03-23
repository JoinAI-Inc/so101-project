#!/bin/bash
gunicorn -w ${WORKERS:=2} \
  -b :8000 -t ${TIMEOUT:=300} \
  -k uvicorn.workers.UvicornWorker \
  server:app
