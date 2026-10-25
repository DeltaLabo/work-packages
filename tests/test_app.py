from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from streamlit.testing.v1 import AppTest

from scripts.data import FIELDS
from scripts.github_store import GitHubError
from test_store import ROW, MemoryStore


class AppTests(unittest.TestCase):
    def setUp(self):
        self.config={"password":"test-password","token":uuid4().hex,"repository":"DeltaLabo/work-packages","branch":"main"}
        self.start_patch("scripts.config.settings",return_value=self.config)
        self.snapshot=self.start_patch("scripts.github_store.WorkPackageStore.snapshot",return_value=(list(FIELDS),[ROW]))
        self.start_patch("requests.request",side_effect=AssertionError("No real GitHub calls in tests"))
        self.saved=self.start_patch("scripts.github_store.WorkPackageStore.save",return_value=ROW|{"id":"022026"})

    def start_patch(self,name,**kwargs):
        p=patch(name,**kwargs);r=p.start();self.addCleanup(p.stop);return r

    def open(self):
        return AppTest.from_file(str(Path(__file__).resolve().parents[1]/"app.py"),default_timeout=20).run()

    def click(self,app,label):
        next(b for b in app.button if b.label==label).click().run()
        self.assertEqual(len(app.exception),0)

    def login(self,app):
        app.text_input(key="login_password").set_value("test-password")
        self.click(app,"Log in")

    def fill(self,app):
        for field in FIELDS[1:]:
            collection=app.text_input if field in ("title","payment","supervisor","professor") else app.text_area
            collection(key="field_"+field).set_value(ROW[field])

    def test_public_browse_pdf_and_literal_search_need_no_password(self):
        app=self.open()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.radio[0].value,"Browse")
        self.assertEqual(len(app.get("download_button")),1)
        self.assertEqual(len(app.text_input),1)
        app.text_input[0].set_value("not-present").run()
        self.assertEqual(len(app.get("download_button")),0)
        self.saved.assert_not_called()

    def test_editing_stays_locked_and_blank_password_disables_it(self):
        app=self.open();app.radio[0].set_value("Create").run()
        self.assertEqual(len(app.text_area),0)
        app.text_input(key="login_password").set_value("wrong")
        self.click(app,"Log in")
        self.assertEqual(app.error[0].value,"Incorrect password.")
        self.saved.assert_not_called()
        self.config["password"]=""
        app=self.open();app.radio[0].set_value("Edit").run()
        self.assertEqual(len(app.text_area),0)

    def test_preview_and_save_use_same_operation_and_logout_removes_editing(self):
        app=self.open();app.radio[0].set_value("Create").run();self.login(app);self.fill(app)
        self.click(app,"Preview PDF")
        self.assertEqual(len(app.get("download_button")),1)
        self.click(app,"Save work package")
        self.assertEqual(self.saved.call_count,1)
        self.assertIn("022026",app.success[0].value)
        self.assertIsNone(self.saved.call_args.args[2])
        self.click(app,"Log out")
        self.assertEqual(len(app.text_area),0)

    def test_target_change_explicitly_reseeds_form_and_snapshot(self):
        self.snapshot.return_value=(list(FIELDS),[ROW,ROW|{"id":"022026","title":"Second"}])
        app=self.open();app.radio[0].set_value("Edit").run();self.login(app)
        app.text_input(key="field_title").set_value("Unsaved change")
        app.selectbox(key="edit_package").set_value("022026").run()
        self.assertEqual(app.text_input(key="field_title").value,"Second")
        self.assertEqual(app.session_state["editor_original"]["id"],"022026")

    def test_failed_save_keeps_operation_for_recovery_without_duplicate_creation(self):
        self.saved.side_effect=GitHubError("Reply lost")
        app=self.open();app.radio[0].set_value("Create").run();self.login(app);self.fill(app)
        self.click(app,"Save work package")
        first=self.saved.call_args.args
        self.saved.side_effect=None
        self.click(app,"Save work package")
        self.assertEqual(first,self.saved.call_args.args)

    def test_missing_token_is_read_only_and_remote_failure_does_not_use_local_data(self):
        self.config["token"]=""
        with patch("scripts.data.read_local",return_value=(list(FIELDS),[ROW])) as local:
            app=self.open()
            self.assertEqual(len(app.get("download_button")),1)
            app.radio[0].set_value("Create").run();self.login(app)
            self.assertEqual(len(app.text_area),0)
        self.config["token"]="configured"
        self.snapshot.side_effect=GitHubError("Offline")
        with patch("scripts.data.read_local",side_effect=AssertionError("No stale fallback")):
            app=self.open()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(len(app.get("download_button")),0)
