FROM debian:trixie-slim
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  curl \
  bash \
  mariadb-client \
  ca-certificates \
  tzdata \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH
RUN curl -fsSLo /usr/local/bin/supercronic \
  "https://github.com/aptible/supercronic/releases/download/v0.2.51/supercronic-linux-${TARGETARCH}" \
  && chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY dbcleanup.sh /app/dbcleanup.sh
COPY dbcleanup-entrypoint.sh /app/dbcleanup-entrypoint.sh
RUN chmod +x /app/dbcleanup.sh /app/dbcleanup-entrypoint.sh

ENTRYPOINT ["/app/dbcleanup-entrypoint.sh"]
