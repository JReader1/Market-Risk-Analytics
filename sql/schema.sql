PRAGMA foreign_keys = ON;

CREATE TABLE daily_prices (
                                            ticker TEXT NOT NULL,
                                            trade_date TEXT NOT NULL,
                                            adjusted_close REAL NOT NULL CHECK (adjusted_close > 0),
                                            volume INTEGER CHECK (volume >= 0),

                                            PRIMARY KEY (ticker, trade_date),

                                            FOREIGN KEY (ticker)
                                                REFERENCES instruments(ticker)
);

CREATE TABLE instruments (
                                           ticker TEXT PRIMARY KEY,
                                           name TEXT NOT NULL,
                                           sector TEXT,
                                           asset_type TEXT NOT NULL
);

CREATE TABLE market_indicators (
                                                 trade_date TEXT PRIMARY KEY,
                                                 vix_close REAL NOT NULL CHECK (vix_close >= 0)
);

CREATE INDEX idx_prices_date
    ON daily_prices(trade_date);

INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_type) VALUES ('SPY', 'SPDR S&P 500 ETF Trust', NULL, 'Benchmark ETF');
INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_type) VALUES ('XLB', 'Materials Select Sector SPDR', 'Materials', 'Sector ETF');
INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_type) VALUES ('XLC', 'Communication Services Select Sector SPDR', 'Communication Services', 'Sector ETF');
INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_type) VALUES ('XLE', 'Energy Select Sector SPDR', 'Energy', 'Sector ETF');
INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_type) VALUES ('XLF', 'Financial Select Sector SPDR', 'Financials', 'Sector ETF');
INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_type) VALUES ('XLI', 'Industrial Select Sector SPDR', 'Industrials', 'Sector ETF');
INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_type) VALUES ('XLK', 'Technology Select Sector SPDR', 'Information Technology', 'Sector ETF');
INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_type) VALUES ('XLP', 'Consumer Staples Select Sector SPDR', 'Consumer Staples', 'Sector ETF');
INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_type) VALUES ('XLRE', 'Real Estate Select Sector SPDR', 'Real Estate', 'Sector ETF');
INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_type) VALUES ('XLU', 'Utilities Select Sector SPDR', 'Utilities', 'Sector ETF');
INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_type) VALUES ('XLV', 'Health Care Select Sector SPDR', 'Health Care', 'Sector ETF');
INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_type) VALUES ('XLY', 'Consumer Discretionary Select Sector SPDR', 'Consumer Discretionary', 'Sector ETF');
