# IAM roles and policies for Integrate Health infrastructure

# EC2 IAM role
resource "aws_iam_role" "ec2" {
  name = "integrate-health-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "integrate-health-ec2-role"
  }
}

# S3 access policy for audio storage
resource "aws_iam_role_policy" "s3_access" {
  name = "integrate-health-s3-access"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.audio.arn,
          "${aws_s3_bucket.audio.arn}/*"
        ]
      }
    ]
  })
}

# Bedrock access policy for LLM calls
resource "aws_iam_role_policy" "bedrock_access" {
  name = "integrate-health-bedrock-access"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.*"
        ]
      }
    ]
  })
}

# CloudWatch Logs access for application logging
resource "aws_iam_role_policy" "cloudwatch_logs" {
  name = "integrate-health-cloudwatch-logs"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/integrate-health/*"
      }
    ]
  })
}

# SSM access for Session Manager (optional alternative to SSH)
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# EC2 instance profile
resource "aws_iam_instance_profile" "ec2" {
  name = "integrate-health-ec2-profile"
  role = aws_iam_role.ec2.name
}

# Spot Fleet IAM role (for Whisper Spot instances)
resource "aws_iam_role" "spot_fleet" {
  count = var.use_spot_for_whisper ? 1 : 0
  name  = "integrate-health-spot-fleet-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "spotfleet.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "integrate-health-spot-fleet-role"
  }
}

resource "aws_iam_role_policy_attachment" "spot_fleet" {
  count      = var.use_spot_for_whisper ? 1 : 0
  role       = aws_iam_role.spot_fleet[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole"
}
