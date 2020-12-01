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
  domain_name       = "mysecretsanta.io"
  validation_method = "DNS"

  tags = {
    Environment = "test"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_elb" "santa-classic-elb" {
  name               = "santa-elastic-load-balancer"
  subnets = [module.santa-vpc.public_subnet_id]

  listener {
    instance_port     = 9000
    instance_protocol = "http"
    lb_port           = 80
    lb_protocol       = "http"
  }

  listener {
    instance_port      = 9000
    instance_protocol  = "http"
    lb_port            = 443
    lb_protocol        = "https"
    ssl_certificate_id = aws_acm_certificate.cert.id
  }

  health_check {
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 3
    target              = "HTTP:9000/"
    interval            = 30
  }

  instances                   = [module.santa-ec2.id]
  security_groups             = [aws_security_group.all_tcp_traffic_to_elb.id]
  cross_zone_load_balancing   = true
  idle_timeout                = 400
  connection_draining         = true
  connection_draining_timeout = 400
  
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