import boto3
from botocore.exceptions import ClientError
import yaml


class AwsResource:
    def __init__(self, resource, instance=None) -> None:

        self.res = resource
        self.instance = instance
        self.lst_instances = self.res.instances

    @classmethod
    def from_resource(cls, res: str='ec2'):
        ec2_res = boto3.resource(res)        
        return cls(ec2_res)
    
    def create_resource(self, **instance_params):
        """
        Creates a new EC2 instance. The instance starts immediately after
        it is created.

        :return: A Boto3 Instance object that represents the newly created instance.
        """
        try:        
            instype = instance_params["InstanceType"]
            keyname = instance_params["KeyName"]
            print(f"Attempting to create {instype} instance")
            print(f"Creating using {keyname} key")        
            
            self.instance = self.res.create_instances(
                **instance_params, MinCount=1, MaxCount=1
            )[0]
            self.instance.wait_until_running()
        except ClientError as err:
            print(
                "Couldn't create instance with image , instance type , and key . "
                "Here's why: %s: %s",
                #instaimage.id,
                #instance_type,
                #key_pair.name,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise
        else:
            self._display(self.instance)
            return self.instance


    def _display(self, instance, indent=1):
        """Display information about instance
        """    
        if self.lst_instances is None:
            print("No instance to display.")
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
    
    def list_instances(self, indent=1):
        """
        Displays information about all running instances.

        :param indent: The visual indent to apply to the output.
        """
        if self.lst_instances is None:
            print("No instance to display.")
            return


        for i, instance in enumerate(self.lst_instances.iterator()):            
            instance.load()
            print(f"Instance number {i}:")
            self._display(instance, indent=indent)

    def terminate(self, 
                  instance_id: str=None)->None:
        """
        Terminates an instance and waits for it to be in a terminated state.
        """
        
        filters = [
        {
            'Name': 'instance-state-name', 
            'Values': ['running']
        }]

        if instance_id is not None:
            try:
                 instances = self.lst_instances.filter(Filters=filters)
                 for instance in instances:
                     if instance.id == instance_id:
                        print(f"Found running instance {instance_id}")
                        self.instance = instance                
            except ClientError as err:
                print(
                "Couldn't load instance %s. Here's why: %s: %s",
                instance_id,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
                
                                
        if self.instance is None:
            print("No instance to terminate.")
            return

        instance_id = self.instance.id
        try:
            print(f"Terminating instance {instance_id}...")
            self.instance.terminate()
            self.instance.wait_until_terminated()            
            self.instance = None
            print(f"Instance {instance_id} successfully terminated.")
        except ClientError as err:
            print(
                "Couldn't terminate instance %s. Here's why: %s: %s",
                instance_id,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise



    
