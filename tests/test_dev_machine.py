import os.path

import boto3
import json
import docker
from moto import mock_aws

from eki_dev.aws_service import AwsService


from eki_dev.dev_machine import (
    create_ec2_instance,
    list_instances,
    _get_lst_instances,
    terminate_instance,
    create_instance_pull_start_server,
    _run_jupyter_notebook,
    clean_dangling_contexts
)

from fixtures import (
    aws_credentials,
    ec2_config,
aws_s3,
create_test_bucket,
bucket_with_project_tags
)

from eki_dev.utils import register_instance, deregister_instance

# @pytest.mark.parametrize("clean_docker_context", "test_instance")
@mock_aws
def test_create_ec2_instance(aws_credentials, ec2_config,bucket_with_project_tags):
    instance = create_ec2_instance(name='test_instance',
                                   project_tag='dev',
                                   **json.loads(ec2_config)["Ec2Instance"]["Properties"]
                                   )
    try:
        docker.ContextAPI.remove_context('test_instance')
    except docker.errors.ContextNotFound:
        pass

    assert instance is not None


@mock_aws
def test_create_ec2_instance_role(aws_credentials, ec2_config,bucket_with_project_tags):

    iam = boto3.client("iam")
    instance_prof = iam.create_instance_profile(InstanceProfileName="EC2ECRAccess")

    conf = json.loads(ec2_config)["Ec2Instance"]["Properties"]
    conf["IamInstanceProfile"] = {"Name": "EC2ECRAccess"}
    instance = create_ec2_instance(name='test_instance',
                                   project_tag='test_project',
                                   **conf
                                   )
    docker.ContextAPI.remove_context('test_instance')

    assert instance.iam_instance_profile["Arn"] == instance_prof["InstanceProfile"]["Arn"]




@mock_aws
def test__run_jupyter_notebook(aws_credentials, ec2_config,bucket_with_project_tags, mocker):
    m = mocker.patch('subprocess.Popen')
    m.return_value.returncode = 0
    m.return_value.communicate.side_effect = [(" ", "command not found"), ("docker v23.test", "127")]

    instance = create_ec2_instance(name='test_instance',
                                   project_tag='dev',
                                   **json.loads(ec2_config)["Ec2Instance"]["Properties"]
                                   )
    account_id = AwsService.from_service('ec2').get_account_id()
    try:
        _run_jupyter_notebook(account_id=account_id,
                              container_name='eki:dev',
                              host_ip=instance.public_ip_address,
                              jupyter_port=8888,
                              dask_port=8889,
                              region=AwsService.from_service('ec2').get_region()
                              )
    except Exception as e:
        print(e)
        pass

    docker.ContextAPI.remove_context('test_instance')


@mock_aws()
def test_create_instance_pull_start_server(aws_credentials, ec2_config,bucket_with_project_tags, mocker):


    m = mocker.patch('subprocess.Popen')
    m.return_value.communicate.return_value = ("docker v23.test", "127")
    m.return_value.returncode = 0

    mrun = mocker.patch('subprocess.run')
    mrun.return_value.returncode = 0

    iam = boto3.client("iam")
    conf = json.loads(ec2_config)["Ec2Instance"]["Properties"]
    instance_prof = iam.create_instance_profile(InstanceProfileName="AccessECR")
    name = "test_instance"
    instance = create_instance_pull_start_server(name=name,
                                                 project_tag='test_project',
                                                 **conf)

    docker.ContextAPI.remove_context('test_instance')


@mock_aws
def test_list_instances(aws_credentials, ec2_config,bucket_with_project_tags):
    instance = create_ec2_instance(
        name='test_instance_1',
        project_tag='test_project',
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    instance = create_ec2_instance(
        name='test_instance_2',
        project_tag='test_project',
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    instance = create_ec2_instance(
        name='test_instance_3',
        project_tag='test_project',
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    lst_inst = _get_lst_instances()
    list_instances()
    assert len(list(lst_inst.all())) == 3

    for instance in list(lst_inst.all()):
        terminate_instance(instance.id)


@mock_aws
def test_clean_dangling_contexts_no_instances_running(aws_credentials, ec2_config):
    name = "test_instance"
    host_ip = "10.10.10.10"

    register_instance(name, host_ip)

    clean_context = clean_dangling_contexts()
    assert clean_context[0] == name

    deregister_instance(name, host_ip)


@mock_aws
def test_clean_dangling_contexts_instance_running(aws_credentials, ec2_config, mocker):

    class minst:
        public_ip_address = "10.10.10.11"

    m = mocker.patch("eki_dev.dev_machine._get_lst_instances")
    m.return_value.iterator.return_value = [minst]

    name = "test"
    host_ip = "10.10.10.10"

    register_instance(name, host_ip)

    r = clean_dangling_contexts()
    assert r[0] == "test"

    deregister_instance(name, host_ip)


def test_clean_dangling_contexts_instance_running_no_dangling_context(aws_credentials, ec2_config, mocker):

    class minst:
        public_ip_address = "10.10.10.10"

    m = mocker.patch("eki_dev.dev_machine._get_lst_instances")
    m.return_value.iterator.return_value= [minst]

    name = "test"
    host_ip = "10.10.10.10"

    register_instance(name, host_ip)

    r = clean_dangling_contexts()
    assert len(r) == 0

    deregister_instance(name, host_ip)


@mock_aws
def test_terminate_instance(aws_credentials, ec2_config,bucket_with_project_tags):
    clean_dangling_contexts()
    instance = create_ec2_instance(
        name='test_instance',
        project_tag='test_project',
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    list_instances()
    terminate_instance(instance.id)
    lst_inst = _get_lst_instances()

    assert list(lst_inst.all())[0].state["Name"] == "terminated"


@mock_aws
def test_terminate_instance_incorrect_id(aws_credentials, ec2_config,bucket_with_project_tags, capsys):
    clean_dangling_contexts()
    instance = create_ec2_instance(
        name='test_instance',
        project_tag='test_project',
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    list_instances()
    terminate_instance("incorrect_id")
    captured = capsys.readouterr().out.strip().split("\n")
    assert captured[-1] == "Instance incorrect_id not found. Instance not terminated."
    #Clean up
    lst_inst = _get_lst_instances()
    terminate_instance(instance.id)

    assert list(lst_inst.all())[0].state["Name"] == "terminated"

@mock_aws
def test_terminate_instance_instance_none(aws_credentials, ec2_config,bucket_with_project_tags):
    clean_dangling_contexts()
    assert terminate_instance() is None
