#!/usr/bin/env bash
source venv/bin/activate
echo "-> Installing dependencies"
pip install -r requirements.txt --quiet
echo "-> Installing Playwright browsers"
python3.7 -m playwright install

echo "-> Removing old Allure results"
rm -r allure-results/* || echo "No results"

echo "-> Start tests"
pytest -n auto  tests --alluredir allure-results
echo "-> Test finished"

echo "-> Generating report"
allure generate allure-results --clean -o allure-report
echo "-> Execute 'allure serve' in the command line"