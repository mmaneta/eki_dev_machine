import pytest
from moto import mock_aws

import yaml

from fixtures import aws_s3, aws_credentials
from aws_cluster import eki_batch


@mock_aws
class TestEkiBatch:

    @pytest.fixture(autouse=True)
    def aws_bucket(self, aws_s3):
        aws_s3.create_bucket(Bucket="eki-dev-machine-config")
        aws_s3.upload_file("test_batch.yaml", "eki-dev-machine-config", "test_batch.yaml")

    @classmethod
    def setup_class(cls):
        pass

    @pytest.mark.parametrize("fn", ["test_batch.yaml", "s3://eki-dev-machine-config/test_batch.yaml"])
    def test_eki_batch(self, fn, aws_bucket):
        batch = eki_batch.EkiBatch(fn)
        batch.task_definition == "arn::test_task_def"

    def test__parse_command_line(self, aws_bucket):
        batch = eki_batch.EkiBatch("s3://eki-dev-machine-config/test_batch.yaml")

        batch._parse_command_line()

        ref_cmds = ['test_command test 1 a test_param1 bash', 'test_command test 1 b test_param1 bash',
         'test_command test 2 a test_param1 bash', 'test_command test 2 b test_param1 bash',
         'test_command test 3 a test_param1 bash', 'test_command test 3 b test_param1 bash']

        for cmd, ref in zip(batch.lst_parsed_cmds, ref_cmds):
            assert cmd == ref

    def test_print_command_list(self, aws_bucket):
        batch = eki_batch.EkiBatch("s3://eki-dev-machine-config/test_batch.yaml")
        batch.print_command_list()

    def test_submit_job(self, aws_bucket):
        batch = eki_batch.EkiBatch("s3://eki-dev-machine-config/test_batch.yaml")

        batch.submit_jobs()


