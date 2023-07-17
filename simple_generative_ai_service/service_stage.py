""" This CDK stack defines a full deployment stage for the Text to Image service.
"""

import aws_cdk as cdk
import constructs
from simple_generative_ai_service.service_endpoint_stack import (
    ServiceEndpointStack,
)


class ServiceStage(cdk.Stage):
    """
    Stack Class. See description in module docstring.
    """

    def __init__(
        self, scope: constructs.Construct, construct_id: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ServiceEndpointStack(
            self,
            "Endpoint",
            description="Guidance for Image Generation on AWS (SO9234)",
        )
