provider "aws" {
  region = "us-west-2"
}

module "santa-vpc" {
    source = "./vpc"
}

module "santa-bastion"{
    source = "./bastion"
    key_path = "keys/pub_key.pub"
    vpc_id = module.santa-vpc.id
    public_subnet_id = module.santa-vpc.public_subnet_id
    instance_ami = "ami-0964eb2dc8b836eb6"
}

module "santa-ec2"{
    source = "./ec2"
    key_name = module.santa-bastion.ssh_key_name
    private_subnet_id = module.santa-vpc.private_subnet_id
    instance_ami = "ami-0964eb2dc8b836eb6"
    ssh_id = module.santa-bastion.ssh_id
}