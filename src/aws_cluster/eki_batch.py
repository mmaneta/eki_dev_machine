import itertools

from eki_dev.aws_service import AwsService
from aws_cluster.cluster_utils import (
    open_yaml
)


class EkiBatch:
    def __init__(self, fn_yaml: str):
        try:
            self.conf = open_yaml(fn_yaml)
        except FileNotFoundError:
            print("EkiBatch config file not found")
            raise

        self.batch_client = AwsService.from_service('batch').client
        self.job_name = self.conf['job_name']
        self.queue = self.conf["queue_arn"]
        self.task_definition = self.conf["task_definition_arn"]
        self.parameters = self.conf["parameters"]
        self.loops = self.conf["loops"]
        self.command_line = self.conf["command_line"]
        self.lst_parsed_cmds = []
        self._parse_command_line()

    def _parse_command_line(self):

        param_combinations = itertools.product(*self.loops.values())

        cmd_line = self.command_line
        for (param, value) in self.parameters.items():
            cmd_line = cmd_line.replace(f"{{{param}}}", str(value))

        for combination in param_combinations:
            cmd_line2 = cmd_line
            for (loop_par, value) in zip(self.loops.keys(), combination):
                cmd_line2 = cmd_line2.replace(f"{{{loop_par}}}", str(value))
            self.lst_parsed_cmds.append(cmd_line2)

    def _print_parsed_cmds(self):
        print(f"There are {len(self.lst_parsed_cmds)} jobs in the configuration file for job {self.job_name}")
        print(f"The jobs will be started with the following commands,"
              f" please check that they are correct before launching:")
        for cmd in self.lst_parsed_cmds:
            print(cmd)

    def print_command_list(self):
        self._print_parsed_cmds()

    def submit_jobs(self, cmd_idx: list = None):

        lst_parsed_cmds = self.lst_parsed_cmds
        if cmd_idx is not None:
            lst_parsed_cmds = self.lst_parsed_cmds[slice(cmd_idx)]
        for cmd in lst_parsed_cmds:

            container_overrides = {"command": cmd.split()}

            try:
                self.batch_client.submit_job(jobName=self.job_name,
                                             jobQueue=self.queue,
                                             jobDefinition=self.task_definition,
                                             parameters=self.parameters,
                                             containerOverrides=container_overrides
                                             )
            except Exception as e:
                print(e)
                raise
