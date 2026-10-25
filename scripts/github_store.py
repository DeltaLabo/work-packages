"""Atomic direct saves with stable retry receipts and concurrent-edit checks."""

import base64
from datetime import datetime, timezone
import json
import re
from urllib.parse import quote
from uuid import UUID

import requests

from scripts.data import DATA_PATH, FIELDS, apply_change, parse_csv, values, write_csv


class GitHubError(Exception):
    pass


class Conflict(GitHubError):
    pass


class WorkPackageStore:
    def __init__(self, token, repository="DeltaLabo/work-packages", branch="main"):
        if not token:
            raise GitHubError("Configure WORK_PACKAGES_TOKEN to enable GitHub saving.")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not branch:
            raise ValueError("Configure a valid repository and branch.")
        self.token, self.repository, self.branch = token, repository, branch
        self.base = "https://api.github.com/repos/" + repository

    def request(self, method, path, *, payload=None, params=None, optional=False):
        try:
            response = requests.request(method, self.base + path, json=payload, params=params,
                headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                         "X-GitHub-Api-Version": "2022-11-28"}, timeout=(5, 25))
        except requests.RequestException:
            raise GitHubError("GitHub did not confirm the operation. Retry without changing the details; completed saves will not be duplicated.") from None
        if optional and response.status_code == 404:
            return None
        if response.status_code in (409, 422):
            raise Conflict("A concurrent update could not be saved. Refresh and review the latest work package.")
        if not 200 <= response.status_code < 300:
            raise GitHubError(f"Repository access failed (HTTP {response.status_code}). Check token permissions.")
        try:
            return response.json()
        except ValueError:
            raise GitHubError("GitHub returned an invalid response. Retry the same operation.") from None

    def head(self):
        return self.request("GET", f"/git/ref/heads/{quote(self.branch, safe='/')}")["object"]["sha"]

    def read(self, path, sha, optional=False):
        response = self.request("GET", "/contents/" + quote(path, safe="/"), params={"ref": sha}, optional=optional)
        if response is None:
            return None
        try:
            if response.get("encoding") != "base64":
                raise ValueError
            raw = base64.b64decode(response["content"])
            try:
                return raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                return raw.decode("latin-1")
        except (ValueError, TypeError):
            raise GitHubError("A repository file could not be read.") from None

    def snapshot(self):
        return parse_csv(self.read(DATA_PATH, self.head()))

    def save(self, operation_id, proposed, original, year):
        operation = UUID(operation_id).hex
        proposed = values(proposed)
        original = {field: str(original.get(field, "")) for field in FIELDS} if original is not None else None
        payload = {"proposed": proposed, "original": original, "year": year}
        receipt_path = f"data/changes/{operation}.json"
        for attempt in range(5):
            parent = self.head()
            previous = self.read(receipt_path, parent, optional=True)
            if previous is not None:
                receipt = json.loads(previous)
                if receipt["payload"] != payload:
                    raise ValueError("This operation already saved different details. Start another change instead of reusing it.")
                return receipt["saved"]
            columns, rows = parse_csv(self.read(DATA_PATH, parent))
            updated, saved = apply_change(columns, rows, proposed, original, year)
            receipt = {"schema_version": 1, "id": operation, "saved_at": datetime.now(timezone.utc).isoformat(),
                       "payload": payload, "saved": saved}
            commit = self.request("GET", f"/git/commits/{parent}")
            tree = self.request("POST", "/git/trees", payload={"base_tree": commit["tree"]["sha"], "tree": [
                {"path": DATA_PATH, "mode": "100644", "type": "blob", "content": write_csv(columns, updated)},
                {"path": receipt_path, "mode": "100644", "type": "blob", "content": json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"}]})
            new_commit = self.request("POST", "/git/commits", payload={"message": f"Save work package {saved['id']}",
                "tree": tree["sha"], "parents": [parent]})
            try:
                self.request("PATCH", f"/git/refs/heads/{quote(self.branch, safe='/')}", payload={"sha": new_commit["sha"], "force": False})
                return saved
            except Conflict:
                if attempt == 4:
                    raise
