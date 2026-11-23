# Troubleshooting

## Why is my application unhealthy
Open Monitoring and look at the demo-app resource. DOWN means Prometheus cannot scrape it: read the scrape error. Then check Incidents for an open ApplicationUnavailable incident, which lists possible causes and recommended steps. If the application is in a failed state, request ACTION-001 on the incident. If the container itself is stopped, start it with docker compose up -d test-app.

## How to resolve HTTP 500 errors
A high 5xx rate raises the HighHttp5xxErrorRate alert and an incident. Compare the 5xx error rate with request rate and latency on the Monitoring page, check the application logs with docker compose logs --tail=100 test-app, and request ACTION-001 to re-initialise the service. If errors continue after recovery the cause is not transient; review recent changes. HTTP 4xx responses are client errors and do not trigger this alert.

## Slow responses or high latency
The HighApiLatency alert fires when p95 latency is above 1 second. Check CPU usage and memory for the same period: latency rising with CPU indicates compute saturation, latency with stable CPU indicates waiting on a dependency.

## An incident does not appear after a failure
Check that Prometheus and Alertmanager are available on the Monitoring page. An alert must be true for its "for" duration before it fires, and Alertmanager waits a few seconds before notifying, so allow up to a minute. If Alertmanager's webhook token does not match ALERT_WEBHOOK_TOKEN the backend rejects the notification with HTTP 401; see the backend logs.

## A remediation request stays QUEUED
The restricted worker is not running or cannot reach the database. The Remediation page shows whether the worker is online. Run docker compose ps worker and docker compose logs worker.

## A remediation request failed
Open the request to read the failure reason and verification checks. Common causes: the demo application container is stopped (ACTION-001 cannot start containers), Prometheus was unavailable so recovery could not be verified, or the configuration file was changed or removed. Fix the cause and have an Administrator retry.

## Cannot sign in
"Incorrect e-mail or password" is shown for any invalid credentials. After 5 failures you must wait up to 5 minutes (HTTP 429). After 20 failures for the same e-mail from any address, that e-mail is refused from every address until the window passes. A deactivated account cannot sign in. An Administrator can reset a password in Settings -> Users.

## The dashboard shows metrics as unavailable
The backend could not get a value from Prometheus: Prometheus may be down, the target may be down, or there is no traffic yet for a rate to be computed. VigilOps shows "unavailable" rather than a guessed number.

## VigilAI says live AI generation is unavailable
The Gemini API key is not configured, the free quota or rate limit is exhausted, or the provider cannot be reached. VigilAI then answers from the documentation and live platform data without AI generation. The rest of the platform is not affected.

## Useful commands
docker compose ps shows service status. docker compose logs -f backend follows backend logs. docker compose restart backend restarts one service. docker compose down stops everything while keeping data; adding -v also deletes the database volume.
