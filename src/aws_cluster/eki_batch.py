import itertools

from aiohttp import ClientError

from eki_dev.aws_service import AwsService
from eki_dev.utils import get_project_tags, check_file_exists_in_s3
from aws_cluster.cluster_utils import (
    open_yaml
)


class EkiBatch:
    def __init__(self, fn_yaml: str,
                 subnet_id: str = "subnet-03273ac6cfdbc7db0",  # public subnet for nat gateway
                 route_table_id: str = "rtb-0a4d4e7bb90a8bf09"
                 ):
        try:
            self.conf = open_yaml(fn_yaml)
        except FileNotFoundError:
            print("EkiBatch config file not found")
            raise

        self._route_table_id = route_table_id

        self.batch_client = AwsService.from_service('batch').client
        self.project_tag = self.conf['project_tag']
        self.job_name = self.conf['job_name']
        self.queue = self.conf["queue_arn"]
        self.task_definition = self.conf["task_definition_arn"]
        self.parameters = self.conf["parameters"]
        self.loops = self.conf["loops"]
        self.success_indicators = self.conf["success_indicators"]
        self.command_line = self.conf["command_line"]
        self.lst_parsed_cmds = []
        self._parse_command_line()

        self.eip = None
        self.nat_gateway = None
        self.route = None

        dct_tags = get_project_tags()
        lst_tags = list(dct_tags.keys())

        if self.project_tag not in lst_tags:
            print(f"tag {self.project_tag} must be one of {lst_tags}")
            raise Exception(f"tag {self.project_tag} must be one of {lst_tags}")

    def _allocate_elastic_ip(self):
        try:
            eip_client = AwsService.from_service('ec2').client.allocate_address(
                Domain='vpc',
                TagSpecifications = [
                    {
                        'ResourceType': 'elastic-ip',
                        'Tags': [
                            {
                                'Key': 'project',
                                'Value': self.project_tag
                            },
                        ]
                    },
                ],
            )
            self.eip = eip_client
        except ClientError as e:
            print(e)
            raise

    @staticmethod
    def _create_route(nat_gateway_id: str,
                      route_table_id: str = "rtb-0a4d4e7bb90a8bf09"):
        print(f"Creating route to connect private network to {nat_gateway_id}")
        route = AwsService.from_service('ec2').client.create_route(
            DestinationCidrBlock='0.0.0.0/0',
            NatGatewayId=nat_gateway_id,
            RouteTableId=route_table_id,

        )
        return route

    def create_nat_gateway(self, subnet_id: str = "subnet-03273ac6cfdbc7db0", # eki cluster public subnet
                            dry_run: bool = False):
        ec2_client = AwsService.from_service('ec2').client

        # Check if there is a NAT Gateway already in the VPC
        nats = ec2_client.describe_nat_gateways(
            Filter=[
                {
                    'Name': 'state',
                    'Values': ['available']
                }
            ]
        )

        if len(nats['NatGateways'][0]) == 0:  # if there is no NAT, create it. Assumes only one NAT exists
            self._allocate_elastic_ip()

            try:
                nat_gateway = ec2_client.create_nat_gateway(
                    AllocationId=self.eip['AllocationId'],
                    DryRun=dry_run,
                    SubnetId=subnet_id,
                    TagSpecifications=[
                        {
                            'ResourceType': 'natgateway',
                            'Tags': [
                                {
                                    'Key': 'project',
                                    'Value': self.project_tag
                                },
                            ]
                        },
                    ],
                )
                self.nat_gateway = nat_gateway

                try:
                    waiter = AwsService.from_service('ec2').client.get_waiter('nat_gateway_available')
                    waiter.wait(NatGatewayIds=[nat_gateway['NatGateway']['NatGatewayId']])
                except Exception as e:
                    print(e)
                    raise

                self.route = self._create_route(nat_gateway_id=nat_gateway['NatGateway']['NatGatewayId'],
                                                route_table_id=self._route_table_id)
            except ClientError as e:
                #clean up elastic ip
                if self.eip is not None:
                    AwsService.from_service('ec2').client.release_address(
                        AllocationId=self.eip['AllocationId'],
                    )
                print(e)
                raise
        else:
            self.nat_gateway = {"NatGateway": nats['NatGateways'][0]}
            route_tables = ec2_client.describe_route_tables(
                RouteTableIds=[self._route_table_id],
            )
            routes = [tables["Routes"] for tables in route_tables["RouteTables"]
                      if tables["RouteTableId"] == self._route_table_id]
            self.route = [route for route in routes[0] if "NatGatewayId" in route.keys()
                          and route['NatGatewayId'] == self.nat_gateway['NatGateway']['NatGatewayId']][0]

    def _parse_command_line(self):

        self.lst_parsed_cmds = []
        param_combinations = itertools.product(*self.loops.values())

        cmd_line = self.command_line
        success_indicators = self.success_indicators.copy()
        for (param, value) in self.parameters.items():
            cmd_line = cmd_line.replace(f"{{{param}}}", str(value))
            success_indicators = [f.replace(f"{{{param}}}", str(value)) for f in success_indicators]

        for combination in param_combinations:
            cmd_line2 = cmd_line
            success_indicators2 = success_indicators
            for (loop_par, value) in zip(self.loops.keys(), combination):
                cmd_line2 = cmd_line2.replace(f"{{{loop_par}}}", str(value))
                success_indicators2 = [f.replace(f"{{{loop_par}}}", str(value)) for f in success_indicators2]
            if all([check_file_exists_in_s3(f) for f in success_indicators2]):
                continue
            self.lst_parsed_cmds.append(cmd_line2)

    def _print_parsed_cmds(self):
        print(f"There are ")
        print(f"{len(self.lst_parsed_cmds)} JOBS ")
        print(f"in the configuration file of {self.job_name}")
        print(f"The jobs will be started with the following commands,"
              f" please check that they are correct before launching:")
        for i,cmd in enumerate(self.lst_parsed_cmds):
            print(f"{i+1}: {cmd}\n")

    def print_command_list(self):
        self._parse_command_line()
        self._print_parsed_cmds()

    def submit_jobs(self, cmd_idx: list = None):


        lst_parsed_cmds = self.lst_parsed_cmds

        if cmd_idx is not None:
            if not isinstance(cmd_idx, list):
                cmd_idx = [cmd_idx]
            lst_parsed_cmds = [self.lst_parsed_cmds[i] for i in cmd_idx]

        for cmd in lst_parsed_cmds:

            print(f"Submitting job {cmd}")

            container_overrides = {"command": cmd.split()}

            try:
               job = self.batch_client.submit_job(jobName=self.job_name,
                                             jobQueue=self.queue,
                                             jobDefinition=self.task_definition,
                                             parameters=self.parameters,
                                             containerOverrides=container_overrides
                                             )
            except Exception as e:
                print(e)
                raise

        return job

    def clean_up_nat_gateway(self):
        print("Cleaning up elastic IP and Nat Gateway")

        ec2_client = AwsService.from_service('ec2').client

        print("deleting NAT gateway")
        if self.nat_gateway is not None:
            ec2_client.delete_nat_gateway(
                NatGatewayId=self.nat_gateway['NatGateway']['NatGatewayId']
            )
            print("Waiting for deletion to complete")
            waiter = ec2_client.get_waiter('nat_gateway_deleted')
            waiter.wait(NatGatewayIds=[self.nat_gateway['NatGateway']['NatGatewayId']])
            print("Deletion Successful")
            self.nat_gateway = None

        print("deleting elastic IP")
        if self.eip is not None:
            ec2_client.release_address(
                AllocationId=self.eip['AllocationId'],
            )
            self.eip = None

        print("deleting route to NAT")
        if self.route is not None:
            ec2_client.delete_route(
                RouteTableId="rtb-0a4d4e7bb90a8bf09",
                DestinationCidrBlock = '0.0.0.0/0',
            )


