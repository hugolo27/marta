"""Shared Earth Engine session init. Service account auth — interactive auth is blocked for
this project's Google accounts (see research_docs/BITACORA_FASES.md, 2026-08-20)."""

import os

import ee
from dotenv import load_dotenv


def init():
    load_dotenv()
    credentials = ee.ServiceAccountCredentials(
        os.environ["EE_SERVICE_ACCOUNT_EMAIL"],
        os.environ["EE_SERVICE_ACCOUNT_KEY_PATH"],
    )
    ee.Initialize(credentials, project=os.environ["EE_PROJECT_ID"])
