#!/bin/sh
set -eu

# `/app/data` is a persistent Docker volume. Without this synchronization the
# volume hides resource files that were added by newer application versions.
# Copy version-controlled seed data into the volume on every start while
# deliberately preserving the live SQLite database and user-created files
# that do not collide with version-controlled resource names.
if [ -d /app/seed-data ]; then
  mkdir -p /app/data
  for source in /app/seed-data/*; do
    [ -e "$source" ] || continue
    case "$(basename "$source")" in
      *.db) continue ;;
    esac
    cp -a "$source" /app/data/
  done
fi

# The server updater builds with its own Dockerfile, so enforce the resource
# integrity check again at runtime after seed data has been synchronized.
python /app/scripts/validate_resource_images.py

exec uvicorn main:app --host 0.0.0.0 --port 8000
