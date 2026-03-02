#!/bin/bash
# Setup script for Whisper Transcription Server
# Run this on the EC2 GPU server after launching

set -e

echo "=== Setting up Whisper Transcription Server ==="

# Check for GPU
echo "Checking for NVIDIA GPU..."
if nvidia-smi &> /dev/null; then
    echo "GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv
else
    echo "WARNING: No NVIDIA GPU detected. Transcription will be very slow."
fi

# Update system (Deep Learning AMI should have most dependencies)
echo "Updating system packages..."
sudo yum update -y

# Activate conda environment (Deep Learning AMI uses conda)
source /home/ec2-user/anaconda3/bin/activate

# Create application directory
echo "Setting up application directory..."
mkdir -p /home/ec2-user/whisper-service
cd /home/ec2-user/whisper-service

# Copy application files (or clone from git)
# For now, assume files are uploaded manually

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install PyTorch with CUDA support
echo "Installing PyTorch with CUDA support..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install other dependencies
echo "Installing dependencies..."
pip install fastapi uvicorn python-multipart openai-whisper

# Download Whisper model (this takes a while)
echo "Downloading Whisper large-v3 model..."
python3 -c "import whisper; whisper.load_model('large-v3')"

# Create app.py if not exists
if [ ! -f app.py ]; then
    echo "IMPORTANT: Copy app.py from the repository to /home/ec2-user/whisper-service/"
fi

# Install systemd service
echo "Installing systemd service..."
cat > /tmp/whisper.service << 'EOF'
[Unit]
Description=Whisper Transcription Service
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/whisper-service
Environment="PATH=/home/ec2-user/whisper-service/venv/bin"
ExecStart=/home/ec2-user/whisper-service/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/whisper.service /etc/systemd/system/whisper.service
sudo systemctl daemon-reload
sudo systemctl enable whisper

# Set permissions
chown -R ec2-user:ec2-user /home/ec2-user/whisper-service

echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Copy app.py to /home/ec2-user/whisper-service/"
echo "2. Start the service: sudo systemctl start whisper"
echo "3. Check status: sudo systemctl status whisper"
echo "4. View logs: sudo journalctl -u whisper -f"
echo "5. Test health: curl http://localhost:8080/health"
