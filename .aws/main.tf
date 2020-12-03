provider "aws" {
  region = "us-east-1"
}

data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical
}


resource "aws_security_group" "all_tcp_traffic_to_elb" {
  name        = "allow_tcp_to_elb"
  description = "Allow TCP traffic to ELB (From the Internet and private subnets)"
  vpc_id      = module.santa-vpc.id

  ingress {
    from_port   = 0
    to_port     = 9999
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port       = 0
    to_port         = 0
    protocol        = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}


resource "aws_security_group" "inbound_traffic" {
  name        = "inbound_traffic"
  description = "Allow HTTP traffic from ELB"
  vpc_id      = module.santa-vpc.id

  ingress {
    from_port   = 9000
    to_port     = 9000
    protocol    = "tcp"
    cidr_blocks = [module.santa-vpc.public_subnet_cidr]
  }

  egress {
    from_port       = 0
    to_port         = 0
    protocol        = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  } 
}

resource "aws_acm_certificate" "cert" {
  domain_name       = "*.mysecretsanta.io"
  validation_method = "DNS"

  tags = {
    Environment = "test"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb" "santa-application-lb" {
  name               = "santa-application-lb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.all_tcp_traffic_to_elb.id]
  subnets            = [module.santa-vpc.public_subnet_id, module.santa-vpc.second_public_subnet_id]

}

resource "aws_lb_listener" "listen_for_https" {
  load_balancer_arn = aws_lb.santa-application-lb.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = aws_acm_certificate.cert.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.santa-lb-target-group.arn
  }

}


resource "aws_lb_listener" "https_redirect" {
  load_balancer_arn = aws_lb.santa-application-lb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_target_group" "santa-lb-target-group"{
  health_check{
    interval                = 10
    path                    = "/"
    protocol                = "HTTP"
    timeout                 = 5
    healthy_threshold       = 5
    unhealthy_threshold     = 2

  }

  name = "santa-lb-target-group"
  port = 80
  protocol = "HTTP"
  target_type = "instance"
  vpc_id  = module.santa-vpc.id
}


resource "aws_lb_target_group_attachment" "santa-ec2-target"{
  target_group_arn = aws_lb_target_group.santa-lb-target-group.arn
  target_id        = module.santa-ec2.id
  port             = 9000
}


module "santa-vpc" {
    source = "./vpc"
}

module "santa-bastion"{
    source = "./bastion"
    key_path = "keys/pub_key.pub"
    vpc_id = module.santa-vpc.id
    public_subnet_id = module.santa-vpc.public_subnet_id
    instance_ami = data.aws_ami.ubuntu.id
}

module "santa-ec2"{
    source = "./ec2"
    key_name = module.santa-bastion.ssh_key_name
    private_subnet_id = module.santa-vpc.private_subnet_id
    instance_ami = data.aws_ami.ubuntu.id
    ssh_id = module.santa-bastion.ssh_id
    inbound_http_id = aws_security_group.inbound_traffic.id
}