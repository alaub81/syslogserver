FROM debian:trixie-slim AS os-packages
ENV DEBIAN_FRONTEND=noninteractive

# Install syslog-ng with SQL support, logrotate and binary download tools.
RUN apt-get update \
  && apt-get upgrade -y --no-install-recommends \
  && apt-get install -y --no-install-recommends \
  syslog-ng \
  syslog-ng-mod-sql \
  libdbi1 \
  libdbd-mysql \
  mariadb-client \
  logrotate \
  curl \
  ca-certificates \
  tzdata \
  netcat-openbsd \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

FROM os-packages

# Download Supercronic for the target architecture.
ARG TARGETARCH
RUN curl -fsSLo /usr/local/bin/supercronic \
  "https://github.com/aptible/supercronic/releases/download/v0.2.51/supercronic-linux-${TARGETARCH}" \
  && chmod +x /usr/local/bin/supercronic

# The entrypoint generates logrotate configuration and starts both processes.
COPY syslogng-entrypoint.sh /usr/local/bin/syslogng-entrypoint.sh
RUN chmod +x /usr/local/bin/syslogng-entrypoint.sh

# syslog-ng stays in the foreground; Supercronic runs in the background.
CMD ["/usr/local/bin/syslogng-entrypoint.sh"]
