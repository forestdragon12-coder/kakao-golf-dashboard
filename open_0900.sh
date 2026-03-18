#!/bin/bash
# 매일 09:00 오픈 시간 수집
# 광주CC → 공식HP, 골드레이크 → 카카오
cd /Users/forestdragon/kakao_golf
PYTHON=/Users/forestdragon/kakao_golf/venv/bin/python

$PYTHON run.py --source official --courses 광주CC --skip-ai &
$PYTHON run.py --courses 골드레이크 --skip-ai &
wait
