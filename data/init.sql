-- MariaDB creates the database and application user from MARIADB_* variables.
-- Init scripts run only when the database volume is empty.

-- Main LogAnalyzer table.
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------
-- Properties for structured logs
-- -------------------------------------------

CREATE TABLE IF NOT EXISTS SystemEventsProperties (
  ID int unsigned NOT NULL AUTO_INCREMENT PRIMARY KEY,
  SystemEventID int,
  ParamName varchar(255),
  ParamValue text
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------
-- Indexes for LogAnalyzer queries and retention
-- ------------------------------------------------------------------

ALTER TABLE SystemEvents
  ADD KEY `FromHost` (`FromHost`),
  ADD KEY `SysLogTag` (`SysLogTag`),
  ADD KEY `Facility` (`Facility`),
  ADD KEY `Priority` (`Priority`),
  ADD KEY `ReceivedAt` (`ReceivedAt`),
  ADD KEY `DeviceReportedTime` (`DeviceReportedTime`);

-- ---------------------------------------
-- LogAnalyzer searches messages using LIKE/REGEXP, not MATCH ... AGAINST.
-- An unused FULLTEXT index adds work to every INSERT and DELETE.
-- Keep the ordinary filter indexes until query measurements justify changes.
-- Retention is handled in small batches by dbcleanup. InnoDB reuses deleted
-- space; routine OPTIMIZE would rebuild the whole table and wear out SD cards.
-- ---------------------------------------
