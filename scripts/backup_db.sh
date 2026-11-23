#!/usr/bin/env sh
# Back up the VigilOps PostgreSQL database to a compressed SQL file.
#
#   ./scripts/backup_db.sh                 # writes backups/vigilops-YYYYmmdd-HHMMSS.sql.gz
#   ./scripts/backup_db.sh /path/to/dir    # choose the output directory
#
# Run from the repository root while the stack is up.  Works in Linux, macOS,
# WSL and Git Bash.  The dump is taken inside the postgres container, so the
# database port never has to be published.
set -eu

OUT_DIR="${1:-backups}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
FILE="${OUT_DIR}/vigilops-${STAMP}.sql.gz"

mkdir -p "${OUT_DIR}"

# --clean --if-exists makes the dump restorable over an existing database.
docker compose exec -T postgres sh -c \
  'pg_dump --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  | gzip > "${FILE}"

# Fail loudly if the dump is empty or truncated.
if ! gzip -t "${FILE}" 2>/dev/null || [ "$(gzip -dc "${FILE}" | head -c 20 | wc -c)" -lt 20 ]; then
  echo "Backup failed: ${FILE} is empty or corrupt." >&2
  rm -f "${FILE}"
  exit 1
fi

echo "Backup written to ${FILE} ($(wc -c < "${FILE}") bytes)"
