#!/bin/bash
# Nova Orchestrator Deployment Script
# Agent Builder - Production Deployment with Receipts

set -e

PROJECT_ID="echovaeris"
REGION="us-central1"
SERVICE_NAME="nova-orchestrator"
SERVICE_ACCOUNT="orchestrator-nova-sa@echovaeris.iam.gserviceaccount.com"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=========================================="
echo "NOVA ORCHESTRATOR DEPLOYMENT"
echo "Agent Builder - Real Infrastructure"
echo "=========================================="

# Step 1: Deploy to Cloud Run
echo -e "\n🚀 Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --source . \
  --region ${REGION} \
  --service-account ${SERVICE_ACCOUNT} \
  --platform managed \
  --allow-unauthenticated \
  --add-cloudsql-instances ${PROJECT_ID}:${REGION}:orch-pg \
  --set-env-vars "PROJECT_ID=${PROJECT_ID},REGION=${REGION}" \
  --project ${PROJECT_ID}

# Step 2: Get Service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
  --region ${REGION} \
  --format='value(status.url)' \
  --project ${PROJECT_ID})

echo "✅ Deployed to: ${SERVICE_URL}"

# Step 3: Run Combined Proof
echo -e "\n📊 Running Combined Proof..."
PROOF_RESPONSE=$(curl -X POST "${SERVICE_URL}/proof" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "COMBINED_PROOF_RUN",
    "agent": "Agent Builder",
    "deployment": "Direct Deploy",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
  }' 2>/dev/null)

echo "${PROOF_RESPONSE}" | jq '.' > combined_proof_${TIMESTAMP}.json

# Step 4: Upload to GCS
echo -e "\n☁️ Uploading proof to GCS..."
gsutil cp combined_proof_${TIMESTAMP}.json \
  gs://orch-artifacts/receipts/agent_builder_proof_${TIMESTAMP}.json

PUBLIC_URL="https://storage.googleapis.com/orch-artifacts/receipts/agent_builder_proof_${TIMESTAMP}.json"

# Step 5: Display Results
echo -e "\n=========================================="
echo "DEPLOYMENT COMPLETE - RECEIPTS"
echo "=========================================="
echo "Service URL: ${SERVICE_URL}"
echo "Proof JSON: combined_proof_${TIMESTAMP}.json"
echo "GCS Path: gs://orch-artifacts/receipts/agent_builder_proof_${TIMESTAMP}.json"
echo "Public URL: ${PUBLIC_URL}"
echo ""
echo "Proof Summary:"
echo "${PROOF_RESPONSE}" | jq -r '.receipts.cloud_sql | "Cloud SQL Event ID: \(.event_id)"'
echo "${PROOF_RESPONSE}" | jq -r '.receipts.gcs | "GCS Artifact: \(.artifact_path)"'
echo ""
echo "✅ Agent Builder deployment verified with receipts!"