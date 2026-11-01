
import sqlite3
from pathlib import Path

import pandas as pd
import yfinance as yf


# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "market-risk.sqlite"

SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql"
REPORTING_PATH = BASE_DIR / "sql" / "reporting.sql"

START_DATE = "2019-01-01"
END_DATE = "2026-01-01"


# --------------------------------------------------
# Database initialization
# --------------------------------------------------

def initialize_database(db_path=DB_PATH):
    """Initialize the database without deleting existing data."""

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Missing SQL schema: {SCHEMA_PATH}"
        )

    if not REPORTING_PATH.exists():
        raise FileNotFoundError(
            f"Missing reporting SQL: {REPORTING_PATH}"
        )

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        existing_tables = {
            row[0]
            for row in conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
            """)
        }

        if not existing_tables:
            conn.executescript(
                SCHEMA_PATH.read_text(encoding="utf-8")
            )

        required_tables = {
            "instruments",
            "daily_prices",
            "market_indicators",
        }

        missing_tables = required_tables - {
            row[0]
            for row in conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
            """)
        }

        if missing_tables:
            raise RuntimeError(
                f"Missing database tables: {missing_tables}"
            )

        instruments = conn.execute(
            "SELECT COUNT(*) FROM instruments"
        ).fetchone()[0]

        if instruments != 12:
            raise RuntimeError(
                f"Expected 12 instruments, found {instruments}"
            )

    print(f"Database ready: {db_path}")
    print(f"Instruments loaded: {instruments}")


# --------------------------------------------------
# Download historical ETF prices
# --------------------------------------------------

def download_missing_prices(db_path=DB_PATH):
    """Download ETFs with no stored historical prices."""

    with sqlite3.connect(db_path) as conn:
        tickers = [
            row[0]
            for row in conn.execute("""
                SELECT ticker
                FROM instruments
                WHERE ticker NOT IN (
                    SELECT DISTINCT ticker
                    FROM daily_prices
                )
                ORDER BY ticker
            """)
        ]

    if not tickers:
        print("\nETF prices already stored. Skipping download.")
        return

    for ticker in tickers:
        print(f"\nDownloading {ticker}...")

        try:
            prices = yf.download(
                ticker,
                start=START_DATE,
                end=END_DATE,
                interval="1d",
                auto_adjust=True,
                multi_level_index=False,
                progress=False,
            )

            if prices.empty:
                print(f"No data returned for {ticker}.")
                continue

            records = []

            for date, row in prices.iterrows():
                close = row["Close"]
                volume = row["Volume"]

                if pd.isna(close) or close <= 0:
                    continue

                records.append((
                    ticker,
                    date.strftime("%Y-%m-%d"),
                    float(close),
                    int(volume) if pd.notna(volume) else None,
                ))

            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")

                conn.executemany("""
                    INSERT INTO daily_prices
                        (ticker, trade_date, adjusted_close, volume)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(ticker, trade_date)
                    DO UPDATE SET
                        adjusted_close = excluded.adjusted_close,
                        volume = excluded.volume
                """, records)

            print(f"Stored {len(records)} rows for {ticker}.")

        except Exception as error:
            print(f"Failed to import {ticker}: {error}")


# --------------------------------------------------
# Download historical VIX observations
# --------------------------------------------------

