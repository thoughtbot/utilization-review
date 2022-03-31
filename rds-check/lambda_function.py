import datetime
import json
import boto3
import os
import urllib3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):

    http = urllib3.PoolManager()

    sns_arn = os.environ['SNS_ARN']
    day_interval = os.environ['DAYS_INTERVAL']
    db_utilisation_threshold = os.environ["DB_UTIL_THRESHOLD"]
    slack_webhook_ssm = os.environ["SLACK_WEBHOOK_SSM"]
    aws_region = os.environ["AWS_REGION"]
    
    rds_client = boto3.client('rds')
    sns_client = boto3.client('sns')
    cloudwatch_client = boto3.client('cloudwatch')
    ssm_client = boto3.client('ssm')

    today = datetime.date.today()

    start_date = today - datetime.timedelta(days=int(day_interval))

    db_instace_list = rds_client.describe_db_instances()

    db_identifier_list = [each_db_dict["DBInstanceIdentifier"] for each_db_dict in db_instace_list["DBInstances"]]

    logger.info(f"{db_identifier_list.count} DB instances returned for current region")

    slack_webhook_parameter = ssm_client.get_parameter(Name=slack_webhook_ssm, WithDecryption=True)

    slack_webhook = slack_webhook_parameter['Parameter']['Value']

    db_return_list = []

    for db_identifier in db_identifier_list:

        cloudwatch_response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/RDS',
            MetricName='CPUUtilization',
            Dimensions=[
                {
                    'Name': 'DBInstanceIdentifier',
                    'Value': db_identifier
                },
            ],
            Period=86400*int(day_interval),
            ExtendedStatistics=["p99"],
            Unit='Percent',
            StartTime= datetime.datetime.fromordinal(start_date.toordinal()),
            EndTime= datetime.datetime.fromordinal(today.toordinal())
        )

        cpu_utilization_percentage = cloudwatch_response["Datapoints"][0]["ExtendedStatistics"]["p99"]

        if int(cpu_utilization_percentage) <= int(db_utilisation_threshold):
            db_return_list.append(f"{db_identifier} : {cpu_utilization_percentage:.2f}%")
    
    logger.info(f"{db_return_list.count} DB instances are currently under-utilised.")

    if db_return_list:

        db_return_list.insert(0, f"The list of under-utilised RDS instances in `{aws_region}` region for the past `{day_interval}` days (_instances below `{db_utilisation_threshold}%` CPUUtilization_)")

        if sns_arn:
            logger.info(f"Sending under-utilised DB list through SNS.")
            sns_response = sns_client.publish (
                TargetArn = sns_arn,
                Message = json.dumps({
                    "default": json.dumps(db_return_list)
                }),
                MessageStructure = 'json'
            )
        
        if slack_webhook:
            logger.info(f"Sending under-utilised DB list through slack.")

            slack_message = '\n• '.join(db_return_list)
            payload = {
                "blocks": [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": slack_message
                    }
                }]
            }
            encoded_msg = json.dumps(payload).encode('utf-8')
            headers = {'Content-type': 'application/json'}
            resp = http.request('POST',slack_webhook, body=encoded_msg, headers=headers)
            logger.info(f"Response from slack webhook: {resp.reason}")
    
    else:

        logger.info(f"There are no under-utilised databases for now.")
            
    return {
        'statusCode': 200,
        'body': json.dumps(sns_response)
    }
