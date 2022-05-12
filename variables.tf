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
  description = "Number of days interval to review CPU Utilization and deliver a report to the provided endpoint. This interval is also used as the period for Cloudwatch metrics."
  type        = number
  default     = 14
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