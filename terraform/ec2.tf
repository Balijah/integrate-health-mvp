# EC2 instances for Integrate Health

# Get latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Get latest Deep Learning AMI for GPU instances
data "aws_ami" "deep_learning" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Deep Learning*AMI*PyTorch*Amazon Linux 2*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

# SSH Key pair (you'll need to create this or import your own)
resource "aws_key_pair" "main" {
  key_name   = "integrate-health-key"
  public_key = file("~/.ssh/id_ed25519.pub")

  tags = {
    Name = "integrate-health-key"
  }
}

# App Server (FastAPI backend)
resource "aws_instance" "app" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.app_instance_type
  subnet_id              = aws_subnet.private_a.id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = aws_key_pair.main.key_name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = base64encode(<<-EOF
    #!/bin/bash
    # Update system
    dnf update -y

    # Install Python 3.11 and dependencies
    dnf install -y python3.11 python3.11-pip nginx git

    # Install Docker (optional, for containerized deployment)
    dnf install -y docker
    systemctl enable docker
    systemctl start docker

    # Create app directory
    mkdir -p /home/ec2-user/app
    chown ec2-user:ec2-user /home/ec2-user/app

    # Install CloudWatch agent
    dnf install -y amazon-cloudwatch-agent

    echo "App server setup complete"
  EOF
  )

  tags = {
    Name = "integrate-health-app"
  }

  depends_on = [aws_nat_gateway.main]
}

# Whisper Server - On-Demand (fallback when Spot not available)
resource "aws_instance" "whisper_ondemand" {
  count = var.use_spot_for_whisper ? 0 : 1

  ami                    = data.aws_ami.deep_learning.id
  instance_type          = var.whisper_instance_type
  subnet_id              = aws_subnet.private_a.id
  vpc_security_group_ids = [aws_security_group.whisper.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = aws_key_pair.main.key_name

  root_block_device {
    volume_size = 50
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = base64encode(local.whisper_user_data)

  tags = {
    Name = "integrate-health-whisper"
  }

  depends_on = [aws_nat_gateway.main]
}

# Whisper Server - Spot Fleet (cost optimized)
resource "aws_spot_fleet_request" "whisper" {
  count = var.use_spot_for_whisper ? 1 : 0

  iam_fleet_role                      = aws_iam_role.spot_fleet[0].arn
  target_capacity                     = 1
  allocation_strategy                 = "capacityOptimized"
  terminate_instances_with_expiration = true
  valid_until                         = timeadd(timestamp(), "8760h")  # 1 year

  launch_specification {
    ami                    = data.aws_ami.deep_learning.id
    instance_type          = var.whisper_instance_type
    subnet_id              = aws_subnet.private_a.id
    vpc_security_group_ids = [aws_security_group.whisper.id]
    iam_instance_profile   = aws_iam_instance_profile.ec2.name
    key_name               = aws_key_pair.main.key_name

    root_block_device {
      volume_size = 50
      volume_type = "gp3"
      encrypted   = true
    }

    user_data = base64encode(local.whisper_user_data)

    tags = {
      Name = "integrate-health-whisper-spot"
    }
  }

  # Try multiple instance types for better Spot availability
  launch_specification {
    ami                    = data.aws_ami.deep_learning.id
    instance_type          = "g5.xlarge"  # Alternative GPU instance
    subnet_id              = aws_subnet.private_a.id
    vpc_security_group_ids = [aws_security_group.whisper.id]
    iam_instance_profile   = aws_iam_instance_profile.ec2.name
    key_name               = aws_key_pair.main.key_name

    root_block_device {
      volume_size = 50
      volume_type = "gp3"
      encrypted   = true
    }

    user_data = base64encode(local.whisper_user_data)

    tags = {
      Name = "integrate-health-whisper-spot"
    }
  }

  tags = {
    Name = "integrate-health-whisper-spot-fleet"
  }

  depends_on = [aws_nat_gateway.main]
}

# User data script for Whisper server
locals {
  whisper_user_data = <<-EOF
    #!/bin/bash
    set -e

    # Log output
    exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

    echo "Starting Whisper server setup..."

    # Wait for network
    sleep 10

    # Update system
    yum update -y

    # Create app directory
    mkdir -p /home/ec2-user/whisper-service
    cd /home/ec2-user/whisper-service

    # Create virtual environment
    python3 -m venv venv
    source venv/bin/activate

    # Install dependencies
    pip install --upgrade pip
    pip install fastapi uvicorn python-multipart openai-whisper torch

    # Create the Whisper service app
    cat > app.py << 'PYEOF'
    from fastapi import FastAPI, UploadFile, File, Form, HTTPException
    import whisper
    import torch
    import tempfile
    import os
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    app = FastAPI(title="Whisper Transcription Service")
    model = None

    @app.on_event("startup")
    def load_model():
        global model
        logger.info("Loading Whisper model...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        model = whisper.load_model("large-v3", device=device)
        logger.info("Whisper model loaded successfully")

    @app.get("/health")
    def health():
        return {
            "status": "healthy",
            "model": "whisper-large-v3",
            "gpu": torch.cuda.is_available(),
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        }

    @app.post("/transcribe")
    async def transcribe(
        audio: UploadFile = File(...),
        mime_type: str = Form("audio/wav")
    ):
        extensions = {
            "audio/wav": ".wav",
            "audio/mp3": ".mp3",
            "audio/mpeg": ".mp3",
            "audio/webm": ".webm",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
            "audio/ogg": ".ogg"
        }
        ext = extensions.get(mime_type, ".wav")

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await audio.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            logger.info(f"Transcribing audio file: {tmp_path}")
            result = model.transcribe(tmp_path, language="en", fp16=torch.cuda.is_available())
            logger.info("Transcription completed")

            return {
                "text": result["text"],
                "duration": result.get("duration", 0),
                "language": result.get("language", "en"),
                "segments": result.get("segments", [])
            }
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            os.unlink(tmp_path)
    PYEOF

    # Set ownership
    chown -R ec2-user:ec2-user /home/ec2-user/whisper-service

    # Create systemd service
    cat > /etc/systemd/system/whisper.service << 'SVCEOF'
    [Unit]
    Description=Whisper Transcription Service
    After=network.target

    [Service]
    User=ec2-user
    WorkingDirectory=/home/ec2-user/whisper-service
    ExecStart=/home/ec2-user/whisper-service/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8080
    Restart=always
    RestartSec=10
    Environment="PATH=/home/ec2-user/whisper-service/venv/bin"

    [Install]
    WantedBy=multi-user.target
    SVCEOF

    # Enable and start service
    systemctl daemon-reload
    systemctl enable whisper
    systemctl start whisper

    echo "Whisper server setup complete"
  EOF
}

# CloudWatch Log Group for application
resource "aws_cloudwatch_log_group" "app" {
  name              = "/integrate-health/app"
  retention_in_days = 30

  tags = {
    Name = "integrate-health-app-logs"
  }
}

resource "aws_cloudwatch_log_group" "whisper" {
  name              = "/integrate-health/whisper"
  retention_in_days = 30

  tags = {
    Name = "integrate-health-whisper-logs"
  }
}
