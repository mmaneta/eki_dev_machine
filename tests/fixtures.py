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


@pytest.fixture
def aws_net(aws_credentials):
    with mock_aws():
        vpc = AwsService.from_service('ec2').client.create_vpc(CidrBlock='10.0.0.0/16')
        subnet = AwsService.from_service('ec2').client.create_subnet(
            VpcId=vpc['Vpc']['VpcId'],
            CidrBlock='10.0.0.0/16'
        )
        return subnet

@pytest.fixture(scope="function")
def aws_s3(aws_credentials):
    with mock_aws():
        yield boto3.client("s3", region_name="us-east-1")


@pytest.fixture#(scope="function")
def create_test_bucket(aws_s3):
    aws_s3.create_bucket(Bucket="eki-dev-machine-config")


@pytest.fixture
def create_aws_batch():
    with mock_aws():
        yield boto3.client("batch", region_name="us-east-1")


@pytest.fixture#(scope="function")
def bucket_with_project_tags(aws_s3, create_test_bucket):
    boto3.client("s3").put_object(Bucket="eki-dev-machine-config",
                                  Body=b"dev:\n"
                                       b"   description:\n"
                                       b"       default project\n"
                                       b"   efs:\n"
                                       b"       fs-034c06bfe2c81394b.efs.us-west-1.amazonaws.com\n"
                                       b"   s3bucket:\n"
                                       b"       s3://eki-dev\n"
                                       b"eki_training:\n"
                                       b"   description:\n"
                                       b"       tag for training\n"
                                       b"   efs:\n"
                                       b"       fs-01234567890123456.efs.us-west-1.amazonaws.com\n"
                                       b"   s3bucket:\n"
                                       b"    s3://eki-training\n"
                                       b"test_project:\n"
                                       b"  description:\n"
                                       b"    another test project\n"
                                       b"  efs:\n"
                                       b"    fs-09876543212456677.efs.us-west-1.amazonaws.com\n"
                                       b"  s3bucket:\n"
                                       b"    s3://eki-test-project"
                                  ,
                                  Key="project_tags_v2.txt"
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
      UserData: |-
          #!/bin/sh
          sudo apt-get update -y
          sudo apt-get -y install docker.io
          sudo service docker start
          sudo usermod -a -G docker ubuntu
          sudo apt-get -y install nfs-common nfs-kernel-server awscli
          sudo systemctl start nfs-kernel-server.service
          sudo mkdir /home/ubuntu/efs
          sudo mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport {}:/ /home/ubuntu/efs
      """
    return json.dumps(yaml.safe_load(conf))


@pytest.fixture(scope="function")
@mock_aws()
def iam_role(aws_credentials):

    iam = boto3.client("iam")
    instance_prof = iam.create_instance_profile(InstanceProfileName="AccessECR")

    return instance_prof


@pytest.fixture#(scope="function")
@mock_aws
def iam_batch_role():

    iam = boto3.client("iam")
    instance_prof = iam.create_role(
        RoleName="AWSBatchServiceRole",
        AssumeRolePolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "batch.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }
                ]
            }
        )
    )

    return instance_prof


# @mock_aws
# def test_aws_service(aws_credentials):
#     service = AwsService.from_service("ec2")
#     assert service.resource.meta.service_name == "ec2"
#     assert service.client.meta.service_model.service_name == "ec2"
#     assert service.client.meta.region_name == "us-west-2"
#     assert service.resource.meta.client.meta.region_name == "us-west-2"
#     assert service.get_region() == "us-west-2"


@pytest.fixture(scope="function")
def docker_registry():
    return "123456.dkr.ecr.us-west-1.amazonaws.com"


@pytest.fixture(scope="function")
def stack_resources_status_response(stack_name, scope="function"):
    with open('test_cf_tplt.yaml') as f:
        cf_tpl = yaml.safe_load(f.read())
    cf = boto3.client("cloudformation")
    response = cf.create_stack(
        StackName=stack_name,
        TemplateBody=json.dumps(cf_tpl),
    )
    return response

