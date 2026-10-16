"""Stabilní doména, verze archivu a identifikátory vlastního frontendu."""

DOMAIN = "mnd_tariff_accounting"
VERSION = "0.1.0"
# Pro 2026.3.0 nebyl vydán přesně odpovídající testovací plugin; 0.13.317
# cílí 2026.3.1. Jde o minimum testovací matice, ne o již potvrzený live test.
MIN_HA_VERSION = "2026.3.1"
PANEL_PATH = "mnd-tariff-accounting"
PLATFORMS = ["sensor", "button"]
POLL_HOURS = 6
SOURCE_DEBOUNCE_SECONDS = 30
