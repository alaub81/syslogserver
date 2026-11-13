#!/usr/bin/env python3
"""Retention safety/error checks without a running database: python3 -m unittest discover -s tests -p 'test_*.py'."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'resources/dbcleanup/dbcleanup.sh'


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.trace = self.directory / 'trace.jsonl'
        client = self.directory / 'mariadb'
        client.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
trace = pathlib.Path(os.environ['TEST_TRACE'])
query = next(a.removeprefix('--execute=') for a in sys.argv if a.startswith('--execute='))
previous = trace.read_text().splitlines() if trace.exists() else []
with trace.open('a') as stream:
    stream.write(json.dumps(query) + '\\n')
if 'DATE_FORMAT' in query:
    print('2026-10-01 00:00:00')
elif os.environ.get('TEST_DB_FAIL'):
    print('simulated SQL error', file=sys.stderr)
    sys.exit(1)
else:
    print(json.loads(os.environ['TEST_COUNTS'])[len(previous) - 1])
''')
        client.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.directory) + os.pathsep + os.environ['PATH'],
                        DB_PASSWORD='test', LOG_RETENTION_DAYS='7',
                        DBCLEANUP_BATCH_SIZE='3', DBCLEANUP_BATCH_PAUSE='0',
                        TEST_COUNTS='[3, 3, 1]', TEST_TRACE=str(self.trace))

    def run_cleanup(self, **env):
        return subprocess.run(['bash', str(SCRIPT)], env=dict(self.env, **env),
                              capture_output=True, text=True)

    def test_multiple_batches_use_fixed_cutoff_and_finish(self):
        result = self.run_cleanup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('deleted 7 row(s)', result.stdout)
        queries = [json.loads(line) for line in self.trace.read_text().splitlines()]
        self.assertEqual(len(queries), 4)
        self.assertEqual(sum('DATE_FORMAT' in query for query in queries), 1)
        for query in queries[1:]:
            self.assertIn("ReceivedAt < '2026-10-01 00:00:00'", query)
            self.assertIn('ORDER BY ReceivedAt, ID LIMIT 3', query)
        self.assertNotIn('OPTIMIZE', ''.join(queries))

    def test_no_expired_rows(self):
        result = self.run_cleanup(TEST_COUNTS='[0]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('deleted 0 row(s)', result.stdout)

    def test_sql_error_is_reported_as_failure(self):
        result = self.run_cleanup(TEST_DB_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('simulated SQL error', result.stderr)
        self.assertNotIn('Cleanup complete', result.stdout)

    def test_invalid_row_count_is_failure(self):
        result = self.run_cleanup(TEST_COUNTS='["unexpected"]')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Cleanup complete', result.stdout)

    def test_invalid_settings_never_contact_database(self):
        for key, values in {
            'LOG_RETENTION_DAYS': ['0', '-1', '7; DELETE FROM SystemEvents', '01'],
            'DBCLEANUP_BATCH_SIZE': ['0', '-1', '10001', '3.5'],
            'DBCLEANUP_BATCH_PAUSE': ['-1', 'invalid', '0; exit 0'],
        }.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    result = self.run_cleanup(**{key: value})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(self.trace.exists())


if __name__ == '__main__':
    unittest.main()
