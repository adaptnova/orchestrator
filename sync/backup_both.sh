#!/bin/bash
# Backup both laptop and xxx VM orchestrator directories

set -e

BACKUP_DIR="/lssd/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
XXX_HOST="34.171.63.140"
XXX_USER="x"

echo "=========================================="
echo "BACKUP: Laptop + xxx VM"
echo "Timestamp: $TIMESTAMP"
echo "=========================================="

# Backup laptop
echo -e "\n📦 Backing up laptop /lssd/orchestrator..."
mkdir -p $BACKUP_DIR/laptop
tar -czf $BACKUP_DIR/laptop/backup_$TIMESTAMP.tar.gz \
  --exclude=venv \
  --exclude=__pycache__ \
  --exclude=.git \
  --exclude='*.pyc' \
  --exclude='*.log' \
  -C /lssd orchestrator/

LAPTOP_SIZE=$(ls -lh $BACKUP_DIR/laptop/backup_$TIMESTAMP.tar.gz | awk '{print $5}')
echo "✅ Laptop backup: $BACKUP_DIR/laptop/backup_$TIMESTAMP.tar.gz ($LAPTOP_SIZE)"

# Backup xxx VM
echo -e "\n📦 Backing up xxx VM /lssd/orchestrator..."
mkdir -p $BACKUP_DIR/xxx

ssh ${XXX_USER}@${XXX_HOST} "tar -czf - \
  --exclude=venv \
  --exclude=__pycache__ \
  --exclude=.git \
  --exclude='*.pyc' \
  --exclude='*.log' \
  -C /lssd orchestrator/" > $BACKUP_DIR/xxx/backup_$TIMESTAMP.tar.gz

XXX_SIZE=$(ls -lh $BACKUP_DIR/xxx/backup_$TIMESTAMP.tar.gz | awk '{print $5}')
echo "✅ xxx backup: $BACKUP_DIR/xxx/backup_$TIMESTAMP.tar.gz ($XXX_SIZE)"

# Show recent backups
echo -e "\n📊 Recent backups:"
ls -lht $BACKUP_DIR/laptop/*.tar.gz 2>/dev/null | head -3
ls -lht $BACKUP_DIR/xxx/*.tar.gz 2>/dev/null | head -3

# Keep only last 7 backups
echo -e "\n🧹 Cleaning old backups (keeping last 7)..."
ls -t $BACKUP_DIR/laptop/*.tar.gz 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true
ls -t $BACKUP_DIR/xxx/*.tar.gz 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true

echo -e "\n✅ Backup complete!"
echo "Restore command:"
echo "  Laptop: tar -xzf $BACKUP_DIR/laptop/backup_$TIMESTAMP.tar.gz -C /lssd"
echo "  xxx VM: tar -xzf $BACKUP_DIR/xxx/backup_$TIMESTAMP.tar.gz -C /lssd"