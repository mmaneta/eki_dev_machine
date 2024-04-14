import os
import yaml
import boto3
from botocore.exceptions import ClientError
import docker


def create_docker_context(name: str,                          
                          host: str):
    try:
        docker.ContextAPI.create_context(name=name, host=host)
    except docker.errors.ContextAlreadyExists as err:
        print("Context name already exists")
        print(err)
        raise
    except docker.errors.ContextException as err:
        print(err)
        raise

class AwsService:
    """
    Initializes the AwsService object with the provided resource and client.

    Args:
        resource: The AWS resource to interact with.
        client: The AWS client to perform operations with.

    Returns:
        None
    """

    def __init__(self, resource=None, client=None):
        """
    Initializes the AwsService object with the provided resource and client.

    Args:
        resource: The AWS resource to interact with.
        client: The AWS client to perform operations with.

    Returns:
        None
        """
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

        region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

        try:
            cls_res = boto3.resource(service, region_name=region)
            cls_client = boto3.client(service, region_name=region)
            return cls(cls_res, cls_client)

        except ClientError as err:
            print(
                "Could not create the requested service: %s %s",
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise


def create_ec2_instance(**instance_params):
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
        instype = instance_params["InstanceType"]
        keyname = instance_params["KeyName"]
        print(f"Attempting to create {instype} instance")
        print(f"Creating using {keyname} key")

        res = AwsService.from_service("ec2")

        instance = res.resource.create_instances(
            **instance_params, MinCount=1, MaxCount=1
        )[0]
        instance.wait_until_running()
        
        ctxt = create_docker_context()
        
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
        instance.terminate()
        instance.wait_until_terminated()
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


# class AwsResource:
#     def __init__(self, resource, instance=None) -> None:

#         self.res = resource
#         self.instance = instance
#         self.lst_instances = self.res.instances

#     @classmethod
#     def from_resource(cls, res: str='ec2'):
#         ec2_res = boto3.resource(res)
#         return cls(ec2_res)

#     def create_resource(self, **instance_params):
#         """
#         Creates a new EC2 instance. The instance starts immediately after
#         it is created.

#         :return: A Boto3 Instance object that represents the newly created instance.
#         """
#         try:
#             instype = instance_params["InstanceType"]
#             keyname = instance_params["KeyName"]
#             print(f"Attempting to create {instype} instance")
#             print(f"Creating using {keyname} key")

#             self.instance = self.res.create_instances(
#                 **instance_params, MinCount=1, MaxCount=1
#             )[0]
#             self.instance.wait_until_running()
#         except ClientError as err:
#             print(
#                 "Couldn't create instance with image , instance type , and key . "
#                 "Here's why: %s: %s",
#                 #instaimage.id,
#                 #instance_type,
#                 #key_pair.name,
#                 err.response["Error"]["Code"],
#                 err.response["Error"]["Message"],
#             )
#             raise
#         else:
#             self._display(self.instance)
#             return self.instance


#     def _display(self, instance, indent=1):
#         """Display information about instance
#         """
#         if self.lst_instances is None:
#             print("No instance to display.")
#             return

#         try:
#             ind = "\t" * indent
#             print(f"{ind}ID: {instance.id}")
#             print(f"{ind}Image ID: {instance.image_id}")
#             print(f"{ind}Instance type: {instance.instance_type}")
#             print(f"{ind}Key name: {instance.key_name}")
#             print(f"{ind}VPC ID: {instance.vpc_id}")
#             print(f"{ind}Public IP: {instance.public_ip_address}")
#             print(f"{ind}State: {instance.state['Name']}")
#         except ClientError as err:
#             print(
#                 "Couldn't display your instance. Here's why: %s: %s",
#                 err.response["Error"]["Code"],
#                 err.response["Error"]["Message"],
#             )
#             raise

#     def list_instances(self, indent=1):
#         """
#         Displays information about all running instances.

#         :param indent: The visual indent to apply to the output.
#         """
#         if self.lst_instances is None:
#             print("No instance to display.")
#             return


#         for i, instance in enumerate(self.lst_instances.iterator()):
#             instance.load()
#             print(f"Instance number {i}:")
#             self._display(instance, indent=indent)

#     def terminate(self,
#                   instance_id: str=None)->None:
#         """
#         Terminates an instance and waits for it to be in a terminated state.
#         """

#         filters = [
#         {
#             'Name': 'instance-state-name',
#             'Values': ['running']
#         }]

#         if instance_id is not None:
#             try:
#                  instances = self.lst_instances.filter(Filters=filters)
#                  for instance in instances:
#                      if instance.id == instance_id:
#                         print(f"Found running instance {instance_id}")
#                         self.instance = instance
#             except ClientError as err:
#                 print(
#                 "Couldn't load instance %s. Here's why: %s: %s",
#                 instance_id,
#                 err.response["Error"]["Code"],
#                 err.response["Error"]["Message"],
#             )


#         if self.instance is None:
#             print("No instance to terminate.")
#             return

#         instance_id = self.instance.id
#         try:
#             print(f"Terminating instance {instance_id}...")
#             self.instance.terminate()
#             self.instance.wait_until_terminated()
#             self.instance = None
#             print(f"Instance {instance_id} successfully terminated.")
#         except ClientError as err:
#             print(
#                 "Couldn't terminate instance %s. Here's why: %s: %s",
#                 instance_id,
#                 err.response["Error"]["Code"],
#                 err.response["Error"]["Message"],
#             )
#             raise
