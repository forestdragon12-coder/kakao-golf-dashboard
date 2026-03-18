#!/bin/bash
# 월 10:00 오픈 시간 수집
# 베르힐 → 공식HP, 무등산 → 카카오
cd /Users/forestdragon/kakao_golf
PYTHON=/Users/forestdragon/kakao_golf/venv/bin/python

$PYTHON run.py --source official --courses 베르힐 --skip-ai &
$PYTHON run.py --courses 무등산 --skip-ai &
wait
