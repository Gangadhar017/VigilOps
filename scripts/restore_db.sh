#!/usr/bin/env sh
# Restore the VigilOps PostgreSQL database from a backup made by backup_db.sh.
#
#   ./scripts/restore_db.sh backups/vigilops-20261123-101500.sql.gz
#
# WARNING: this REPLACES the current database contents with the backup.
# The script asks for confirmation unless CONFIRM=yes is set.
#
# The API and worker are stopped during the restore so nothing writes to the
# database, and started again afterwards.
set -eu

FILE="${1:-}"
if [ -z "${FILE}" ] || [ ! -f "${FILE}" ]; then
  echo "Usage: $0 <backup-file.sql.gz>" >&2
  exit 2
fi
gzip -t "${FILE}" || { echo "Not a valid gzip file: ${FILE}" >&2; exit 2; }

if [ "${CONFIRM:-}" != "yes" ]; then
  printf "This will overwrite the current VigilOps database with %s. Type 'yes' to continue: " "${FILE}"
  read -r answer
  [ "${answer}" = "yes" ] || { echo "Aborted."; exit 1; }
fi

echo "Stopping the API and worker..."
docker compose stop backend worker

echo "Restoring ${FILE}..."
# The audit table is append-only (trigger).  session_replication_role=replica
# disables user triggers for this session only, which a restore legitimately needs.
gzip -dc "${FILE}" | docker compose exec -T postgres sh -c \
  'PGOPTIONS="-c session_replication_role=replica" psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  > /dev/null

echo "Starting the API and worker..."
docker compose start backend worker

echo "Restore complete."
