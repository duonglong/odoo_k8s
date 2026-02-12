#!/bin/bash
set -e

# -------------------------------------------------------
# Odoo K8s Entrypoint
# Waits for PostgreSQL, then starts Odoo
# -------------------------------------------------------

DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-odoo}"
DB_PASSWORD="${DB_PASSWORD:-odoo}"

echo "==> Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
/usr/local/bin/wait-for-it.sh "${DB_HOST}:${DB_PORT}" --timeout=60 --strict -- \
    echo "==> PostgreSQL is ready."

# If the first argument is 'odoo', run it with the config
if [ "$1" = "odoo" ]; then
    shift
    exec odoo \
        --config=/etc/odoo/odoo.conf \
        --db_host="${DB_HOST}" \
        --db_port="${DB_PORT}" \
        --db_user="${DB_USER}" \
        --db_password="${DB_PASSWORD}" \
        "$@"
fi

# Otherwise, run whatever command was passed
exec "$@"
