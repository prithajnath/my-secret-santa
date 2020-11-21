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
	redis \
	nmap \
	net-tools \
    	&& rm -rf /var/lib/apt/lists/*

WORKDIR /usr/bin/secretsanta

COPY . .

RUN pip install -r requirements.txt
RUN chmod u+x entrypoint.sh
RUN chmod u+x dev-entrypoint.sh
RUN chmod u+x celery-init.sh


RUN groupadd --gid 5000 santaadmin \
    && useradd --home-dir /home/newuser --create-home --uid 5000 \
    --gid 5000 --shell /bin/sh --skel /dev/null santaadmin

EXPOSE 9000

ENTRYPOINT ["./entrypoint.sh"]