# Delivery Plan

Small independently verified phases.

## phase-01 — Project Skeleton

- FastAPI app factory and Jinja templates
- SQLite settings, health endpoint, landing page
- `make test`, `make run`

## phase-02 — Web Authentication

- Register, login, logout
- Salted password hashing and signed session cookie
- Protect dashboard and listing pages

## phase-03 — Data Layer

- User, watchlist, and market-data models
- Normalized stock/fund symbol handling
- Deterministic test fixtures plus live provider adapters

## phase-04 — Analysis

- Return, volatility, maximum drawdown, trend and moving averages
- Clear handling for empty/invalid series

## phase-05 — Web UI / API

- Protected dashboard and analysis pages
- Add/remove saved symbols
- JSON analysis endpoint

## phase-06 — Documentation

- Configuration, runtime commands, known limitations

## Completed

- phase-01 project skeleton
- phase-02 authentication
- phase-03 data layer
- phase-04 indicators
- phase-05 web and JSON interface
- phase-06 documentation
- phase-07 CSV upload/import

## Next phase

- phase-08 multi-asset comparison and expanded screening
