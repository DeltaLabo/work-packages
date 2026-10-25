# DeltaLAB work packages context

The user requested a deployable app and explicitly chose public browsing/PDF
downloads with a shared password only for creation/editing. Repo is public.
app.py is the Streamlit entry point on main. No individual accounts/registration.
Branding uses the same transparent flat assets/images/logo.svg and scripts/ui.py
as the other DeltaLAB apps: title left, logo right, responsive stacking, same-tab
Back to administration, default https://deltalab-admi.streamlit.app/.
Private editing uses the sidebar. Preserve current passwords/access semantics.

Secrets: WORK_PACKAGES_PASSWORD, WORK_PACKAGES_TOKEN, WORK_PACKAGES_REPOSITORY
(DeltaLabo/work-packages), WORK_PACKAGES_BRANCH (main). Contents Read/write only;
no PRs. Optional ADMIN_APP_URL overrides the public navigation link. Blank password
or token disables writes. No token permits labelled local read-only browsing;
configured remote failures must not fall back to stale local data for writes.
Tell the user when ready to deploy main/app.py. Do not guess a deployed URL;
Administration already has a configurable WORK_PACKAGES_APP_URL waiting for it.

data/work_packages.csv is the only live catalog. Keep its schema, padded IDs,
entered text, unknown columns and existing rows. No assistant directory belongs
here. New package IDs continue sequence/year, at least two sequence digits plus
four-digit year using America/Costa_Rica. Assign against the latest branch during
an atomic save; preserve IDs on edits. Never merge distinct packages by title.
Lists accept semicolons/newlines without rewriting existing entries on browsing.

scripts/github_store.py writes the CSV plus data/changes/UUID.json in one commit,
using pinned reads and non-forced ref updates. Retry concurrent creations with a
fresh read, preserve unrelated concurrent edits and reject conflicts in changed
fields. Recover uncertain writes by the same UUID/full payload BEFORE recalculating
an ID or stale check. Reject changed saved payloads. Never force refs or overwrite
receipts. Never print secrets, HTTP bodies or create real records in tests.

Seed keyed edit widgets and freeze original/operation/year when a target changes.
Preserve same-target unsaved values, UUID and original on errors/retries. Clear
stale previews when the target changes. Unsaved PDFs must be labelled as drafts.
No app download or preview writes source/output files; all are in memory.

scripts/pdf.py uses ReportLab, bundled Vera fonts and logo_pdf.png (derived from
the approved flat logo). No server TeX installation. Escape entered text, wrap
long content, keep headings with following content and repeat headers/footers.
Preserve scripts/generate_work_packages.py and its original PNG/JPG logos and
LuaLaTeX CLI behavior. Never regenerate saved documents or edit live CSVs to test.

Run python -m unittest discover -s tests -v. Tests must use fixtures/mocked GitHub.
Use ignored tmp/pdfs for PDF rendering QA. Maintain README/AGENTS and push completed
work. Do not change other DeltaLAB repositories by inference.
