-- -------------------------------------------
-- Datenbank und Benutzer einrichten
-- -------------------------------------------

CREATE DATABASE IF NOT EXISTS syslogdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'syslog'@'%' IDENTIFIED BY 'syslogpass';
GRANT ALL PRIVILEGES ON syslogdb.* TO 'syslog'@'%';
FLUSH PRIVILEGES;

USE syslogdb;

-- -------------------------------------------
-- Haupttabelle für LogAnalyzer
-- -------------------------------------------

CREATE TABLE IF NOT EXISTS SystemEvents (
  ID int unsigned NOT NULL AUTO_INCREMENT PRIMARY KEY,
  CustomerID bigint,
  ReceivedAt datetime NOT NULL,
  DeviceReportedTime datetime NOT NULL,
  Facility smallint NOT NULL,
  Priority smallint NOT NULL,
  FromHost varchar(60) NOT NULL,
  Message text,
  NTSeverity int,
  Importance int,
  EventSource varchar(60),
  EventUser varchar(60),
  EventCategory int,
  EventID int,
  EventBinaryData text,
  MaxAvailable int,
  CurrUsage int,
  MinUsage int,
  MaxUsage int,
  InfoUnitID int,
  SysLogTag varchar(60),
  EventLogType varchar(60),
  GenericFileName varchar(60),
  SystemID int,
  ProcessID int,
  checksum varchar(64) DEFAULT NULL
);

-- -------------------------------------------
-- Zusatzdaten für strukturierte Logs
-- -------------------------------------------

CREATE TABLE IF NOT EXISTS SystemEventsProperties (
  ID int unsigned NOT NULL AUTO_INCREMENT PRIMARY KEY,
  SystemEventID int,
  ParamName varchar(255),
  ParamValue text
);
