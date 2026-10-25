"""Public work-package browsing and shared-password editing."""

import hashlib
import hmac
from uuid import uuid4

import streamlit as st

from scripts.config import settings
from scripts.data import EDITABLE, LABELS, LIST_FIELDS, ROOT, issuance_year, items, read_local, values
from scripts.github_store import WorkPackageStore, GitHubError
from scripts.pdf import work_package_pdf
from scripts.ui import app_header


@st.cache_data(ttl=15, max_entries=4, show_spinner=False)
def live_snapshot(token, repository, branch):
    return WorkPackageStore(token, repository, branch).snapshot()


def authenticated(password):
    with st.sidebar:
        st.header("Authentication")
        if not password:
            st.info("Editing is not enabled. Configure WORK_PACKAGES_PASSWORD.")
            return False
        version = hashlib.sha256(password.encode()).hexdigest()
        if st.session_state.get("authenticated_version") == version:
            if st.button("Log out"):
                st.session_state.clear()
                st.rerun()
            return True
        with st.form("login"):
            entered = st.text_input("Work packages password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            if hmac.compare_digest(entered.encode(), password.encode()):
                st.session_state.pop("login_password", None)
                st.session_state["authenticated_version"] = version
                st.rerun()
            st.error("Incorrect password.")
        return False


def show_package(row):
    st.header(row["title"])
    st.caption(f"ID: {row['id']}")
    st.write(row["description"])
    for field in LIST_FIELDS:
        entries = items(row.get(field, ""))
        if entries:
            st.subheader(LABELS[field])
            for item in entries:
                st.write("• " + item)
    for field in ("payment", "supervisor", "professor"):
        if row.get(field):
            st.write(f"**{LABELS[field]}:** {row[field]}")


def download(row, *, draft=False):
    try:
        pdf = work_package_pdf(row)
    except (ValueError, OSError, KeyError):
        st.error("Could not generate this work-package PDF.")
        return
    prefix = "draft_" if draft else ""
    st.download_button("Download draft PDF" if draft else "Download PDF", pdf,
                       file_name=f"{prefix}work_package_{row['id']}.pdf", mime="application/pdf")
    st.pdf(pdf, height=650)


def browse(rows):
    search = st.text_input("Search work packages", placeholder="ID, title, objectives or tasks").strip().casefold()
    matches = [row for row in rows if not search or any(search in row.get(field, "").casefold() for field in ("id", *EDITABLE))]
    if not matches:
        st.info("No work packages match your search.")
        return
    labels = {row["id"]: row for row in matches}
    code = st.selectbox("Work package", list(labels), format_func=lambda value: f"{labels[value]['title']} · {value}", key="browse_package")
    show_package(labels[code])
    download(labels[code])


def editor(rows, store, *, creating):
    if not store:
        st.info("Configure WORK_PACKAGES_TOKEN with Contents: Read and write to enable saving.")
        return
    original = None
    if not creating:
        if not rows:
            st.info("There are no work packages to edit yet.")
            return
        by_id = {row["id"]: row for row in rows}
        code = st.selectbox("Work package to edit", list(by_id), format_func=lambda value: f"{by_id[value]['title']} · {value}", key="edit_package")
        original = by_id[code]
    context = "create" if creating else original["id"]
    if st.session_state.get("editor_context") != context:
        st.session_state["editor_context"] = context
        st.session_state["editor_original"] = dict(original) if original else None
        st.session_state["editor_operation"] = uuid4().hex
        st.session_state["editor_year"] = issuance_year()
        st.session_state.pop("editor_preview", None)
        for field in EDITABLE:
            st.session_state["field_"+field] = original.get(field, "") if original else ""
    frozen = st.session_state["editor_original"]
    st.caption("An ID is assigned automatically when saved." if creating else f"ID: {frozen['id']} (unchanged)")
    st.caption("Objectives, tasks, equipment, deliverables and work breakdown accept one entry per line or entries separated by semicolons.")
    with st.form("work_package_editor"):
        entered = {}
        for field in EDITABLE:
            if field in ("title", "payment", "supervisor", "professor"):
                entered[field] = st.text_input(LABELS[field], key="field_"+field, max_chars=300 if field=="title" else 10000)
            else:
                entered[field] = st.text_area(LABELS[field], key="field_"+field, max_chars=10000)
        preview = st.form_submit_button("Preview PDF")
        save = st.form_submit_button("Save work package")
    if preview or save:
        try:
            proposed = values(entered)
            if save:
                saved = store.save(st.session_state["editor_operation"], proposed, frozen, st.session_state["editor_year"])
                live_snapshot.clear()
                st.session_state["save_notice"] = f"Work package {saved['id']} saved in GitHub."
                st.session_state["saved_package"] = saved
                st.session_state.pop("editor_context", None)
                st.rerun()
            st.session_state["editor_preview"] = {"id": frozen["id"] if frozen else "DRAFT", **proposed}
        except (ValueError, GitHubError, OSError, KeyError) as error:
            st.error(str(error) if isinstance(error, (ValueError, GitHubError)) else "Could not confirm the save. Retry the same details.")
    if st.session_state.get("editor_preview"):
        st.caption("Unsaved preview. Save work package to make it available in Browse.")
        download(st.session_state["editor_preview"], draft=True)


def main():
    st.set_page_config(page_title="DeltaLAB: work packages", layout="wide")
    app_header("DeltaLAB: work packages", ROOT / "assets/images/logo.svg")
    config = settings()
    action = st.radio("Workspace", ("Browse", "Create", "Edit"), horizontal=True)
    if action != "Browse" and not authenticated(config["password"]):
        st.info("Open the sidebar to sign in for creating and editing work packages.")
        return
    if st.session_state.get("save_notice"):
        st.success(st.session_state.pop("save_notice"))
    if st.button("Refresh work packages"):
        live_snapshot.clear()
        for key in ("editor_context", "editor_preview", "saved_package"):
            st.session_state.pop(key, None)
        st.rerun()
    try:
        store = WorkPackageStore(config["token"], config["repository"], config["branch"]) if config["token"] else None
        _, rows = live_snapshot(config["token"], config["repository"], config["branch"]) if store else read_local()
    except (GitHubError, ValueError, OSError, KeyError):
        st.error("Could not load the work-package source. Check repository access or the CSV format and refresh.")
        return
    if not store:
        st.caption("Local read-only snapshot. Configure GitHub access for current data and saving.")
    if action == "Browse":
        browse(rows)
    else:
        editor(rows, store, creating=action=="Create")


if __name__ == "__main__":
    main()
