#!/usr/bin/env python3
"""
BJS Admin CLI Tool

Headless/CLI-Variante des Admin-Tools für:
- CSV-Import von Schülerdaten
- Riegen-Erstellung
- DB-Export für die Web-App
- Backup-Erstellung

Nutzung:
    python -m admin.cli --help
    python -m admin.cli import-csv --csv path/to/schueler.csv --output bjs_2025.db
    python -m admin.cli create-riege --name "MaxMustermann" --stufe 5 --klassen "a,b,c" --geschlecht m
    python -m admin.cli export-db --source admin/bjs_database_2025.db --target app/database/
    python -m admin.cli backup --source app/database/bjs_database_2025.db
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import numpy as np
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("Warning: pandas not installed. CSV import will not work.")

from admin.admin_database import Database


def log_info(message: str):
    """Print info message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] ℹ️  {message}")


def log_success(message: str):
    """Print success message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] ✅ {message}")


def log_error(message: str):
    """Print error message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] ❌ {message}", file=sys.stderr)


def log_warning(message: str):
    """Print warning message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] ⚠️  {message}")


def log_progress(current: int, total: int, message: str = ""):
    """Print progress bar."""
    percent = (current / total) * 100 if total > 0 else 0
    bar_length = 30
    filled = int(bar_length * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_length - filled)
    print(f"\r    [{bar}] {percent:.1f}% {message}", end="", flush=True)
    if current >= total:
        print()  # New line when complete


def validate_csv_file(csv_path: str) -> tuple[bool, str]:
    """
    Validate CSV file format.

    Expected columns:
    - Geschlecht (m/w)
    - Klasse (e.g., 5a)
    - Name
    - Vorname
    - Geburtsjahr
    - Profil (True/False)
    """
    if not HAS_PANDAS:
        return False, "pandas not installed"

    if not os.path.exists(csv_path):
        return False, f"File not found: {csv_path}"

    try:
        # Try different delimiters
        for delimiter in [";", ",", "\t"]:
            try:
                df = pd.read_csv(csv_path, delimiter=delimiter, nrows=5)
                if len(df.columns) >= 5:
                    break
            except Exception:
                continue

        expected_columns = {"Geschlecht", "Klasse", "Name", "Vorname", "Geburtsjahr"}
        actual_columns = set(df.columns)

        missing = expected_columns - actual_columns
        if missing:
            # Try case-insensitive matching
            actual_lower = {c.lower() for c in df.columns}
            missing_lower = {c.lower() for c in missing}
            if missing_lower - actual_lower:
                return False, f"Missing columns: {', '.join(missing)}"

        return True, "Valid"

    except Exception as e:
        return False, f"Error reading CSV: {e}"


def import_csv(csv_path: str, db_path: str, delimiter: str = ";") -> int:
    """
    Import students from CSV file.

    Returns number of imported students.
    """
    if not HAS_PANDAS:
        log_error("pandas is required for CSV import. Install with: pip install pandas")
        return 0

    log_info(f"Reading CSV: {csv_path}")

    try:
        df = pd.read_csv(csv_path, delimiter=delimiter)
        log_info(f"Found {len(df)} rows, {len(df.columns)} columns")
        log_info(f"Columns: {', '.join(df.columns)}")
    except Exception as e:
        log_error(f"Failed to read CSV: {e}")
        return 0

    # Initialize database
    log_info(f"Initializing database: {db_path}")
    db = Database(path=db_path)

    imported = 0
    errors = 0
    data = np.array(df)
    total = len(data)

    log_info(f"Importing {total} students...")

    for i, row in enumerate(data):
        try:
            # Expected format: Geschlecht, Klasse, Name, Vorname, Geburtsjahr, Profil
            geschlecht = str(row[0]).lower().strip()
            klasse_full = str(row[1]).strip()
            name = str(row[2]).strip()
            vorname = str(row[3]).strip()
            geburtsjahr = int(row[4])

            # Profil handling
            profil = False
            if len(row) > 5:
                profil_val = row[5]
                if isinstance(profil_val, bool):
                    profil = profil_val
                elif isinstance(profil_val, str):
                    profil = profil_val.lower() in ("true", "1", "yes", "ja")

            # Parse Klasse (e.g., "5a" -> stufe=5, buchstabe="a")
            stufe = int(klasse_full[:-1]) if klasse_full[:-1].isdigit() else 5
            klassenbuchstabe = klasse_full[-1] if klasse_full else ""

            db.add_schueler(
                name=name,
                vorname=vorname,
                geschlecht=geschlecht,
                klasse=stufe,
                klassenbuchstabe=klassenbuchstabe,
                geburtsjahr=geburtsjahr,
                profil=profil,
            )
            imported += 1

        except Exception as e:
            errors += 1
            if errors <= 5:
                log_warning(f"Row {i + 1} error: {e}")
            elif errors == 6:
                log_warning("Suppressing further row errors...")

        if (i + 1) % 10 == 0 or i + 1 == total:
            log_progress(i + 1, total, f"({imported} imported, {errors} errors)")

    db.connection.close()

    log_success(f"Import complete: {imported} students imported, {errors} errors")
    return imported


def create_riege(
    db_path: str,
    name: str,
    stufe: int,
    klassen: str,
    geschlecht: str,
    profil: bool = False,
) -> int:
    """
    Create a new Riege and assign students.

    Args:
        db_path: Path to database
        name: Riegenführer name
        stufe: Class level (5-10)
        klassen: Comma-separated class letters (e.g., "a,b,c")
        geschlecht: m, w, or mw (both)
        profil: Sports profile flag

    Returns:
        Riegenführer ID
    """
    log_info(f"Creating Riege: {name}")
    log_info(
        f"  Stufe: {stufe}, Klassen: {klassen}, Geschlecht: {geschlecht}, Profil: {profil}"
    )

    db = Database(path=db_path)

    # Parse klassenendungen
    klassenendungen = klassen.replace(" ", "").replace(",", "")

    # Create Riegenführer
    try:
        rf_id = db.add_riegenfuehrer(
            name=name,
            geschlecht=geschlecht.upper() if len(geschlecht) <= 2 else geschlecht,
            profil=profil,
            stufe=stufe,
            klassenendung=klassenendungen,
        )
        log_success(f"Created Riegenführer with ID: {rf_id}")
    except Exception as e:
        log_error(f"Failed to create Riegenführer: {e}")
        db.connection.close()
        return 0

    # Assign students
    assigned = 0
    geschlechter = (
        ["m", "w"]
        if geschlecht.lower() == "mw" or geschlecht.lower() == "beide"
        else [geschlecht.lower()]
    )

    for kl_end in klassenendungen:
        for g in geschlechter:
            try:
                db.add_riegenfuehrer_to_schueler(
                    rf_id=rf_id,
                    klassenbuchstabe=kl_end,
                    stufe=stufe,
                    geschlecht=g,
                    profil=profil,
                )
                # Count affected students
                db.cursor.execute(
                    "SELECT COUNT(*) FROM Schueler WHERE RiegenfuehrerID = ?", (rf_id,)
                )
                assigned = db.cursor.fetchone()[0]
            except Exception as e:
                log_warning(f"Error assigning students ({kl_end}, {g}): {e}")

    db.connection.close()
    log_success(f"Assigned {assigned} students to Riege")
    return rf_id


def export_db(source_path: str, target_path: str) -> bool:
    """
    Export/copy database to target location.

    Args:
        source_path: Source database path
        target_path: Target directory or file path

    Returns:
        Success status
    """
    log_info(f"Exporting database from: {source_path}")

    if not os.path.exists(source_path):
        log_error(f"Source database not found: {source_path}")
        return False

    target = Path(target_path)

    # If target is a directory, use same filename
    if target.is_dir() or target_path.endswith("/") or target_path.endswith("\\"):
        target.mkdir(parents=True, exist_ok=True)
        target = target / Path(source_path).name
    else:
        target.parent.mkdir(parents=True, exist_ok=True)

    log_info(f"Target: {target}")

    try:
        shutil.copy2(source_path, target)
        file_size = target.stat().st_size / 1024
        log_success(f"Database exported: {target} ({file_size:.1f} KB)")
        return True
    except Exception as e:
        log_error(f"Export failed: {e}")
        return False


def create_backup(db_path: str, backup_dir: str = None) -> str:
    """
    Create a backup of the database.

    Args:
        db_path: Database path
        backup_dir: Optional backup directory (default: same as db)

    Returns:
        Backup file path
    """
    log_info(f"Creating backup of: {db_path}")

    if not os.path.exists(db_path):
        log_error(f"Database not found: {db_path}")
        return ""

    source = Path(db_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{source.stem}_backup_{timestamp}.db"

    if backup_dir:
        backup_path = Path(backup_dir) / backup_name
        backup_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        backup_path = source.with_name(backup_name)

    try:
        shutil.copy2(source, backup_path)
        file_size = backup_path.stat().st_size / 1024
        log_success(f"Backup created: {backup_path} ({file_size:.1f} KB)")
        return str(backup_path)
    except Exception as e:
        log_error(f"Backup failed: {e}")
        return ""


def list_riegen(db_path: str):
    """List all Riegenführer in the database."""
    log_info(f"Listing Riegen from: {db_path}")

    if not os.path.exists(db_path):
        log_error(f"Database not found: {db_path}")
        return

    db = Database(path=db_path)

    db.cursor.execute("""
        SELECT r.ID, r.Name, r.Geschlecht, r.Profil, r.Stufe, r.Klassenendungen,
               COUNT(s.SchuelerID) as schueler_count
        FROM Riegenfuehrer r
        LEFT JOIN Schueler s ON s.RiegenfuehrerID = r.ID
        GROUP BY r.ID
        ORDER BY r.Name
    """)

    rows = db.cursor.fetchall()
    db.connection.close()

    if not rows:
        log_warning("No Riegen found in database")
        return

    print("\n" + "=" * 80)
    print(
        f"{'ID':<5} {'Name':<25} {'Geschl.':<8} {'Profil':<8} {'Stufe':<6} {'Klassen':<10} {'Schüler':<8}"
    )
    print("=" * 80)

    for row in rows:
        profil_str = "Ja" if row[3] else "Nein"
        print(
            f"{row[0]:<5} {row[1]:<25} {row[2]:<8} {profil_str:<8} {row[4]:<6} {row[5]:<10} {row[6]:<8}"
        )

    print("=" * 80)
    print(f"Total: {len(rows)} Riegen")


def show_stats(db_path: str):
    """Show database statistics."""
    log_info(f"Database statistics: {db_path}")

    if not os.path.exists(db_path):
        log_error(f"Database not found: {db_path}")
        return

    db = Database(path=db_path)

    stats = {}

    # Count students
    db.cursor.execute("SELECT COUNT(*) FROM Schueler")
    stats["students"] = db.cursor.fetchone()[0]

    # Count students with Riege
    db.cursor.execute("SELECT COUNT(*) FROM Schueler WHERE RiegenfuehrerID IS NOT NULL")
    stats["students_assigned"] = db.cursor.fetchone()[0]

    # Count Riegen
    db.cursor.execute("SELECT COUNT(*) FROM Riegenfuehrer")
    stats["riegen"] = db.cursor.fetchone()[0]

    # Count results
    try:
        db.cursor.execute("SELECT COUNT(*) FROM Schueler_Disziplin_Ergebnis")
        stats["results"] = db.cursor.fetchone()[0]
    except Exception:
        stats["results"] = 0

    # Gender distribution
    db.cursor.execute("""
        SELECT Geschlecht, COUNT(*) FROM Schueler GROUP BY Geschlecht
    """)
    stats["gender"] = {row[0]: row[1] for row in db.cursor.fetchall()}

    # Class distribution
    db.cursor.execute("""
        SELECT Klasse, COUNT(*) FROM Schueler GROUP BY Klasse ORDER BY Klasse
    """)
    stats["classes"] = {row[0]: row[1] for row in db.cursor.fetchall()}

    db.connection.close()

    # Display
    print("\n" + "=" * 50)
    print("DATABASE STATISTICS")
    print("=" * 50)
    print(f"Total Students:     {stats['students']}")
    print(f"Assigned to Riege:  {stats['students_assigned']}")
    print(f"Unassigned:         {stats['students'] - stats['students_assigned']}")
    print(f"Total Riegen:       {stats['riegen']}")
    print(f"Total Results:      {stats['results']}")
    print("-" * 50)
    print("Gender Distribution:")
    for gender, count in stats["gender"].items():
        print(f"  {gender}: {count}")
    print("-" * 50)
    print("Class Distribution:")
    for klasse, count in stats["classes"].items():
        print(f"  Klasse {klasse}: {count}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="BJS Admin CLI Tool - Headless database management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Import CSV:
    python -m admin.cli import-csv --csv data/schueler.csv --db bjs_2025.db

  Create Riege:
    python -m admin.cli create-riege --db bjs_2025.db --name "MaxMustermann" --stufe 5 --klassen "a,b" --geschlecht m

  Export DB:
    python -m admin.cli export-db --source admin/bjs_2025.db --target ../app/database/

  Create Backup:
    python -m admin.cli backup --db bjs_2025.db --dir backups/

  Show Statistics:
    python -m admin.cli stats --db bjs_2025.db

  List Riegen:
    python -m admin.cli list-riegen --db bjs_2025.db
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Import CSV command
    import_parser = subparsers.add_parser("import-csv", help="Import students from CSV")
    import_parser.add_argument("--csv", required=True, help="Path to CSV file")
    import_parser.add_argument(
        "--db", default=f"bjs_database_{datetime.now().year}.db", help="Database path"
    )
    import_parser.add_argument(
        "--delimiter", default=";", help="CSV delimiter (default: ;)"
    )

    # Create Riege command
    riege_parser = subparsers.add_parser("create-riege", help="Create a new Riege")
    riege_parser.add_argument("--db", required=True, help="Database path")
    riege_parser.add_argument("--name", required=True, help="Riegenführer name")
    riege_parser.add_argument(
        "--stufe", type=int, required=True, help="Class level (5-10)"
    )
    riege_parser.add_argument(
        "--klassen", required=True, help="Class letters (e.g., 'a,b,c')"
    )
    riege_parser.add_argument(
        "--geschlecht", required=True, choices=["m", "w", "mw"], help="Gender (m/w/mw)"
    )
    riege_parser.add_argument("--profil", action="store_true", help="Sports profile")

    # Export DB command
    export_parser = subparsers.add_parser(
        "export-db", help="Export database to target location"
    )
    export_parser.add_argument("--source", required=True, help="Source database path")
    export_parser.add_argument(
        "--target", required=True, help="Target directory or file path"
    )

    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Create database backup")
    backup_parser.add_argument("--db", required=True, help="Database path")
    backup_parser.add_argument(
        "--dir", help="Backup directory (default: same as source)"
    )

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.add_argument("--db", required=True, help="Database path")

    # List Riegen command
    list_parser = subparsers.add_parser("list-riegen", help="List all Riegen")
    list_parser.add_argument("--db", required=True, help="Database path")

    # Validate CSV command
    validate_parser = subparsers.add_parser(
        "validate-csv", help="Validate CSV file format"
    )
    validate_parser.add_argument("--csv", required=True, help="Path to CSV file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    print()
    print("=" * 60)
    print("  BJS Admin CLI Tool")
    print("=" * 60)
    print()

    try:
        if args.command == "import-csv":
            valid, msg = validate_csv_file(args.csv)
            if not valid:
                log_error(f"CSV validation failed: {msg}")
                return 1
            count = import_csv(args.csv, args.db, args.delimiter)
            return 0 if count > 0 else 1

        elif args.command == "create-riege":
            rf_id = create_riege(
                db_path=args.db,
                name=args.name,
                stufe=args.stufe,
                klassen=args.klassen,
                geschlecht=args.geschlecht,
                profil=args.profil,
            )
            return 0 if rf_id > 0 else 1

        elif args.command == "export-db":
            success = export_db(args.source, args.target)
            return 0 if success else 1

        elif args.command == "backup":
            path = create_backup(args.db, args.dir)
            return 0 if path else 1

        elif args.command == "stats":
            show_stats(args.db)
            return 0

        elif args.command == "list-riegen":
            list_riegen(args.db)
            return 0

        elif args.command == "validate-csv":
            valid, msg = validate_csv_file(args.csv)
            if valid:
                log_success(f"CSV file is valid: {msg}")
                return 0
            else:
                log_error(f"CSV validation failed: {msg}")
                return 1

    except KeyboardInterrupt:
        print("\n")
        log_warning("Operation cancelled by user")
        return 130
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
