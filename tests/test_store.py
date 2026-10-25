import base64
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import requests

from scripts.data import DATA_PATH, FIELDS, apply_change, next_id, parse_csv, values, write_csv
from scripts.github_store import Conflict, GitHubError, WorkPackageStore


ROW = dict(zip(FIELDS, ("012026", "Example package", "A sample description", "First objective;Second objective",
    "First task;Second task", "Test equipment", "Test deliverable", "Two weeks", "Example terms", "Example supervisor", "Example professor")))


class MemoryStore(WorkPackageStore):
    def __init__(self, rows=None):
        super().__init__("test-only-token")
        initial = write_csv([*FIELDS, "extra"], rows if rows is not None else [ROW | {"extra": "preserve"}])
        self.commits = {"initial": {"files": {DATA_PATH: initial, "keep.txt": "preserve"}, "parent": None}}
        self.ref, self.trees, self.serial = "initial", {}, 0
        self.before_patch, self.lose_reply = None, False

    @property
    def files(self):
        return self.commits[self.ref]["files"]

    def request(self, method, path, *, payload=None, params=None, optional=False):
        self.serial += 1
        if method == "GET" and path == "/git/ref/heads/main":
            return {"object": {"sha": self.ref}}
        if method == "GET" and path.startswith("/contents/"):
            result = self.commits[params["ref"]]["files"].get(path.removeprefix("/contents/"))
            if result is None and optional:
                return None
            if result is None:
                raise GitHubError("Missing file")
            return {"encoding": "base64", "content": base64.b64encode(result.encode()).decode()}
        if method == "GET" and path.startswith("/git/commits/"):
            return {"tree": {"sha": path.removeprefix("/git/commits/")}}
        if method == "POST" and path == "/git/trees":
            name = f"tree-{self.serial}"
            self.trees[name] = deepcopy(self.commits[payload["base_tree"]]["files"])
            self.trees[name].update({item["path"]: item["content"] for item in payload["tree"]})
            return {"sha": name}
        if method == "POST" and path == "/git/commits":
            name = f"commit-{self.serial}"
            self.commits[name] = {"files": self.trees[payload["tree"]], "parent": payload["parents"][0]}
            return {"sha": name}
        if method == "PATCH" and path == "/git/refs/heads/main":
            if self.before_patch:
                callback, self.before_patch = self.before_patch, None
                callback()
            if payload["force"] or self.commits[payload["sha"]]["parent"] != self.ref:
                raise Conflict("Concurrent update")
            self.ref = payload["sha"]
            if self.lose_reply:
                self.lose_reply = False
                raise GitHubError("Reply lost")
            return {}
        raise AssertionError(f"Unexpected request: {method} {path}")


class DataTests(unittest.TestCase):
    def test_round_trip_preserves_id_text_and_unknown_columns(self):
        columns = [*FIELDS, "unknown"]
        row = ROW | {"unknown": "001, á\nextra", "description": "  keep spaces  "}
        self.assertEqual(parse_csv(write_csv(columns, [row])), (columns, [row]))
        self.assertEqual(values(row)["description"], "  keep spaces  ")
        self.assertEqual(next_id([ROW], 2026), "022026")
        self.assertEqual(next_id([ROW], 2027), "012027")

    def test_duplicate_ids_and_broken_rows_are_rejected(self):
        for text in (write_csv(FIELDS,[ROW,ROW]), write_csv(FIELDS,[ROW|{"id":"../outside"}]), "id,title\n1,Title\n"):
            with self.subTest(text=text[:20]), self.assertRaises(ValueError):
                parse_csv(text)
        with self.assertRaisesRegex(ValueError,"Title is required"):
            values(ROW|{"title":"  "})

    def test_unmodified_fields_do_not_overwrite_concurrent_changes(self):
        current = ROW|{"equipment":"New equipment", "extra":"keep"}
        _,saved=apply_change([*FIELDS,"extra"],[current],ROW|{"title":"New title"},ROW,2026)
        self.assertEqual(saved["equipment"],"New equipment")
        self.assertEqual(saved["extra"],"keep")
        with self.assertRaisesRegex(ValueError,"changed"):
            apply_change(FIELDS,[ROW|{"title":"Concurrent title"}],ROW|{"title":"My title"},ROW,2026)

    def test_network_errors_never_expose_credentials_or_response_bodies(self):
        store=WorkPackageStore("sensitive-token")
        with patch("requests.request",return_value=Mock(status_code=403,text="sensitive-token")), self.assertRaises(GitHubError) as error:
            store.head()
        self.assertNotIn("sensitive-token",str(error.exception))
        with patch("requests.request",side_effect=requests.Timeout("sensitive-token")), self.assertRaises(GitHubError) as error:
            store.head()
        self.assertNotIn("sensitive-token",str(error.exception))


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.db=MemoryStore()
        self.operation=uuid4().hex

    def save(self, proposed=None, original=None, operation=None):
        return self.db.save(operation or self.operation, proposed or ROW,original,2026)

    def test_new_record_and_receipt_are_one_commit_and_unknown_data_survives(self):
        saved=self.save()
        self.assertEqual(saved["id"],"022026")
        columns,rows=self.db.snapshot()
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["extra"],"preserve")
        self.assertEqual(self.db.files["keep.txt"],"preserve")
        receipt=json.loads(self.db.files[f"data/changes/{self.operation}.json"])
        self.assertEqual(receipt["saved"]["id"],"022026")

    def test_lost_reply_recovers_same_id_and_rejects_changed_retry(self):
        self.db.lose_reply=True
        with self.assertRaises(GitHubError):
            self.save()
        parent=self.db.ref
        self.assertEqual(self.save()["id"],"022026")
        self.assertEqual(parent,self.db.ref)
        self.assertEqual(len(self.db.snapshot()[1]),2)
        with self.assertRaisesRegex(ValueError,"different details"):
            self.save(ROW|{"title":"Different"})

    def test_concurrent_creations_receive_distinct_ids_without_losing_rows(self):
        self.db.before_patch=lambda:self.save(ROW|{"title":"Other"},operation=uuid4().hex)
        self.assertEqual(self.save()["id"],"032026")
        self.assertEqual({row["id"] for row in self.db.snapshot()[1]},{"012026","022026","032026"})

    def test_concurrent_edits_merge_untouched_fields_and_reject_same_field(self):
        self.db.before_patch=lambda:self.save(ROW|{"equipment":"New equipment"},ROW,uuid4().hex)
        saved=self.save(ROW|{"title":"New title"},ROW)
        self.assertEqual(saved["equipment"],"New equipment")
        with self.assertRaisesRegex(ValueError,"changed"):
            self.save(ROW|{"title":"Stale"},ROW,uuid4().hex)

    def test_empty_catalog_accepts_first_package(self):
        self.db=MemoryStore([])
        self.assertEqual(self.save()["id"],"012026")
