FROM buildkite/puppeteer:latest

WORKDIR /usr/bin/santa-puppet

RUN apt update
RUN DEBIAN_FRONTEND=noninteractive apt install -y libgconf-2-4 \
    libpq-dev \
    build-essential \
    wget \
    traceroute \
    curl \
    iputils-ping \
    bridge-utils \
    dnsutils \
    netcat-openbsd \
    jq \
    gnupg

COPY package.json package.json
COPY package-lock.json package-lock.json
COPY jest.config.js jest.config.js

COPY tests/js/*.js /usr/bin/santa-puppet/tests/js/

COPY test_end_to_end.sh test_end_to_end.sh

RUN npm i --global jest
RUN npm i

RUN groupadd -r pptruser && useradd -r -g pptruser -G audio,video pptruser \
    && mkdir -p /home/pptruser/Downloads \
    && chown -R pptruser:pptruser /home/pptruser \
    && chown -R pptruser:pptruser ./node_modules

RUN chmod u+x test_end_to_end.sh
RUN chown pptruser.pptruser test_end_to_end.sh

# Run everything after as non-privileged user.
USER pptruser

ENTRYPOINT ["./test_end_to_end.sh"]
