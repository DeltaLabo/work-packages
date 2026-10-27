# DeltaLAB: work packages

Public browsing and PDF downloads, with password-protected creation and editing.
The original CSV and LaTeX/PDF command-line generator are preserved.

## Deploy to Streamlit

Deployed at https://deltalab-work-packages.streamlit.app/, verified from the
owner's public Streamlit profile and the matching repository link.
Deployment: repository **DeltaLabo/work-packages**, branch **main**, entry
point **app.py**. Dependencies are in the root requirements.txt. The web app
generates PDFs in memory with ReportLab and does not need a TeX installation.

Paste this into Streamlit Settings > Secrets, replacing the placeholders:

```toml
WORK_PACKAGES_PASSWORD = "your-private-editing-password"
WORK_PACKAGES_TOKEN = "your-fine-grained-github-token"
WORK_PACKAGES_REPOSITORY = "DeltaLabo/work-packages"
WORK_PACKAGES_BRANCH = "main"
```

Restrict the token to this repository with **Contents: Read and write**.
No pull-request permission is needed. Saves commit directly to the configured
branch, which must allow the token to write. Never commit completed secrets.
Public browsing/downloads require no password. Blank credentials disable editing.
Without a token, browsing uses the bundled local snapshot, labelled read-only;
configured remote errors block loading rather than silently using stale data.

The title is DeltaLAB: work packages. The transparent flat SVG appears to the
right of the title, stacks on phones, and shared-password sign-in appears in the
sidebar. Back to administration opens the confirmed
https://deltalab-admi.streamlit.app/ in a new tab. Optional ADMIN_APP_URL can
override that public link. No account registration or new identity database is
used. Administration now has the verified deployed URL as its default;
WORK_PACKAGES_APP_URL can override that public link.

## Web workflow

- Browse: search by ID or entered text, view a package and download its PDF.
- Create: sign in, enter the work description, preview the unsaved PDF and save.
- Edit: sign in, select a package, correct its contents, preview and save.

New IDs are assigned automatically at save time, continuing the existing
sequence/year pattern: 012026, 022026, etc. Existing IDs remain immutable.
The year uses America/Costa_Rica. Lists accept one item per line or semicolons.
Titles, descriptions, objectives, tasks and deliverables are required on new saves;
equipment, work breakdown, payment, supervisor and professor are optional.
Existing Spanish descriptions and unknown CSV columns are retained.

Each save updates data/work_packages.csv and an immutable UUID receipt under
data/changes/ in one atomic GitHub commit. Non-forced branch updates retry
concurrent saves. New IDs are assigned against the latest source. Retries reuse
their operation UUID and full payload, recovering a completed save without
creating another package. Changed retries are rejected. Edits compare only the
fields being changed and preserve other concurrent changes; conflicting edits
require refresh/review. Refresh discards the current editing snapshot.

## Original command-line workflow

```powershell
python scripts/generate_work_packages.py
python scripts/generate_work_packages.py 012026
```

The CLI uses LuaLaTeX, the approved flat DeltaLAB logo and the original TEC logo. It generates files in
output/tex/ and output/pdf/. The app never runs that compiler or modifies saved
documents. Original data and legacy source images are preserved.

## Development

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
streamlit run app.py
```

Tests use invented data and mock GitHub. They check public downloads, editing
access, form reseeding, document pagination, concurrent saves, lost-response
recovery and preservation of original/unknown fields. No live requests are saved.

## Generated document branding

Future document generation uses `assets/images/logo_pdf.png`, the transparent
render of the approved flat `logo.svg`. Keep the two assets in sync. Retain
legacy source images and existing saved documents; do not regenerate historical
PDFs or signed letters as part of branding changes.

Both web and offline CLI PDFs use this logo. Preserve the separate TEC
institutional logo and existing saved output documents.
