output "id" {
  value = aws_vpc.vpc.id
}

output "nat_gateway_id" {
  value = aws_nat_gateway.nat-gw.id
}

output "public_subnet_id" {
    value = aws_subnet.public-subnet.id
}

output "private_subnet_id"{
    value = aws_subnet.private-subnet.id
}