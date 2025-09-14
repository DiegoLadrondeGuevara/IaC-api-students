provider "aws" {
  region = "us-east-1"
}

variable "account_id" {
  default = "149521578179"
}

variable "vpc_id" {
  default = "vpc-08ed223bfdfc22f50"
}

variable "subnet_ids" {
  default = [
    "subnet-0587d39bd30583f10", # Subred 1
    "subnet-0de6def124f822a7e"  # Subred 2
  ]
}

variable "iam_role_arn" {
  default = "arn:aws:iam::149521578179:role/LabRole"
}

variable "sg_id" {
  default = "sg-09ce4ffb028b6bb1d"  # Security Group que mencionaste
}

resource "aws_ecs_cluster" "cluster" {
  name = "api-students-cluster"
}

resource "aws_lb" "alb" {
  name               = "api-students-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.sg_id]  # Usamos el SG adecuado
  subnets            = var.subnet_ids
}

resource "aws_lb_target_group" "tg" {
  name     = "api-students-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }
}

resource "aws_lb_listener" "listener" {
  load_balancer_arn = aws_lb.alb.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.tg.arn
  }
}

resource "aws_ecs_task_definition" "task" {
  family                   = "api-students-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"

  execution_role_arn = var.iam_role_arn
  task_role_arn      = var.iam_role_arn

  container_definitions = jsonencode([{
    name      = "api-students"
    image     = "${var.account_id}.dkr.ecr.us-east-1.amazonaws.com/api-students:latest"
    essential = true
    portMappings = [
      {
        containerPort = 8000
        protocol      = "tcp"
      }
    ]
  }])
}

resource "aws_ecs_service" "service" {
  name            = "api-students-service"
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.task.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.subnet_ids
    assign_public_ip = true
    security_groups = [var.sg_id]  # Usamos el SG adecuado para el ECS Service
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.tg.arn
    container_name   = "api-students"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.listener]
}
