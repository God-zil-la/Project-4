"""Standalone SQLite/PostgreSQL verification; never loads production settings."""
from contextlib import ExitStack
from pathlib import Path
import os
import secrets
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
BIN = Path('C:/Users/shan_/Documents/Codex/2026-09-16/referenced-chatgpt-conversation-this-is-an-2/work/postgresql-runtime/pgsql/bin')
PORT = 56462


def suite(postgres):
    import django
    django.setup()
    from django.core.management import call_command
    tests = ['ai_assistant.tts.test_validation', 'ai_assistant.tts.test_authorization',
             'ai_assistant.tts.test_service',
             'ai_assistant.tts.test_message_access',
             'ai_assistant.tts.test_message_identity',
             'ai_assistant.tts.test_saved_service',
             'ai_assistant.tts.test_saved_synthesis',
             'ai_assistant.tts.test_saved_synthesis_db',
             'ai_assistant.tts.test_provider_openai',
             'ai_assistant.tts.test_api_views',
             'ai_assistant.tts.test_audio_storage',
             'ai_assistant.tts.test_audio_store_memory',
             'ai_assistant.tts.test_audio_access',
             'ai_assistant.tts.test_audio_access_db',
             'ai_assistant.tts.test_audio_retrieval',
             'ai_assistant.tts.test_audio_finalization',
             'ai_assistant.tts.test_audio_pipeline',
             'ai_assistant.tts.test_saved_synthesis_storage',
             'ai_assistant.tts.test_storage_integration']
    if postgres:
        tests.append('ai_assistant.tts.test_postgresql')
    # No provider HTTP can escape the test process. PostgreSQL uses local libpq.
    original_connect = socket.socket.connect
    def local_only(sock, address):
        if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', '::1'):
            raise AssertionError('External network forbidden')
        return original_connect(sock, address)
    with ExitStack() as stack:
        stack.enter_context(patch('requests.sessions.Session.request', side_effect=AssertionError('HTTP forbidden')))
        stack.enter_context(patch('socket.socket.connect', new=local_only))
        call_command('test', *tests, verbosity=2, interactive=False)
        call_command('makemigrations', 'u62_tts', check=True, dry_run=True)


def main():
    if sys.argv[1:] not in (['sqlite'], ['postgresql']):
        raise SystemExit('Usage: python -B -m ai_assistant.tts.verify sqlite|postgresql')
    postgres = sys.argv[1] == 'postgresql'
    for key in list(os.environ):
        if key.upper().startswith(('PG', 'DATABASE', 'DJANGO', 'PYTHONPATH', 'U62_')):
            del os.environ[key]
    (ROOT / 'runtime').mkdir(exist_ok=True)
    if not postgres:
        os.environ['DJANGO_SETTINGS_MODULE'] = 'ai_assistant.tts.test_settings'
        suite(False)
        return
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', PORT))
    runtime = ROOT / 'runtime' / ('pg-' + secrets.token_hex(8))
    runtime.mkdir()
    data = runtime / 'data'
    password = secrets.token_urlsafe(32)
    password_file = runtime / 'init-password.txt'
    password_file.write_text(password, encoding='ascii')
    def run(name, *args):
        log = runtime / (name + '-' + secrets.token_hex(4) + '.log')
        with log.open('w') as output:
            result = subprocess.run([str(BIN / (name + '.exe')), *map(str, args)],
                stdout=output, stderr=subprocess.STDOUT, timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW)
        print(log.read_text(), flush=True)
        result.check_returncode()
    try:
        run('initdb', '-D', data, '-U', 'u62_test', '--pwfile', password_file,
            '--auth=scram-sha-256', '--encoding=UTF8', '--locale=C')
        password_file.unlink()
        with (data / 'postgresql.conf').open('a') as conf:
            conf.write("\nlisten_addresses='127.0.0.1'\nport=56462\nmax_connections=30\n"
                       "default_transaction_isolation='read committed'\n")
        (data / 'pg_hba.conf').write_text('host all u62_test 127.0.0.1/32 scram-sha-256\n', encoding='ascii')
        run('pg_ctl', '-D', data, '-l', runtime / 'server.log', '-w', 'start')
        import psycopg2
        conn = psycopg2.connect(host='127.0.0.1', port=PORT, user='u62_test',
                               password=password, dbname='postgres', connect_timeout=5)
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT version(), current_setting('data_directory'), current_setting('listen_addresses'), current_setting('port'), current_setting('transaction_isolation')")
                version, directory, listen, port, isolation = cur.fetchone()
                if (Path(directory).resolve() != data.resolve() or listen != '127.0.0.1'
                        or port != str(PORT) or isolation != 'read committed'):
                    raise RuntimeError('Cluster isolation check failed')
                print('VERIFIED ISOLATED CLUSTER:', version, directory, isolation, flush=True)
                cur.execute('CREATE DATABASE u62_test')
        finally:
            conn.close()
        os.environ['U62_ISOLATED'] = 'mock-tests-only'
        os.environ['U62_PG_PASSWORD'] = password
        os.environ['DJANGO_SETTINGS_MODULE'] = 'ai_assistant.tts.test_settings_postgresql'
        suite(True)
    finally:
        password_file.unlink(missing_ok=True)
        if (data / 'postmaster.pid').exists():
            run('pg_ctl', '-D', data, '-m', 'fast', '-w', 'stop')
        os.environ.pop('U62_PG_PASSWORD', None)


if __name__ == '__main__':
    main()
