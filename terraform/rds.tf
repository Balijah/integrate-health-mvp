# RDS PostgreSQL configuration for Integrate Health

# DB subnet group (requires 2 AZs)
resource "aws_db_subnet_group" "main" {
  name       = "integrate-health-db-subnet"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  tags = {
    Name = "integrate-health-db-subnet"
  }
}

# RDS PostgreSQL instance
resource "aws_db_instance" "main" {
  identifier = "integrate-health-db"

  # Engine configuration
  engine               = "postgres"
  engine_version       = "15"
  instance_class       = var.db_instance_class
  allocated_storage    = var.db_allocated_storage
  max_allocated_storage = 100  # Enable storage autoscaling up to 100GB
  storage_type         = "gp3"
  storage_encrypted    = true  # HIPAA requirement

  # Database configuration
  db_name  = "integrate_health"
  username = var.db_username
  password = var.db_password
  port     = 5432

  # Network configuration
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  publicly_accessible    = false  # Private subnet only

  # Backup configuration
  backup_retention_period = 7     # Keep backups for 7 days
  backup_window          = "03:00-04:00"  # UTC
  maintenance_window     = "Mon:04:00-Mon:05:00"

  # Performance Insights (helps with troubleshooting)
  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  # Enhanced monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  # Deletion protection (disable for MVP/testing)
  deletion_protection = false
  skip_final_snapshot = true  # For MVP; set to false in production

  # Enable automatic minor version upgrades
  auto_minor_version_upgrade = true

  # Parameter group for custom settings
  parameter_group_name = aws_db_parameter_group.main.name

  tags = {
    Name = "integrate-health-db"
  }
}

# RDS parameter group for PostgreSQL tuning
resource "aws_db_parameter_group" "main" {
  family = "postgres15"
  name   = "integrate-health-pg15"

  # Log configuration for HIPAA audit
  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_statement"
    value = "ddl"
  }

  # SSL enforcement
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = {
    Name = "integrate-health-pg15"
  }
}

# IAM role for RDS enhanced monitoring
resource "aws_iam_role" "rds_monitoring" {
  name = "integrate-health-rds-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "monitoring.rds.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "integrate-health-rds-monitoring"
  }
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
