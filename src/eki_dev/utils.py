import os
import subprocess
from rich.pretty import pprint
from pathlib import Path
import yaml
import importlib_resources

from eki_dev.aws_service import AwsService


def generate_makefile(image_name : str,
                      repo_name : str,
                      makefile_name : str = 'Makefile') -> str:

    tmpl = makefile_template.format(image_name, repo_name)
    print(f"Writing Makefile to {makefile_name} with repo {image_name} and image {repo_name}")
    with open(makefile_name, "w") as makefile:
        makefile.write(tmpl)
    return tmpl


class Config:
    def __init__(self):
        self.conf = self.retrieve_configuration()

    @staticmethod
    def retrieve_configuration():
        ref = importlib_resources.files('eki_dev') / 'default_conf.yaml'
        with importlib_resources.as_file(ref) as data_path:
            with open(data_path, "r", encoding='utf8') as f:
                conf = yaml.load(f, Loader=yaml.FullLoader)
        return conf

    def update_ssh_key_name(self, key_name: str):
        print(f"Updating ssh key name to {key_name}")
        d = {"KeyName": key_name}
        self.conf["Ec2Instance"]["Properties"].update(d)
        return self

    def write_configuration(self):
        ref = importlib_resources.files('eki_dev') / 'default_conf.yaml'
        with importlib_resources.as_file(ref) as data_path:
            with open(data_path, "w", encoding='utf8') as f:
                yaml.dump(self.conf, f)

    def create_ssh_keys(self,
                        name: str,
                        path_ssh_config: str = '~/.ssh',
                        KeyType: str = 'rsa',
                        DryRun: bool = False,
                        KeyFormat: str = 'pem'):
        path_ssh_config = os.path.expanduser(path_ssh_config)
        client = AwsService.from_service('ec2')
        resp = client.client.create_key_pair(KeyName=name,
                                      DryRun=DryRun,
                                      KeyType=KeyType,
                                      KeyFormat=KeyFormat)
        if resp['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise Exception("Key pair creation failed")

        private_key = resp['KeyMaterial']
        namepem = name + '.pem'
        with open(os.path.join(path_ssh_config,namepem), 'w') as f:
            f.write(private_key)
            os.chmod(os.path.join(path_ssh_config,namepem), 0o600)

        print(f'Key pair {name} created and private key save to {os.path.join(path_ssh_config,namepem)}.')

        print(f'Updating EKI Dev Machine ssh key name to {name}')
        self.update_ssh_key_name(name).write_configuration()

        print(f"\nPlease, make this ssh key pair {name} the default by")
        print(f"adding the lines ")
        print(f"""
        \tIdentityFile {os.path.join(path_ssh_config,namepem)}
        \tStrictHostKeyChecking no
        """)
        print(f"to your {path_ssh_config}/config file ")

    def user_input_configuration(self):
        ssh_key_name = input("Enter ssh key name: ")
        self.create_ssh_keys(ssh_key_name)


# Show task progress (red for download, green for extract)
def show_progress(line, progress, tasks):

    if line['status'] == 'Downloading':
        #id_ = f'[red][Download {line["id"]}]'
        pprint(f'Downloading: {line["id"]}')
        return
    elif line['status'] == 'Extracting':
        id_ = f'[green][Extract  {line["id"]}]'
    else:
        # skip other statuses
        return

    if id_ not in tasks.keys():
        tasks[id_] = progress.add_task(f"{id_}", total=line['progressDetail']['total'])
    #else:
    progress.update(tasks[id_], completed=line['progressDetail']['current'])


def get_project_tags(bucket='eki-dev-machine-config'):
    s3 = AwsService.from_service('s3')
    response = s3.client.get_object(Bucket=bucket, Key='project_tags.txt')
    data = response['Body'].read()
    tags = data.decode('utf8').strip().split(',')
    return tags


def add_instance_tags(project_tag,
                      **instance_params):
    # add user and project tags
    tag = {
                    'Key': 'project',
                    'Value': project_tag
                }
    instance_params['TagSpecifications'][0]['Tags'].append(tag)
    return instance_params


def register_instance(
        name : str,
        host_ip : str,
        CONFIG_DIR='.dev_machine',
              ) -> str:
    HOME = os.path.expanduser("~")
    dev_machine_dir = os.path.join(HOME, CONFIG_DIR)
    Path(dev_machine_dir).mkdir(parents=False, exist_ok=True)
    p = os.path.join(dev_machine_dir, name + "@" + host_ip)
    Path(p).touch()
    return p


def deregister_instance(name : str,
                        host_ip : str,
                        CONFIG_DIR='.dev_machine')->str:
    HOME = os.path.expanduser("~")
    p = os.path.join(HOME, CONFIG_DIR, name + "@" + host_ip)
    try:
        os.remove(p)
    except FileNotFoundError:
        pass
    return p


def ssh_splitter(ssh_connect_string):
    ssh_connect_string = ssh_connect_string.replace('ssh://', '')
    user_host, _, path = ssh_connect_string.partition(':')
    user, _, host = user_host.rpartition('@')
    return user, host, path


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

makefile_template = \
"""
SHELL = /bin/bash
IMAGE = {}
TAG ?= dev
REGION = $(shell aws configure get region)
AWS_ACCOUNT_ID = $(shell aws sts get-caller-identity --query Account --output text)
REPO = {}
 
build:
	DOCKER_BUILDKIT=1 && export DOCKER_BUILDKIT
	docker build -f Dockerfile -t $(IMAGE):$(TAG) . 

run: build
	@docker run --rm -it -v .:/home/eki --platform linux/amd64 $(IMAGE):$(TAG)

run_aws: build
	@docker run --rm -it -v /home/ubuntu/efs:/home/eki/efs --platform linux/amd64 $(IMAGE):$(TAG)

push_aws: check-tag
	aws ecr get-login-password --region $(REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com
	docker tag $(REPO):$(TAG) $(AWS_ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com/$(REPO):$(TAG)
	docker push  $(AWS_ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com/$(REPO):$(TAG)

pull_aws: check-tag
    aws ecr get-login-password --region $(REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com
    docker pull  $(AWS_ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com/$(REPO):$(TAG)
    
jupyter-lab: build
    @docker run --rm -it -v .:/home/eki -p 8888:8888 -p 8889:8889 -u 0 $(REPO):$(TAG) jupyter-lab --no-browser --ip=0.0.0.0 --allow-root

.PHONY:	build run run_aws push_aws pull_aws jupyter-lab check-tag

check-tag:
ifndef TAG
    $(error TAG needs to be set)
endif
"""