"""Headless client, collector, and strategy toolkit for the Giggles video market.

The package is organized by phase of the plan in ``.claude/workspace``:

- :mod:`giggles.config`, :mod:`giggles.auth`, :mod:`giggles.client` talk to the
  backend the mobile app uses, with every response recorded for schema discovery.
- :mod:`giggles.store` and :mod:`giggles.collector` build the dataset Phase 0 needs.
- :mod:`giggles.analysis` identifies the pricing model from that dataset.
- :mod:`giggles.strategy` holds the fee-aware sizing and signal math.
- :mod:`giggles.faucets` claims the deterministic Aura sources.
"""
