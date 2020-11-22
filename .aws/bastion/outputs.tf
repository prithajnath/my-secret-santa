output "ssh_id"{
    value = aws_security_group.allow-ssh.id
}

output "ssh_key_name" {
    value = aws_key_pair.mykeypair.key_name
}