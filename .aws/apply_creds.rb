#!/usr/bin/env ruby

access_key_id, secret_access_key = `cat ~/.aws/credentials.csv`.split.slice(5,).split(",")
puts "AWS_ACCESS_KEY_ID=#{access_key_id}"
puts "AWS_SECRET_ACCESS_KEY=#{secret_access_key}"
