import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parent.parent / '.github' / 'workflows'
CHECKOUT_REF = re.compile(r'repository: TheIvoryDisaster/GutenStructure\s*\n\s*ref: ([0-9a-f]{40})')


def central_refs(workflow):
    """The commits a workflow checks GutenStructure's own scripts out at."""
    return CHECKOUT_REF.findall((WORKFLOWS / workflow).read_text())


class ReleaseHelperPinTests(unittest.TestCase):
    def test_publisher_runs_the_same_release_gate_as_the_gate_job(self):
        """Both jobs run scripts/release_gate.py; a stale publisher pin rejects the current branch policy after the gate passed."""
        gate = central_refs('release-gate.yml')
        publisher = central_refs('package-meitou-mod.yml')
        self.assertEqual(len(gate), 1)
        self.assertEqual(len(publisher), 1)
        self.assertEqual(publisher, gate)


if __name__ == '__main__':
    unittest.main()
