# Security groups for Integrate Health infrastructure

# App server security group
resource "aws_security_group" "app" {
  name        = "integrate-health-app-sg"
  description = "Security group for app server"
  vpc_id      = aws_vpc.main.id

  # SSH access (restricted)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
    description = "SSH from allowed CIDR"
  }

  # HTTP (for redirect to HTTPS or health checks)
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP from anywhere"
  }

  # HTTPS
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS from anywhere"
  }

  # FastAPI direct (for internal use during development)
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
    description = "FastAPI from allowed CIDR"
  }

  # Outbound: Allow all
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "integrate-health-app-sg"
  }
}

# Whisper server security group
resource "aws_security_group" "whisper" {
  name        = "integrate-health-whisper-sg"
  description = "Security group for Whisper transcription server"
  vpc_id      = aws_vpc.main.id

  # SSH access (restricted)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
    description = "SSH from allowed CIDR"
  }

  # Whisper API from app server only
  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
    description     = "Whisper API from app server"
  }

  # Outbound: Allow all (for downloading model, updates)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "integrate-health-whisper-sg"
  }
}

# RDS security group
resource "aws_security_group" "rds" {
  name        = "integrate-health-rds-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = aws_vpc.main.id

  # PostgreSQL from app and whisper servers
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id, aws_security_group.whisper.id]
    description     = "PostgreSQL from app and whisper servers"
  }

  tags = {
    Name = "integrate-health-rds-sg"
  }
}
