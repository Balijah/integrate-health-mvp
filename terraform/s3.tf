# S3 bucket configuration for audio storage

# Audio storage bucket
resource "aws_s3_bucket" "audio" {
  bucket = "integrate-health-audio-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "integrate-health-audio"
  }
}

# Enable versioning (helps with accidental deletion recovery)
resource "aws_s3_bucket_versioning" "audio" {
  bucket = aws_s3_bucket.audio.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption (HIPAA requirement)
resource "aws_s3_bucket_server_side_encryption_configuration" "audio" {
  bucket = aws_s3_bucket.audio.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Block all public access (HIPAA requirement)
resource "aws_s3_bucket_public_access_block" "audio" {
  bucket = aws_s3_bucket.audio.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle rules for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "audio" {
  bucket = aws_s3_bucket.audio.id

  rule {
    id     = "archive-old-audio"
    status = "Enabled"

    filter {}  # Apply to all objects

    # Move to Glacier Deep Archive after 7 days (rarely accessed)
    transition {
      days          = 7
      storage_class = "DEEP_ARCHIVE"
    }

    # Delete old audio files after 1 year (adjust based on retention requirements)
    expiration {
      days = 365
    }

    # Clean up incomplete multipart uploads
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  rule {
    id     = "delete-old-versions"
    status = "Enabled"

    filter {}  # Apply to all objects

    # Delete old versions after 30 days
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# S3 bucket logging for audit trail
resource "aws_s3_bucket" "logs" {
  bucket = "integrate-health-logs-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "integrate-health-logs"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket = aws_s3_bucket.logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Allow audio bucket to write logs
resource "aws_s3_bucket_policy" "logs" {
  bucket = aws_s3_bucket.logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "logging.s3.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.logs.arn}/*"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

# Enable access logging for audio bucket
resource "aws_s3_bucket_logging" "audio" {
  bucket = aws_s3_bucket.audio.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "s3-access-logs/audio/"
}

# Lifecycle for logs bucket
resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    id     = "archive-logs"
    status = "Enabled"

    filter {}  # Apply to all objects

    transition {
      days          = 30
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}
