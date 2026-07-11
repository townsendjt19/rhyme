@echo off
rem Pre-2021 regime test, cells 3a/3b (pullback parent, 0.8p + 1.6p spread).
rem Launched detached via WMI (tool sessions kill their children; WMI children
rem survive -- established project pattern). Writes DONE/FAILED marker at end.
cd /d D:\workspace\rhyme_validator

D:\workspace\rhyme\venv\Scripts\python.exe validate.py --plugin D:/workspace/rhyme/trend_origin_pullback_plugin.py --mode scalp30 --spread-pips 0.8 --strategy-name pre2021_pullback_parent_sp08.validator-v2 --instrument USD_JPY --start 2010-01-01 --end 2019-12-31 --balance 4075.63 --fixed-risk 80 > D:\workspace\rhyme\pre2021_pullback_sp08.runlog 2>&1
if errorlevel 1 goto fail

D:\workspace\rhyme\venv\Scripts\python.exe validate.py --plugin D:/workspace/rhyme/trend_origin_pullback_plugin.py --mode scalp30 --spread-pips 1.6 --strategy-name pre2021_pullback_parent_sp16.validator-v2 --instrument USD_JPY --start 2010-01-01 --end 2019-12-31 --balance 4075.63 --fixed-risk 80 > D:\workspace\rhyme\pre2021_pullback_sp16.runlog 2>&1
if errorlevel 1 goto fail

echo done > D:\workspace\rhyme\pre2021_pullback_runs.DONE
exit /b 0

:fail
echo failed > D:\workspace\rhyme\pre2021_pullback_runs.FAILED
exit /b 1
