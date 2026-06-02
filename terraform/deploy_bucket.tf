# Dedicated S3 bucket for deployment artifacts (backend tarballs, frontend dist)
# Kept separate from the PHI audio bucket for HIPAA access-control separation.

resource "aws_s3_bucket" "deploy" {
  bucket = "integrate-health-deploy-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "integrate-health-deploy"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "deploy" {
  bucket = aws_s3_bucket.deploy.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "deploy" {
  bucket = aws_s3_bucket.deploy.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Deploy artifacts are ephemeral — keep only the last 30 days
resource "aws_s3_bucket_lifecycle_configuration" "deploy" {
  bucket = aws_s3_bucket.deploy.id

  rule {
    id     = "expire-old-deploys"
    status = "Enabled"

    filter {}

    expiration {
      days = 30
    }
  }
}

# Grant EC2 instance profile read access to the deploy bucket
resource "aws_iam_role_policy" "deploy_bucket_access" {
  name = "integrate-health-deploy-bucket-access"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "DeployBucketReadWrite"
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
      ]
      Resource = [
        aws_s3_bucket.deploy.arn,
        "${aws_s3_bucket.deploy.arn}/*",
      ]
    }]
  })
}
