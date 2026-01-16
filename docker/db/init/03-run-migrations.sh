#!/bin/bash
# Run app migrations after Supabase is set up

set -e

echo "Running application migrations..."

# Run each migration file in order
for f in /docker-entrypoint-initdb.d/migrations/*.sql; do
    if [ -f "$f" ]; then
        echo "Running migration: $f"
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$f"
    fi
done

echo "Migrations completed successfully!"
