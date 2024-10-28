import boto3
import time
import yaml
import pandas as pd
import botocore
from aiohttp import ClientError
from s3path import S3Path
import s3path
from eki_dev.aws_service import AwsService

from logging import getLogger

logger = getLogger(__name__)

DEFAULT_PEST_CF_TEMPLATE = "https://eki-cf-templates.s3.us-west-1.amazonaws.com/PestCluster-cf-tpl.yaml"

status_color_codes ={
    "CREATE_COMPLETE": ['background-color: green'],
    "CREATE_FAILED": ['background-color: red'],
    "CREATE_IN_PROGRESS": ['background-color: yellow'],
    "DELETE_COMPLETE": ['background-color: blue'],
    "DELETE_FAILED": ['background-color: red'],
    "DELETE_IN_PROGRESS": ['background-color: yellow'],
    "TERMINATE_COMPLETE":['background-color: green'],
    "TERMINATE_FAILED": ['background-color: red'],
    "TERMINATE_IN_PROGRESS": ['background-color: yellow'],
}


def open_yaml(fn_config_yaml):

    if fn_config_yaml.startswith("s3://"):
        fn_config_yaml = fn_config_yaml[len("s3:/"):]
        with s3path.S3Path(fn_config_yaml).open() as f:
            config = yaml.safe_load(f)
    else:
        with open(fn_config_yaml, 'r') as f:
            config = yaml.safe_load(f)
    return config


def check_resource_creation_status(stack_name: str):
    """
    Checks the status of the pest cluster resources created by cloud formation.
    """
    cf = AwsService.from_service('cloudformation')
    try:
        ret = cf.client.describe_stack_resources(StackName=stack_name)
    except botocore.exceptions.ClientError as e:
        print(f"Stack {stack_name} does not exist")
        return
    if ret['ResponseMetadata']['HTTPStatusCode'] == 200:
        df = pd.DataFrame(ret['StackResources'])[["LogicalResourceId","ResourceStatus"]]
        df_style = df.style.apply(lambda x: status_color_codes[x["ResourceStatus"]]*len(x), axis=1)
        return df_style
    else:
        print(ret['ResponseMetadata']['HTTPStatusCode'])


def check_stack_creation_status(stack_name: str):
    cf = AwsService.from_service('cloudformation')
    try:
        stack_status = cf.client.describe_stacks(StackName=stack_name)
    except botocore.exceptions.ClientError as error:
        print(f"Stack {stack_name} does not exist")
        return
    for stack in stack_status['Stacks']:
        if stack['StackName'] == stack_name:
            return stack['StackStatus']

    logger.error(f"Stack {stack_name} does not exist")


def get_arn_of_target_group(stack_name: str = "PestClusterInfrastructure"):
    cf = AwsService.from_service('cloudformation')
    stack_resources = cf.client.describe_stack_resources(StackName=stack_name)
    for resource in stack_resources['StackResources']:
        if resource['ResourceType'] == "AWS::ElasticLoadBalancingV2::TargetGroup":
            target_group_arn = resource['PhysicalResourceId']
            return target_group_arn

    logger.error(f"Target group in {stack_name} does not exist")


def get_ip_of_ecs_task(cluster_name: str,
                       task_arn: str):
    ecs_client = AwsService.from_service('ecs')

    main_task = ecs_client.client.describe_tasks(cluster=cluster_name,
                                                 tasks=[task_arn])
    container_arn = main_task['tasks'][0]['containerInstanceArn']
    main_container = ecs_client.client.describe_container_instances(cluster=cluster_name,
                                                            containerInstances=[container_arn])
    main_instance_id = main_container['containerInstances'][0]['ec2InstanceId']

    ec2_client = AwsService.from_service('ec2')
    main_instance = ec2_client.client.describe_instances(InstanceIds=[main_instance_id])
    main_instance_ip = main_instance['Reservations'][0]['Instances'][0]['PrivateIpAddress']

    return main_instance_ip


def get_arn_of_agents(stack_name: str = "PestClusterInfrastructure"):
    ecs_client = AwsService.from_service('ecs')

    main_task = ecs_client.client.describe_tasks(tasks=[task_arn])
    container_arn = main_task['tasks'][0]['containerInstanceArn']
    main_container = ecs_client.client.describe_container_instances(cluster="PestCluster",
                                                            containerInstances=[container_arn])
    main_instance_id = main_container['containerInstances'][0]['ec2InstanceId']

    ec2_client = AwsService.from_service('ec2')
    main_instance = ec2_client.client.describe_instances(InstanceIds=[main_instance_id])
    main_instance_ip = main_instance['Reservations'][0]['Instances'][0]['PrivateIpAddress']

    return main_instance_ip


def get_list_tasks_service(cluster_name: str,
                           service_name: str):

    ecs_client = AwsService.from_service("ecs").client

    # List tasks in the specified ECS service
    response = ecs_client.list_tasks(
        cluster=cluster_name,
        serviceName=service_name
    )

    # Retrieve task ARNs
    task_arns = response.get("taskArns", [])

    if not task_arns:
        print("No tasks found in the service.")
        return []

    return task_arns



def check_cluster_workers_status(stack_name: str):
    cf = AwsService.from_service('cloudformation')
    stack_status = check_stack_creation_status(stack_name)
    if stack_status != "CREATE_COMPLETE":
        print(f"Stack status is {stack_status}. Please wait until status is CREATE_COMPLETE")
        return False

    ret = cf.client.describe_stack_resources(StackName=stack_name)
    if ret['ResponseMetadata']['HTTPStatusCode'] == 200:
        for resource in ret['StackResources']:
            if resource["LogicalResourceId"] == "ECSService":
                resource[["LogicalResourceId"]]










