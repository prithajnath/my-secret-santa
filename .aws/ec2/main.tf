resource "aws_instance" "private-instance" {
  ami           = var.instance_ami
  instance_type = "t3a.large"

  subnet_id = var.private_subnet_id

  vpc_security_group_ids = [var.ssh_id, var.inbound_http_id]

  key_name = var.key_name
  
  tags = {
    Name = "private-instance"
  }
}