import pytest
import docker
from moto import mock_aws

from eki_dev.docker_utils import (
    list_docker_context,
    inspect_docker_context,
    remove_docker_context,
    check_docker_context_does_not_exist,
    find_context_name_from_instance_ip,
    _check_docker_installed,
    login_into_ecr,
    list_host_ip_for_all_contexts
)

from fixtures import (
    aws_credentials,
    ec2_config,
    docker_registry
)


@pytest.fixture(scope="function")
def docker_context() -> docker.Context:
    yield docker.ContextAPI.create_context(name='test_context',
                                           orchestrator='docker',
                                           host='ssh://test_user@1.2.3.4:22')
    try:
        docker.ContextAPI.remove_context('test_context')
    except docker.errors.ContextNotFound:
        pass


@mock_aws
def test_login_into_ecr(docker_registry, mocker):
    m = mocker.patch.object(docker.DockerClient, "login")
    ecr_client = login_into_ecr(docker_registry)
    assert ecr_client is not None


@pytest.mark.parametrize("name, expected", [("default", "default")])
def test_check_docker_context_exists(name, expected):
    with pytest.raises(docker.errors.ContextAlreadyExists) as e:
        check_docker_context_does_not_exist(name)

    assert e.value.name == expected


def test_check_docker_context_not_exists():
    assert check_docker_context_does_not_exist("non_existent_context")


def test__check_docker_installed(mocker,):
    m = mocker.patch('subprocess.Popen')
    m.return_value.communicate.side_effect = [(" ", "command not found"), ("docker v23.test", "127")]


    user = 'ubuntu'
    host = '10.10.10.10'
    m.return_value.returncode = 10
    assert _check_docker_installed(user, host) == False
    m.return_value.returncode = 0
    assert _check_docker_installed(user, host) == True


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


def test_list_host_ip_for_all_contexts():
    lst = list_host_ip_for_all_contexts()
    assert isinstance(lst, list)