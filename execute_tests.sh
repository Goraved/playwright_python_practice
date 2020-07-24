#!/usr/bin/env bash
rm -r allure-results/*
HEADLESS=true
pytest -n auto tests --alluredir allure-results

allure generate allure-results --clean -o allure-report