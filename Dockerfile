FROM python:3.8-slim-buster

RUN apt update

# GCC and other essentials
RUN apt install -y libpq-dev \
    build-essential \
    gnupg2 \
    procps

# Networking tools
RUN apt install -y \
	traceroute \
	curl \
	iputils-ping \
	bridge-utils \
	dnsutils \
	netcat-openbsd \
	jq \
	postgresql-client \
	nmap \
	net-tools \
    	&& rm -rf /var/lib/apt/lists/*

WORKDIR /usr/bin/secretsanta

COPY . .

RUN pip install -r requirements.txt
RUN chmod u+x entrypoint.sh
RUN chmod u+x dev-entrypoint.sh

EXPOSE 9000

ENTRYPOINT ["./entrypoint.sh"]