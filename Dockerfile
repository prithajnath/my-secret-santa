FROM python:3.10-bookworm

RUN apt update

# GCC and other essentials
RUN apt install -y libpq-dev \
	build-essential \
	gnupg2 \
	procps

# Networking tools
RUN apt install -y \
	lsb-release \
	traceroute \
	wget \
	curl \
	iputils-ping \
	bridge-utils \
	dnsutils \
	netcat-openbsd \
	jq \
	redis \
	nmap \
	net-tools \
	&& rm -rf /var/lib/apt/lists/*

# PSQL
RUN echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list | sh
RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

RUN apt update && apt install -y postgresql-client

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