import os
import time
import subprocess
import boto3
from botocore.exceptions import ClientError
import docker
from rich.progress import Progress


# Show task progress (red for download, green for extract)
def show_progress(line, progress):
    tasks = {}

    if line['status'] == 'Downloading':
        id = f'[red][Download {line["id"]}]'
    elif line['status'] == 'Extracting':
        id = f'[green][Extract  {line["id"]}]'
    else:
        # skip other statuses
        return

    if id not in tasks.keys():
        tasks[id] = progress.add_task(f"{id}", total=line['progressDetail']['total'])
    else:
        progress.update(tasks[id], completed=line['progressDetail']['current'])

def configure(CONFIG_DIR='.dev_machine',
              CONFIG_FILE='dev_machine.config'):
    HOME=os.path.expanduser("~")
    config_path = os.path.join(HOME, CONFIG_DIR, CONFIG_FILE)
    with open(config_path, 'w') as f:
        input("")
        f.writelines()


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


def check_docker_context_does_not_exist(name: str) -> bool:
    """Returns True if context with `name` does not exist, otherwise raise
    docker.error.ContextAlreadyExists exception."""

    for ctx in list_docker_context():
        if ctx.name == name:
            raise docker.errors.ContextAlreadyExists(name)

    return True



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
        self.region = self.session.region_name
        self.account_id = self.session.client('sts').get_caller_identity().get('Account')
        ecr_auth = self.session.client('ecr').get_authorization_token()
        self.ecr_pass = ecr_auth.get("authorizationData")[0].get('authorizationToken')


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

    def get_region(self) -> str:
        """
        Just what the method name says
        """
        return self.region

    def get_account_id(self) -> str:
        """
        returns a string with aws account id
        """
        return self.account_id

    def get_ecr_authorization(self) -> str:
        """returns an authorization token for ECR"""
        return self.ecr_pass


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


def ssh_tunnel(user: str,
               host: str,
               jupyter_port: int,
               dask_port: int,
               ):
    tunnel_cmd = f"ssh -f -N -L {jupyter_port}:localhost:{jupyter_port} -L {dask_port}:localhost:{dask_port} {user}@{host}"
    proc = subprocess.Popen(tunnel_cmd, shell=True, stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE, executable="/bin/bash")
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise ConnectionError(stderr)
    return tunnel_cmd


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


def login_into_ecr(registry):
    password = AwsService.from_service('ec2').get_ecr_authorization()
    docker_client = docker.from_env()
    docker_client.login(username='AWS', password=password, reauth=True)


def _run_jupyter_notebook(account_id: str,
                          container_name: str,
                          host_ip: str,
                          jupyter_port: int,
                          dask_port: int,
                          user: str = "ubuntu",
                          region: str = "us-west-1", ):
    REGION=region
    ACCOUNT=account_id
    container_full_name = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{container_name}"
    host = host_ip
    os.environ["DOCKER_HOST"] = f"ssh://{user}@{host}"

    while not _check_docker_installed(user, host):
        pass

    docker_client = docker.from_env()
    # res = docker_client.login(username = "AWS",
    #                     password = f"$(aws ecr get-login-password --region {REGION})",
    #                     registry = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com")
    #print(res)
    login_cmd = (f"docker login --username AWS "
                 f"-p $(aws ecr get-login-password --region {REGION}) {ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com")
    proc = subprocess.run(login_cmd, shell=True)


    # pull_cmd = f"docker pull {container_full_name}"
    # for _ in range(5):
    #     print(f"Attempting to pull from registry...")
    #     proc = subprocess.run(pull_cmd.split())
    #     if proc.returncode == 0:
    #         break

    # run_cmd = (f"docker run --rm -v /home/ubuntu/efs:/home/eki/efs "
    #            f"-p{jupyter_port}:{jupyter_port} -p{dask_port}:{dask_port}"
    #            f" -u 0 {container_full_name} jupyter-lab --port {jupyter_port}"
    #            f" --no-browser --ip=0.0.0.0 --allow-root")
    # for _ in range(5):
    #     print(f"Attempting to start jupyter lab...")
    #     proc = subprocess.run(run_cmd, shell=True)
    #     if proc.returncode == 0:
    #         break

    with Progress() as progress:

        resp = docker_client.api.pull(repository=f"{container_full_name}"[:-4], tag="dev", stream=True, decode=True)
        for line in resp:
            show_progress(line, progress)


    docker_client.api.containers.exec(image=f"{container_full_name}",
                                 command=f"jupyter-lab --port {jupyter_port} --no-browser --ip=0.0.0.0 --allow-root",
                                 auto_remove=True,
                                 detach=True,
                                 volumes=['/home/ubuntu/efs:/home/eki/efs'],
                                 ports={jupyter_port: jupyter_port, dask_port: dask_port},
                                 )


def create_instance_pull_start_server(name: str,
                                      jupyter_port: int = 8888,
                                      dask_port: int = 8889,
                                      container: str = "eki:dev",
                                      **instance_params):

    try:
        check_docker_context_does_not_exist(name)
    except docker.errors.ContextAlreadyExists as e:
        print(f"Context {name} already exists")
        return -1

    instance_params["IamInstanceProfile"] = {"Name": "AccessECR"}


    try:
        i = create_ec2_instance(name=name, **instance_params)
    except:
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
    