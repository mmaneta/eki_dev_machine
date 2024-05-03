import os
import yaml
import boto3
from botocore.exceptions import ClientError
import docker


def create_docker_context(instance_name: str,
                          host: str,
                          port: int = 22,
                          user_name: str = 'ubuntu'):

    host = "ssh://"+user_name+"@"+host+f":{port}"
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


def ssh_splitter(ssh_connect_string):
    ssh_connect_string = ssh_connect_string.replace('ssh://', '')
    user_host, _, path = ssh_connect_string.partition(':')
    user, _, host = user_host.rpartition('@')
    return user, host, path


def find_context_name_from_instance_ip(ip: str) -> str:

    for ctx in list_docker_context():

        host = ctx.Host
        _, host_ip, _ = ssh_splitter(host)
        if host_ip == ip:
            return ctx.Name

    print("Could not find context name from ip")
    return None


class AwsService:
    """
    Initializes the AwsService object with the provided resource and client.

    Args:
        resource: The AWS resource to interact with.
        client: The AWS client to perform operations with.

    Returns:
        None
    """

    def __init__(self, session=None, resource=None, client=None):
        """
    Initializes the AwsService object with the provided resource and client.

    Args:
        resource: The AWS resource to interact with.
        client: The AWS client to perform operations with.

    Returns:
        None
        """
        self.session = session
        self.resource = resource
        self.client = client


    @classmethod
    def from_service(cls, service: str) -> "AwsService":
        """
        Creates an AwsService object for the specified AWS service.

        Args:
            service: The AWS service to interact with.

        Returns:
            An instance of AwsService initialized with the AWS resource and client for the specified service.

        Raises:
            ClientError: If there is an error creating the AWS resource or client for the service.
        """

        session = boto3.session.Session()
        region = session.region_name
        #region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        try:
            cls_res = boto3.resource(service, region_name=region)
            cls_client = boto3.client(service, region_name=region)
            return cls(session, cls_res, cls_client)

        except ClientError as err:
            print(
                "Could not create the requested service: %s %s",
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise


def create_ec2_instance(name: str,
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
        print(docker_ctxt)
        
    except ClientError as err:
        print(
            "Couldn't create instance with image , instance type , and key . "
            "Here's why: %s: %s",
            # instaimage.id,
            # instance_type,
            # key_pair.name,
            err.response["Error"]["Code"],
            err.response["Error"]["Message"],
        )
        raise
    else:
        _display(instance)
        return instance


def list_instances(indent=1):
    """
    Displays information about all running instances.

    :param indent: The visual indent to apply to the output.
    """

    lst_instances = _get_lst_instances()

    if lst_instances is None:
        print("No instance to display.")
        return

    for i, instance in enumerate(lst_instances.iterator()):
        instance.load()
        print(f"Instance number {i}:")
        _display(instance, indent=indent)


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
        raise


def terminate_instance(instance_id: str = None) -> None:
    """
    Terminates an instance and waits for it to be in a terminated state.
    """

    filters = [{"Name": "instance-state-name", "Values": ["running"]}]

    if instance_id is not None:
        try:
            lst_instances = _get_lst_instances()
            instances = lst_instances.filter(Filters=filters)
            for inst in instances:
                if inst.id == instance_id:
                    print(f"Found running instance {instance_id}")
                    instance = inst

        except ClientError as err:
            print(
                "Couldn't load instance %s. Here's why: %s: %s",
                instance_id,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise

    if instances is None:
        print("No instance to terminate.")
        return

    instance_id = instance.id
    try:
        print(f"Terminating instance {instance_id}...")
        ip = instance.public_ip_address
        ctx_name = find_context_name_from_instance_ip(ip)
        instance.terminate()


        print(f"Context associated with instance {instance_id} found. Removing context")
        if ctx_name is not None:
            remove_docker_context(ctx_name)

        instance.wait_until_terminated(instance_id)
        instance = None
        print(f"Instance {instance_id} successfully terminated.")
    except ClientError as err:
        print(
            "Couldn't terminate instance %s. Here's why: %s: %s",
            instance_id,
            err.response["Error"]["Code"],
            err.response["Error"]["Message"],
        )
        raise
    