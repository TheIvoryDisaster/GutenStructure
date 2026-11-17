"""Shared API exception identity for imported modules and python -m entry points."""
class GitHubFailure(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"GitHub returned HTTP {status}; verify administration permission and repository setup")

