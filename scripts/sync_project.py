"""Synchronize an explicit issue manifest into the Meitou organization project."""
import argparse
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_OWNER = "Meitou-Modding-Ecosystem"
PROJECT_NUMBER = 1
ALLOWED_REPOSITORIES = {
    "TheIvoryDisaster/GutenStructure",
    *(f"{PROJECT_OWNER}/{name}" for name in (
        "MeitouClient", "MeitouMods", "PZAKenshiMotionLab",
        "TheWastelandRemembers", "PZAMeitouUi", "PZAMeitouUiProbe")),
}
URL = re.compile(r"https://github\.com/([^/]+/[^/]+)/issues/([1-9][0-9]*)\Z")


def validate_manifest(document):
    """Reject unintended owners, duplicate issues, and ambiguous field values."""
    if document.get("owner") != PROJECT_OWNER or document.get("number") != PROJECT_NUMBER:
        raise ValueError("Only Meitou-Modding-Ecosystem Project 1 is supported")
    cards = document.get("cards")
    if not isinstance(cards, list):
        raise ValueError("cards must be a list")
    seen = set()
    for card in cards:
        if not isinstance(card, dict):
            raise ValueError("Each card must be an object")
        url = card.get("url", "")
        match = URL.fullmatch(url) if isinstance(url, str) else None
        if not match or match[1] not in ALLOWED_REPOSITORIES:
            raise ValueError("Issue URL is outside the explicit repository allowlist")
        if url in seen:
            raise ValueError("Duplicate issue URL")
        seen.add(url)
        fields = card.get("fields", {})
        if not isinstance(fields, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in fields.items()
        ):
            raise ValueError("fields must map names to single-select option names")
    return document


class GitHub:
    def __init__(self, token):
        if not token:
            raise ValueError("MEITOU_PROJECT_TOKEN is required for remote synchronization")
        self.token = token

    def query(self, query, **variables):
        payload = json.dumps({"query": query, "variables": variables}).encode()
        request = urllib.request.Request(
            "https://api.github.com/graphql", data=payload,
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json", "User-Agent": "GutenStructure-project-sync"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            # Never log headers, request bodies or credentials.
            raise RuntimeError(f"GitHub returned HTTP {error.code}") from None
        if result.get("errors"):
            raise RuntimeError("GitHub rejected the project query; check token permissions and field configuration")
        return result["data"]


def inspect_project(api):
    data = api.query("""query($owner:String!, $number:Int!) {
      organization(login:$owner) { projectV2(number:$number) {
        id viewerCanUpdate fields(first:100) { nodes {
          __typename ... on ProjectV2SingleSelectField { id name options { id name } }
        } pageInfo { hasNextPage } }
      } }
    }""", owner=PROJECT_OWNER, number=PROJECT_NUMBER)
    organization = data.get("organization")
    project = organization and organization.get("projectV2")
    if not project or not project["viewerCanUpdate"]:
        raise RuntimeError("The token must have write access to Meitou Project 1")
    if project["fields"]["pageInfo"]["hasNextPage"]:
        raise RuntimeError("More than 100 project fields; refusing an incomplete field inventory")
    fields = {}
    for node in project["fields"]["nodes"]:
        if node.get("__typename") != "ProjectV2SingleSelectField":
            continue
        if node["name"] in fields:
            raise RuntimeError("Ambiguous project field names")
        fields[node["name"]] = node
    return project["id"], fields


def existing_items(api, project_id):
    items, cursor = {}, None
    while True:
        project = api.query("""query($id:ID!, $cursor:String) {
          node(id:$id) { ... on ProjectV2 { items(first:100, after:$cursor) {
            nodes { id content { ... on Issue { url } } }
            pageInfo { hasNextPage endCursor }
          } } }
        }""", id=project_id, cursor=cursor)["node"]["items"]
        for item in project["nodes"]:
            content = item.get("content")
            if content and "url" in content:
                if content["url"] in items:
                    raise RuntimeError("Project already contains duplicate issue items; review before synchronizing")
                items[content["url"]] = item["id"]
        if not project["pageInfo"]["hasNextPage"]:
            return items
        cursor = project["pageInfo"]["endCursor"]


def synchronize(api, document, apply=False):
    validate_manifest(document)
    project_id, fields = inspect_project(api)
    # Validate every configured option before any mutation.
    for card in document["cards"]:
        for name, value in card.get("fields", {}).items():
            field = fields.get(name)
            matches = [] if not field else [opt for opt in field["options"] if opt["name"] == value]
            if len(matches) != 1:
                raise ValueError(f"Unknown or ambiguous project option: {name}={value}")
    items = existing_items(api, project_id)
    # Resolve every issue before creating any card; restricted tokens may lack access to issue metadata.
    issues = {}
    for card in document["cards"]:
        match = URL.fullmatch(card["url"])
        owner, repository = match[1].split("/")
        issue = api.query("""query($owner:String!, $name:String!, $number:Int!) {
          repository(owner:$owner,name:$name) { issue(number:$number) { id url } }
        }""", owner=owner, name=repository, number=int(match[2]))
        repository_data = issue.get("repository")
        content = repository_data and repository_data.get("issue")
        if not content or content["url"] != card["url"]:
            raise ValueError("Issue is unavailable or redirected outside the configured URL")
        issues[card["url"]] = content["id"]
    report = []
    for card in document["cards"]:
        item_id = items.get(card["url"])
        action = "existing" if item_id else "add"
        if not item_id and apply:
            item_id = api.query("""mutation($project:ID!, $content:ID!) {
              addProjectV2ItemById(input:{projectId:$project,contentId:$content}) { item { id } }
            }""", project=project_id, content=issues[card["url"]])["addProjectV2ItemById"]["item"]["id"]
            items[card["url"]] = item_id
        if apply:
            for name, value in card.get("fields", {}).items():
                field = fields[name]
                option = next(opt["id"] for opt in field["options"] if opt["name"] == value)
                api.query("""mutation($project:ID!, $item:ID!, $field:ID!, $option:String!) {
                  updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,
                    fieldId:$field,value:{singleSelectOptionId:$option}}) { projectV2Item { id } }
                }""", project=project_id, item=item_id, field=field["id"], option=option)
        report.append({"url": card["url"], "action": action, "applied": apply, "fields": card.get("fields", {})})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="backlog/project.json")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    document = validate_manifest(json.loads(Path(args.manifest).read_text()))
    if args.validate_only:
        print(f"Validated {len(document['cards'])} configured issues; no GitHub calls made.")
        return
    report = synchronize(GitHub(os.environ.get("MEITOU_PROJECT_TOKEN")), document, args.apply)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
