CREATE VIEW daily_returns AS

WITH price_history AS (
    SELECT
        ticker,
        trade_date,
        adjusted_close,

        LAG(adjusted_close) OVER (
            PARTITION BY ticker
            ORDER BY trade_date
            ) AS previous_close

    FROM daily_prices
)

SELECT
    ticker,
    trade_date,
    adjusted_close / previous_close - 1.0
        AS daily_return

FROM price_history

WHERE previous_close IS NOT NULL;

CREATE VIEW portfolio_daily_returns AS

SELECT
    trade_date,

    SUM(
            CASE ticker
                WHEN 'XLK' THEN 0.40 * daily_return
                WHEN 'XLE' THEN 0.30 * daily_return
                WHEN 'XLP' THEN 0.30 * daily_return
                END
    ) AS daily_return

FROM daily_returns

WHERE ticker IN ('XLK', 'XLE', 'XLP')

GROUP BY trade_date

HAVING COUNT(DISTINCT ticker) = 3;

CREATE VIEW price_drawdowns AS

WITH running_peaks AS (
    SELECT
        ticker,
        trade_date,
        adjusted_close,

        MAX(adjusted_close) OVER (
            PARTITION BY ticker
            ORDER BY trade_date
            ROWS BETWEEN UNBOUNDED PRECEDING
                AND CURRENT ROW
            ) AS running_peak

    FROM daily_prices
)

SELECT
    ticker,
    trade_date,
    adjusted_close,
    running_peak,

    adjusted_close / running_peak - 1.0
        AS drawdown

FROM running_peaks;

CREATE VIEW sector_market_daily AS

WITH vix_history AS (
    SELECT
        trade_date,
        vix_close,

        LAG(vix_close) OVER (
            ORDER BY trade_date
            ) AS previous_vix

    FROM market_indicators
)

SELECT
    r.trade_date,
    r.ticker,
    i.sector,

    r.daily_return AS sector_return,
    spy.daily_return AS market_return,

    r.daily_return - spy.daily_return
        AS excess_return,

    v.vix_close,
    v.previous_vix,

    CASE
        WHEN v.vix_close < 15 THEN 'Low'
        WHEN v.vix_close <= 25 THEN 'Moderate'
        ELSE 'High'
        END AS current_regime,

    CASE
        WHEN v.previous_vix < 15 THEN 'Low'
        WHEN v.previous_vix <= 25 THEN 'Moderate'
        ELSE 'High'
        END AS previous_regime

FROM daily_returns AS r

         JOIN instruments AS i
              ON r.ticker = i.ticker

         JOIN daily_returns AS spy
              ON r.trade_date = spy.trade_date
                  AND spy.ticker = 'SPY'

         JOIN vix_history AS v
              ON r.trade_date = v.trade_date

WHERE i.asset_type = 'Sector ETF';

CREATE VIEW sector_regime_summary AS

WITH regime_data AS (

    SELECT
        'Same-day' AS timing,
        ticker,
        sector,
        current_regime AS regime,
        sector_return,
        market_return,
        excess_return

    FROM sector_market_daily

    UNION ALL

    SELECT
        'Prior-day' AS timing,
        ticker,
        sector,
        previous_regime AS regime,
        sector_return,
        market_return,
        excess_return

    FROM sector_market_daily

    WHERE previous_vix IS NOT NULL
)

SELECT
    timing,
    ticker,
    sector,
    regime,

    COUNT(*) AS observations,

    ROUND(
            AVG(sector_return) * 100, 4
    ) AS avg_sector_return_pct,

    ROUND(
            AVG(market_return) * 100, 4
    ) AS avg_spy_return_pct,

    ROUND(
            AVG(excess_return) * 100, 4
    ) AS avg_excess_return_pp,

    ROUND(
            AVG(
                    CASE
                        WHEN excess_return > 0 THEN 1.0
                        ELSE 0.0
                        END
            ) * 100, 2
    ) AS days_beating_spy_pct

FROM regime_data

GROUP BY
    timing,
    ticker,
    sector,
    regime;

CREATE VIEW sector_risk_summary AS

WITH return_stats AS (
    SELECT
        ticker,
        COUNT(*) AS observations,
        AVG(daily_return) AS mean_return,
        AVG(daily_return * daily_return) AS mean_squared_return
    FROM daily_returns
    GROUP BY ticker
),

     volatility AS (
         SELECT
             ticker,
             observations,
             mean_return * 100.0 AS avg_daily_return_pct,

             SQRT(
                     MAX(
                             0.0,
                             (mean_squared_return - mean_return * mean_return)
                                 * observations / (observations - 1.0)
                     )
             ) * SQRT(252.0) * 100.0
                                 AS annualized_volatility_pct

         FROM return_stats
         WHERE observations > 1
     ),

     ranked_drawdowns AS (
         SELECT
             ticker,
             trade_date AS trough_date,
             drawdown,

             ROW_NUMBER() OVER (
                 PARTITION BY ticker
                 ORDER BY drawdown ASC, trade_date ASC
                 ) AS risk_rank

         FROM price_drawdowns
     )

SELECT
    v.ticker,
    COALESCE(i.sector, 'S&P 500 Benchmark') AS sector,
    i.asset_type,
    v.observations,
    v.avg_daily_return_pct,
    v.annualized_volatility_pct,
    d.drawdown * 100.0 AS maximum_drawdown_pct,
    d.trough_date

FROM volatility AS v

         JOIN instruments AS i
              ON v.ticker = i.ticker

         JOIN ranked_drawdowns AS d
              ON v.ticker = d.ticker
                  AND d.risk_rank = 1;