def download_vix(db_path=DB_PATH):
    """Download VIX observations if not already populated."""

    with sqlite3.connect(db_path) as conn:
        existing_vix = conn.execute(
            "SELECT COUNT(*) FROM market_indicators"
        ).fetchone()[0]

    if existing_vix > 0:
        print(
            f"\nVIX observations already stored: "
            f"{existing_vix}. Skipping download."
        )
        return

    print("\nDownloading VIX data...")

    vix = yf.download(
        "^VIX",
        start=START_DATE,
        end=END_DATE,
        interval="1d",
        auto_adjust=False,
        multi_level_index=False,
        progress=False,
    )

    if vix.empty:
        raise ValueError("No VIX data downloaded.")

    records = []

    for date, row in vix.iterrows():
        value = row["Close"]

        if pd.isna(value) or value <= 0:
            continue

        records.append((
            date.strftime("%Y-%m-%d"),
            float(value),
        ))

    with sqlite3.connect(db_path) as conn:
        conn.executemany("""
            INSERT INTO market_indicators
                (trade_date, vix_close)
            VALUES (?, ?)
            ON CONFLICT(trade_date)
            DO UPDATE SET
                vix_close = excluded.vix_close
        """, records)

    print(f"Stored {len(records)} VIX observations.")


# --------------------------------------------------
# Initialize SQL reporting views
# --------------------------------------------------

def initialize_reporting_views(db_path=DB_PATH):
    """Create missing reporting views from the SQL script."""

    with sqlite3.connect(db_path) as conn:
        existing_views = {
            row[0]
            for row in conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'view'
            """)
        }

        if not existing_views:
            conn.executescript(
                REPORTING_PATH.read_text(encoding="utf-8")
            )

        views = [
            row[0]
            for row in conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'view'
                ORDER BY name
            """)
        ]

        if len(views) != 6:
            raise RuntimeError(
                f"Expected 6 reporting views, "
                f"found {len(views)}: {views}"
            )

        for view in views:
            conn.execute(
                f'SELECT * FROM "{view}" LIMIT 0'
            ).fetchall()

    print(f"\nReporting views verified: {len(views)}")


# --------------------------------------------------
# Validate imported data
# --------------------------------------------------

def validate_database(db_path=DB_PATH):
    """Validate ETF coverage and market observations."""

    with sqlite3.connect(db_path) as conn:
        total_prices = conn.execute("""
            SELECT COUNT(*)
            FROM daily_prices
        """).fetchone()[0]

        securities = conn.execute("""
            SELECT COUNT(DISTINCT ticker)
            FROM daily_prices
        """).fetchone()[0]

        vix_count = conn.execute("""
            SELECT COUNT(*)
            FROM market_indicators
        """).fetchone()[0]

        duplicates = conn.execute("""
            SELECT COUNT(*)
            FROM (
                SELECT ticker, trade_date
                FROM daily_prices
                GROUP BY ticker, trade_date
                HAVING COUNT(*) > 1
            )
        """).fetchone()[0]

        missing_prices = conn.execute("""
            SELECT COUNT(*)
            FROM daily_prices
            WHERE adjusted_close IS NULL
               OR adjusted_close <= 0
        """).fetchone()[0]

        unmatched_dates = conn.execute("""
            SELECT COUNT(*)
            FROM daily_prices AS p
            LEFT JOIN market_indicators AS m
              ON p.trade_date = m.trade_date
            WHERE m.trade_date IS NULL
        """).fetchone()[0]

    print("\n--- Database Validation ---")
    print(f"Price records: {total_prices}")
    print(f"Securities imported: {securities}/12")
    print(f"VIX observations: {vix_count}")
    print(f"Duplicate price records: {duplicates}")
    print(f"Invalid price records: {missing_prices}")
    print(f"Price rows without VIX: {unmatched_dates}")

    if (
        securities != 12
        or total_prices == 0
        or vix_count == 0
        or duplicates != 0
        or missing_prices != 0
        or unmatched_dates != 0
    ):
        raise RuntimeError(
            "Database validation failed. "
            "Review the imported market data."
        )

    print("\nDatabase validation PASSED.")


# --------------------------------------------------
# Main execution
# --------------------------------------------------

def main():
    print("MARKET RISK ANALYTICS")
    print("=" * 40)

    initialize_database()
    download_missing_prices()
    download_vix()
    initialize_reporting_views()
    validate_database()

    print("\nMarket data pipeline completed successfully.")


if __name__ == "__main__":
    main()
