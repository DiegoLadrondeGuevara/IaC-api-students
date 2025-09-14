import pulumi
import pulumi_aws as aws
import json
from pulumi_aws import ecs, iam, cloudwatch, lb, ec2

# ========================
# Config (valores proporcionados)
# ========================
ECR_IMAGE = "149521578179.dkr.ecr.us-east-1.amazonaws.com/api-students"
CONTAINER_PORT = 8000
AWS_REGION = "us-east-1"

VPC_ID = "vpc-08ed223bfdfc22f50"
SUBNETS = [
    "subnet-0587d39bd30583f10",  # us-east-1c
    "subnet-0de6def124f822a7e",  # us-east-1e
]
# Usaremos este SG solo si quieres mantenerlo; de todos modos el código crea SGs propias más seguras.
EXISTING_SG = "sg-09ce4ffb028b6bb1d"

# ========================
# Crear SGs (ALB y Tasks) - más seguro que usar el mismo SG para todo
# ========================
alb_sg = ec2.SecurityGroup(
    "albSg",
    description="Allow HTTP inbound from internet",
    vpc_id=VPC_ID,
    ingress=[ec2.SecurityGroupIngressArgs(
        protocol="tcp", from_port=80, to_port=80, cidr_blocks=["0.0.0.0/0"]
    )],
    egress=[ec2.SecurityGroupEgressArgs(
        protocol="-1", from_port=0, to_port=0, cidr_blocks=["0.0.0.0/0"]
    )]
)

tasks_sg = ec2.SecurityGroup(
    "tasksSg",
    description="Allow traffic from ALB SG to container port",
    vpc_id=VPC_ID,
    ingress=[ec2.SecurityGroupIngressArgs(
        protocol="tcp", from_port=CONTAINER_PORT, to_port=CONTAINER_PORT, security_groups=[alb_sg.id]
    )],
    egress=[ec2.SecurityGroupEgressArgs(
        protocol="-1", from_port=0, to_port=0, cidr_blocks=["0.0.0.0/0"]
    )]
)

# ========================
# ECS Cluster
# ========================
cluster = ecs.Cluster("apiStudentsCluster")

# ========================
# CloudWatch Logs
# ========================
log_group = cloudwatch.LogGroup(
    "apiStudentsLogGroup",
    retention_in_days=7
)

# ========================
# IAM Role para ejecución de ECS
# ========================
exec_role = iam.Role(
    "apiStudentsExecRole",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
            "Effect": "Allow"
        }]
    })
)

iam.RolePolicyAttachment(
    "apiStudentsExecRoleAttachment",
    role=exec_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
)

# ========================
# ECS Task Definition
# Construimos el JSON de container_definitions dentro de un apply y
# nos aseguramos que todas las opciones sean strings.
# ========================
def make_container_definitions(lg_name):
    container = {
        "name": "api-students",
        "image": ECR_IMAGE,
        "essential": True,
        "portMappings": [{"containerPort": int(CONTAINER_PORT)}],
        "logConfiguration": {
            "logDriver": "awslogs",
            "options": {
                # forzamos strings con f-strings
                "awslogs-group": f"{lg_name}",
                "awslogs-region": f"{AWS_REGION}",
                "awslogs-stream-prefix": "ecs"
            }
        }
    }
    # Task expects a JSON string containing a LIST of containers
    return json.dumps([container])

container_definitions = log_group.name.apply(make_container_definitions)

task_def = ecs.TaskDefinition(
    "apiStudentsTaskDef",
    family="api-students",
    cpu="512",
    memory="1024",
    network_mode="awsvpc",
    requires_compatibilities=["FARGATE"],
    execution_role_arn=exec_role.arn,
    container_definitions=container_definitions
)

# ========================
# ALB (Application Load Balancer) - v2
# ========================
alb = lb.LoadBalancer(
    "apiStudentsALB",
    internal=False,
    load_balancer_type="application",
    security_groups=[alb_sg.id],
    subnets=SUBNETS
)

# Target group: ALB -> targets (Fargate IP) on CONTAINER_PORT
target_group = lb.TargetGroup(
    "apiStudentsTG",
    port=CONTAINER_PORT,
    protocol="HTTP",
    target_type="ip",
    vpc_id=VPC_ID,
    health_check=lb.TargetGroupHealthCheckArgs(
        path="/",          # ajusta si tu app tiene otro endpoint de health
        protocol="HTTP",
        matcher="200-399",
        interval=30,
        timeout=5,
        healthy_threshold=2,
        unhealthy_threshold=2
    )
)

listener = lb.Listener(
    "apiStudentsListener",
    load_balancer_arn=alb.arn,
    port=80,
    protocol="HTTP",
    default_actions=[{
        "type": "forward",
        "target_group_arn": target_group.arn
    }]
)

# ========================
# ECS Service
# ========================
ecs_service = ecs.Service(
    "apiStudentsService",
    cluster=cluster.id,
    task_definition=task_def.arn,
    desired_count=1,
    launch_type="FARGATE",
    network_configuration=ecs.ServiceNetworkConfigurationArgs(
        assign_public_ip=True,
        subnets=SUBNETS,
        security_groups=[tasks_sg.id]
    ),
    load_balancers=[ecs.ServiceLoadBalancerArgs(
        target_group_arn=target_group.arn,
        container_name="api-students",
        container_port=CONTAINER_PORT
    )],
    opts=pulumi.ResourceOptions(depends_on=[listener])
)

# ========================
# Outputs
# ========================
pulumi.export("alb_dns_name", alb.dns_name)
pulumi.export("ecr_image", ECR_IMAGE)
pulumi.export("container_port", CONTAINER_PORT)