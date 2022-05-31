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

    dynamic_threshold = False

    sns_arn = os.environ['SNS_ARN']
    day_interval = os.environ['DAYS_INTERVAL']
    ec_utilisation_threshold = os.environ["EC_CPU_UTIL_THRESHOLD"]
    slack_webhook_ssm = os.environ["SLACK_WEBHOOK_SSM"]
    aws_region = os.environ["AWS_REGION"]

    exempt_instances_classes = list(event["exempt_instances_classes"])
    
    ec_client = boto3.client('elasticache')
    sns_client = boto3.client('sns')
    cloudwatch_client = boto3.client('cloudwatch')
    ssm_client = boto3.client('ssm')
    ec2_client = boto3.client('ec2')

    today = datetime.date.today()

    start_date = today - datetime.timedelta(days=int(day_interval))

    ec_instance_list = ec_client.describe_cache_clusters(ShowCacheNodeInfo=False,ShowCacheClustersNotInReplicationGroups=False)

    ec_identifier_list = [each_ec_dict["CacheClusterId"] for each_ec_dict in ec_instance_list["CacheClusters"] if each_ec_dict["CacheNodeType"] not in exempt_instances_classes]

    logger.info(f"{ec_identifier_list.count} elasticache instances returned for current region")

    slack_webhook_parameter = ssm_client.get_parameter(Name=slack_webhook_ssm, WithDecryption=True)

    slack_webhook = slack_webhook_parameter['Parameter']['Value']

    ec_return_list = []

    for each_cluster_id in ec_identifier_list:

        cloudwatch_response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/ElastiCache',
            MetricName='CPUUtilization',
            Dimensions=[
                {
                    'Name': 'CacheClusterId',
                    'Value': each_cluster_id
                },
            ],
            Period=86400*int(day_interval),
            ExtendedStatistics=["p99"],
            Unit='Percent',
            StartTime= datetime.datetime.fromordinal(start_date.toordinal()),
            EndTime= datetime.datetime.fromordinal(today.toordinal())
        )

        cpu_utilization_percentage = cloudwatch_response["Datapoints"][0]["ExtendedStatistics"]["p99"]

        if ec_utilisation_threshold == 0:

            ec_cache_instance_type = [each_ec_dict["CacheNodeType"] for each_ec_dict in ec_instance_list["CacheClusters"] if each_ec_dict["CacheClusterId"] == each_cluster_id ][0]
            ec2_core_count = ec2_client.describe_instance_types(InstanceTypes=[ec_cache_instance_type])['InstanceTypes'][0]['VCpuInfo']['DefaultCores']

            ec_utilisation_threshold = 90/ec2_core_count

            dynamic_threshold = True

        if int(cpu_utilization_percentage) <= int(ec_utilisation_threshold):
            
            if dynamic_threshold:
                ec_return_list.append(f"{each_cluster_id} : {cpu_utilization_percentage:.2f}%, threshold: {ec_utilisation_threshold}%")
            else:
                ec_return_list.append(f"{each_cluster_id} : {cpu_utilization_percentage:.2f}%")
                
    
    logger.info(f"{ec_return_list.count} Elasticache instances are currently under-utilised.")

    if ec_return_list:

        if dynamic_threshold:
            ec_return_list.insert(0, f"The list of under-utilised Elasticache instances in `{aws_region}` region for the past `{day_interval}` days")
        else:
            ec_return_list.insert(0, f"The list of under-utilised Elasticache instances in `{aws_region}` region for the past `{day_interval}` days (_instances below `{ec_utilisation_threshold}%` CPUUtilization_)")

        if sns_arn:
            logger.info(f"Sending under-utilised Elasticache instances list through SNS.")
            sns_response = sns_client.publish (
                TargetArn = sns_arn,
                Message = json.dumps({
                    "default": json.dumps(ec_return_list)
                }),
                MessageStructure = 'json'
            )
        
        if slack_webhook:
            logger.info(f"Sending under-utilised Elasticache instances list through slack.")

            slack_message = '\n• '.join(ec_return_list)
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

        logger.info(f"There are no under-utilised Elasticache instances for now.")
            
    return {
        'statusCode': 200,
        'body': json.dumps(sns_response)
    }
