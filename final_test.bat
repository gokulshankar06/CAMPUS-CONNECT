@echo off
echo ============================================================
echo CAMPUSCONNECT FINAL TEST SUITE
echo ============================================================
echo.
echo Deleting old test report...
if exist test_report.json del test_report.json

echo Running comprehensive tests...
python scripts\comprehensive_tests.py

echo.
echo ============================================================
echo TEST COMPLETE - Checking Results
echo ============================================================

if exist test_report.json (
    echo Test report generated successfully!
    python -c "import json; report=json.load(open('test_report.json')); print(f\"Pass Rate: {report['summary']['passed']}/{report['summary']['passed']+report['summary']['failed']} tests passed\")"
) else (
    echo No test report generated - tests may have failed to run
)

pause
