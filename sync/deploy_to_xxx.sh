#!/bin/bash
# Run this on xxx VM to deploy the synced files

set -e

BACKUP_DIR="/lssd/backups/pre_sync_$(date +%Y%m%d_%H%M%S)"
TARGET_DIR="/lssd/orchestrator"
NOVA_DIR="$TARGET_DIR/nova_deployment"

echo "=========================================="
echo "DEPLOYING SYNC TO XXX VM"
echo "=========================================="

# Backup existing
echo "📦 Backing up existing files..."
mkdir -p $BACKUP_DIR
cp -r $TARGET_DIR $BACKUP_DIR/ 2>/dev/null || true

# Create nova_deployment subdirectory for new files
echo "📁 Creating nova_deployment directory..."
mkdir -p $NOVA_DIR

# Extract sync package to nova_deployment
echo "🔄 Extracting synced files..."
tar -xzf /tmp/sync_package_*.tar.gz -C $NOVA_DIR --strip-components=3

# Show what was deployed
echo -e "\n✅ Deployment complete!"
echo "New files in: $NOVA_DIR"
echo ""
echo "Key files deployed:"
ls -la $NOVA_DIR/*.py | head -10
echo ""
echo "To integrate with main orchestrator:"
echo "1. Review files in $NOVA_DIR"
echo "2. Copy needed functions to $TARGET_DIR/main.py"
echo "3. Test with: python $TARGET_DIR/main.py"
