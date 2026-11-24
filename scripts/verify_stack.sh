#!/usr/bin/env sh
# Quick health verification of a running VigilOps stack.
#
#   ./scripts/verify_stack.sh              # checks http://localhost:8080
#   BASE_URL=https://ops.example.com ./scripts/verify_stack.sh
#
# Checks that every container is running, that the public entry point serves the
# application and the API, and that internal endpoints are NOT exposed through
# the reverse proxy.  Exit code 0 = all checks passed.
# For the full functional demonstrations run:  python scripts/run_e2e_demos.py
set -u

# Port: environment variable, else the value in .env, else 8080.
if [ -z "${VIGILOPS_HTTP_PORT:-}" ] && [ -f .env ]; then
  VIGILOPS_HTTP_PORT="$(grep -E '^VIGILOPS_HTTP_PORT=' .env | tail -n 1 | cut -d= -f2 | tr -d '\r"')"
fi
BASE_URL="${BASE_URL:-http://localhost:${VIGILOPS_HTTP_PORT:-8080}}"
FAILED=0

pass() { echo "  [PASS] $1"; }
fail() { echo "  [FAIL] $1"; FAILED=$((FAILED + 1)); }

echo "Containers"
for service in postgres backend worker test-app prometheus alertmanager web; do
  state="$(docker compose ps --format '{{.State}}' "${service}" 2>/dev/null | head -n 1)"
  if [ "${state}" = "running" ]; then pass "${service} is running"; else fail "${service} is ${state:-not found}"; fi
done
for service in postgres backend worker test-app; do
  health="$(docker compose ps --format '{{.Health}}' "${service}" 2>/dev/null | head -n 1)"
  if [ "${health}" = "healthy" ]; then pass "${service} is healthy"; else fail "${service} health is ${health:-unknown}"; fi
done

echo "Public entry point (${BASE_URL})"
code="$(curl -ks -o /dev/null -w '%{http_code}' "${BASE_URL}/")"
[ "${code}" = "200" ] && pass "web application is served (HTTP 200)" || fail "web application returned HTTP ${code}"

body="$(curl -ks "${BASE_URL}/api/health")"
echo "${body}" | grep -q '"status":"healthy"' && pass "API is healthy and the database is reachable" || fail "API health check failed: ${body}"

code="$(curl -ks -o /dev/null -w '%{http_code}' "${BASE_URL}/api/incidents")"
[ "${code}" = "401" ] && pass "protected API requires authentication (HTTP 401)" || fail "unauthenticated API call returned HTTP ${code}"

code="$(curl -ks -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{"alerts":[]}' "${BASE_URL}/api/alerts/webhook")"
[ "${code}" = "401" ] || [ "${code}" = "422" ] && pass "alert webhook rejects unauthenticated calls (HTTP ${code})" || fail "alert webhook returned HTTP ${code}"

echo "Demonstration application (${BASE_URL}/orbitcrate/)"
curl -ks "${BASE_URL}/orbitcrate/" | grep -q 'OrbitCrate' && pass "the storefront is served" || fail "the storefront is not served at /orbitcrate/"
curl -ks "${BASE_URL}/orbitcrate/api/catalog" | grep -q '"plans"' && pass "the store API answers" || fail "the store API does not answer"
for path in internal/state metrics health/ready; do
  code="$(curl -ks -o /dev/null -w '%{http_code}' "${BASE_URL}/orbitcrate/${path}")"
  [ "${code}" = "404" ] && pass "the application's /${path} is not exposed (HTTP 404)" || fail "the application's /${path} returned HTTP ${code}"
done

echo "Internal endpoints must not be exposed by the reverse proxy"
if curl -ks "${BASE_URL}/metrics" | grep -q 'http_requests_total'; then fail "/metrics is exposed publicly"; else pass "/metrics is not exposed"; fi
if curl -ks "${BASE_URL}/openapi.json" | grep -q '"openapi"'; then fail "/openapi.json is exposed publicly"; else pass "/openapi.json is not exposed"; fi
if curl -ks "${BASE_URL}/health/ready" | grep -q '"checks"'; then fail "backend /health/ready is exposed publicly"; else pass "backend /health/* is not exposed"; fi

headers="$(curl -ksI "${BASE_URL}/")"
echo "${headers}" | grep -qi 'content-security-policy' && pass "Content-Security-Policy header is set" || fail "Content-Security-Policy header is missing"
echo "${headers}" | grep -qi 'x-frame-options' && pass "X-Frame-Options header is set" || fail "X-Frame-Options header is missing"

echo
if [ "${FAILED}" -eq 0 ]; then
  echo "All checks passed."
else
  echo "${FAILED} check(s) failed."
  exit 1
fi
