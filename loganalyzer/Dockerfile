FROM php:8.2-apache

# benötigte PHP-Extensions
RUN apt-get update && apt-get install -y unzip libzip-dev && \
    docker-php-ext-install mysqli && \
    apt-get clean

# Loganalyzer kopieren
COPY ./data/loganalyzer-${LOGANALYZER_VERSION}/src/ /var/www/html/

# Zugriffsrechte setzen
RUN chown -R www-data:www-data /var/www/html && chmod -R 755 /var/www/html