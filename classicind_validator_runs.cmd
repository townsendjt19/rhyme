@echo off
cd /d D:\workspace\rhyme_validator
call D:\workspace\rhyme\venv\Scripts\python.exe validate.py --plugin D:/workspace/rhyme/adx_gate_plugin.py --instrument USD_JPY --mode scalp30 --start 2021-07-01 --end 2026-07-01 --fixed-risk 80 >> D:\workspace\rhyme\classicind_validator.runlog 2>&1
call D:\workspace\rhyme\venv\Scripts\python.exe validate.py --plugin D:/workspace/rhyme/frama_plugin.py --instrument USD_JPY --mode scalp30 --start 2021-07-01 --end 2026-07-01 --fixed-risk 80 >> D:\workspace\rhyme\classicind_validator.runlog 2>&1
echo VALIDATOR RUNS COMPLETE >> D:\workspace\rhyme\classicind_validator.runlog
