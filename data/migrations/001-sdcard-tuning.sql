-- Optional, one-time migration for an existing MariaDB database.
-- Back up first, select DB_NAME, and run during a maintenance window.
-- No log rows are deleted. Dropping FULLTEXT can take time on a large table.
-- Skip the DROP INDEX if external applications use MATCH(Message) AGAINST(...).
DROP EVENT IF EXISTS cleanup_logs;
DROP INDEX IF EXISTS Message ON SystemEvents;
