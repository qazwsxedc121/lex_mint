#!/bin/bash
# Test all commands in CLAUDE.md to ensure they are correct

echo "Testing CLAUDE.md Commands"
echo "=" 60

echo ""
echo "[Test 1] Python version"
./venv/Scripts/python --version
if [ $? -eq 0 ]; then echo "OK: python command works"; else echo "FAIL: python command"; exit 1; fi

echo ""
echo "[Test 2] Pip version"
./venv/Scripts/pip --version
if [ $? -eq 0 ]; then echo "OK: pip command works"; else echo "FAIL: pip command"; exit 1; fi

echo ""
echo "[Test 3] Pytest version"
./venv/Scripts/pytest --version
if [ $? -eq 0 ]; then echo "OK: pytest command works"; else echo "FAIL: pytest command"; exit 1; fi

echo ""
echo "[Test 4] Uvicorn version"
./venv/Scripts/uvicorn --version
if [ $? -eq 0 ]; then echo "OK: uvicorn command works"; else echo "FAIL: uvicorn command"; exit 1; fi

echo ""
echo "[Test 5] Run Python script"
./venv/Scripts/python test_composite_key.py > /dev/null 2>&1
if [ $? -eq 0 ]; then echo "OK: python script execution works"; else echo "FAIL: python script execution"; exit 1; fi

echo ""
echo "=" 60
echo "SUCCESS: All CLAUDE.md commands are correct!"
echo "=" 60
