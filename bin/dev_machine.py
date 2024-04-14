#!/usr/bin/env python

import sys
import argparse
import importlib_resources
import yaml

import eki_dev.dev_machine as dev_m

ref = importlib_resources.files('eki_dev') / 'default_conf.yaml'
with importlib_resources.as_file(ref) as data_path:    
    with open(data_path, "r", encoding='utf8') as f:
        conf = yaml.load(f, Loader=yaml.FullLoader)

def main(args):

    if args.command == "blank":
        d = {"InstanceType": str(args.instance_type)}
        conf["Ec2Instance"]["Properties"].update(d)
        res = dev_m.create_ec2_instance(**conf["Ec2Instance"]["Properties"])

    if args.command == "list":
        dev_m.list_instances()

    if args.command == "remove":
        dev_m.terminate_instance(args.instance_id)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(prog="dev_machine", 
                                     description="Development Machine provisioner for EKI Environment and Water")
    subparsers = parser.add_subparsers(dest="command")

    subparser_blank = subparsers.add_parser(
        name="blank", help="Create a blank EC2 instance"
    )
    subparser_blank.add_argument(
        "--instance_type", "-i", type=str, help="instance type", default="t2.micro"
    )

    subparser_blank = subparsers.add_parser(name="list", help="List running instances")

    subparser_blank = subparsers.add_parser(
        name="remove", help="Terminate running instance"
    )
    subparser_blank.add_argument("instance_id", type=str, help="instance id")
    

    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    main(args)
