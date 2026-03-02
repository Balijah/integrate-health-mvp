# Terraform configuration for Integrate Health MVP
# HIPAA-compliant AWS infrastructure with cost optimization

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend configuration for state management
  # Uncomment and configure for production use
  # backend "s3" {
  #   bucket         = "integrate-health-terraform-state"
  #   key            = "production/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "integrate-health-terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "integrate-health"
      Environment = var.environment
      ManagedBy   = "terraform"
      HIPAA       = "true"
    }
  }
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# Get current AWS region
data "aws_region" "current" {}
