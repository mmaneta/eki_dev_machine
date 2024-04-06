import argparse
import dev_machine.dev_machine as dev_m
import yaml

with open('./dev_machine/default_conf.yaml', 'r') as f:
    conf = yaml.load(f, Loader=yaml.FullLoader)

def main(instance_type: str='t2.micro'):

    ec2 = dev_m.AwsResource.from_resource()

    if args.command == 'blank':
        d = {'InstanceType': str(args.instance_type)}
        conf['Ec2Instance']['Properties'].update(d)
        res = ec2.create_resource(**conf['Ec2Instance']['Properties'])

    if args.command == 'list':
        ec2.list_instances()

    if args.command == 'remove':
        ec2.terminate(args.instance_id)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(prog='dev_machine')
    subparsers = parser.add_subparsers(dest='command')
    
    subparser_blank = subparsers.add_parser(name='blank', help='Create a blank EC2 instance')
    subparser_blank.add_argument('--instance_type', '-i', type=str, help='instance type', default='t2.micro')

    subparser_blank = subparsers.add_parser(name='list', help='List running instances')

    subparser_blank = subparsers.add_parser(name='remove', help='Terminate running instance')
    subparser_blank.add_argument('instance_id',  type=str, help='instance id')
    
    args = parser.parse_args()

    main(args)

