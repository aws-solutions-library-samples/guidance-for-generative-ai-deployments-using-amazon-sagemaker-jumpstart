"""
This stack defines the repository that will be used as base for the CDK pipeline of this project.
It is not part of the CDK pipeline taking care of the application stack. Redeployments of this
stack should be rare and handled manually with care.
"""
import aws_cdk as cdk
import aws_cdk.aws_codecommit as codecommit
import constructs
from .config import config


class RepositoryStack(cdk.Stack):
    """
    Stack Class. See description in module docstring.
    """

    def __init__(
        self, scope: constructs.Construct, construct_id: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.repository = codecommit.Repository(
            scope=self,
            id="repo",
            repository_name=config["CONFIG"]["repository_name"],
        )
