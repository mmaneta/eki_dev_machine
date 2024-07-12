import base64

from eki_dev.utils import ssh_splitter
from eki_dev.aws_service import AwsService

import time
import re
import subprocess
import docker
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)


def login_into_ecr(registry):
    """returns an authenticated docker client for ECR"""
    print("Retrieving ECR credentials")
    token = AwsService.from_service('ecr').get_ecr_authorization()
    username, password = base64.b64decode(token).decode('utf-8').split(':')

    docker_client = None
    for i in range(500):
        print("Creating docker client for ECR, attempt {}".format(i+1))
        try:
            docker_client = docker.from_env()
            break

        except docker.errors.DockerException as e:
            time.sleep(2)
            continue
    if not docker_client:
        raise Exception("Unable to create docker client for ECR")



    print("Logging into {}".format(registry))
    registry = registry.replace("https://", "")
    for i in range(3):
        print("{} attempt to log into ECR".format(i+1))
        try:
            ret = docker_client.login(username='AWS', password=password, registry=registry, reauth=True)
            if ret['Status'] == 'Login Succeeded':
                logger.info("Login succeeded")
                break
            time.sleep(1)
        except docker.errors.APIError as e:
            print(e)
            logger.error(e)

    return docker_client


def create_docker_context(instance_name: str,
                          host: str,
                          port: int = 22,
                          user_name: str = 'ubuntu'):
    host = "ssh://" + user_name + "@" + host + f":{port}"
    print(f"Creating docker context for {host}")
    try:
        ret = docker.ContextAPI.create_context(name=instance_name,
                                               orchestrator='docker',
                                               host=host)
    except docker.errors.ContextAlreadyExists as err:
        print("Context name already exists")
        print(err)
        raise
    except docker.errors.ContextException as err:
        print(err)
        raise

    return ret


def list_docker_context() -> docker.Context:
    try:
        ls_ctxt = docker.ContextAPI.contexts()
    except docker.errors.APIError as err:
        print(err)
        raise

    return ls_ctxt


def inspect_docker_context(name: str) -> dict:
    try:
        return docker.ContextAPI.inspect_context(name)
    except docker.errors.ContextNotFound as err:
        print("Context with name {} does not exist".format(name))
        print(err)


def remove_docker_context(name: str) -> docker.Context:
    try:
        docker.ContextAPI.remove_context(name)
        print("Context with name {} removed".format(name))

    except docker.errors.ContextNotFound as err:
        print("Context with name {} does not exist".format(name))
        print(err)

    return list_docker_context()


def find_context_name_from_instance_ip(ip: str) -> str:

    for ctx in list_docker_context():

        host = ctx.Host
        _, host_ip, _ = ssh_splitter(host)
        if host_ip == ip:
            return ctx.Name

    print("Could not find context name from ip")
    return None


def list_host_ip_for_all_contexts() -> list:

    lst_ip = []
    for ctx in list_docker_context():
        host = ctx.Host
        _, host_ip, _ = ssh_splitter(host)
        lst_ip.append((ctx.Name,host_ip))
    return lst_ip


def check_docker_context_does_not_exist(name: str) -> bool:
    """Returns True if context with `name` does not exist, otherwise raise
    docker.error.ContextAlreadyExists exception."""

    for ctx in list_docker_context():
        if ctx.name == name:
            raise docker.errors.ContextAlreadyExists(name)

    return True


def _check_docker_installed(user: str, host: str):
    """
    Returns True if docker is installed. The function ssh into the host machine,
    calls docker --version, and parses stderr
    Args:
        user: Username to log into host
        host: IP address of host

    Returns: True if docker is installed in host machine, False otherwise.

    """

    ps = subprocess.Popen(f"ssh -o StrictHostKeyChecking=accept-new {user}@{host} docker --version",
                                           shell=True,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE)
    ps.wait()
    stdout, stderr = ps.communicate()
    if ps.returncode == 0:
        print(f"{str(stdout)} is running")
        return True
    else:
        print("Waiting for docker...")
        time.sleep(5)
        return False


def wait_for_token(container):
    max_attempts = 10  # Maximum number of attempts to check logs
    attempt = 0

    while attempt < max_attempts:
        logs = container.logs().decode('utf-8')
        match = re.search(r'\?token=([a-f0-9]+)', logs)

        if match:
            token = match.group(1)
            return token

        attempt += 1
        time.sleep(5)  # Wait for 1 second before checking logs again

    return None
