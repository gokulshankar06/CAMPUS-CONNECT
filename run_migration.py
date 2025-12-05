#!/usr/bin/env python3
"""Run the teams migration and show output"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from migrations.fix_teams_is_open import main

if __name__ == '__main__':
    result = main()
    print(f"\nMigration exit code: {result}")
    sys.exit(result)
