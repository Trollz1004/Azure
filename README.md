# Azure

This repository hosts the Twin Boss Agent self-hosted stack.

## Twin Boss Agent - Self-Hosted

### Run
1) Open PowerShell in this folder:
   `powershell -ExecutionPolicy Bypass -File .\deploy.ps1`

- Console: http://localhost:8080
- API:     http://localhost:8011

### Endpoints
- POST /agents/twin/execute {query}
- POST /agents/create {name}
- POST /fundraising/deploy
- POST /business/integrate
- POST /admin/automate
- GET  /previews/stream  (SSE)
