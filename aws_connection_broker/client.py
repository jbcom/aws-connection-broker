import boto3
import botocore.client
import botocore.exceptions
from aws_assume_role_lib import assume_role

from typing import Optional

from gitops_utils.utils import (
    Utils,
    get_cloud_call_params,
    get_default_dict,
    all_non_empty,
    is_nothing,
)
from aws_connection_broker.errors import FailedResponseError


def get_aws_call_params(max_results: Optional[int] = 100, **kwargs):
    return get_cloud_call_params(
        max_results=max_results, first_letter_to_upper=True, **kwargs
    )


class AWSClient(Utils):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.AWS_ACCESS_KEY_ID = self.get_input("AWS_ACCESS_KEY_ID", required=False)
        self.AWS_SECRET_ACCESS_KEY = self.get_input(
            "AWS_SECRET_ACCESS_KEY", required=False
        )
        self.AWS_SESSION_TOKEN = self.get_input("AWS_SESSION_TOKEN", required=False)

        self.default_aws_session = None
        self.aws_sessions = get_default_dict(default_type=boto3.Session)
        self.aws_clients = get_default_dict(default_type=botocore.client.BaseClient)

    def get_default_aws_session(self) -> boto3.Session:
        if self.default_aws_session is not None:
            return self.default_aws_session

        if all_non_empty(
            self.AWS_ACCESS_KEY_ID, self.AWS_SECRET_ACCESS_KEY, self.AWS_SESSION_TOKEN
        ):
            self.default_aws_session = boto3.Session(
                aws_access_key_id=self.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY,
                aws_session_token=self.AWS_SESSION_TOKEN,
            )

            return self.default_aws_session

        self.default_aws_session = boto3.Session()
        return self.default_aws_session

    def get_aws_session(
        self,
        execution_role_arn: Optional[str] = None,
        role_session_name: Optional[str] = None,
    ) -> boto3.Session:
        if is_nothing(execution_role_arn):
            return self.get_default_aws_session()

        if is_nothing(role_session_name):
            role_session_name = self.get_unique_signature(delim=".", maxlen=64)

        session = self.aws_sessions[execution_role_arn].get(role_session_name)
        if session is not None:
            return session

        session = assume_role(
            session=self.get_default_aws_session(),
            RoleArn=execution_role_arn,
            RoleSessionName=role_session_name,
        )

        self.aws_sessions[execution_role_arn][role_session_name] = session

        return self.aws_sessions[execution_role_arn][role_session_name]

    def get_aws_resource(
        self,
        service_name: str,
        execution_role_arn: Optional[str] = None,
        role_session_name: Optional[str] = None,
        **resource_args,
    ):
        aws_session = self.get_aws_session(
            execution_role_arn=execution_role_arn, role_session_name=role_session_name
        )

        return aws_session.resource(service_name, **resource_args)

    def get_aws_client(
        self,
        client_name: str,
        execution_role_arn: Optional[str] = None,
        role_session_name: Optional[str] = None,
    ) -> botocore.client.BaseClient:
        if is_nothing(execution_role_arn):
            execution_name = "default"
        else:
            execution_name = execution_role_arn

        execution = self.aws_clients[client_name].get(execution_name)
        if execution is not None:
            return execution

        session = self.get_aws_session(
            execution_role_arn=execution_role_arn, role_session_name=role_session_name
        )

        execution = session.client(client_name)
        self.aws_clients[client_name][execution_name] = execution
        return self.aws_clients[client_name][execution_name]

    def get_caller_account_id(self):
        aws_client = self.get_aws_client(client_name="sts")
        response = aws_client.get_caller_identity()
        caller_account_id = response.get("Account")

        if is_nothing(caller_account_id):
            raise RuntimeError("Failed to get caller account ID")

        return caller_account_id
