FROM alpine:latest

# Relevante Pakete installieren
RUN apk add --no-cache \
    syslog-ng \
    syslog-ng-openrc \
    syslog-ng-libdbi \
    libdbi-drivers \
    libdbi-drivers-mysql \
    mysql-client

# Konfigurationsverzeichnis vorbereiten
#COPY syslog-ng.conf /etc/syslog-ng/syslog-ng.conf

# Startkommando
CMD ["/usr/sbin/syslog-ng", "-F", "--no-caps"]