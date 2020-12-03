output "id" {
  value = aws_vpc.vpc.id
}

output "nat_gateway_id" {
  value = aws_nat_gateway.nat-gw.id
}

output "public_subnet_id" {
    value = aws_subnet.public-subnet.id
}

output "public_subnet_cidr" {
    value = aws_subnet.public-subnet.cidr_block
}

output "second_public_subnet_id" {
    value = aws_subnet.second-public-subnet.id
}

output "second_public_subnet_cidr" {
    value = aws_subnet.second-public-subnet.cidr_block
}

output "private_subnet_id"{
    value = aws_subnet.private-subnet.id
}

output "private_subnet_cidr" {
    value = aws_subnet.private-subnet.cidr_block
}