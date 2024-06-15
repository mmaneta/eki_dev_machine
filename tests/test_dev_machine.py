import contextlib
import os
import pytest
import boto3
import yaml
import json
import docker
from docker import Context
from moto import mock_aws

from eki_dev.dev_machine import (
    AwsService,
    create_ec2_instance,
    list_instances,
    _get_lst_instances,
    terminate_instance,
    list_docker_context,
    inspect_docker_context,
    remove_docker_context,
    check_docker_context_does_not_exist,
    ssh_splitter,
    find_context_name_from_instance_ip,
    _check_docker_installed,
    create_instance_pull_start_server,
    _run_jupyter_notebook,
    ssh_tunnel,
    login_into_ecr
)

def test_login_into_ecr():
    login_into_ecr()


def test_ssh_splitter_with_ssh():
    assert list(ssh_splitter('ssh://test_user@1.0.1.1:22')) == ['test_user', '1.0.1.1', '22']


def test_ssh_splitter_without_ssh():
    assert list(ssh_splitter('test_user@1.0.1.1:22')) == ['test_user', '1.0.1.1', '22']


def test_ssh_splitter_without_user():
    assert list(ssh_splitter('ssh://1.0.1.1:22')) == ['', '1.0.1.1', '22']


def test_ssh_splitter_without_port():
    assert list(ssh_splitter('ssh://1.0.1.1')) == ['', '1.0.1.1', '']


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


@pytest.fixture(scope="function")
def docker_context() -> Context:
    yield docker.ContextAPI.create_context(name='test_context',
                                           orchestrator='docker',
                                           host='ssh://test_user@1.2.3.4:22')
    try:
        docker.ContextAPI.remove_context('test_context')
    except docker.errors.ContextNotFound:
        pass

@pytest.mark.parametrize("name, expected", [("default", "default")])
def test_check_docker_context_exists(name, expected):
    with pytest.raises(docker.errors.ContextAlreadyExists) as e:
        check_docker_context_does_not_exist(name)

    assert e.value.name == expected


def test_check_docker_context_not_exists():
    assert check_docker_context_does_not_exist("non_existent_context")


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


# @pytest.mark.parametrize("clean_docker_context", "test_instance")
@mock_aws
def test_create_ec2_instance(aws_credentials, ec2_config):
    instance = create_ec2_instance(name='test_instance',
                                   **json.loads(ec2_config)["Ec2Instance"]["Properties"]
                                   )
    docker.ContextAPI.remove_context('test_instance')

    assert instance is not None


@mock_aws
def test_create_ec2_instance_role(aws_credentials, ec2_config):

    iam = boto3.client("iam")
    instance_prof = iam.create_instance_profile(InstanceProfileName="EC2ECRAccess")

    conf = json.loads(ec2_config)["Ec2Instance"]["Properties"]
    conf["IamInstanceProfile"] = {"Name": "EC2ECRAccess"}
    instance = create_ec2_instance(name='test_instance',
                                   **conf
                                   )
    docker.ContextAPI.remove_context('test_instance')

    assert instance.iam_instance_profile["Arn"] == instance_prof["InstanceProfile"]["Arn"]


def test__check_docker_installed(mocker,):
    m = mocker.patch('subprocess.Popen')
    m.return_value.communicate.side_effect = [(" ", "command not found"), ("docker v23.test", "127")]


    user = 'ubuntu'
    host = '10.10.10.10'
    m.return_value.returncode = 10
    assert _check_docker_installed(user, host) == False
    m.return_value.returncode = 0
    assert _check_docker_installed(user, host) == True


@mock_aws()
def test__run_jupyter_notebook(aws_credentials, ec2_config, mocker):
    m = mocker.patch('subprocess.Popen')
    m.return_value.communicate.side_effect = [(" ", "command not found"), ("docker v23.test", "127")]

    instance = create_ec2_instance(name='test_instance',
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


def test_ssh_tunnel_connection_error():

    with pytest.raises(ConnectionError) as e:
        ssh_tunnel(user='test_user',
               host='10.10.10.10',
               jupyter_port=8888,
               dask_port=8889)

    assert "Connection refused" in str(e.value.args[0])


@mock_aws()
def test_create_instance_pull_start_server(aws_credentials, ec2_config, mocker):


    m = mocker.patch('subprocess.Popen')
    m.return_value.communicate.return_value = ("docker v23.test", "127")
    m.return_value.returncode = 0

    mrun = mocker.patch('subprocess.run')
    mrun.return_value.returncode = 0

    iam = boto3.client("iam")
    conf = json.loads(ec2_config)["Ec2Instance"]["Properties"]
    instance_prof = iam.create_instance_profile(InstanceProfileName="AccessECR")
    name = "test_instance"
    instance = create_instance_pull_start_server(name, **conf)

    docker.ContextAPI.remove_context('test_instance')


@mock_aws
def test_list_instances(aws_credentials, ec2_config):
    instance = create_ec2_instance(
        name='test_instance_1',
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    instance = create_ec2_instance(
        name='test_instance_2',
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    instance = create_ec2_instance(
        name='test_instance_3',
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    lst_inst = _get_lst_instances()
    list_instances()
    assert len(list(lst_inst.all())) == 3

    for instance in list(lst_inst.all()):
        terminate_instance(instance.id)


@mock_aws
def test_terminate_instance(aws_credentials, ec2_config):
    instance = create_ec2_instance(
        name='test_instance',
        **json.loads(ec2_config)["Ec2Instance"]["Properties"]
    )
    list_instances()
    terminate_instance(instance.id)
    lst_inst = _get_lst_instances()

    assert list(lst_inst.all())[0].state["Name"] == "terminated"


def test_list_docker_contexts(aws_credentials, ec2_config):
    ls_ctxt = list_docker_context()
    assert len(ls_ctxt) > 0


def test_inspect_context_not_found(aws_credentials, ec2_config):
    ctx = inspect_docker_context('name_not_found')
    assert ctx is None


def test_inspect_context_default(aws_credentials, ec2_config):
    ctx = inspect_docker_context('default')
    assert ctx['Name'] == 'default'


def test_remove_docker_context_not_found(aws_credentials, ec2_config, docker_context):
    try:
        ctx = remove_docker_context('name_not_found')
        assert ctx is not None
    except:
        assert False


def test_remove_docker_context_default(aws_credentials,
                                       ec2_config,
                                       docker_context):
    ctx = inspect_docker_context('test_context')
    assert ctx['Name'] == 'test_context'
    ctx = remove_docker_context('test_context')
    assert all([c.Name != 'test_context' for c in ctx])


def test_find_context_name_from_instance_ip(docker_context):
    name = find_context_name_from_instance_ip('1.2.3.4')
    assert name == 'test_context'
