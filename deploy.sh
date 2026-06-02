#!/bin/bash
# Integrate Health — full deploy script
# Deploys backend to EC2 via SSM and frontend to S3/CloudFront
# Usage: ./deploy.sh [--backend-only | --frontend-only]

set -e

INSTANCE_ID="i-0393d6a09fd7df62f"
S3_AUDIO="integrate-health-audio-317440775804"
S3_DEPLOY="integrate-health-deploy-317440775804"
S3_FRONTEND="integrate-health-frontend-317440775804"
CF_DISTRIBUTION="E3O39Z192PMEOR"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DEPLOY_KEY="backend-${TIMESTAMP}.tar.gz"

SKIP_BACKEND=false
SKIP_FRONTEND=false

for arg in "$@"; do
  case $arg in
    --backend-only)  SKIP_FRONTEND=true ;;
    --frontend-only) SKIP_BACKEND=true ;;
  esac
done

# ── BACKEND ──────────────────────────────────────────────────────────────────
if [ "$SKIP_BACKEND" = false ]; then
  echo "=== Building backend package ==="
  COPYFILE_DISABLE=1 tar -czf /tmp/backend-deploy.tar.gz \
    --exclude='*/__pycache__' \
    --exclude='*/*.pyc' \
    --exclude='*/._*' \
    --exclude='.DS_Store' \
    backend/app/ \
    backend/alembic/ \
    backend/requirements.txt \
    deployment/worker.service

  echo "=== Uploading to S3 (deploy bucket) ==="
  aws s3 cp /tmp/backend-deploy.tar.gz "s3://${S3_DEPLOY}/${DEPLOY_KEY}"

  echo "=== Creating pre-migration RDS snapshot ==="
  aws rds create-db-snapshot \
    --db-instance-identifier integrate-health-db \
    --db-snapshot-identifier "pre-deploy-${TIMESTAMP}" \
    --no-cli-pager || echo "WARNING: RDS snapshot request failed — continuing deploy"

  echo "=== Pruning pre-deploy snapshots older than 7 days ==="
  CUTOFF=$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)
  aws rds describe-db-snapshots \
    --db-instance-identifier integrate-health-db \
    --snapshot-type manual \
    --query "DBSnapshots[?SnapshotCreateTime<='${CUTOFF}' && starts_with(DBSnapshotIdentifier, 'pre-deploy-')].DBSnapshotIdentifier" \
    --output text | tr '\t' '\n' | while read -r SNAP; do
      [ -z "$SNAP" ] && continue
      echo "  Deleting old snapshot: $SNAP"
      aws rds delete-db-snapshot --db-snapshot-identifier "$SNAP" --no-cli-pager || true
    done

  echo "=== Deploying to EC2 (SSM) ==="
  CMD_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --timeout-seconds 120 \
    --parameters "commands=[
      \"set -e\",
      \"aws s3 cp s3://${S3_DEPLOY}/${DEPLOY_KEY} /tmp/backend-deploy.tar.gz\",
      \"find /home/ec2-user/app/backend -name '._*' -delete 2>/dev/null || true\",
      \"tar -xzf /tmp/backend-deploy.tar.gz -C /home/ec2-user/app/ --strip-components=0\",
      \"cd /home/ec2-user/app/backend && source venv/bin/activate && alembic upgrade head 2>&1\",
      \"sudo systemctl restart integrate-health\",
      \"sudo cp /home/ec2-user/app/deployment/worker.service /etc/systemd/system/integrate-health-worker.service\",
      \"sudo systemctl daemon-reload\",
      \"sudo systemctl enable integrate-health-worker\",
      \"sudo systemctl restart integrate-health-worker\",
      \"sleep 5\",
      \"sudo systemctl is-active integrate-health\",
      \"sudo systemctl is-active integrate-health-worker\",
      \"curl -sf http://localhost:8000/health && echo '' || (echo 'HEALTH CHECK FAILED' && exit 1)\"
    ]" \
    --query 'Command.CommandId' --output text)

  echo "=== Waiting for EC2 deploy (command: $CMD_ID) ==="
  # Poll until done (migrations can take 30-60s on first run)
  for _i in $(seq 1 18); do
    _st=$(aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'Status' --output text 2>/dev/null)
    echo "  status: $_st"
    if [ "$_st" = "Success" ] || [ "$_st" = "Failed" ] || [ "$_st" = "TimedOut" ]; then break; fi
    sleep 10
  done
  RESULT=$(aws ssm get-command-invocation \
    --command-id "$CMD_ID" \
    --instance-id "$INSTANCE_ID" \
    --query '{Status:Status,Output:StandardOutputContent}' \
    --output json)

  STATUS=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['Status'])")
  OUTPUT=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['Output'])")

  echo "$OUTPUT"

  if [ "$STATUS" != "Success" ]; then
    echo "ERROR: Backend deploy failed with status: $STATUS"
    exit 1
  fi
  echo "=== Backend deploy complete ==="
fi

# ── FRONTEND ─────────────────────────────────────────────────────────────────
if [ "$SKIP_FRONTEND" = false ]; then
  echo "=== Building frontend ==="
  cd frontend
  npm run build
  cd ..

  echo "=== Packaging frontend dist ==="
  COPYFILE_DISABLE=1 tar -czf /tmp/frontend-dist.tar.gz \
    --exclude='*/._*' \
    --exclude='.DS_Store' \
    frontend/dist/

  echo "=== Uploading to S3 (deploy bucket) ==="
  aws s3 cp /tmp/frontend-dist.tar.gz "s3://${S3_DEPLOY}/frontend-dist.tar.gz"

  echo "=== Deploying frontend to EC2 (SSM) ==="
  FE_CMD_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --timeout-seconds 60 \
    --parameters "commands=[
      \"set -e\",
      \"aws s3 cp s3://${S3_DEPLOY}/frontend-dist.tar.gz /tmp/frontend-dist.tar.gz\",
      \"sudo tar -xzf /tmp/frontend-dist.tar.gz -C /var/www/html/ --strip-components=2\",
      \"sudo nginx -t && sudo systemctl reload nginx\"
    ]" \
    --query 'Command.CommandId' --output text)

  echo "=== Waiting for frontend deploy (command: $FE_CMD_ID) ==="
  sleep 15
  FE_STATUS=$(aws ssm get-command-invocation \
    --command-id "$FE_CMD_ID" \
    --instance-id "$INSTANCE_ID" \
    --query 'Status' --output text)

  if [ "$FE_STATUS" != "Success" ]; then
    echo "ERROR: Frontend deploy failed with status: $FE_STATUS"
    exit 1
  fi
  echo "=== Frontend deploy complete ==="

  echo "=== Invalidating CloudFront cache ==="
  aws cloudfront create-invalidation \
    --distribution-id "$CF_DISTRIBUTION" \
    --paths "/*" \
    --query 'Invalidation.Id' --output text
  echo "=== CloudFront invalidation created ==="
fi

echo ""
echo "=== DEPLOY COMPLETE ==="
echo "Site: https://app.integratehealth.ai"
