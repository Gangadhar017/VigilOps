# Installation and Configuration

## Prerequisites
Docker Desktop with WSL2 on Windows, or Docker Engine with the Compose plugin on Linux. No AWS account, cloud subscription, Ollama installation or model training is required.

## Local installation
1) Clone the repository. 2) Copy .env.example to .env. 3) Run docker compose up --build -d. 4) Open http://localhost:8080 and sign in with the bootstrap Administrator or Operator account defined in .env. Database migrations run automatically when the backend starts.

## Local addresses
Web application: http://localhost:8080 (this computer only by default; set VIGILOPS_BIND_ADDRESS=0.0.0.0 to allow other devices on a trusted network). API documentation (development): http://localhost:8000/docs. Prometheus: http://localhost:9090. Alertmanager: http://localhost:9093. These tool ports are bound to the local machine only.

## Environment configuration
Configuration lives in the .env file, never in source code. Important settings: SECRET_KEY (JWT signing), POSTGRES_PASSWORD, ALERT_WEBHOOK_TOKEN, BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD, DEMO_CONTROLS_ENABLED, AI_PROVIDER, GEMINI_API_KEY and GEMINI_MODEL. In production mode the backend refuses to start with the placeholder values from .env.example.

## Gemini API setup
Create an API key in Google AI Studio, then set GEMINI_API_KEY in .env and restart the backend with docker compose up -d backend. The model is chosen with GEMINI_MODEL and can be changed without code changes. The key stays on the backend; it is never sent to the browser. Without a key VigilAI works in documentation mode. Free-tier quotas are limited and can change; paid billing is never enabled by VigilOps.

## Demo controls
When DEMO_CONTROLS_ENABLED=true and the environment is not production, an Administrator can inject a controlled fault into the demo application and reset the sample configuration from Settings -> Demo controls. In production mode these controls are disabled unless the hosted-demonstration opt-in ALLOW_DEMO_CONTROLS_IN_PRODUCTION is also set.

## Data persistence
PostgreSQL data, Prometheus data and the scan workspace are stored in named Docker volumes, so records survive container restarts and docker compose down. Only docker compose down -v removes them.

## Production deployment
Use compose.prod.yaml on a Linux server: it sets production mode, disables demo controls and API docs, publishes only ports 80 and 443 through Caddy with automatic HTTPS, and keeps PostgreSQL, Prometheus, Alertmanager and the worker on the private network. Database backup and restore scripts are in the scripts folder.
