import pytest
from moto import mock_aws

import boto3
import yaml

from fixtures import (aws_s3,
                      aws_credentials,
                      create_aws_batch,
                      iam_batch_role,
                      aws_net,
                      create_test_bucket,
                      bucket_with_project_tags#, aws_batch
                      )
from aws_cluster import eki_batch


@pytest.fixture
def aws_batch(aws_credentials, create_aws_batch, iam_batch_role):

    comp_env = create_aws_batch.create_compute_environment(
        computeEnvironmentName="test-compute-environment",
        type="UNMANAGED",
        serviceRole=iam_batch_role["Role"]["Arn"],
    )

    job_def = create_aws_batch.register_job_definition(
        jobDefinitionName="test_task_def",
        type="container",
        containerProperties={"image": "image_test",
                             "memory": 1024,
                             "vcpus": 2,},
    )
    job_queue = create_aws_batch.create_job_queue(
        jobQueueName="test_queue_arn",
        state="ENABLED",
        priority=1,
        computeEnvironmentOrder=[{"order": 1,
                                  "computeEnvironment": comp_env["computeEnvironmentArn"]}]
    )
    yield create_aws_batch


@mock_aws
class TestEkiBatch:

    @pytest.fixture(autouse=True)
    def aws_bucket(self, aws_s3):
        aws_s3.create_bucket(Bucket="eki-dev-machine-config")
        aws_s3.upload_file("test_batch.yaml", "eki-dev-machine-config", "test_batch.yaml")
        aws_s3.upload_file("a", "eki-dev-machine-config", "a")

    @classmethod
    def setup_class(cls):
        pass

    def test_allocate_ip(self, bucket_with_project_tags, aws_net, aws_batch):
        batch = eki_batch.EkiBatch("s3://eki-dev-machine-config/test_batch.yaml",
                                   route_table_id=aws_net[1]['RouteTable']['RouteTableId'])
        batch._allocate_elastic_ip()

        assert batch.eip['AllocationId'] is not None

    def test_create_nat(self, bucket_with_project_tags,aws_net, aws_batch):
        batch = eki_batch.EkiBatch("s3://eki-dev-machine-config/test_batch.yaml",
                                   route_table_id=aws_net[1]['RouteTable']['RouteTableId'])
        batch.create_nat_gateway(subnet_id=aws_net[0]['Subnet']['SubnetId'])

        assert batch.nat_gateway['NatGateway']['NatGatewayId'] is not None


    @pytest.mark.parametrize("fn", ["test_batch.yaml", "s3://eki-dev-machine-config/test_batch.yaml"])
    def test_eki_batch(self, fn, bucket_with_project_tags,aws_bucket, aws_net):
        batch = eki_batch.EkiBatch(fn,
                                   route_table_id=aws_net[1]['RouteTable']['RouteTableId'])
        assert batch.task_definition == "arn:aws:batch:us-east-1:123456789012:job-definition/test_task_def:1"

    def test__parse_command_line(self, bucket_with_project_tags,aws_net, aws_bucket):
        batch = eki_batch.EkiBatch("s3://eki-dev-machine-config/test_batch.yaml",
                                   route_table_id=aws_net[1]['RouteTable']['RouteTableId'])

        batch._parse_command_line()

        ref_cmds = ['test_command test 1 a test_param1 bash', 'test_command test 1 b test_param1 bash',
         'test_command test 2 a test_param1 bash', 'test_command test 2 b test_param1 bash',
         'test_command test 3 a test_param1 bash', 'test_command test 3 b test_param1 bash']

        for cmd, ref in zip(batch.lst_parsed_cmds, ref_cmds):
            assert cmd == ref

    def test_print_command_list(self, bucket_with_project_tags,aws_net, aws_bucket):
        batch = eki_batch.EkiBatch("s3://eki-dev-machine-config/test_batch.yaml",
                                   route_table_id=aws_net[1]['RouteTable']['RouteTableId'])
        batch.print_command_list()

    def test_submit_job(self, bucket_with_project_tags,aws_net, aws_bucket, aws_batch):
        batch = eki_batch.EkiBatch("s3://eki-dev-machine-config/test_batch.yaml",
                                   route_table_id=aws_net[1]['RouteTable']['RouteTableId'])

        job = batch.submit_jobs()

        assert job["jobId"] is not None



