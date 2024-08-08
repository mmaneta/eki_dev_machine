import os
import time
import re

from botocore.exceptions import ClientError
import docker

from rich.progress import Progress

from eki_dev.aws_service import AwsService

from eki_dev.docker_utils import (
    create_docker_context,
    remove_docker_context,
    _check_docker_installed,
    find_context_name_from_instance_ip,
    check_docker_context_does_not_exist,
    login_into_ecr,
    wait_for_token
)

from eki_dev.utils import (
    show_progress,
    ssh_tunnel,
    register_instance,
    deregister_instance,
    add_instance_tags,
    get_project_tags
)


def create_ec2_instance(name: str,
                        project_tag: str,
                        **instance_params):
    """
    Creates a new EC2 instance based on the provided instance parameters.

    Args:
        **instance_params: Parameters for creating the EC2 instance.

    Returns:
        The newly created EC2 instance.

    Raises:
        ClientError: If instance creation fails.
    """

    instance = None
    lst_tags = get_project_tags()
    if project_tag in lst_tags:
        instance_params = add_instance_tags(project_tag, **instance_params)
    else:
        print(f"tag {project_tag} must be one of {lst_tags}")
        raise Exception(f"tag {project_tag} must be one of {lst_tags}")

    try:
        check_docker_context_does_not_exist(name)
    except docker.errors.ContextAlreadyExists as e:
        print(f"Context {name} already exists")
        raise

    try:
        res = AwsService.from_service("ec2")

        instype = instance_params["InstanceType"]
        keyname = instance_params["KeyName"]
        region = res.client.meta.region_name
        print(f"Attempting to create {instype} instance in region {region}")
        print(f"Creating using {keyname} key")

        instance = res.resource.create_instances(
            **instance_params, MinCount=1, MaxCount=1
        )[0]
        instance.wait_until_running()

        instance.reload() # required to update public ip address

        host_ip = instance.public_ip_address
        print(f"public ip {host_ip} assigned. Creating Docker context now")
        docker_ctxt = create_docker_context(name,
                                                host=host_ip)

    except (ClientError, Exception, KeyboardInterrupt) as e:
        print("Error creating or provisioning the instance request. Here is why:")
        print(e)
        if (instance is not None) & (instance.state not in ["shutting-down", "terminated"]):
            print(f"instance {instance.id} was created and in state {instance.state}")
            print("Terminating instance")
            terminate_instance(instance.id)
            raise

    else:
        _display(instance)
        register_instance(name, host_ip)
        return instance


def _run_jupyter_notebook(account_id: str,
                          container_name: str,
                          host_ip: str,
                          jupyter_port: int,
                          dask_port: int,
                          user: str = "ubuntu",
                          region: str = "us-west-1", ):
    REGION=region
    ACCOUNT=account_id
    registry = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com"
    c_name, c_tag = container_name.split(':')
    container_full_name = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{c_name}"
    host = host_ip
    os.environ["DOCKER_HOST"] = f"ssh://{user}@{host}"

    while not _check_docker_installed(user, host):
        pass

    docker_client = login_into_ecr(registry)

    tasks = {}
    with Progress(refresh_per_second=500, transient=True) as progress:

        resp = docker_client.api.pull(repository=f"{container_full_name}", tag=c_tag, stream=True, decode=True)
        for line in resp:
            show_progress(line, progress, tasks)

    print("Running container with Jupyter notebook...")
    c_full_name = ":".join([container_full_name, c_tag])
    c = docker_client.containers.run(image=f"{c_full_name}",
                                 command=f"jupyter-lab --port {jupyter_port} --no-browser --ip=0.0.0.0 --allow-root",
                                 user=0,
                                 #auto_remove=True,
                                 detach=True,
                                 volumes=['/home/ubuntu/efs:/home/eki/efs'],
                                 ports={jupyter_port: jupyter_port, dask_port: dask_port},
                                 )

    token = wait_for_token(c)

    if token:
        jupyter_url = f"http://localhost:{jupyter_port}"
        jupyter_lab_url = f"{jupyter_url}/?token={token}"

        print(f"\tJupyterLab is running at: {jupyter_lab_url}")
        print(f"\tToken: {token}")
    else:
        print("Timeout: Failed to find token in container logs.")
        raise Exception("Timeout: Failed to find token in container logs.")


