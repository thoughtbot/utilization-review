variable "slack_webhook_ssm" {
  description = "AWS Parameter store name for slack endpoint to send under-utilised DB list in using AWS lambda"
  type        = string
}

variable "email_address_list" {
  description = "List of email addreses to send under-utilised DB list through SNS"
  type        = list(string)
  default     = []
}

variable "days_interval" {
  description = "The Cloudwatch period / interval to review metrics for the RDS instances."
  type        = number
  default     = 7
}

variable "review_frequency" {
  description = "This is the cron frenquency to be used by the lambda script. It states how often the lambda script is to be run to review the RDS instances. It is provided in AWS cron expression in UTC+0 - https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html#eb-cron-expressions. Default value is to run every Monday at 12 PM UTC."
  type        = string
  default     = "0 12 ? * 2 *"
}

variable "exempt_db_classes" {
  description = "List of DB instance classes that are expemted from monitoring."
  type        = list(string)
  default     = []
}

variable "utilisation_threshold" {
  description = "This is the CPU Utilization threshold in percentage below which an RDS instance is considered under-utilised."
  type        = number
  default     = 25
}

variable "tags" {
  type        = map(string)
  description = "Tags to be applied to created resources"
  default     = {}
}