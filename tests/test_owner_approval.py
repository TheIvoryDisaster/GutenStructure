import unittest
from scripts.owner_approval import evaluate, parse_owners

class OwnerApprovalTests(unittest.TestCase):
    def check(self, author='alice', branch='beta', reviews=None, files=None, ownership='* @alice', members=None):
        return evaluate(author, 'head', branch, files or ['docs/a.md'], ownership, reviews or [],
                        members or {'@alice': {'alice'}, '@bob': {'bob'}, '__writers__': {'alice', 'bob', 'carol'}})[0]
    def review(self, user='bob', state='APPROVED', commit='head', number=1):
        return {'id': number, 'user': {'login': user}, 'state': state, 'commit_id': commit}
    def test_author_owner_can_authorize_beta(self): self.assertTrue(self.check())
    def test_author_owner_needs_external_release_review(self): self.assertFalse(self.check(branch='release'))
    def test_release_owner_author_and_other_reviewer(self): self.assertTrue(self.check(branch='release', reviews=[self.review()]))
    def test_nonowner_needs_owner(self): self.assertFalse(self.check(author='carol', reviews=[self.review()]))
    def test_nonowner_release_owner_approval_is_enough(self): self.assertTrue(self.check(author='carol', branch='release', reviews=[self.review('alice')]))
    def test_specific_override(self): self.assertFalse(self.check(ownership='* @alice\n/docs/ @bob'))
    def test_all_paths_need_owner(self): self.assertFalse(self.check(files=['docs/a.md','src/a.cs'], ownership='/docs/ @alice\n/src/ @bob'))
    def test_stale_approval(self): self.assertFalse(self.check(branch='release', reviews=[self.review(commit='old')]))
    def test_dismissed_approval(self): self.assertFalse(self.check(branch='release', reviews=[self.review(),self.review(state='DISMISSED',number=2)]))
    def test_comment_does_not_replace_approval(self): self.assertTrue(self.check(branch='release', reviews=[self.review(),self.review(state='COMMENTED',number=2)]))
    def test_author_review_not_external(self): self.assertFalse(self.check(branch='release', reviews=[self.review('alice')]))
    def test_changes_requested_blocks(self): self.assertFalse(self.check(reviews=[self.review(state='CHANGES_REQUESTED')]))
    def test_team_author(self): self.assertTrue(self.check(ownership='* @Meitou-Modding-Ecosystem/owners',members={'@meitou-modding-ecosystem/owners':{'alice'},'__writers__':{'alice'}}))
    def test_empty_override(self): self.assertFalse(self.check(ownership='* @alice\n/docs/'))
    def test_unsupported_pattern_fails_closed(self):
        with self.assertRaises(ValueError): parse_owners('[ab] @alice')
