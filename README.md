# Guidance for Generative AI Deployments using Amazon SageMaker JumpStart

**Important**: This Guidance requires the use of AWS CodeCommit, which is no longer available to new customers. Existing customers of AWS CodeCommit can continue using and deploying this Guidance as normal.

## Purpose

This repository provides a pattern for simple generative AI deployments on AWS. It aims at keeping deployment easy, the architecture understandable and the used resources as low-maintenance and cost-effective as possible.

This is achieved by using foundation models that [SageMaker Jumpstart](https://docs.aws.amazon.com/sagemaker/latest/dg/studio-jumpstart.html) provides, deploying them in a [SageMaker Asynchronous Endpoint](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference.html) which can scale to zero and requires no additional operations effort. The use of [CDK Pipelines](https://docs.aws.amazon.com/cdk/v2/guide/cdk_pipeline.html) ensures repeatability and traceability of deployment and configuration activities.

While we chose to use [Stable Diffusion](https://stability.ai/stablediffusion) for text to image generation as the implemented example here, it should be easy to adjust the code to fit other models and use cases, too. Keep in mind that the [Lambda function working with the successful output](simple_generative_ai_service/lambda/extract_image/) of the SageMaker inference needs to be adjusted if your use case differs. Currently, it is programmed to work with JSON output containing image pixel RGB arrays. If you would rather use [real-time](https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints.html) than [asynchronous](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference.html) inference, [the endpoint stack](simple_generative_ai_service/service_endpoint_stack.py) can be adjusted accordingly.

## Architecture

## Deployment

### Configuration

If you just want to test this solution or actually need a scale-to-zero Stable Diffusion 2.1 endpoint deployed in eu-central-1, you can skip configuration - that is the default.

Otherwise, you can modify the [TOML](https://toml.io/en/) formatted configuration file [config/config.toml](config/config.toml) to your needs. All adjustable parameters are described there in the comments.

### Software Requirements

To successfully deploy this project, you need to have the following software installed on your workstation:

* [Python](https://www.python.org/) version 3.8 or newer
* [Python Poetry](https://python-poetry.org/)
* [git](https://git-scm.com/)
* [git-remote-codecommit](https://docs.aws.amazon.com/codecommit/latest/userguide/setting-up-git-remote-codecommit.html#setting-up-git-remote-codecommit-install)
* [Node.js](https://nodejs.org/en), current LTS version recommended

### Deployment Instructions

These instructions have been tested on Linux and Mac. In case you are using Windows, you may either use a bash terminal in the Windows Subsystem for Linux or adjust the commands for setting and using the environment variables.

1. Set your environment to the AWS account you want to deploy into.
1. [Bootstrap](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html) your account for CDK in the region you intend to deploy to in case this has not been done yet.
1. Clone this repository and change your working directory into it.
1. Create a Python virtual environment, activate and install the dependencies into it with `poetry shell` and `poetry install`
1. Some environment variables need to be set according to your settings in [config/config.toml](config/config.toml). For this example, the default values for Stable Diffusion are used.
    ```bash
    export REPOSITORY_NAME=StableDiffusionService
    export REPOSITORY_BRANCH=main
    export AWS_REGION=eu-central-1
    export INITIAL_DEPLOY=yes
    ```
    The `INITIAL_DEPLOY` environment variable takes care that the CDK is only working with the stacks and resources required for deploying the solution repository and a minimal pipeline. This eliminates the need of having Docker installed and running on the developer's machine as well as decreasing the runtime of CDK commands there. We leave the heavy lifting to the execution within the AWS CodePipeline CodeBuild steps later.
1. Deploy the CloudFormation Stack creating the CodeCommit repository by executing
    ```bash
    cdk deploy ${REPOSITORY_NAME}RepositoryStack
    ```
1. Change the remote origin of this project to the new CodeCommit repository via
    ```bash
    git remote set-url origin codecommit::${AWS_REGION}://${REPOSITORY_NAME}
    ```
1. In case you modified [config/config.toml](config/config.toml), `git add` and `git commit` those changes. 
1. Push the code to your new repository with
    ```bash
    git push origin ${REPOSITORY_BRANCH}
    ```
1. Deploy the Service Stack by executing
    ```bash
    cdk deploy ${REPOSITORY_NAME}ServiceStack
    ```

The [CDK Pipeline](https://docs.aws.amazon.com/cdk/v2/guide/cdk_pipeline.html) configured will start deploying all resources defined and self-update to contain the full application stack (as it does not have the INITIAL_DEPLOY environment variable set). From this point on, you initiate changes in the architecture by just committing to the repository and letting the pipeline take care of the rest.

Wait for the pipeline to be finished.

# Executing

You can use [util/generate_image.py](util/generate_image.py) to test the image generation. The file [util/test_request.json](util/test_request.json) in the same folder works with the StableDiffusion model configured in the standard config.toml.

Example

```bash
./util/generate_image.py --request-input-file util/test_request.json
```

With the SageMaker Asynchronous Endpoint scaled to zero, it will take a few minutes for an instance starting up to serve the request. You can check the current state of the endpoint in the SageMaker console `Inference` submenu, `Endpoints` item.

The `generate_image.py` command will show you the endpoint name which you will find in the list. On its detail page in the `Endpoint runtime settings`, you will first see the `Desired instance count` increasing, then the `Current instance count` when one is started.

In the `Monitor` section, the `View logs` link leads to the CloudWatch console with all log streams of the endpoint available for the full inference execution details.

After this step is finished, you can check the logs of the two Lambda functions deployed with the solution. The `ExtractImageFunction` will execute and protocol the conversion of the RGB pixel array of the inference result to PNG files while the `SaveMessageFunction` stores the execution info to S3.

Finally, you will see the generated images in the S3 bucket path the `generate_image.py` output tells you.
