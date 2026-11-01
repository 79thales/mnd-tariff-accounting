"""Syntetické regrese registrace zdroje; neověřují živý mobilní prohlížeč."""

import unittest
from unittest.mock import AsyncMock, Mock

from custom_components.mnd_tariff_accounting.frontend_resource import ensure_resource

URL = "/mnd_tariff_accounting/mnd-panel.js?v=synthetic-new"


class ResourceTests(unittest.IsolatedAsyncioTestCase):
    def resources(self, items):
        resources = Mock()
        resources.async_get_info = AsyncMock()
        resources.async_items.return_value = items
        resources.async_create_item = AsyncMock()
        resources.async_update_item = AsyncMock()
        return resources

    async def test_new_source_loads_collection_before_creation(self):
        resources = self.resources([])
        resources.async_items.side_effect = lambda: (
            self.assertEqual(resources.async_get_info.await_count, 1) or []
        )
        self.assertEqual(await ensure_resource(resources, URL), "created")
        resources.async_create_item.assert_awaited_once_with({"url": URL, "res_type": "module"})

    async def test_existing_source_is_idempotent(self):
        resources = self.resources([{"id": "synthetic", "url": URL, "type": "module"}])
        self.assertEqual(await ensure_resource(resources, URL), "unchanged")
        resources.async_create_item.assert_not_awaited()
        resources.async_update_item.assert_not_awaited()

    async def test_upgrade_changes_hash_and_type_without_creating_duplicate(self):
        resources = self.resources([
            {"id": "synthetic", "url": URL.split("?")[0] + "?v=old", "type": "js"}
        ])
        self.assertEqual(await ensure_resource(resources, URL), "updated")
        resources.async_update_item.assert_awaited_once_with(
            "synthetic", {"url": URL, "res_type": "module"}
        )
        resources.async_create_item.assert_not_awaited()

    async def test_external_source_with_same_path_is_not_overwritten(self):
        resources = self.resources([{"id": "foreign", "url": "https://example.org" + URL}])
        self.assertEqual(await ensure_resource(resources, URL), "created")
        resources.async_update_item.assert_not_awaited()

    async def test_storage_failure_is_not_reported_as_success(self):
        resources = self.resources([])
        resources.async_create_item.side_effect = RuntimeError("synthetic storage failure")
        with self.assertRaisesRegex(RuntimeError, "synthetic storage failure"):
            await ensure_resource(resources, URL)
