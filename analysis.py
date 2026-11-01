
import numpy as np

import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "market-risk.sqlite"

if not DB_PATH.exists():
    raise FileNotFoundError(DB_PATH)

# Read our SQL reporting view
with sqlite3.connect(DB_PATH) as conn:
    df = pd.read_sql_query("""
        SELECT *
        FROM sector_market_daily
        ORDER BY trade_date, ticker
    """, conn)

# Convert dates into proper datetime values
df["trade_date"] = pd.to_datetime(df["trade_date"])

# Validate the dataset
print("Rows:", len(df))
print("Sectors:", df["ticker"].nunique())
print("Trading days:", df["trade_date"].nunique())

duplicates = df.duplicated(
    subset=["ticker", "trade_date"]
).sum()

print("Duplicate records:", duplicates)
print("\nMissing values:")
print(df.isna().sum())

# Ensure all 11 sectors are present each day
daily_counts = df.groupby("trade_date")["ticker"].nunique()

if duplicates != 0:
    raise ValueError("Duplicate ticker-date observations.")

if not (daily_counts == 11).all():
    raise ValueError("Some trading dates are missing sectors.")

# Export unrounded analytical observations
export_path = BASE_DIR / "data" / "sector_market_daily.csv"

df.to_csv(export_path, index=False)

print(f"\nExported data to: {export_path}")


# Statistical robustness: block bootstrap
focus = ["XLK", "XLV", "XLU", "XLP"]

returns = df.pivot(
    index="trade_date",
    columns="ticker",
    values="excess_return"
).sort_index()

regimes = (
    df[df["ticker"] == "XLK"]
    .set_index("trade_date")
    [["current_regime", "previous_regime"]]
    .reindex(returns.index)
)

returns = returns[focus].to_numpy()

rng = np.random.default_rng(42)

n = len(returns)
block_size = 20
iterations = 1000

results = []

for timing, column in [
    ("Same-day", "current_regime"),
    ("Prior-day", "previous_regime")
]:
    high = regimes[column].eq("High").to_numpy()

    observed = returns[high].mean(axis=0) * 100

    boot = np.empty((iterations, len(focus)))

    for i in range(iterations):
        # Draw blocks of consecutive trading days
        starts = rng.integers(
            0, n,
            size=int(np.ceil(n / block_size))
        )

        indices = (
            starts[:, None] + np.arange(block_size)
        ) % n

        indices = indices.ravel()[:n]

        sampled_high = high[indices]
        sampled_returns = returns[indices]

        boot[i] = (
            sampled_returns[sampled_high].mean(axis=0)
            * 100
        )

    lower, upper = np.percentile(
        boot, [2.5, 97.5], axis=0
    )

    for j, ticker in enumerate(focus):
        results.append({
            "timing": timing,
            "ticker": ticker,
            "mean_excess_pp": observed[j],
            "ci_lower": lower[j],
            "ci_upper": upper[j]
        })

summary = pd.DataFrame(results)

print("\nBlock bootstrap results:")
print(summary.round(4).to_string(index=False))


# Save our original bootstrap results
summary.to_csv(
    BASE_DIR / "data" / "bootstrap_results.csv",
    index=False
)

# Sensitivity analysis for our two main findings
checks = [
    ("Same-day", "current_regime", "XLV"),
    ("Prior-day", "previous_regime", "XLK")
]

print("\nBootstrap sensitivity analysis:")

for block_days in (10, 40):
    rng = np.random.default_rng(42)

    for timing, column, ticker in checks:
        j = focus.index(ticker)
        high = regimes[column].eq("High").to_numpy()

        estimates = np.empty(2000)

        for b in range(2000):
            starts = rng.integers(
                0, n,
                size=int(np.ceil(n / block_days))
            )

            indices = (
                starts[:, None] + np.arange(block_days)
            ) % n

            indices = indices.ravel()[:n]

            selected = high[indices]

            estimates[b] = (
                returns[indices, j][selected].mean() * 100
            )

        lower, upper = np.percentile(
            estimates, [2.5, 97.5]
        )

        print(
            f"{ticker} | {timing} | "
            f"Block: {block_days} | "
            f"95% CI: [{lower:.4f}, {upper:.4f}]"
        )



# Export risk analytics for Power BI

with sqlite3.connect(DB_PATH) as conn:
    risk_summary = pd.read_sql_query(
        """
        SELECT *
        FROM sector_risk_summary
        ORDER BY ticker
        """,
        conn
    )

risk_path = BASE_DIR / "data" / "sector_risk_summary.csv"

risk_summary.to_csv(risk_path, index=False)

print("\nRisk analytics exported:")
print(risk_summary[
    ["ticker", "annualized_volatility_pct",
     "maximum_drawdown_pct"]
].round(2).to_string(index=False))

print(f"\nSaved to: {risk_path}")



# Export reproducible SQL definitions

SQL_DIR = BASE_DIR / "sql"
SQL_DIR.mkdir(exist_ok=True)

with sqlite3.connect(DB_PATH) as conn:
    objects = conn.execute("""
        SELECT type, name, sql
        FROM sqlite_master
        WHERE type IN ('table', 'view', 'index')
          AND sql IS NOT NULL
          AND name NOT LIKE 'sqlite_%'
        ORDER BY
            CASE type
                WHEN 'table' THEN 1
                WHEN 'index' THEN 2
                WHEN 'view' THEN 3
            END,
            name
    """).fetchall()

    schema_statements = []
    reporting_statements = []

    for object_type, name, sql in objects:
        statement = sql.rstrip(";") + ";"

        if object_type == "view":
            reporting_statements.append(statement)
        else:
            schema_statements.append(statement)

    # Preserve the 12 ETF definitions.
    instruments = conn.execute("""
        SELECT ticker, name, sector, asset_type
        FROM instruments
        ORDER BY ticker
    """).fetchall()

    seed_statements = []

    for instrument in instruments:
        quoted = conn.execute(
            "SELECT quote(?), quote(?), quote(?), quote(?)",
            instrument
        ).fetchone()

        seed_statements.append(
            "INSERT OR IGNORE INTO instruments "
            "(ticker, name, sector, asset_type) "
            f"VALUES ({', '.join(quoted)});"
        )

schema_path = SQL_DIR / "schema.sql"
reporting_path = SQL_DIR / "reporting.sql"

schema_path.write_text(
    "PRAGMA foreign_keys = ON;\n\n"
    + "\n\n".join(schema_statements)
    + "\n\n"
    + "\n".join(seed_statements)
    + "\n",
    encoding="utf-8"
)

reporting_path.write_text(
    "\n\n".join(reporting_statements) + "\n",
    encoding="utf-8"
)

print("\nSQL definitions exported:")
print(f"Schema objects: {len(schema_statements)}")
print(f"Reporting views: {len(reporting_statements)}")
print(f"Seed instruments: {len(seed_statements)}")
print(f"Saved to: {SQL_DIR}")


