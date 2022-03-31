locals {
  # create unique function name
  function_name = "RDS-Utilisation-Review-${random_id.unique_id.dec}"

  tags = merge({ "Project" : "RDS Utilisation review" }, var.tags)
}

resource "aws_lambda_function" "rds_review" {
  function_name    = local.function_name
  description      = "Lambda function to check under-utilised RDS instances and send SNS notifications for same"
  filename         = data.archive_file.function.output_path
  handler          = "lambda_function.lambda_handler"
  role             = aws_iam_role.lambda_role.arn
  runtime          = "python3.8"
  source_code_hash = data.archive_file.function.output_base64sha256
  timeout          = 60

  environment {
    variables = {
      SNS_ARN           = aws_sns_topic.rds_review.arn
      DAYS_INTERVAL     = var.days_interval
      DB_UTIL_THRESHOLD = var.utilisation_threshold
      SLACK_WEBHOOK_SSM = var.slack_webhook_ssm
    }
  }
  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    aws_iam_role.lambda_role
  ]

  tags = local.tags
}

data "aws_iam_policy_document" "assume_role_policy_doc" {
  statement {
    sid    = "AllowAwsToAssumeRole"
    effect = "Allow"

    actions = ["sts:AssumeRole"]

    principals {
      type = "Service"

      identifiers = [
        "lambda.amazonaws.com",
      ]
    }
  }
}

resource "aws_iam_role" "lambda_role" {
  name               = "${local.function_name}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role_policy_doc.json

  tags = local.tags
}

resource "aws_iam_role_policy" "logs_role_policy" {
  name   = "${local.function_name}-policy"
  role   = aws_iam_role.lambda_role.id
  policy = data.aws_iam_policy_document.rds_review_lambda_policy.json
}

resource "random_id" "unique_id" {
  byte_length = 3
}

data "archive_file" "function" {
  output_path = "lambda_function.zip"
  source_file = "${path.module}/rds-check/lambda_function.py"
  type        = "zip"
}

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = 14

  tags = local.tags
}

data "aws_iam_policy_document" "rds_review_lambda_policy" {
  statement {
    sid       = "rdsdescribeinstances"
    effect    = "Allow"
    resources = ["*"]
    actions   = ["rds:DescribeDBInstances"]
  }
  statement {
    sid       = "snspublishnotifiations"
    effect    = "Allow"
    resources = [aws_sns_topic.rds_review.arn]
    actions   = ["sns:Publish"]
  }
  statement {
    sid       = "cloudwatchgetmetricstatitics"
    effect    = "Allow"
    resources = ["*"]
    actions   = ["cloudwatch:GetMetricStatistics"]
  }
  statement {
    sid       = "cloudwatchwritelambdalogs"
    effect    = "Allow"
    resources = ["arn:aws:logs:*:*:*"]
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
  }
  statement {
    sid       = "ssmparameerstoreparam"
    effect    = "Allow"
    resources = ["*"]
    actions   = ["ssm:GetParameter"]
  }
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = local.function_name

  dashboard_body = <<EOF
{
  "widgets": [
    {
      "type": "metric",
      "x": 0,
      "y": 0,
      "width": 18,
      "height": 12,
      "properties": {
        "metrics": [
          [ { "expression": "SEARCH('{AWS/RDS,DBInstanceIdentifier} MetricName=\"CPUUtilization\"', 'p99', ${86400 * var.days_interval})" } ]
        ],
        "view": "singleValue",
        "stacked": false,
        "region": "us-east-1",
        "stat": "p99",
        "period": ${86400 * var.days_interval}
      }
    }
  ]
}
EOF
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rds_review.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.rds_review.arn
}

resource "aws_sns_topic" "rds_review" {
  name = local.function_name

  tags = local.tags
}

resource "aws_sns_topic_subscription" "rds_review" {
  count = length(var.email_address_list)

  topic_arn = aws_sns_topic.rds_review.arn
  protocol  = "email-json"
  endpoint  = var.email_address_list[count.index]
}

resource "aws_cloudwatch_event_target" "rds_review" {
  arn  = aws_lambda_function.rds_review.arn
  rule = aws_cloudwatch_event_rule.rds_review.id
}

resource "aws_cloudwatch_event_rule" "rds_review" {
  name                = local.function_name
  description         = "Cloudwatch event to trigger lambda function to review utilisation for RDS instances"
  schedule_expression = "rate(${var.days_interval} days)"

  tags = local.tags
}

