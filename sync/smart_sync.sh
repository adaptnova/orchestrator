#!/bin/bash
# Smart bidirectional sync with conflict detection

set -e

XXX_HOST="34.171.63.140"
XXX_USER="x"
LAPTOP_DIR="/lssd/orchestrator"
XXX_DIR="/lssd/orchestrator"
EXCLUDE_FILE="/lssd/sync/.rsync_exclude"
STATE_FILE="/lssd/sync/.sync_state"

echo "=========================================="
echo "SMART SYNC: Laptop ↔️ xxx VM"
echo "=========================================="

# Function to get file checksums
get_checksums() {
    local dir=$1
    local host=$2
    if [ -z "$host" ]; then
        # Local
        find $dir -type f -name "*.py" -o -name "*.sh" -o -name "*.md" -o -name "*.txt" -o -name "*.json" 2>/dev/null | \
            grep -v venv | grep -v __pycache__ | xargs md5sum 2>/dev/null | sort
    else
        # Remote
        ssh ${XXX_USER}@$host "find $dir -type f -name '*.py' -o -name '*.sh' -o -name '*.md' -o -name '*.txt' -o -name '*.json' 2>/dev/null | \
            grep -v venv | grep -v __pycache__ | xargs md5sum 2>/dev/null | sort"
    fi
}

# Step 1: Backup both before sync
echo "📦 Creating safety backups..."
/lssd/sync/backup_both.sh > /dev/null 2>&1
echo "✅ Backups created"

# Step 2: Check what's different
echo -e "\n🔍 Analyzing differences..."
get_checksums $LAPTOP_DIR "" > /tmp/laptop_checksums.txt
get_checksums $XXX_DIR $XXX_HOST > /tmp/xxx_checksums.txt

# Find differences
diff -u /tmp/laptop_checksums.txt /tmp/xxx_checksums.txt > /tmp/sync_diff.txt 2>/dev/null || true

if [ -s /tmp/sync_diff.txt ]; then
    echo "📊 Found differences:"
    grep "^+" /tmp/sync_diff.txt | grep -v "^+++" | head -10
    grep "^-" /tmp/sync_diff.txt | grep -v "^---" | head -10
else
    echo "✅ Already in sync!"
    exit 0
fi

# Step 3: Determine sync direction
echo -e "\n🤔 Determining sync direction..."

# Check last modified times
LAPTOP_NEWEST=$(find $LAPTOP_DIR -type f -name "*.py" -o -name "*.sh" 2>/dev/null | \
    xargs stat -c %Y 2>/dev/null | sort -rn | head -1 || echo 0)
XXX_NEWEST=$(ssh ${XXX_USER}@$XXX_HOST "find $XXX_DIR -type f -name '*.py' -o -name '*.sh' 2>/dev/null | \
    xargs stat -c %Y 2>/dev/null | sort -rn | head -1" || echo 0)

if [ "$LAPTOP_NEWEST" -gt "$XXX_NEWEST" ]; then
    echo "➡️  Laptop is newer - syncing laptop → xxx"
    DIRECTION="to_xxx"
elif [ "$XXX_NEWEST" -gt "$LAPTOP_NEWEST" ]; then
    echo "⬅️  xxx is newer - syncing xxx → laptop"
    DIRECTION="from_xxx"
else
    echo "🤷 Same age - defaulting to laptop → xxx"
    DIRECTION="to_xxx"
fi

# Step 4: Perform sync
echo -e "\n🔄 Syncing files..."

if [ "$DIRECTION" = "to_xxx" ]; then
    # Laptop to xxx
    rsync -avz --progress \
        --exclude-from=$EXCLUDE_FILE \
        --backup --backup-dir=/lssd/backups/rsync_backup_$(date +%Y%m%d) \
        $LAPTOP_DIR/ ${XXX_USER}@${XXX_HOST}:${XXX_DIR}/
    
    echo "✅ Synced laptop → xxx"
    
    # Record state
    echo "last_sync=$(date +%s)" > $STATE_FILE
    echo "direction=laptop_to_xxx" >> $STATE_FILE
    
else
    # xxx to laptop
    rsync -avz --progress \
        --exclude-from=$EXCLUDE_FILE \
        --backup --backup-dir=/lssd/backups/rsync_backup_$(date +%Y%m%d) \
        ${XXX_USER}@${XXX_HOST}:${XXX_DIR}/ $LAPTOP_DIR/
    
    echo "✅ Synced xxx → laptop"
    
    # Record state
    echo "last_sync=$(date +%s)" > $STATE_FILE
    echo "direction=xxx_to_laptop" >> $STATE_FILE
fi

# Step 5: Git status check
echo -e "\n📝 Git status on both machines:"
echo "Laptop:"
cd $LAPTOP_DIR && git status --short | head -5

echo -e "\nxxx VM:"
ssh ${XXX_USER}@${XXX_HOST} "cd $XXX_DIR && git status --short | head -5"

echo -e "\n✅ Smart sync complete!"
echo ""
echo "Next steps:"
echo "1. Check the changes with: git diff"
echo "2. Commit if happy: git add -A && git commit -m 'Sync from $DIRECTION'"
echo "3. Push to GitHub: git push origin main"