"""Run RLS/RPC checks in a disposable local PostgreSQL cluster, never Supabase.

Requires initdb/pg_ctl/psql on PATH, STORM_POSTGRES_BIN, or a local install.

Listens on 127.0.0.1 on a port picked free at startup, rather than on a Unix
socket: Windows has no Unix sockets, and a single path keeps the two platforms
running the same test. A loopback listener is reachable by anything else on
the machine, so `trust` would be too loose here — the cluster is created with
scram-sha-256 and a password generated per run, handed to psql through the
environment and never written to the command line.
"""
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

ROOT = Path(__file__).resolve().parents[1]
ADMIN = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
OTHER = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
MEMBER = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
NEW = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'


def _postgres_bin():
    """The directory holding initdb, or None when there is no install to use."""
    directory = os.getenv('STORM_POSTGRES_BIN')
    if not directory and shutil.which('initdb'):
        directory = str(Path(shutil.which('initdb')).parent)
    if not directory:
        # Installers that do not put themselves on PATH: EDB on macOS, and the
        # same installer's default location on Windows.
        for candidate in sorted(Path('/Library/PostgreSQL').glob('*/bin/initdb'), reverse=True):
            directory = str(candidate.parent)
            break
    if not directory:
        for root in (Path('C:/Program Files/PostgreSQL'), Path('C:/Program Files (x86)/PostgreSQL')):
            for candidate in sorted(root.glob('*/bin/initdb.exe'), reverse=True):
                directory = str(candidate.parent)
                break
            if directory:
                break
    return directory


def _free_port():
    """A port nothing is listening on, released before postgres claims it."""
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


class MemberDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = _postgres_bin()
        if not directory:
            raise unittest.SkipTest('PostgreSQL binaries are not installed')
        cls.bin = Path(directory)
        # ignore_cleanup_errors: Windows refuses to unlink a file another
        # process still holds, and a slow postgres shutdown would otherwise
        # turn a passing run into an error raised from the teardown.
        cls.temp = tempfile.TemporaryDirectory(prefix='storm-db-', ignore_cleanup_errors=True)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.data = cls.base/'data'
        cls.port = _free_port()
        cls.password = secrets.token_urlsafe(24)
        cls.env = {**os.environ, 'PGPASSWORD': cls.password}
        pwfile = cls.base/'pwfile'
        pwfile.write_text(cls.password, encoding='utf-8')
        subprocess.run([str(cls.bin/'initdb'), '-D', str(cls.data), '-U', 'storm_test',
            '-A', 'scram-sha-256', f'--pwfile={pwfile}', '--no-locale', '--encoding=UTF8'],
            check=True, capture_output=True)
        pwfile.unlink()
        cls.pg_ctl('-l', str(cls.base/'postgres.log'),
            '-o', f'-F -h 127.0.0.1 -p {cls.port}', '-w', 'start')
        cls.addClassCleanup(lambda: cls.pg_ctl('-m', 'immediate', '-w', 'stop'))
        cls.sql('''
create role anon;
create role authenticated;
create role service_role bypassrls;
create schema auth;
create table auth.users (id uuid primary key, email text, created_at timestamptz default now(), raw_user_meta_data jsonb default '{}');
create function auth.jwt() returns jsonb language sql stable as $$ select coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb $$;
create function auth.uid() returns uuid language sql stable as $$ select (auth.jwt()->>'sub')::uuid $$;
grant usage on schema auth to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
''')
        schema = (ROOT/'docs/supabase-schema.sql').read_text()
        cls.sql(schema)
        cls.sql(schema)  # An existing deployment can rerun the migration.

    @classmethod
    def pg_ctl(cls, *arguments):
        """Run pg_ctl without holding a pipe open for the server's lifetime.

        `pg_ctl start` hands the server its own stdout and stderr. Captured
        through a pipe, that pipe stays open for as long as postgres runs, and
        the caller waits on EOF that only arrives when the cluster shuts down
        — so `capture_output=True` here hangs on Windows rather than starting
        a database. Output goes to a file instead, quoted back on failure.
        """
        log = cls.base/'pg_ctl.log'
        with open(log, 'w', encoding='utf-8') as handle:
            result = subprocess.run([str(cls.bin/'pg_ctl'), '-D', str(cls.data), *arguments],
                stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT)
        if result.returncode:
            detail = log.read_text(encoding='utf-8', errors='replace').strip()
            server = cls.base/'postgres.log'
            if server.exists():
                detail += '\n' + server.read_text(encoding='utf-8', errors='replace').strip()
            raise AssertionError(f'pg_ctl {" ".join(arguments)} failed:\n{detail}')

    @classmethod
    def sql(cls, statement, ok=True):
        result = subprocess.run([str(cls.bin/'psql'), '-X', '-q', '-t', '-A', '-v', 'ON_ERROR_STOP=1',
            '-h', '127.0.0.1', '-p', str(cls.port), '-U', 'storm_test', '-d', 'postgres', '-c', statement],
            text=True, capture_output=True, env=cls.env, stdin=subprocess.DEVNULL)
        if ok and result.returncode:
            raise AssertionError(result.stderr)
        if not ok and not result.returncode:
            raise AssertionError('SQL operation unexpectedly succeeded')
        return result.stdout.strip() if ok else result.stderr

    @classmethod
    def as_user(cls, uid, statement, ok=True, role='authenticated'):
        claims = json.dumps({'sub': uid, 'role':role, 'email': uid+'@example.com'})
        return cls.sql(f"set role {role}; select set_config('request.jwt.claims', '{claims}', false); {statement}", ok=ok)

    def setUp(self):
        self.sql("truncate public.member_audit_log, public.runs, public.profiles; delete from auth.users;")
        for uid in [ADMIN, OTHER, MEMBER, NEW]:
            self.sql(f"insert into auth.users(id,email) values('{uid}','{uid}@example.com');")
        for uid in [ADMIN, OTHER, MEMBER]:
            self.as_user(uid, f"insert into public.profiles(id,email,display_name) values('{uid}','{uid}@example.com','Test member');")
        self.sql(f"update public.profiles set role='admin' where id in ('{ADMIN}','{OTHER}'); truncate public.member_audit_log;")

    def test_self_demotion_suspension_and_delete_are_denied(self):
        for change in ["new_role => 'member'", 'new_active => false']:
            error = self.as_user(ADMIN, f"select public.admin_set_profile('{ADMIN}', {change});", ok=False)
            self.assertIn('cannot demote or suspend your own account', error)
        self.assertIn('permission denied', self.as_user(ADMIN, f"delete from public.profiles where id='{ADMIN}';", ok=False))
        self.assertEqual(self.sql(f"select role||':'||is_active::text from public.profiles where id='{ADMIN}';"), 'admin:true')

    def test_batch_rolls_back_all_changes_and_audit_on_error(self):
        edits = [{'target':MEMBER,'changes':{'monthly_run_limit':30}}, {'target':ADMIN,'changes':{'role':'member'}}]
        self.as_user(ADMIN, f"select public.admin_set_profiles('{json.dumps(edits)}');", ok=False)
        self.assertEqual(self.sql(f"select monthly_run_limit from public.profiles where id='{MEMBER}';"), '10')
        self.assertEqual(self.sql('select count(*) from public.member_audit_log;'), '0')

    def test_successful_edits_audit_and_stale_baseline(self):
        edit = {'target':MEMBER,'changes':{'is_active':False},'expected':{'role':'member','monthly_run_limit':10,'is_active':True}}
        self.as_user(ADMIN, f"select public.admin_set_profiles('{json.dumps([edit])}');")
        self.assertEqual(self.sql("select source||':'||outcome from public.member_audit_log;"), 'admin_edit:success')
        self.assertEqual(self.sql('select actor_id from public.member_audit_log;'), ADMIN)
        edit['changes'] = {'monthly_run_limit':30}
        self.assertIn('member changed', self.as_user(ADMIN, f"select public.admin_set_profiles('{json.dumps([edit])}');", ok=False))
        self.assertEqual(self.sql(f"select monthly_run_limit from public.profiles where id='{MEMBER}';"), '10')

    def test_members_cannot_escalate_or_forge_provenance_or_audit(self):
        self.assertIn('not authorised', self.as_user(MEMBER, f"select public.admin_set_profile('{MEMBER}',new_role=>'admin');",ok=False))
        for statement in [f"update public.profiles set role='admin' where id='{MEMBER}';",
            f"update public.profiles set created_via='admin_create' where id='{MEMBER}';",
            f"insert into public.profiles(id,email,role) values('{NEW}','{NEW}@example.com','admin');",
            "delete from public.member_audit_log;",
            "insert into public.member_audit_log(event,source,outcome) values('account_created','admin_create','success');",
            f"select public.register_account_creation('{NEW}','admin_create','{ADMIN}');",
            f"select public.admin_creation_ready('{MEMBER}');"]:
            self.as_user(MEMBER, statement, ok=False)

    def test_suspended_users_and_admins_have_no_run_or_management_access(self):
        self.as_user(MEMBER, f"insert into public.runs(user_id,topic) values('{MEMBER}','Test');")
        self.as_user(ADMIN, f"select public.admin_set_profile('{MEMBER}',new_active=>false);")
        output = self.as_user(MEMBER, 'select count(*) from public.runs;')
        self.assertTrue(output.endswith('\n0'), output)
        self.as_user(MEMBER, f"insert into public.runs(user_id,topic) values('{MEMBER}','Blocked');",ok=False)
        self.as_user(ADMIN, f"select public.admin_set_profile('{OTHER}',new_active=>false);")
        self.assertIn('not authorised', self.as_user(OTHER, f"select public.admin_set_profile('{MEMBER}',new_active=>true);",ok=False))

    def test_backend_creation_records_auth_identity_and_verified_creator(self):
        self.as_user(ADMIN, f"select public.register_account_creation('{NEW}','admin_create','{ADMIN}');", role='service_role')
        self.assertEqual(self.sql(f"select role||':'||created_via||':'||created_by::text from public.profiles where id='{NEW}';"), 'member:admin_create:'+ADMIN)
        self.assertEqual(self.sql('select event||\':\'||source from public.member_audit_log;'), 'account_created:admin_create')
        self.as_user(ADMIN, f"select public.register_account_creation('{NEW}','admin_create','{ADMIN}');", role='service_role')
        self.assertEqual(self.sql('select count(*) from public.member_audit_log;'), '1')
        self.assertTrue(self.as_user(MEMBER,'select count(*) from public.member_audit_log;').endswith('\n0'))
        self.assertTrue(self.as_user(ADMIN,'select count(*) from public.member_audit_log;').endswith('\n1'))

    def test_concurrent_cross_demotions_leave_one_active_admin(self):
        barrier=Barrier(2)
        def demote(actor, target):
            barrier.wait()
            try:
                self.as_user(actor, f"select public.admin_set_profile('{target}',new_role=>'member');")
                return True
            except AssertionError:
                return False
        with ThreadPoolExecutor(max_workers=2) as executor:
            first=executor.submit(demote, ADMIN, OTHER)
            second=executor.submit(demote, OTHER, ADMIN)
            self.assertEqual(sum([first.result(),second.result()]), 1)
        self.assertEqual(self.sql("select count(*) from public.profiles where role='admin' and is_active;"),'1')

if __name__ == '__main__': unittest.main()
