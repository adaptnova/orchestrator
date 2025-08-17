#!/bin/bash
# Prepare sync package for xxx VM when it's available

set -e

LAPTOP_DIR="/lssd/orchestrator"
SYNC_PACKAGE="/lssd/sync/sync_package_$(date +%Y%m%d_%H%M%S).tar.gz"
MANIFEST="/lssd/sync/sync_manifest.txt"

echo "=========================================="
echo "SYNC PREPARATION: Laptop → xxx VM"
echo "=========================================="

# Step 1: Create manifest of files to sync
echo -e "\n📝 Creating file manifest..."
find $LAPTOP_DIR -type f \( -name "*.py" -o -name "*.sh" -o -name "*.md" -o -name "*.txt" -o -name "*.json" -o -name "*.toml" \) \
    -not -path "*/venv/*" \
    -not -path "*/__pycache__/*" \
    -not -path "*/.git/*" \
    -not -name "service-account-key.json" \
    -not -name "*.pyc" | sort > $MANIFEST

echo "✅ Found $(wc -l < $MANIFEST) files to sync"

# Step 2: Show what's unique to laptop (Cloud Run deployment files)
echo -e "\n🆕 Key files for xxx VM sync:"
echo "  Cloud Run deployments:"
grep -E "(cloudrun|deploy_cloudrun|nova_complete)" $MANIFEST | sed 's/^/    /'
echo ""
echo "  Agent Engine deployments:"
grep -E "(agent_entry|deploy_agent|agent_env)" $MANIFEST | sed 's/^/    /'
echo ""
echo "  PostgreSQL integration:"
grep -E "(nova_orchestrator_complete|sql|postgres)" $MANIFEST | sed 's/^/    /'

# Step 3: Create sync package
echo -e "\n📦 Creating sync package..."
tar -czf $SYNC_PACKAGE \
    --exclude=venv \
    --exclude=__pycache__ \
    --exclude=.git \
    --exclude='*.pyc' \
    --exclude='*.log' \
    --exclude='service-account-key.json' \
    --files-from=$MANIFEST

PACKAGE_SIZE=$(ls -lh $SYNC_PACKAGE | awk '{print $5}')
echo "✅ Sync package ready: $SYNC_PACKAGE ($PACKAGE_SIZE)"

# Step 4: Create deployment script for xxx VM
cat > /lssd/sync/deploy_to_xxx.sh <<'EOF'
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
EOF

chmod +x /lssd/sync/deploy_to_xxx.sh

# Step 5: Create instructions
echo -e "\n📋 SYNC INSTRUCTIONS:"
echo "================================"
echo "When xxx VM is available:"
echo ""
echo "1. Test connection:"
echo "   ssh x@34.171.63.140 'echo Connected'"
echo ""
echo "2. Copy sync package:"
echo "   scp $SYNC_PACKAGE x@34.171.63.140:/tmp/"
echo ""
echo "3. Copy deployment script:"
echo "   scp /lssd/sync/deploy_to_xxx.sh x@34.171.63.140:/tmp/"
echo ""
echo "4. Run deployment on xxx:"
echo "   ssh x@34.171.63.140 'bash /tmp/deploy_to_xxx.sh'"
echo ""
echo "5. Verify and commit:"
echo "   ssh x@34.171.63.140 'cd /lssd/orchestrator && git status'"
echo ""
echo "Files are prepared and ready for sync!"