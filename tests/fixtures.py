import os
import pytest
import boto3
import json
import yaml

from moto import mock_aws

from eki_dev.aws_service import AwsService


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
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture(scope="function")
def aws_s3(aws_credentials):
    with mock_aws():
        yield boto3.client("s3", region_name="us-east-1")


@pytest.fixture#(scope="function")
def create_test_bucket(aws_s3):
    boto3.client("s3").create_bucket(Bucket="eki-dev-machine-config")


@pytest.fixture#(scope="function")
def bucket_with_project_tags(aws_s3, create_test_bucket):
    boto3.client("s3").put_object(Bucket="eki-dev-machine-config",
                                  Body=b'dev,eki_training,test_project',
                                  Key="project_tags.txt"
                                  )


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
      TagSpecifications:
        - ResourceType: instance
          Tags:
            - Key: user
              Value: ${aws:username}
  """
    return json.dumps(yaml.safe_load(conf))


@pytest.fixture(scope="function")
@mock_aws()
def iam_role(aws_credentials):

    iam = boto3.client("iam")
    instance_prof = iam.create_instance_profile(InstanceProfileName="EC2ECRAccess")

    return instance_prof


@mock_aws
def test_aws_service(aws_credentials):
    service = AwsService.from_service("ec2")
    assert service.resource.meta.service_name == "ec2"
    assert service.client.meta.service_model.service_name == "ec2"
    assert service.client.meta.region_name == "us-west-2"
    assert service.resource.meta.client.meta.region_name == "us-west-2"
    assert service.get_region() == "us-west-2"


@pytest.fixture(scope="function")
def docker_registry():
    return "123456.dkr.ecr.us-west-1.amazonaws.com"
