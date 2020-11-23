provider "aws" {
  region = "us-west-2"
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
}