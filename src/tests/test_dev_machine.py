import os
import pytest
import boto3
import yaml
import json

from moto import mock_aws

from eki_dev.dev_machine import (
    AwsService,
    create_ec2_instance,
    list_instances,
    _get_lst_instances,
    terminate_instance,
list_docker_context,
inspect_docker_context
)


@pytest.fixture(scope="function")
def aws_credentials():
    """
    Fixture to set AWS credentials for testing purposes.

    Args:
        None

    Returns:
        None
    """

    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_ID"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-west-2"


@pytest.fixture(scope="function")
def ec2_config():
    """
    Fixture to provide EC2 configuration data for testing purposes.

    Args:
        None

    Returns:
        JSON string representing the EC2 configuration data.
    """
    # with open('./dev_machine/default_conf.yaml', 'r') as f:
    #   conf = yaml.load(f, Loader=yaml.FullLoader)
    conf = """
  Ec2Instance:
    Type: AWS::EC2::Instance
    Properties:
      ImageId: ami-123456"
      KeyName: test_key
      InstanceType:  t2.micro.test
  """
    return json.dumps(yaml.safe_load(conf))


@mock_aws
def test_aws_service(aws_credentials):

    service = AwsService.from_service("ec2")
    assert service.resource.meta.service_name == "ec2"
    assert service.client.meta.service_model.service_name == "ec2"
    assert service.client.meta.region_name == "us-west-2"
    assert service.resource.meta.client.meta.region_name == "us-west-2"


## Tests construction with us-east-1 if default region env variable not set
@mock_aws
def test_aws_service_no_env(aws_credentials):
    os.environ.pop("AWS_DEFAULT_REGION")
    service = AwsService.from_service("ec2")
    assert service.resource.meta.service_name == "ec2"
    assert service.client.meta.service_model.service_name == "ec2"
    assert service.client.meta.region_name == "us-east-1"
    assert service.resource.meta.client.meta.region_name == "us-east-1"


@mock_aws
def test_create_ec2_instance(aws_credentials, ec2_config):
    instance = create_ec2_instance(
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    print(instance)
    assert instance is not None


@mock_aws
def test_list_instances(aws_credentials, ec2_config):

    instance = create_ec2_instance(
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    instance = create_ec2_instance(
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    instance = create_ec2_instance(
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    lst_inst = _get_lst_instances()
    list_instances()
    assert len(list(lst_inst.all())) == 3


@mock_aws
def test_terminate_instance(aws_credentials, ec2_config):

    instance = create_ec2_instance(
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    list_instances()
    terminate_instance(instance.id)
    lst_inst = _get_lst_instances()

    assert list(lst_inst.all())[0].state["Name"] == "terminated"


def test_list_docker_contexts(aws_credentials, ec2_config):
    ls_ctxt = list_docker_context()
    print(ls_ctxt)
    assert len(ls_ctxt) > 0


def test_inspect_context_not_found(aws_credentials, ec2_config):
    ctx = inspect_docker_context('name_not_found')
    assert ctx is None


def test_inspect_context_default(aws_credentials, ec2_config):
    ctx = inspect_docker_context('default')
    assert ctx['Name'] == 'default'
