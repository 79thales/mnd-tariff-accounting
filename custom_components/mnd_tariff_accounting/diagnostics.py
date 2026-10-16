"""Diagnostika podle whitelistu; žádné částky, identity, dokumenty ani vstupy."""


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    data = coordinator.repository.data
    return {
        "schema_version": data["schema_version"],
        "revision": data["revision"],
        "place_count": len(data["places"]),
        "cloud_status": coordinator.cloud_status,
        "places": [
            {
                "reading_count": len(place["readings"]),
                "import_count": len(place["imports"]),
                "snapshot_count": len(place["snapshots"]),
            }
            for place in data["places"].values()
        ],
    }
