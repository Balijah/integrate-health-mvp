# SQS queues for asynchronous note generation

# Dead-letter queue — receives messages after 3 failed processing attempts
resource "aws_sqs_queue" "notes_dlq" {
  name                      = "integrate-health-notes-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name = "integrate-health-notes-dlq"
  }
}

# Main processing queue
resource "aws_sqs_queue" "notes" {
  name                       = "integrate-health-notes"
  visibility_timeout_seconds = 600       # 10 min; worker heartbeat extends this for long jobs
  message_retention_seconds  = 86400     # 24 hours
  receive_wait_time_seconds  = 20        # long polling — reduces empty receive API calls

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notes_dlq.arn
    maxReceiveCount     = 3 # move to DLQ after 3 unacknowledged delivery attempts
  })

  tags = {
    Name = "integrate-health-notes"
  }
}
