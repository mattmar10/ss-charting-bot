from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_sns as sns,
    aws_lambda as _lambda,
    aws_lambda_python_alpha as _alambda,
    aws_iam as iam,
    aws_logs as logs,
    aws_sns_subscriptions as subs,
    aws_s3 as s3,

)
from constructs import Construct
from dotenv import load_dotenv
import os
load_dotenv()


class SsChartingBotStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        log_group = logs.LogGroup(self, "SsChartingBotLogGroup",
                                  log_group_name="/aws/lambda/ss-charting-ds-bot-logger-grp",
                                  retention=logs.RetentionDays.ONE_WEEK)

        chart_bucket = s3.Bucket(self, "ss-chart-bucket",
                                 block_public_access=s3.BlockPublicAccess.BLOCK_ACLS,
                                 removal_policy=RemovalPolicy.DESTROY,  # Optional for development
                                 public_read_access=True)

        lambda_role = iam.Role(self, "SsChartDSBotRole",
                               assumed_by=iam.ServicePrincipal(
                                   "lambda.amazonaws.com"),
                               managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")])

        chart_bucket.grant_put(lambda_role)

        existing_topic_arn = 'arn:aws:sns:us-east-1:464570369687:SsDiscordBotStack-prod-ssdiscordchartcommandtopicB1E16849-jUtbEwxvxtbR'

        # Create a Python Lambda function
        command_handler_lambda = _alambda.PythonFunction(self, 'SsChartDiscordBotCommandHandler',
                                                         entry='./lambda_handlers/',
                                                         index='candlestick-maker.py',
                                                         runtime=_lambda.Runtime.PYTHON_3_8,
                                                         timeout=Duration.seconds(
                                                             30),
                                                         log_group=log_group,
                                                         role=lambda_role,
                                                         memory_size=512,
                                                         environment={
                                                             'FMP_API_KEY': os.getenv('FMP_API_KEY'),
                                                             'CHART_BUCKET': chart_bucket.bucket_name}
                                                         )

        # Get existing SNS topic
        existing_topic = sns.Topic.from_topic_arn(
            self, 'chart-command-topic', existing_topic_arn)

        existing_topic.add_subscription(
            subs.LambdaSubscription(command_handler_lambda))
