import os.path

import boto3
from botocore.stub import Stubber
import json
import yaml

import pytest
from moto import mock_aws

from aws_cluster.cluster_utils import check_resource_creation_status

from fixtures import (stack_resources_status_response)
from aws_cluster import pest_cluster


@mock_aws
@pytest.mark.parametrize("fn", ["parameters.yaml","s3://scratch-marco/parameters.yaml"])
def test_create_pest_cluster_stack(fn):
    fn = "parameters.yaml"
    response = pest_cluster.create_pest_cluster_stack(fn_config_yaml=fn,
                                           cf_template = 'test_cf_tplt.yaml')
    assert response["StackId"] is not None


@mock_aws
def test_create_pest_cluster_stack_2():
    with open('test_cf_tplt.yaml') as f:
        cf_tpl = yaml.safe_load(f.read())
    cf = boto3.client("cloudformation")
    response = cf.create_stack(
        StackName="test_stack",
        TemplateBody=json.dumps(cf_tpl),
    )
    assert response["StackId"] is not None


@mock_aws
def test_check_resource_creation_status(mocker):
    with open('test_cf_tplt.yaml') as f:
        cf_tpl = yaml.safe_load(f.read())
    cf = boto3.client("cloudformation")
    response = cf.create_stack(
        StackName="test_stack",
        TemplateBody=json.dumps(cf_tpl),
    )
    df = check_resource_creation_status("test_stack")
    # Check if the styling is applied correctly
    assert df.to_string().render().find('background-color: green') ==  1


