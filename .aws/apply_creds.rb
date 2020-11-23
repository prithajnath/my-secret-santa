#!/usr/bin/env ruby

access_key_id = `xsv select "Access key ID" ~/.aws/credentials.csv`.split("\n")[1]
secret_access_key = `xsv select "Secret access key" ~/.aws/credentials.csv`.split("\n")[1]
puts "AWS_ACCESS_KEY_ID=#{access_key_id}"
puts "AWS_SECRET_ACCESS_KEY=#{secret_access_key}"
