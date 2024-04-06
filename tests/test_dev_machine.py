import os
import pytest
import boto3
  
from moto import mock_ec2
from dev_machine.dev_machine import AwsResource

@pytest.fixture(scope='function')
def aws_credentials():
  os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
  os.environ['AWS_SECRET_ACCESS_ID'] = 'testing'
  os.environ['AWS_SECURITY_TOKEN'] = 'testing'
  os.environ['AWS_SESSION_TOKEN'] = 'testing'



@mock_ec2
class TestClassAwsResource:
    def test_init(self):
        
