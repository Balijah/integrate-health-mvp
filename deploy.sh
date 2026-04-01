#!/bin/bash
# Integrate Health — full deploy script
# Deploys backend to EC2 via SSM and frontend to S3/CloudFront
# Usage: ./deploy.sh [--backend-only | --frontend-only]

set -e

INSTANCE_ID="i-0393d6a09fd7df62f"
S3_AUDIO="integrate-health-audio-317440775804"
S3_FRONTEND="integrate-health-frontend-317440775804"
CF_DISTRIBUTION="E3O39Z192PMEOR"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DEPLOY_KEY="deploys/backend-${TIMESTAMP}.tar.gz"

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
    backend/requirements.txt

  echo "=== Uploading to S3 ==="
  aws s3 cp /tmp/backend-deploy.tar.gz "s3://${S3_AUDIO}/${DEPLOY_KEY}"

  echo "=== Deploying to EC2 (SSM) ==="
  CMD_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --timeout-seconds 120 \
    --parameters "commands=[
      \"set -e\",
      \"aws s3 cp s3://${S3_AUDIO}/${DEPLOY_KEY} /tmp/backend-deploy.tar.gz\",
      \"find /home/ec2-user/app/backend -name '._*' -delete 2>/dev/null || true\",
      \"tar -xzf /tmp/backend-deploy.tar.gz -C /home/ec2-user/app/ --strip-components=0\",
      \"cd /home/ec2-user/app/backend && source venv/bin/activate && alembic upgrade head 2>&1\",
      \"sudo systemctl restart integrate-health\",
      \"sleep 5\",
      \"sudo systemctl is-active integrate-health\",
      \"curl -sf http://localhost:8000/health && echo '' || (echo 'HEALTH CHECK FAILED' && exit 1)\"
    ]" \
    --query 'Command.CommandId' --output text)

  echo "=== Waiting for EC2 deploy (command: $CMD_ID) ==="
  sleep 20
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

  echo "=== Syncing to S3 ==="
  # Assets: long cache (content-hashed filenames)
  aws s3 sync frontend/dist/ "s3://${S3_FRONTEND}/" \
    --delete \
    --cache-control "public,max-age=31536000,immutable" \
    --exclude "index.html"

  # index.html: no cache (always fetch latest)
  aws s3 cp frontend/dist/index.html "s3://${S3_FRONTEND}/index.html" \
    --cache-control "no-cache,no-store,must-revalidate"

  echo "=== Invalidating CloudFront cache ==="
  aws cloudfront create-invalidation \
    --distribution-id "$CF_DISTRIBUTION" \
    --paths "/*" \
    --query 'Invalidation.{Id:Id,Status:Status}' \
    --output json

  echo "=== Frontend deploy complete ==="
fi

echo ""
echo "=== DEPLOY COMPLETE ==="
echo "Site: https://d3nem3tkboqfr7.cloudfront.net"
