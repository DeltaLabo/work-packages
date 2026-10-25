"""Deployment settings; never log configured credentials."""

import os
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


def settings():
    def get(name, default=""):
        if name in os.environ:
            return os.environ[name]
        try:
            return str(st.secrets.get(name, default))
        except (FileNotFoundError, StreamlitSecretNotFoundError):
            return default
    return {"password": get("WORK_PACKAGES_PASSWORD"),
            "token": get("WORK_PACKAGES_TOKEN") or get("GITHUB_TOKEN"),
            "repository": get("WORK_PACKAGES_REPOSITORY", "DeltaLabo/work-packages"),
            "branch": get("WORK_PACKAGES_BRANCH", "main")}
