@echo off
echo Running database fix...
python check_and_fix_db.py > db_fix_output.txt 2>&1
echo Done! Check db_fix_output.txt for results
type db_fix_output.txt
