# Built-in imports
import os

# External imports
from aws_cdk import (
    Duration,
    aws_apigateway as aws_apigw,
    aws_dynamodb,
    aws_events,
    aws_events_targets,
    aws_iam,
    aws_lambda,
    aws_logs,
    aws_s3,
    aws_stepfunctions as aws_sfn,
    aws_stepfunctions_tasks as aws_sfn_tasks,
    CfnOutput,
    RemovalPolicy,
    Stack,
    Tags,
)
from constructs import Construct


class BackendStack(Stack):
    """
    Class to create the IDP Backend resources, which includes the S3, DynamoDB, State Machine
    and the necessary connections/permissions for the IDP workflows.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        main_resources_name: str,
        app_config: dict[str],
        **kwargs,
    ) -> None:
        """
        :param scope (Construct): Parent of this stack, usually an 'App' or a 'Stage', but could be any construct.
        :param construct_id (str): The construct ID of this stack (same as aws-cdk Stack 'construct_id').
        :param main_resources_name (str): The main unique identified of this stack.
        :param app_config (dict[str]): Dictionary with relevant configuration values for the stack.
        """
        super().__init__(scope, construct_id, **kwargs)

        # Input parameters
        self.construct_id = construct_id
        self.main_resources_name = main_resources_name
        self.app_config = app_config
        self.deployment_environment = self.app_config["deployment_environment"]

        # Main methods for the deployment
        self.create_s3_buckets()
        self.create_dynamodb_tables()
        self.create_lambda_layers()
        self.create_lambda_functions()
        self.create_state_machine_tasks()
        self.create_state_machine_definition()
        self.create_state_machine()
        self.configure_s3_trigger_state_machine()
        self.create_rest_api()
        self.configure_rest_api()

        # Generate CloudFormation outputs
        self.generate_cloudformation_outputs()

    def create_s3_buckets(self):
        """
        Create S3 buckets for storing for storing the files of the receipts.
        """
        bucket_name = f"{self.app_config['s3_bucket_name_prefix']}-{self.account}"
        self.s3_bucket_receipts = aws_s3.Bucket(
            self,
            "S3-Bucket-IDPData",
            bucket_name=bucket_name,
            auto_delete_objects=True,
            block_public_access=aws_s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
            event_bridge_enabled=True,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=aws_s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
        )
        Tags.of(self.s3_bucket_receipts).add("Name", bucket_name)

    def create_dynamodb_tables(self):
        """
        Create DynamoDB table for storing the data of the receipts.
        """
        self.dynamodb_table = aws_dynamodb.Table(
            self,
            "DynamoDB-Table-IDPData",
            table_name=self.app_config["table_name"],
            partition_key=aws_dynamodb.Attribute(
                name="PK", type=aws_dynamodb.AttributeType.STRING
            ),
            sort_key=aws_dynamodb.Attribute(
                name="SK", type=aws_dynamodb.AttributeType.STRING
            ),
            stream=aws_dynamodb.StreamViewType.NEW_IMAGE,
            billing_mode=aws_dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        Tags.of(self.dynamodb_table).add("Name", self.app_config["table_name"])

    def create_lambda_layers(self) -> None:
        """
        Create the Lambda layers that are necessary for the additional runtime
        dependencies of the Lambda Functions.
        """

        # Layer for "LambdaPowerTools" (for logging, traces, observability, etc)
        self.lambda_layer_powertools = aws_lambda.LayerVersion.from_layer_version_arn(
            self,
            "Layer-PowerTools",
            layer_version_arn=f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:71",
        )

        # Layer for "common" Python requirements (fastapi, pydantic, ...)
        self.lambda_layer_common = aws_lambda.LayerVersion(
            self,
            "Layer-common",
            code=aws_lambda.Code.from_asset("lambda-layers/common/modules"),
            compatible_runtimes=[
                aws_lambda.Runtime.PYTHON_3_11,
            ],
            description="Lambda Layer for Python with <common> library",
            removal_policy=RemovalPolicy.DESTROY,
            compatible_architectures=[aws_lambda.Architecture.X86_64],
        )

    def create_lambda_functions(self) -> None:
        """
        Create the Lambda Functions for the solution.
        """
        # Get relative path for folder that contains Lambda function source
        # ! Note--> we must obtain parent dirs to create path (that"s why there is "os.path.dirname()")
        PATH_TO_LAMBDA_FUNCTION_FOLDER = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "backend",
        )

        # Lambda Function that will run the State Machine steps for processing the messages
        # TODO: In the future, can be migrated to MULTIPLE Lambda Functions for each step...
        self.lambda_state_machine_process_idp_processing = aws_lambda.Function(
            self,
            "Lambda-SM-IDPProcessing",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            handler="state_machine/state_machine_handler.lambda_handler",
            function_name=f"{self.main_resources_name}-state-machine-lambda",
            description=f"Function to process the IDP documents inside the State Machine for {self.main_resources_name}",
            code=aws_lambda.Code.from_asset(PATH_TO_LAMBDA_FUNCTION_FOLDER),
            timeout=Duration.seconds(60),
            memory_size=512,
            environment={
                "ENVIRONMENT": self.app_config["deployment_environment"],
                "LOG_LEVEL": self.app_config["log_level"],
                "TABLE_NAME": self.dynamodb_table.table_name,
                "S3_BUCKET_NAME": self.s3_bucket_receipts.bucket_name,
                "BEDROCK_LLM_MODEL_ID": self.app_config["bedrock_llm_model_id"],
            },
            layers=[
                self.lambda_layer_powertools,
                self.lambda_layer_common,
            ],
        )
        self.dynamodb_table.grant_read_write_data(
            self.lambda_state_machine_process_idp_processing
        )
        self.s3_bucket_receipts.grant_read_write(
            self.lambda_state_machine_process_idp_processing
        )
        self.lambda_state_machine_process_idp_processing.role.add_managed_policy(
            aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonBedrockFullAccess",
            ),
        )

        # Lambda Function for managing CRUD operations on "DOCUMENTS"
        self.lambda_documents_api: aws_lambda.Function = aws_lambda.Function(
            self,
            "Lambda-DocumentsAPI",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            function_name=f"{self.main_resources_name}-api-documents",
            description=f"FastAPI for IDP CRUD actions of documents for {self.main_resources_name}",
            handler="api/v1/main.handler",
            code=aws_lambda.Code.from_asset(PATH_TO_LAMBDA_FUNCTION_FOLDER),
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                "ENVIRONMENT": self.app_config["deployment_environment"],
                "LOG_LEVEL": self.app_config["log_level"],
                "TABLE_NAME": self.dynamodb_table.table_name,
                "S3_BUCKET_NAME": self.s3_bucket_receipts.bucket_name,
            },
            layers=[
                self.lambda_layer_powertools,
                self.lambda_layer_common,
            ],
        )
        self.dynamodb_table.grant_read_write_data(self.lambda_documents_api)
        self.s3_bucket_receipts.grant_read_write(self.lambda_documents_api)

    def create_state_machine_tasks(self) -> None:
        """ "
        Method to create the tasks for the Step Function State Machine.
        """

        # TODO: create abstraction to reuse the definition of tasks

        self.task_validate_input = aws_sfn_tasks.LambdaInvoke(
            self,
            "Task-ValidateInput",
            state_name="Validate Input",
            lambda_function=self.lambda_state_machine_process_idp_processing,
            payload=aws_sfn.TaskInput.from_object(
                {
                    "event.$": "$",
                    "params": {
                        "class_name": "ValidateInput",
                        "method_name": "validate_input",
                    },
                }
            ),
            output_path="$.Payload",
        )

        # Pass States to simplify State Machine UI understanding
        self.task_pass_image = aws_sfn.Pass(
            self,
            "Task-Image",
            comment="Indicates that the input data type is Image",
            state_name="Image",
        )

        self.task_pass_pdf = aws_sfn.Pass(
            self,
            "Task-PDF",
            comment="Indicates that the input data type is PDF",
            state_name="PDF",
        )

        self.task_pass_other = aws_sfn.Pass(
            self,
            "Task-Other",
            comment="Indicates that the input data type is Other",
            state_name="Other",
        )

        self.task_process_image = aws_sfn_tasks.LambdaInvoke(
            self,
            "Task-ProcessImage",
            state_name="Process Image",
            lambda_function=self.lambda_state_machine_process_idp_processing,
            payload=aws_sfn.TaskInput.from_object(
                {
                    "event.$": "$",
                    "params": {
                        "class_name": "ProcessImage",
                        "method_name": "process_image",
                    },
                }
            ),
            output_path="$.Payload",
        )
        # Add retry configuration (default behavior has all errors are retried)
        self.task_process_image.add_retry(
            max_attempts=5,  # Retry up to 5 times (Bedrock has as of now errors eventually)
            interval=Duration.seconds(1),  # Wait 1 seconds between retries
            backoff_rate=2.0,  # Exponential backoff multiplier
        )

        self.task_process_pdf = aws_sfn_tasks.LambdaInvoke(
            self,
            "Task-ProcessPDF",
            state_name="Process PDF",
            lambda_function=self.lambda_state_machine_process_idp_processing,
            payload=aws_sfn.TaskInput.from_object(
                {
                    "event.$": "$",
                    "params": {
                        "class_name": "ProcessPDF",
                        "method_name": "process_pdf",
                    },
                }
            ),
            output_path="$.Payload",
        )
        # Add retry configuration (default behavior has all errors are retried)
        self.task_process_pdf.add_retry(
            max_attempts=5,  # Retry up to 5 times (Bedrock has as of now errors eventually)
            interval=Duration.seconds(1),  # Wait 1 seconds between retries
            backoff_rate=2.0,  # Exponential backoff multiplier
        )

        self.task_process_other = aws_sfn_tasks.LambdaInvoke(
            self,
            "Task-ProcessOther",
            state_name="Process Other",
            lambda_function=self.lambda_state_machine_process_idp_processing,
            payload=aws_sfn.TaskInput.from_object(
                {
                    "event.$": "$",
                    "params": {
                        "class_name": "ProcessOther",
                        "method_name": "process_other",
                    },
                }
            ),
            output_path="$.Payload",
        )

        self.task_save_data = aws_sfn_tasks.LambdaInvoke(
            self,
            "Task-SaveData",
            state_name="Save Data",
            lambda_function=self.lambda_state_machine_process_idp_processing,
            payload=aws_sfn.TaskInput.from_object(
                {
                    "event.$": "$",
                    "params": {
                        "class_name": "SaveData",
                        "method_name": "save_data",
                    },
                }
            ),
            output_path="$.Payload",
        )
        # Add retry configuration (default behavior has all errors are retried)
        self.task_save_data.add_retry(
            max_attempts=5,  # Retry up to 5 times (Bedrock has as of now errors eventually)
            interval=Duration.seconds(1),  # Wait 1 seconds between retries
            backoff_rate=2.0,  # Exponential backoff multiplier
        )

        self.task_not_implemented = aws_sfn.Pass(
            self,
            "Task-NotImplemented",
            comment="Not implemented yet",
        )

        self.task_process_success = aws_sfn_tasks.LambdaInvoke(
            self,
            "Task-Success",
            state_name="Process Success",
            lambda_function=self.lambda_state_machine_process_idp_processing,
            payload=aws_sfn.TaskInput.from_object(
                {
                    "event.$": "$",
                    "params": {
                        "class_name": "Success",
                        "method_name": "process_success",
                    },
                }
            ),
            output_path="$.Payload",
        )

        self.task_process_failure = aws_sfn_tasks.LambdaInvoke(
            self,
            "Task-Failure",
            state_name="Process Failure",
            lambda_function=self.lambda_state_machine_process_idp_processing,
            payload=aws_sfn.TaskInput.from_object(
                {
                    "event.$": "$",
                    "params": {
                        "class_name": "Failure",
                        "method_name": "process_failure",
                    },
                }
            ),
            output_path="$.Payload",
        )

        self.task_success = aws_sfn.Succeed(
            self,
            id="Succeed",
            comment="Successful execution of State Machine",
        )

        self.task_failure = aws_sfn.Fail(
            self,
            id="Exception Handling Finished",
            comment="State Machine Exception or Failure",
        )

    def create_state_machine_definition(self) -> None:
        """
        Method to create the Step Function State Machine definition.
        """

        # Conditions to simplify Choices in the State Machine
        self.choice_image = aws_sfn.Condition.string_equals("$.input_type", "image")
        self.choice_pdf = aws_sfn.Condition.string_equals("$.input_type", "pdf")
        self.choice_other = aws_sfn.Condition.string_equals("$.input_type", "other")

        # State Machine event type initial configuration entrypoints
        self.state_machine_definition = self.task_validate_input.next(
            aws_sfn.Choice(self, "Input Type?")
            .when(self.choice_image, self.task_pass_image)
            .when(self.choice_pdf, self.task_pass_pdf)
            .when(self.choice_other, self.task_pass_other)
        )

        # Pass States entrypoints
        self.task_pass_image.next(self.task_process_image.next(self.task_save_data))
        self.task_pass_pdf.next(self.task_process_pdf.next(self.task_save_data))
        self.task_pass_other.next(self.task_not_implemented)

        self.task_save_data.next(self.task_process_success)
        self.task_not_implemented.next(self.task_process_success)

        self.task_process_success.next(self.task_success)

        # TODO: Add failure handling for the State Machine with "process_failure"
        # self.task_process_failure.next(self.task_failure)

    def create_state_machine(self) -> None:
        """
        Method to create the Step Function State Machine for processing the messages.
        """

        log_group_name = f"/aws/vendedlogs/states/{self.main_resources_name}"
        self.state_machine_log_group = aws_logs.LogGroup(
            self,
            "StateMachine-LogGroup",
            log_group_name=log_group_name,
            removal_policy=RemovalPolicy.DESTROY,
        )
        Tags.of(self.state_machine_log_group).add("Name", log_group_name)

        self.state_machine = aws_sfn.StateMachine(
            self,
            "StateMachine-IDPProcessing",
            state_machine_name=f"{self.main_resources_name}-document-processing",
            state_machine_type=aws_sfn.StateMachineType.EXPRESS,
            definition_body=aws_sfn.DefinitionBody.from_chainable(
                self.state_machine_definition,
            ),
            logs=aws_sfn.LogOptions(
                destination=self.state_machine_log_group,
                include_execution_data=True,
                level=aws_sfn.LogLevel.ALL,
            ),
        )

    def configure_s3_trigger_state_machine(self) -> None:
        """
        Method to configure the S3 Event to trigger for the Step Function State Machine.
        """

        # Create EventBridge rule to trigger the Step Function State Machine
        self.eventbridge_rule_s3_trigger = aws_events.Rule(
            self,
            "EventBridge-Rule-S3Trigger",
            rule_name=f"{self.main_resources_name}-s3-trigger-state-machine",
            description="EventBridge Rule to trigger the Step Function State Machine from S3 Event",
            event_pattern=aws_events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created", "Object Updated"],
                detail={
                    "bucket": {
                        "name": [self.s3_bucket_receipts.bucket_name],
                    },
                },
            ),
        )
        self.eventbridge_rule_s3_trigger.add_target(
            aws_events_targets.SfnStateMachine(self.state_machine)
        )

    def create_rest_api(self):
        """
        Method to create the REST-API Gateway for exposing the "DOCUMENTS"
        functionalities.
        """
        rest_api_name = self.app_config["api_gw_name"]

        # TODO: as of now only X-API key, later add cognito...
        self.api_method_options_public = aws_apigw.MethodOptions(
            api_key_required=False,
            authorization_type=aws_apigw.AuthorizationType.NONE,
            authorizer=None,
        )
        self.api_method_options_private = aws_apigw.MethodOptions(
            api_key_required=True,
            authorization_type=aws_apigw.AuthorizationType.NONE,
            authorizer=None,
        )

        self.api = aws_apigw.LambdaRestApi(
            self,
            "RESTAPI",
            rest_api_name=rest_api_name,
            description=f"REST API Gateway for {self.main_resources_name}",
            handler=self.lambda_documents_api,
            deploy_options=aws_apigw.StageOptions(
                stage_name=self.deployment_environment,
                description=f"REST API for {self.main_resources_name} in {self.deployment_environment} environment",
                metrics_enabled=True,
            ),
            default_cors_preflight_options=aws_apigw.CorsOptions(
                allow_origins=aws_apigw.Cors.ALL_ORIGINS,
                allow_methods=aws_apigw.Cors.ALL_METHODS,
                allow_headers=["*"],
            ),
            endpoint_types=[aws_apigw.EndpointType.REGIONAL],
            cloud_watch_role=False,
            proxy=False,  # Proxy disabled to have more control
        )

        # API Key (used for authentication via "x-api-key" header in request)
        rest_api_key = self.api.add_api_key(
            "RESTAPI-Key",
            api_key_name=rest_api_name,
        )
        Tags.of(self.api).add("Name", rest_api_name)

        # API Usage Plan (to associate the API Key with the API Stage)
        usage_plan = self.api.add_usage_plan(
            "RESTAPI-UsagePlan",
            name=rest_api_name,
            api_stages=[
                aws_apigw.UsagePlanPerApiStage(
                    api=self.api, stage=self.api.deployment_stage
                )
            ],
            throttle=aws_apigw.ThrottleSettings(
                rate_limit=self.app_config["api_usage_plan_throttle_rate_limit"],
                burst_limit=self.app_config["api_usage_plan_throttle_burst_limit"],
            ),
            quota=aws_apigw.QuotaSettings(
                limit=self.app_config["api_usage_plan_quota_limit_day"],
                period=aws_apigw.Period.DAY,
            ),
            description=f"Usage plan for {self.main_resources_name} API",
        )
        usage_plan.add_api_key(rest_api_key)

    def configure_rest_api(self):
        """
        Method to configure the REST-API Gateway with resources and methods (simple way).
        Note: simple config, with proxy... Can be more granular/specific if needed.
        """

        # Define REST-API resources
        root_resource_api = self.api.root.add_resource("api")
        root_resource_v1 = root_resource_api.add_resource("v1")

        # Endpoints ("docs" without auth and "documents" with auth)
        root_resource_docs: aws_apigw.Resource = root_resource_v1.add_resource(
            "docs",
            default_method_options=self.api_method_options_public,
        )
        root_resource_documents = root_resource_v1.add_resource(
            "documents",
            default_method_options=self.api_method_options_private,
        )

        # Define all API-Lambda integrations for the API methods
        api_lambda_integration_documents = aws_apigw.LambdaIntegration(
            self.lambda_documents_api
        )

        # Enable proxies for the "/api/v1/docs" swagger endpoints (public)
        root_resource_docs.add_method("GET", api_lambda_integration_documents)
        root_resource_docs.add_proxy(
            any_method=True,  # To don't explicitly adding methods on the `proxy` resource
            default_integration=api_lambda_integration_documents,
        )

        # Enable proxies for the "/api/v1/documents" endpoints
        root_resource_documents.add_method("GET", api_lambda_integration_documents)
        root_resource_documents.add_method("POST", api_lambda_integration_documents)
        root_resource_documents.add_method("PATCH", api_lambda_integration_documents)
        root_resource_documents.add_method("DELETE", api_lambda_integration_documents)
        root_resource_documents.add_proxy(
            any_method=True,  # To don't explicitly adding methods on the `proxy` resource
            default_integration=api_lambda_integration_documents,
            # default_method_options=self.api_method_options_private,
        )

    def generate_cloudformation_outputs(self) -> None:
        """
        Method to add the relevant CloudFormation outputs.
        """

        CfnOutput(
            self,
            "DeploymentEnvironment",
            value=self.app_config["deployment_environment"],
            description="Deployment environment",
        )

        CfnOutput(
            self,
            "APIDocs",
            value=f"https://{self.api.rest_api_id}.execute-api.{self.region}.amazonaws.com/{self.deployment_environment}/api/v1/docs",
            description="API endpoint Docs",
        )

        CfnOutput(
            self,
            "APIDocuments",
            value=f"https://{self.api.rest_api_id}.execute-api.{self.region}.amazonaws.com/{self.deployment_environment}/api/v1/documents",
            description="API endpoint Documents",
        )
