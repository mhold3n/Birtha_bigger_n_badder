#!/bin/bash
set -euo pipefail

# Backup environment configuration before deployment
# Usage: ./backup_env.sh

BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/env_backup_$TIMESTAMP.tar.gz"

echo "💾 Creating environment backup..."

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup environment files
tar -czf "$BACKUP_FILE" \
    .env \
    .env.* \
    docker-compose*.yml \
    infra/ \
    worker/ \
    2>/dev/null || true

echo "✅ Environment backed up to: $BACKUP_FILE"

# List recent backups
echo "📋 Recent backups:"
ls -la "$BACKUP_DIR"/env_backup_*.tar.gz 2>/dev/null | tail -5 || echo "No previous backups found"

# Cleanup old backups (keep last 10)
echo "🧹 Cleaning up old backups..."
ls -t "$BACKUP_DIR"/env_backup_*.tar.gz 2>/dev/null | tail -n +11 | xargs rm -f || true

echo "🎉 Backup completed successfully!"
