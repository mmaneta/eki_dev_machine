import pandas as pd
import yaml
from aws_cluster.cluster_utils import (DEFAULT_PEST_CF_TEMPLATE,
                                       open_yaml,
                                       get_arn_of_target_group,
                                       get_ip_of_ecs_task,
                                       get_list_tasks_service)

from eki_dev.aws_service import AwsService
from eki_dev.docker_utils import create_docker_context
from eki_dev.utils import register_instance
from logging import getLogger
logger = getLogger(__name__)


def create_pest_cluster_stack(fn_config_yaml: str,
                              cf_template: str = DEFAULT_PEST_CF_TEMPLATE):

    config = open_yaml(fn_config_yaml)

    ECSClusterName = config["Parameters"]["ECSClusterName"]
    TaskDefinitionImage = config["Parameters"]["TaskDefinitionImage"]
    ContainerMemory = config["Parameters"]["ContainerMemory"]
    ContainerPortPestHP = config["Parameters"]["ContainerPortPestHP"]
    HostPortPestHP = config["Parameters"]["HostPortPestHP"]
    DesiredNumberAgents = config["Parameters"]["DesiredNumberAgents"]
    PestCaseName = config["Parameters"]["PestCaseName"]
    SshKeyName = config["Parameters"]["KeyName"]

    ProjectTag = config["Tags"]["ProjectTag"]

    iam_service = AwsService.from_service('iam')
    user_name = iam_service.client.get_user()['User']['UserName']

    cf = AwsService.from_service('cloudformation')
    try:
        response = cf.client.create_stack(
            StackName="PestClusterInfrastructure",
            TemplateURL=cf_template,
            Parameters=[
                {
                    'ParameterKey': 'TaskDefinitionImage',
                    'ParameterValue': TaskDefinitionImage,
                },
                {
                    'ParameterKey': 'ContainerMemory',
                    'ParameterValue': str(ContainerMemory),
                },
                {
                    'ParameterKey': 'ContainerPortPestHP',
                    'ParameterValue': str(ContainerPortPestHP),
                },
                {
                    'ParameterKey': 'HostPortPestHP',
                    'ParameterValue': str(HostPortPestHP),
                },
                {
                    'ParameterKey': 'DesiredNumberAgents',
                    'ParameterValue': str(DesiredNumberAgents),
                },
                {
                    'ParameterKey': 'PestCaseName',
                    'ParameterValue': PestCaseName,
                },
                {
                    'ParameterKey': 'KeyName',
                    'ParameterValue': SshKeyName,
                },

            ],
            Tags=[
                {
                    'Key': 'project_tag',
                    'Value': f"{ProjectTag}"
                },
                {
                    'Key': 'user',
                    'Value': f"{user_name}"
                },
            ],
        )
    except cf.client.exceptions.LimitExceededException:
        print("PestCluster stack limit exceeded")
        return False
    except cf.client.exceptions.AlreadyExistsException:
        print("PestCluster stack already exists")
        return False
    except cf.client.exceptions.TokenAlreadyExistsException:
        print("Token already exists")
        return False
    except cf.client.exceptions.InsufficientCapabilitiesException:
        print("Insufficient Capabilities")
        return False

    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        logger.info("Creating PestCluster stack")
        return True


def create_main_task(fn_config_yaml: str,):

    config = open_yaml(fn_config_yaml)

    ECSClusterName = config["Parameters"]["ECSClusterName"]
    TaskDefinitionImage = config["Parameters"]["TaskDefinitionImage"]
    ContainerMemory = config["Parameters"]["ContainerMemory"]
    ContainerPortPestHP = config["Parameters"]["ContainerPortPestHP"]
    HostPortPestHP = config["Parameters"]["HostPortPestHP"]
    PestCaseName = config["Parameters"]["PestCaseName"]

    ProjectTag = config["Tags"]["ProjectTag"]

    overrides = {
        'containerOverrides': [
            {
                'name': 'model',
                'command': [
                    "pest_hp",
                    f"{PestCaseName}",
                "/h",
                f":{HostPortPestHP}",
                ],
                'memory': int(f"{ContainerMemory}"),
            },
        ],
    }

    iam_service = AwsService.from_service('iam')
    user_name = iam_service.client.get_user()['User']['UserName']

    ecs = AwsService.from_service('ecs')

    resp = ecs.client.run_task(
        cluster=ECSClusterName,
        count=1,
        taskDefinition='arn:aws:ecs:us-west-1:054507568115:task-definition/pest_host:5',
        overrides=overrides,
        tags=[
            {
                'key': 'project_tag',
                'value': f"{ProjectTag}"
            },
            {
                'key': 'user',
                'value': f"{user_name}"
            },
        ],
    )

    task_arn = resp['tasks'][0]['taskArn']
    waiter = ecs.client.get_waiter('tasks_running')
    print("Waiting for Main Task to be Created...")
    waiter.wait(cluster=ECSClusterName,
                tasks=[task_arn])

    print("Main Task Created. Registering IP in Target Group")
    main_instance_ip = get_ip_of_ecs_task(cluster_name=ECSClusterName,
                                          task_arn=task_arn)
    print("Main Instance IP: {}".format(main_instance_ip))
    target_group_arn = get_arn_of_target_group("PestClusterInfrastructure")

    elbv_client = AwsService.from_service('elbv2').client
    elbv_client.register_targets(TargetGroupArn=target_group_arn,
                                        Targets=[{
                                            'Id': main_instance_ip,
                                            'Port': ContainerPortPestHP,
                                        }])

    return resp


