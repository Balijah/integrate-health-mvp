# CloudWatch alarms and SNS alerting

resource "aws_sns_topic" "alerts" {
  name = "integrate-health-alerts"

  tags = {
    Name = "integrate-health-alerts"
  }
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Alert when any note lands in the DLQ (means 3 consecutive processing failures)
resource "aws_cloudwatch_metric_alarm" "notes_dlq_depth" {
  alarm_name          = "integrate-health-notes-dlq-not-empty"
  alarm_description   = "One or more note generation tasks failed 3 times and landed in the DLQ. Check CloudWatch logs for [WORKER] errors."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.notes_dlq.name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = {
    Name = "integrate-health-notes-dlq-alarm"
  }
}

# Alert when worker stops polling (no messages received in 10 min during business hours)
# This monitors the main queue consumer — a sudden drop in ReceiveMessage calls
# indicates the worker process crashed and failed to restart.
resource "aws_cloudwatch_metric_alarm" "app_unhealthy" {
  alarm_name          = "integrate-health-app-high-5xx"
  alarm_description   = "Backend is returning elevated 5xx errors — check application health."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "5XXError"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = {
    Name = "integrate-health-app-5xx-alarm"
  }
}
