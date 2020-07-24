#!/usr/bin/env bash
rm -r allure-results/*

source venv/bin/activate
pip install -r requirements.txt --quiet

pytest -n auto tests --alluredir allure-results

allure serve