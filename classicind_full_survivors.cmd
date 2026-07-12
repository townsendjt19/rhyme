@echo off
cd /d D:\workspace\rhyme
call venv\Scripts\python.exe classicind_killtest.py full EUR_USD adxgate  >> classicind_full.runlog 2>&1
call venv\Scripts\python.exe classicind_killtest.py full EUR_USD tkcross  >> classicind_full.runlog 2>&1
call venv\Scripts\python.exe classicind_killtest.py full GBP_USD kumo     >> classicind_full.runlog 2>&1
call venv\Scripts\python.exe classicind_killtest.py full USD_JPY adxgate  >> classicind_full.runlog 2>&1
call venv\Scripts\python.exe classicind_killtest.py full USD_JPY frama    >> classicind_full.runlog 2>&1
echo ALL SURVIVOR FULL RUNS COMPLETE >> classicind_full.runlog
