"""Protected member edits, admin provisioning, and actual Streamlit controls."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend/demo_light'))
import auth
from member_management import MemberManagementError, pending_edits, validate_changes
from streamlit.testing.v1 import AppTest

ADMIN = {'id': 'admin-id', 'display_name': 'Admin', 'email': 'admin@example.com',
         'role': 'admin', 'monthly_run_limit': 20, 'is_active': True, 'created_at': '2026-09-01'}
MEMBER = {'id': 'member-id', 'display_name': 'Member', 'email': 'member@example.com',
          'role': 'member', 'monthly_run_limit': 10, 'is_active': True, 'created_at': '2026-09-02'}

class MemberRulesTests(unittest.TestCase):
    def test_own_demotion_and_suspension_are_rejected(self):
        for fields in [{'role': 'member'}, {'is_active': False}]:
            with self.assertRaisesRegex(MemberManagementError, 'self_protected'):
                validate_changes('admin-id', 'admin-id', fields)
        validate_changes('admin-id', 'admin-id', {'monthly_run_limit': 30})

    def test_invalid_roles_status_and_limits_are_rejected(self):
        for fields in [{'role':'owner'}, {'is_active':'false'}, {'monthly_run_limit':-1},
                       {'monthly_run_limit':True}, {'monthly_run_limit':2**31}]:
            with self.assertRaises(MemberManagementError):
                validate_changes('member-id', 'admin-id', fields)

    def test_batch_contains_only_changed_fields_and_original_baseline(self):
        edited = {**MEMBER, 'role': 'admin'}
        changes = pending_edits([ADMIN, MEMBER], [ADMIN, edited], 'admin-id')
        self.assertEqual(changes, [{'target': 'member-id', 'changes': {'role': 'admin'},
            'expected': {'role':'member','monthly_run_limit':10,'is_active':True}}])
        self.assertEqual(pending_edits([ADMIN, MEMBER], [ADMIN, MEMBER], 'admin-id'), [])

class ProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.identity = SimpleNamespace(id='new-id')
        self.backend.auth.admin.create_user.return_value.user = self.identity
        self.client = Mock()
        self.client.auth.get_user.return_value.user = SimpleNamespace(id='admin-id')
        self.login = SimpleNamespace(access_token='admin-token', user=SimpleNamespace(id='admin-id'))
        for patcher in [patch.object(auth, 'dev_mode', return_value=False),
            patch.object(auth, 'session', return_value=self.login),
            patch.object(auth, 'user_id', return_value='admin-id'),
            patch.object(auth, '_client', return_value=self.client),
            patch.object(auth, '_service_client', return_value=self.backend)]:
            patcher.start(); self.addCleanup(patcher.stop)

    def test_created_member_does_not_replace_admin_session_and_logs_verified_actor(self):
        with patch.object(auth, '_remember') as remember:
            result = auth.create_member(' NEW@example.com ', 'secret123', 'New Member')
        self.assertIs(result, self.identity)
        remember.assert_not_called()
        self.client.auth.get_user.assert_called_once_with('admin-token')
        self.assertEqual(self.backend.rpc.call_args_list[0].args, ('admin_creation_ready', {'actor': 'admin-id'}))
        self.assertEqual(self.backend.rpc.call_args_list[-1].args, ('register_account_creation',
            {'created_user':'new-id', 'creation_source':'admin_create', 'creator':'admin-id'}))
        self.backend.auth.admin.delete_user.assert_not_called()

    def test_missing_migration_is_detected_before_creating_identity(self):
        self.backend.rpc.return_value.execute.side_effect = RuntimeError('missing migration')
        with self.assertRaises(RuntimeError):
            auth.create_member('new@example.com', 'secret123', 'New')
        self.backend.auth.admin.create_user.assert_not_called()

    def test_profile_registration_failure_cleans_up_only_new_identity_and_logs_failure(self):
        def rpc(name, args):
            result = Mock()
            if name == 'register_account_creation':
                result.execute.side_effect = RuntimeError('database failed')
            return result
        self.backend.rpc.side_effect = rpc
        with self.assertRaisesRegex(MemberManagementError, 'create_failed'):
            auth.create_member('new@example.com', 'secret123', 'New')
        self.backend.auth.admin.delete_user.assert_called_once_with('new-id')
        self.assertEqual(self.backend.rpc.call_args_list[-1].args, ('record_account_creation_failure',
            {'actor':'admin-id','target_email':'new@example.com','reason':'profile_registration_failed'}))
        self.assertNotIn('secret123', str(self.backend.rpc.call_args_list))

    def test_cleanup_failure_is_explicit(self):
        def rpc(name, args):
            result = Mock()
            if name == 'register_account_creation':
                result.execute.side_effect = RuntimeError('database failed')
            return result
        self.backend.rpc.side_effect = rpc
        self.backend.auth.admin.delete_user.side_effect = RuntimeError('cleanup failed')
        with self.assertRaisesRegex(MemberManagementError, 'rollback_failed'):
            auth.create_member('new@example.com', 'secret123', 'New')

    def test_spoofed_session_user_is_rejected_before_privileged_call(self):
        self.client.auth.get_user.return_value.user.id = 'someone-else'
        with self.assertRaisesRegex(MemberManagementError, 'denied'):
            auth.create_member('new@example.com', 'secret123', 'New')
        self.backend.rpc.assert_not_called()
        self.backend.auth.admin.create_user.assert_not_called()

class MemberPageTests(unittest.TestCase):
    def page(self):
        script = f'''
import streamlit as st
from unittest.mock import patch
import auth
from pages_util import Admin
st.session_state.setdefault('ui_lang', 'ไทย')
profiles = st.session_state.setdefault('test_profiles', {[ADMIN, MEMBER]!r})
def save(edits):
    st.session_state['test_saved'] = edits
    for edit in edits:
        next(p for p in profiles if p['id'] == edit['target']).update(edit['changes'])
    return len(edits)
with patch.object(auth, 'is_admin', return_value=True), patch.object(auth,'user_id',return_value='admin-id'), \\
     patch.object(auth,'list_profiles',return_value=profiles), patch.object(auth,'usage_since_month_start',return_value={{}}), \\
     patch.object(auth,'admin_creation_configured',return_value=False), patch.object(auth,'dev_mode',return_value=False), \\
     patch.object(auth,'recent_runs',return_value=[]), patch.object(auth,'recent_member_events',return_value=[]), \\
     patch.object(auth,'update_profiles',side_effect=save):
    Admin.admin_page()
'''
        app = AppTest.from_string(script).run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        return app

    def test_own_role_status_locked_and_current_account_label_is_visible(self):
        app = self.page()
        self.assertTrue(app.selectbox(key='admin_edit_role_admin-id').disabled)
        self.assertTrue(app.selectbox(key='admin_edit_active_admin-id').disabled)
        self.assertEqual(app.selectbox(key='admin_edit_role_member-id').options, ['สมาชิก', 'ผู้ดูแลระบบ'])
        self.assertEqual(app.selectbox(key='admin_edit_active_member-id').options, ['ใช้งานได้', 'ระงับการใช้งาน'])
        self.assertTrue(any('บัญชีที่คุณกำลังใช้งาน' in e.value for e in app.markdown))
        self.assertTrue(app.button(key='admin_save').disabled)

    def test_dirty_save_revert_save_and_reset(self):
        app = self.page()
        app.selectbox(key='admin_edit_role_member-id').select('admin').run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertFalse(app.button(key='admin_save').disabled)
        app.selectbox(key='admin_edit_role_member-id').select('member').run()
        self.assertTrue(app.button(key='admin_save').disabled)
        app.selectbox(key='admin_edit_active_member-id').select(False).run()
        app.button(key='admin_reset').click().run()
        self.assertTrue(app.button(key='admin_save').disabled)
        self.assertTrue(app.selectbox(key='admin_edit_active_member-id').value)
        app.number_input(key='admin_edit_limit_member-id').set_value(30).run()
        app.button(key='admin_save').click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertTrue([b for b in app.button if b.key == 'admin_save'][-1].disabled)
        self.assertEqual(app.session_state['test_saved'][0]['changes'], {'monthly_run_limit':30})
        self.assertTrue(any('บันทึกแล้ว' in e.value for e in app.success))

    def test_suspended_account_cannot_pass_page_gate(self):
        app = AppTest.from_string('''
import streamlit as st
from unittest.mock import patch
import auth
from pages_util import Account
st.session_state['ui_lang']='ไทย'
with patch.object(auth,'signed_in',return_value=True), patch.object(auth,'profile',return_value={'is_active':False}):
    st.session_state['test_allowed']=Account.gate()
''').run()
        self.assertFalse(app.exception)
        self.assertFalse(app.session_state['test_allowed'])
        self.assertTrue(any('ระงับ' in e.value for e in app.error))

if __name__ == '__main__':
    unittest.main()
