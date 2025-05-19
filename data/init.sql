CREATE DATABASE syslogdb;
CREATE USER 'syslog'@'%' IDENTIFIED BY 'syslogpass';
GRANT ALL PRIVILEGES ON syslogdb.* TO 'syslog'@'%';
FLUSH PRIVILEGES;

USE syslogdb;

CREATE TABLE logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  received_at datetime default NULL,
  device_reporting text,
  facility int default NULL,
  priority int default NULL,
  program text,
  msg text,
  fromhost text,
  info_unit_id int,
  syslogtag text
);