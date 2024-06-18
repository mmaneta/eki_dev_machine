import boto3
from botocore.exceptions import ClientError
from boto3.exceptions import ResourceNotExistsError


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

        # region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

        try:
            cls_res = boto3.resource(service, region_name=region)
        except ResourceNotExistsError:
            cls_res = None
            print("Resource interface not available for service '{}'.".format(service))
            print("Attempting Client interface...")
        try:
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
