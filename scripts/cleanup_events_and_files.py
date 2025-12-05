import os
import sys
import sqlite3

# One-time cleanup script to delete ALL events and related data,
# and remove uploaded abstract/team files from disk.
#
# Run from project root:
#   python scripts/cleanup_events_and_files.py

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'database.db')


def table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def resolve_path(path: str) -> str | None:
    """Resolve DB file_path (usually relative) to an absolute path."""
    if not path:
        return None
    # Trim whitespace
    path = path.strip()
    if not path:
        return None
    if os.path.isabs(path):
        return path
    return os.path.join(PROJECT_ROOT, path)


def delete_files_from_table(conn, table: str, column: str) -> None:
    if not table_exists(conn, table):
        print(f"[SKIP] Table '{table}' not found, skipping file deletion.")
        return

    rows = conn.execute(
        f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL AND TRIM({column}) != ''"
    ).fetchall()

    if not rows:
        print(f"[INFO] No files recorded in {table}.{column}.")
        return

    print(f"[INFO] Deleting files referenced by {table}.{column} ({len(rows)} entries)...")
    seen = set()
    deleted = 0
    missing = 0

    for row in rows:
        # sqlite3.Row supports name or index
        path = row[column] if isinstance(row, sqlite3.Row) else row[0]
        abs_path = resolve_path(path)
        if not abs_path:
            continue
        if abs_path in seen:
            continue
        seen.add(abs_path)

        if os.path.exists(abs_path):
            try:
                print(f"  - Deleting file: {abs_path}")
                os.remove(abs_path)
                deleted += 1
            except Exception as e:
                print(f"    ! Failed to delete {abs_path}: {e}")
        else:
            missing += 1

    print(f"[RESULT] {deleted} file(s) deleted, {missing} missing (already gone).")


def main() -> None:
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found at: {DB_PATH}")
        sys.exit(1)

    print("PROJECT_ROOT:", PROJECT_ROOT)
    print("DB_PATH:", DB_PATH)
    print("\nWARNING: This will PERMANENTLY delete:")
    print("  - ALL events")
    print("  - ALL abstract submissions and their history")
    print("  - ALL teams and related team records")
    print("  - Uploaded abstract files and team files from disk")
    print("\nMake sure you have a backup of database.db and static/uploads/ before continuing.\n")

    confirm = input("Type EXACTLY 'DELETE' to continue, or anything else to abort: ")
    if confirm.strip() != 'DELETE':
        print("[ABORTED] No changes were made.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Show current counts for information
        def count(table: str) -> int:
            if not table_exists(conn, table):
                return 0
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        print("\n[INFO] Current row counts before deletion:")
        for t in [
            'events',
            'event_requirements',
            'event_registrations',
            'teams',
            'team_members',
            'team_files',
            'team_activity_logs',
            'team_invitations',
            'team_join_requests',
            'abstract_submission_history',
            'abstract_submissions',
        ]:
            if table_exists(conn, t):
                print(f"  - {t}: {count(t)}")

        print("\n[STEP 1] Deleting uploaded files from disk...")
        delete_files_from_table(conn, 'abstract_submissions', 'file_path')
        delete_files_from_table(conn, 'team_files', 'file_path')

        print("\n[STEP 2] Deleting database rows (events and related data)...")
        conn.execute('PRAGMA foreign_keys = ON;')

        # Delete in dependency-safe order (children first, parents last)
        for stmt in [
            # Abstract history then submissions
            "DELETE FROM abstract_submission_history",
            "DELETE FROM abstract_submissions",
            # Team-related tables
            "DELETE FROM team_files",
            "DELETE FROM team_activity_logs",
            "DELETE FROM team_members",
            "DELETE FROM team_invitations",
            "DELETE FROM team_join_requests",
            # Event registrations / requirements
            "DELETE FROM event_registrations",
            "DELETE FROM event_requirements",
            # Teams and finally events
            "DELETE FROM teams",
            "DELETE FROM events",
        ]:
            table_name = stmt.split()[2]
            if table_exists(conn, table_name):
                print(f"  - Executing: {stmt}")
                conn.execute(stmt)
            else:
                print(f"  - [SKIP] Table '{table_name}' not found, skipping.")

        conn.commit()
        print("\n[DONE] All events, related records, and uploaded files have been deleted.")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Cleanup failed, transaction rolled back: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