def list_agent_tasks(fn_config_yaml: str):

    config = open_yaml(fn_config_yaml)
    ECSClusterName = config["Parameters"]["ECSClusterName"]

    ecs = AwsService.from_service('ecs')
    service_arns = ecs.client.list_services(cluster="PestCluster")["serviceArns"]

    lst_tasks = get_list_tasks_service(cluster_name=ECSClusterName,
                                       service_name=service_arns[0])
    return pd.DataFrame(lst_tasks)


def add_docker_context_to_main_instance(fn_config_yaml: str,):
    config = open_yaml(fn_config_yaml)
    ECSClusterName = config["Parameters"]["ECSClusterName"]
    PestCaseName = config["Parameters"]["PestCaseName"]
    TaskDefinitionImage = config["Parameters"]["TaskDefinitionImage"]
    ContainerPortPestHP = config["Parameters"]["ContainerPortPestHP"]
    HostPortPestHP = config["Parameters"]["HostPortPestHP"]
    PestCaseName = config["Parameters"]["PestCaseName"]

    cf = AwsService.from_service('cloudformation')
    stack_resources = cf.client.describe_stack_resources(StackName="PestClusterInfrastructure")
    for resource in stack_resources['StackResources']:
        if resource['ResourceType'] == "AWS::EC2::Instance":
            ec2_arn = resource['PhysicalResourceId']

    ec2 = AwsService.from_service('ec2')
    public_ip = ec2.client.describe_instances(
        InstanceIds=[ec2_arn]
    )["Reservations"][0]["Instances"][0]["PublicIpAddress"]
    print(f"Public IP: {public_ip}")
    print(f"creating docker context with name {PestCaseName}")
    docker_ctxt = create_docker_context(PestCaseName,
                                        host=public_ip)
    register_instance(PestCaseName, public_ip)

    repo_tag = TaskDefinitionImage.split('/')[-1]
    repo, tag = repo_tag.split(":")
    print("To initiate the main task and interact with the PEST HP Cluster open a terminal and:")
    print(f"1. $> edamame generate-makefile --image-name {repo} --repo-name {repo}")
    print(f"2. $> docker context use {PestCaseName}")
    print(f"3. $> make TAG={tag} pull_aws")
    print(f"4. $> docker run -d -v /home/ubuntu/efs:/home/eki/efs "
          f"-p {ContainerPortPestHP}:{HostPortPestHP} {repo}:{tag} pest_hp {PestCaseName} /h :{HostPortPestHP}")






def update_number_agents(fn_config_yaml: str,
                         desired_number_agents: int):

    config = open_yaml(fn_config_yaml)
    ECSClusterName = config["Parameters"]["ECSClusterName"]

    ecs = AwsService.from_service('ecs')
    service_arns = ecs.client.list_services(cluster="PestCluster")["serviceArns"]

    resp = ecs.client.update_service(
        cluster=ECSClusterName,
        service=service_arns[0],
        desiredCount=desired_number_agents)

    return resp

def terminate_cluster():
    cf = AwsService.from_service('cloudformation')
    ecs = AwsService.from_service('ecs')

    ecs.client.update_service(
        cluster='PestCluster',
        service='agent_private_net',
        desiredCount=0)

    res = cf.client.delete_stack(StackName='PestClusterInfrastructure')

    return res




