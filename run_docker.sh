#!/usr/bin/env bash
docker build -t playwright_test_image .
docker run --name test_playwright_container -i playwright_test_image
docker cp test_playwright_container:/playwright_tests/allure-results  ./
docker stop test_playwright_container
docker rm test_playwright_container


## Install allure
## Linux
#sudo apt-add-repository ppa:qameta/allure
#sudo apt-get update
#sudo apt-get install allure
## Mac
#brew install allure

## Open generated report

rm -r allure-results/*
allure serve