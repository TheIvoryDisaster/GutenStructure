"""Manifest boundary, pagination and safe retry checks without network access."""
import copy
import unittest
from scripts.sync_project import validate_manifest, synchronize

URL = "https://github.com/TheIvoryDisaster/GutenStructure/issues/3"
MANIFEST = {"owner": "Meitou-Modding-Ecosystem", "number": 1, "cards": [{"url": URL, "fields": {}}]}


class FakeGitHub:
    def __init__(self, existing=False):
        self.existing = existing
        self.mutations = []
        self.item_pages = 0

    def query(self, query, **variables):
        if "viewerCanUpdate" in query:
            return {"organization": {"projectV2": {"id": "P", "viewerCanUpdate": True,
                    "fields": {"nodes": [], "pageInfo": {"hasNextPage": False}}}}}
        if "items(first" in query:
            self.item_pages += 1
            nodes = [{"id": "I", "content": {"url": URL}}] if self.existing and variables["cursor"] else []
            return {"node": {"items": {"nodes": nodes, "pageInfo": {
                "hasNextPage": variables["cursor"] is None, "endCursor": "page2"}}}}
        if "repository(owner" in query:
            return {"repository": {"issue": {"id": "ISSUE", "url": URL}}}
        self.mutations.append((query, variables))
        self.existing = True
        return {"addProjectV2ItemById": {"item": {"id": "I"}}}


class ProjectSyncTests(unittest.TestCase):
    def test_rejects_out_of_scope_targets(self):
        for url in ["https://github.com/another-owner/repo/issues/1", URL + "?x=1", URL.replace("https:", "http:")]:
            manifest = copy.deepcopy(MANIFEST)
            manifest["cards"][0]["url"] = url
            with self.assertRaises(ValueError):
                validate_manifest(manifest)

    def test_rejects_other_project_and_duplicate_cards(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest["number"] = 2
        with self.assertRaises(ValueError):
            validate_manifest(manifest)
        manifest = copy.deepcopy(MANIFEST)
        manifest["cards"] *= 2
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_preview_never_mutates(self):
        api = FakeGitHub()
        self.assertEqual(synchronize(api, MANIFEST)[0]["action"], "add")
        self.assertEqual(api.mutations, [])
        self.assertEqual(api.item_pages, 2)

    def test_existing_card_on_second_page_is_not_duplicated(self):
        api = FakeGitHub(existing=True)
        self.assertEqual(synchronize(api, MANIFEST, apply=True)[0]["action"], "existing")
        self.assertEqual(api.mutations, [])

    def test_retry_does_not_add_duplicate(self):
        api = FakeGitHub()
        synchronize(api, MANIFEST, apply=True)
        synchronize(api, MANIFEST, apply=True)
        self.assertEqual(len(api.mutations), 1)

    def test_unknown_field_aborts_before_mutation(self):
        api = FakeGitHub()
        manifest = copy.deepcopy(MANIFEST)
        manifest["cards"][0]["fields"] = {"Status": "Invented"}
        with self.assertRaises(ValueError):
            synchronize(api, manifest, apply=True)
        self.assertEqual(api.mutations, [])


if __name__ == "__main__":
    unittest.main()
