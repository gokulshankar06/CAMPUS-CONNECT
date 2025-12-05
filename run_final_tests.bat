@echo off
echo Running Final CampusConnect Tests...
echo =====================================
python final_fix_test.py
echo.
echo =====================================
echo Running Comprehensive Tests...
echo =====================================
python scripts\comprehensive_tests.py
pause
