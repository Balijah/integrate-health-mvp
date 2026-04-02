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

# CloudWatch Log Group for application
resource "aws_cloudwatch_log_group" "app" {
  name              = "/integrate-health/app"
  retention_in_days = 30

  tags = {
    Name = "integrate-health-app-logs"
  }
}

