"""Disposable local PostgreSQL verification; no production configuration loaded."""
from pathlib import Path
import os
import secrets
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
BIN = Path('C:/Users/shan_/Documents/Codex/2026-09-16/referenced-chatgpt-conversation-this-is-an-2/work/postgresql-runtime/pgsql/bin')
RUNTIME = ROOT / 'pg-test-runtime' / ('run-' + secrets.token_hex(8))
DATA = RUNTIME / 'data'
PORT = 56461

def main():
    if RUNTIME.exists():
        raise RuntimeError('Refusing to reuse an existing cluster directory')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', PORT))
    RUNTIME.mkdir(parents=True)
    password = secrets.token_urlsafe(32)
    pw = RUNTIME / 'init-password.txt'
    pw.write_text(password, encoding='ascii')
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('PG', 'DATABASE', 'DJANGO', 'PYTHONPATH'))}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    for key in list(os.environ):
        if key.upper().startswith(('PG', 'DATABASE', 'DJANGO', 'PYTHONPATH')):
            del os.environ[key]
    def run(name, *args):
        # A server child can retain inherited pipe handles. Use a regular file
        # so pg_ctl completion never waits for the server to close a pipe.
        log = RUNTIME / (name + '-' + secrets.token_hex(4) + '.log')
        with log.open('w') as output:
            result = subprocess.run([str(BIN / (name + '.exe')), *map(str, args)], env=env,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=60,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        print(log.read_text(), flush=True)
        result.check_returncode()
    started = False
    try:
        run('initdb', '-D', DATA, '-U', 'u61_test', '--pwfile', pw,
            '--auth=scram-sha-256', '--encoding=UTF8', '--locale=C')
        pw.unlink()
        with (DATA / 'postgresql.conf').open('a') as conf:
            conf.write("\nlisten_addresses='127.0.0.1'\nport=56461\nmax_connections=30\n"
                       "default_transaction_isolation='read committed'\n")
        (DATA / 'pg_hba.conf').write_text(
            'host all u61_test 127.0.0.1/32 scram-sha-256\n', encoding='ascii')
        run('pg_ctl', '-D', DATA, '-l', RUNTIME / 'server.log', '-w', 'start')
        started = True
        import psycopg2
        conn = psycopg2.connect(host='127.0.0.1', port=PORT, user='u61_test',
                               password=password, dbname='postgres', connect_timeout=5)
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT version(), current_setting('data_directory'), current_setting('listen_addresses'), current_setting('port'), current_setting('transaction_isolation')")
                version, directory, listen, port, isolation = cur.fetchone()
                assert Path(directory).resolve() == DATA.resolve()
                assert listen == '127.0.0.1' and port == str(PORT)
                print('VERIFIED CLUSTER:', version, directory, listen, port, isolation, flush=True)
                cur.execute('CREATE DATABASE u61_verification')
        finally:
            conn.close()
        os.environ['U6_PG_ISOLATED'] = 'u61-local-20261016'
        os.environ['U6_PG_PASSWORD'] = password
        os.environ['DJANGO_SETTINGS_MODULE'] = 'ai_assistant.stt.test_settings_postgresql'
        import django
        django.setup()
        from django.core.management import call_command
        # All HTTP must be mocked; accidental live requests fail immediately.
        with patch('requests.sessions.Session.request', side_effect=AssertionError('Live HTTP forbidden')):
            call_command('test', 'ai_assistant.stt.test_foundation', 'ai_assistant.stt.test_ledger',
                         'ai_assistant.stt.test_normalizer', 'ai_assistant.stt.test_postgresql',
                         'ai_assistant.stt.test_charge_migration',
                         verbosity=2, interactive=False)
        call_command('makemigrations', 'u6_stt', check=True, dry_run=True, verbosity=1)
    finally:
        if pw.exists():
            pw.unlink()
        # A partially successful start must also be stopped, but only this data directory.
        if started or (DATA / 'postmaster.pid').exists():
            run('pg_ctl', '-D', DATA, '-m', 'fast', '-w', 'stop')
        os.environ.pop('U6_PG_PASSWORD', None)

if __name__ == '__main__':
    main()
