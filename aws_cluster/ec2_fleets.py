import boto3


class AwsResource:
    def __init__(self, resource) -> None:

        self.client = resource
        

    @classmethod
    def from_resource(cls, res: str='ec2'):
        aws_client = boto3.client(res)        
        return cls(aws_client)


class ec2_fleet:
    def __init__(self, aws_res: AwsResource = AwsResource.from_resource('ec2')):
        self.aws_res = aws_res

    
        