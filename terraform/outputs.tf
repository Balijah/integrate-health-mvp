# Output values for Integrate Health infrastructure

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "Public subnet ID"
  value       = aws_subnet.public.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = [aws_subnet.private_a.id, aws_subnet.private_b.id]
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.main.endpoint
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.main.db_name
}

output "s3_bucket_name" {
  description = "S3 bucket name for audio storage"
  value       = aws_s3_bucket.audio.id
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.audio.arn
}

output "app_server_private_ip" {
  description = "App server private IP"
  value       = aws_instance.app.private_ip
}

output "app_server_id" {
  description = "App server instance ID"
  value       = aws_instance.app.id
}

output "app_security_group_id" {
  description = "App server security group ID"
  value       = aws_security_group.app.id
}

output "ec2_instance_profile_name" {
  description = "EC2 instance profile name"
  value       = aws_iam_instance_profile.ec2.name
}

output "database_url" {
  description = "PostgreSQL connection URL (without password)"
  value       = "postgresql+asyncpg://${var.db_username}@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}"
  sensitive   = true
}

output "nat_gateway_ip" {
  description = "NAT Gateway public IP (for whitelisting)"
  value       = var.enable_nat_gateway ? aws_eip.nat[0].public_ip : null
}