def create_instance_pull_start_server(name: str,
                                      project_tag: str,
                                      jupyter_port: int = 8888,
                                      dask_port: int = 8889,
                                      container: str = "data_explorer:prod",
                                      **instance_params):

    try:
        check_docker_context_does_not_exist(name)
    except docker.errors.ContextAlreadyExists as e:
        print(f"Context {name} already exists")
        raise

    instance_params["IamInstanceProfile"] = {"Name": "AccessECR"}


    try:
        i = create_ec2_instance(name=name,
                                project_tag=project_tag,
                                **instance_params)
    except Exception as e:
        print(e)
        raise

    print("PROVISIONING INSTANCE WITH REQUIRED SERVICES...")
    aws_account = AwsService.from_service('ec2').get_account_id()
    aws_region = AwsService.from_service('ec2').get_region()
    user = "ubuntu"
    host = i.public_ip_address
    _run_jupyter_notebook(aws_account,
                          container_name=container,
                          host_ip=host,
                          jupyter_port=jupyter_port,
                          dask_port=dask_port,
                          region=aws_region)

    del os.environ["DOCKER_HOST"]

    try:
        tunnel_cmd = ssh_tunnel(user=user,
                   host=host,
                   jupyter_port=jupyter_port,
                   dask_port=dask_port)
    except ConnectionError as e:
        print(e)
        pass

    print(f"To reconnect to jupyter server use the following command:\n")
    print(f"\t\t {tunnel_cmd}")
    return i


def clean_dangling_contexts(CONFIG_DIR='.dev_machine') -> []:

    print("CLEANING DANGLING CONTEXTS...")
    lst_cleaned_contexts = []
    lst_instances = _get_lst_instances()
    lst_ips = []
    for instance in lst_instances.iterator():
        lst_ips.append(instance.public_ip_address)

    HOME = os.path.expanduser("~")
    for root, dirs, files in os.walk(os.path.join(HOME, CONFIG_DIR)):
        for file in files:
            try:
                name, ip = file.split("@")
            except ValueError:
                continue
            if ip not in lst_ips:
                try:
                    remove_docker_context(name)
                except Exception as e:
                    pass

                try:
                    os.remove(os.path.join(root, file))
                except Exception as e:
                    pass
                lst_cleaned_contexts.append(name)

    return lst_cleaned_contexts


def list_instances(indent=1):
    """
    Displays information about all running instances. Returns a list of instances

    :param indent: The visual indent to apply to the output.
    """

    lst_instances = _get_lst_instances()

    if lst_instances is None:
        print("No instance to display.")
        return

    lst_instances = [i for i in lst_instances.iterator()]

    for i, instance in enumerate(lst_instances):
        instance.load()
        print(f"Instance number {i}:")
        _display(instance, indent=indent)

    return lst_instances


def _get_lst_instances():
    try:
        svc = AwsService.from_service("ec2")
        lst_instances = svc.resource.instances
    except ClientError as err:
        print(err.response["Error"]["Code"], err.response["Error"]["Message"])
        raise
    return lst_instances


def _display(instance, indent=1):
    """Display information about instance"""
    if instance is None:
        print("No instances to display.")
        return

    try:
        ind = "\t" * indent
        print(f"{ind}ID: {instance.id}")
        print(f"{ind}Image ID: {instance.image_id}")
        print(f"{ind}Instance type: {instance.instance_type}")
        print(f"{ind}Key name: {instance.key_name}")
        print(f"{ind}VPC ID: {instance.vpc_id}")
        print(f"{ind}Public IP: {instance.public_ip_address}")
        print(f"{ind}State: {instance.state['Name']}")
    except ClientError as err:
        print(
            "Couldn't display your instance. Here's why: %s: %s",
            err.response["Error"]["Code"],
            err.response["Error"]["Message"],
        )
        raise err


def terminate_instance(instance_id: str = None) -> None:
    """
    Terminates an instance and waits for it to be in a terminated state.
    """

    filters = [{"Name": "instance-state-name", "Values": ["running"]}]

    if instance_id is None:
        return
    else:
        try:
            lst_instances = _get_lst_instances()
            instances = lst_instances.filter(Filters=filters)
            if instances is None:
                print("No instance to terminate.")
                return
            for inst in instances:
                if inst.id == instance_id:
                    print(f"Found running instance {instance_id}")
                    instance = inst
                    instance_id = instance.id
                    _remove_instance(instance_id, instance)
                    return
            print(f"Instance {instance_id} not found. Instance not terminated.")
            return

        except ClientError as err:
            print(
                "Couldn't load instance %s. Here's why: %s: %s",
                instance_id,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            return


def _remove_instance(instance_id, instance):
    try:
        print(f"Terminating instance {instance_id}...")
        ip = instance.public_ip_address
        ctx_name = find_context_name_from_instance_ip(ip)
        instance.terminate()

        print(f"Context associated with instance {instance_id} found. Removing context")
        if ctx_name is not None:
            remove_docker_context(ctx_name)

        #instance.wait_until_terminated(instance_id)
        instance = None
        deregister_instance(ctx_name, ip)
        print(f"Instance {instance_id} successfully terminated.")
    except ClientError as err:
        raise err
    