from pathlib import Path
from unittest import TestCase

from cldk import CLDK
from cldk.analysis import AnalysisLevel

from emb_coverage import EMBCoverage
from test_emb_coverage import TestEMBCoverage


if __name__ == '__main__':
    t=TestEMBCoverage()
    t.setUp()
    t.test_get_reachability_coverage()
    t.test_get_app_coverage()
    