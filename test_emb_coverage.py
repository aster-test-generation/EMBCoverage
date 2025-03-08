from pathlib import Path
from unittest import TestCase

from cldk import CLDK
from cldk.analysis import AnalysisLevel

from emb_coverage import EMBCoverage

import json

class TestEMBCoverage(TestCase):
    def setUp(self):
        # Add JaCoCo agent port number
        self.jacoco_port_number = 8000
        # Add project path
        project_path = Path('/home/rkh/25spring/aster/EMBv3.4.0/jdk_8_maven/cs/rest/original/restcountries/')
        self.dataset = Path(project_path).name
        self.analysis_path = Path.cwd().joinpath('output', self.dataset)
        self.analysis = CLDK(language="java").analysis(
            project_path=project_path,
            # analysis_backend="codeanalyzer",
            # analysis_backend_path=None,
            analysis_level=AnalysisLevel.call_graph,
            analysis_json_path="./output",
        )
        self.emb_coverage = EMBCoverage(self.analysis, self.jacoco_port_number)

    def test_get_reachability_coverage(self):
        reachability_coverage = self.emb_coverage.get_reachability_coverage()
        # write to ./output folder
        with open('./output/reachability_coverage.json', 'w') as f:
            # convert reachability_coverage to json
            json.dump(reachability_coverage, f)
        self.assertIsNotNone(reachability_coverage)

    def test_get_app_coverage(self):
        application_coverage = self.emb_coverage.get_app_coverage()
        # write to output folder
        with open('./output/application_coverage.json', 'w') as f:
            # convert application_coverage to json
            json.dump(application_coverage, f)
        self.assertIsNotNone(application_coverage)
