from aws_cdk import App, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_logs as logs

class MyStack(Stack):
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # VPC
        vpc = ec2.Vpc(self, "VPC", max_azs=2)  # 2 AZs (availability zones)

        # ECS Cluster
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)
        
        # Fargate service with Application Load Balancer
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "FargateService",
            cluster=cluster,
            cpu=512,  # CPU units for the task
            memory_limit_mib=1024,  # Memory in MiB for the task
            desired_count=1,  # Desired number of tasks
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_registry("149521578179.dkr.ecr.us-east-1.amazonaws.com/api-students"),  # Your ECR image
                container_port=8000,  # Port that the container will expose
                log_driver=ecs.AwsLogDriver(stream_prefix="ecs", log_group=logs.LogGroup(self, "LG", log_group_name="/ecs/api-students"))
            ),
            public_load_balancer=True,  # Expose to public internet
            health_check=ecs.HealthCheck(path="/health", healthy_http_codes="200")
        )

app = App()
MyStack(app, "MyStack")
app.synth()