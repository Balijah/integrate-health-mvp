#!/bin/bash
# Setup script for Integrate Health App Server
# Run this on the EC2 app server after launching

set -e

echo "=== Setting up Integrate Health App Server ==="

# Update system
echo "Updating system packages..."
sudo dnf update -y

# Install dependencies
echo "Installing dependencies..."
sudo dnf install -y python3.11 python3.11-pip nginx git

# Create application user (if not ec2-user)
# sudo useradd -m -s /bin/bash appuser

# Clone repository (or upload manually)
echo "Setting up application directory..."
mkdir -p /home/ec2-user/app
cd /home/ec2-user/app

# If cloning from git:
# git clone https://github.com/your-repo/integrate-health-mvp.git .

# Setup backend
echo "Setting up Python virtual environment..."
cd /home/ec2-user/app/backend
python3.11 -m venv venv
source venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Setup environment file (you'll need to fill in values)
echo "Creating environment file template..."
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Application
ENVIRONMENT=production
DEBUG=false

# Security (generate these with: openssl rand -hex 32)
APP_SECRET_KEY=CHANGE_ME
JWT_SECRET_KEY=CHANGE_ME

# Database (from Terraform output)
DATABASE_URL=postgresql+asyncpg://USER:PASS@RDS_ENDPOINT:5432/integrate_health

# AWS Configuration
AWS_REGION=us-east-1
S3_BUCKET_NAME=CHANGE_ME
STORAGE_MODE=s3

# Whisper Service (internal IP from Terraform)
WHISPER_SERVICE_URL=http://WHISPER_IP:8080

# Bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
EOF
    echo "IMPORTANT: Edit /home/ec2-user/app/backend/.env with your values!"
fi

# Run database migrations
echo "Running database migrations..."
source venv/bin/activate
alembic upgrade head

# Install systemd service
echo "Installing systemd service..."
sudo cp /home/ec2-user/app/deployment/app.service /etc/systemd/system/integrate-health.service
sudo systemctl daemon-reload
sudo systemctl enable integrate-health

# Setup Nginx
echo "Configuring Nginx..."
sudo cp /home/ec2-user/app/deployment/nginx.conf /etc/nginx/conf.d/integrate-health.conf
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

# Set permissions
chown -R ec2-user:ec2-user /home/ec2-user/app

echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Edit /home/ec2-user/app/backend/.env with your configuration"
echo "2. Start the service: sudo systemctl start integrate-health"
echo "3. Check status: sudo systemctl status integrate-health"
echo "4. View logs: sudo journalctl -u integrate-health -f"
