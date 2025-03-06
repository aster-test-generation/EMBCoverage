import json
import subprocess
from json import JSONDecodeError
from typing import List, Tuple, Any

from cldk.analysis.java import JavaAnalysis

from reachability_emb import EMBReachability


class EMBCoverage:
    def __init__(self, analysis: JavaAnalysis, jacoco_port_number: int):
        self.analysis = analysis
        self.jacoco_port_number = jacoco_port_number

    def get_reachability_coverage(self) -> List[dict]:
        """
        Computes and returns the reachable coverage using coverage monitoring agent
        Args:
        Returns:
            List[dict]: List of dictionaries with coverage information
        """
        # Get coverage details from the coverage monitor
        coverage_details = self.__get_method_coverage()
        db_coverage = self.__get_db_coverage(self.jacoco_port_number)
        covered_db_interaction_lines = 0
        total_db_interaction_lines = 0
        total_lines = 0
        total_branches = 0
        total_inst = 0
        covered_lines = 0
        covered_branches = 0
        covered_inst = 0
        processed_methods = []
        coverage_dict = {}
        db_uncovered_lines_app = {}
        class_method_pairs = []
        reachability = EMBReachability(self.analysis)
        # gather all endpoints
        for cls in self.analysis.get_classes():
            all_method = self.analysis.get_methods_in_class(cls)
            # Get lines that are uncovered
            endpoint_methods = [method for method in all_method if all_method[method].is_entrypoint]

            for endpoint_method in endpoint_methods:
                class_method_pairs.append([cls, endpoint_method])

        # Go through each endpoint class and method
        for class_method_pair in class_method_pairs:
            qualified_class_name = class_method_pair[0]
            method_signature = class_method_pair[1]
            # Get all the reachable methods
            all_reachable_methods = reachability.get_reachable_methods(qualified_class_name, method_signature)

            # Go through each reachable method
            for method in all_reachable_methods:
                if method not in processed_methods:
                    # class name is present
                    if method["qualified_class_name"] in coverage_details:
                        # Go through each method from the jacoco agent report
                        for method_jacoco in coverage_details[method["qualified_class_name"]]:
                            method_name = method_jacoco.split(':')[0]
                            start_line = int(method_jacoco.split(':')[1])
                            # Match name and the start line. Since start line is off by 1, we used the range
                            if (method_name == method["method_signature"].split('(')[0] and
                                    method["end_line"] >= start_line >= method["start_line"]):
                                method_coverage_details = coverage_details[method["qualified_class_name"]][
                                    method_jacoco]
                                covered_db_interaction_lines_per_method = 0
                                total_db_interaction_lines_per_method = 0
                                db_uncovered_lines = []
                                # Get database interaction coverage
                                if method["qualified_class_name"] in db_coverage:
                                    for method_db in db_coverage[method["qualified_class_name"]]:
                                        if method["method_signature"] == method_db["method_signature"]:
                                            total_db_interaction_lines_per_method = method_db["total_db_line_count"]
                                            covered_db_interaction_lines_per_method = (
                                                    total_db_interaction_lines_per_method - len(
                                                method_db["db_uncovered_lines"]))
                                            if total_db_interaction_lines_per_method > 0:
                                                db_uncovered_lines = method_db["db_uncovered_lines"]
                                                db_uncovered_lines_app[str(Tuple[method["qualified_class_name"],
                                                method["method_signature"]])] = (
                                                    method_db)["db_uncovered_lines"]
                                # Collect data for overall coverage
                                total_lines += method_coverage_details["totalLines"]
                                total_branches += method_coverage_details["totalBranches"]
                                total_inst += method_coverage_details["totalInsts"]
                                covered_lines += method_coverage_details["coveredLines"]
                                covered_branches += method_coverage_details["fullyCoveredBranches"]
                                covered_inst += method_coverage_details["coveredInsts"]
                                total_db_interaction_lines += total_db_interaction_lines_per_method
                                covered_db_interaction_lines += covered_db_interaction_lines_per_method

                                # Store method wise coverage
                                coverage = {"method_signature": method["method_signature"],
                                            "line_coverage": (method_coverage_details["coveredLines"] /
                                                              method_coverage_details["totalLines"]) * 100.0 if
                                            method_coverage_details["totalLines"] > 0 else -100.0,
                                            "branch_coverage": (method_coverage_details["fullyCoveredBranches"] /
                                                                method_coverage_details["totalBranches"]) * 100.0 if
                                            method_coverage_details["totalBranches"] > 0 else -100.0,
                                            "instruction_coverage": (method_coverage_details["coveredInsts"] /
                                                                     method_coverage_details["totalInsts"]) * 100.0 if
                                            method_coverage_details["totalInsts"] > 0 else -100.0,
                                            "database_interaction_coverage": (covered_db_interaction_lines_per_method /
                                                                              total_db_interaction_lines_per_method) * 100.0 if
                                            total_db_interaction_lines_per_method > 0 else -100.0,
                                            "database_uncovered_lines": db_uncovered_lines if
                                            len(db_uncovered_lines) > 0 else None,
                                            }
                                if method["qualified_class_name"] not in coverage_dict:
                                    coverage_dict[method["qualified_class_name"]] = [coverage]
                                else:
                                    coverage_dict[method["qualified_class_name"]].append(coverage)
                processed_methods.append(method)

        # Add overall coverage
        coverage_dict["overall_coverage"] = [
            {"line_coverage": (covered_lines / total_lines) * 100.0 if total_lines > 0 else -100,
             "branch_coverage": (covered_branches / total_branches) * 100.0 if total_branches > 0 else -100,
             "instruction_coverage": (covered_inst / total_inst) * 100.0 if total_inst > 0 else -100,
             "database_interaction_coverage": (covered_db_interaction_lines / total_db_interaction_lines)
                                              * 100.0 if total_db_interaction_lines > 0 else -100,
             "database_uncovered_lines": json.dumps(db_uncovered_lines_app)}, ]
        return coverage_dict

    def get_app_coverage(self) -> dict:
        """
        Computes and returns the application coverage using coverage monitoring agent
        Args:

        Returns:
            CoverageEvaluation: application coverage
        """
        uncovered_lines = self.__execute_http_requests(
            [f"curl -X GET http://localhost:{self.jacoco_port_number}/appcoverage"]
        )[0]

        try:
            total_db_line = 0
            total_covered_db_line = 0
            current_coverage_details = json.loads(uncovered_lines[1])
            keys = list(current_coverage_details.keys())
            current_coverage_details = current_coverage_details[keys[0]]
            db_coverage = self.__get_db_coverage(self.jacoco_port_number)
            for klazz in db_coverage:
                for method in db_coverage[klazz]:
                    total_db_line += method["total_db_line_count"]
                    total_covered_db_line += method["total_db_line_count"] - len(method["db_uncovered_lines"])
            coverage = {"line_coverage": current_coverage_details["line"],
                        "branch_coverage": current_coverage_details["branch"],
                        "instruction_coverage": current_coverage_details["instruction"],
                        "database_interaction_line_coverage":
                            total_covered_db_line / total_db_line * 100.0 if
                            total_db_line > 0 else -100.0}
            return coverage
        except JSONDecodeError:
            return print('JSON Error')

    @staticmethod
    def __execute_http_requests(http_commands: List[str]) -> List[Tuple[int, Any]]:
        """
        Execute a list of curl commands and return their responses with status codes.

        Args:
            http_commands (List[str]): List of curl commands to execute

        Returns:
            List[Tuple[int, Any]]: List of tuples containing (status_code, response)
        """
        responses = []

        for cmd in http_commands:
            # Append --write-out for status code and separate response
            cmd_with_status = f"{cmd} --silent --write-out 'STATUS:%{{http_code}}'"

            # Execute the command
            process = subprocess.Popen(
                cmd_with_status,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            try:
                stdout, stderr = process.communicate(timeout=10)
                # Split response and status code using a unique delimiter
                if "STATUS:" in stdout:
                    response_text, status_code = stdout.rsplit("STATUS:", 1)
                    response_text = response_text.strip()
                    status_code = int(status_code.strip())
                else:
                    # Handle cases where "STATUS:" is missing
                    response_text = stdout.strip() or stderr.strip()
                    status_code = 0  # Default to 0 if no status code is captured

                responses.append((status_code, response_text))
            except Exception as e:
                print(f"Error executing http request: {cmd}: {e}")
                responses.append((-100, e))
                continue

        return responses

    def __get_db_coverage(self, jacoco_port_number: int):
        """
        Computes the database coverage for the entire app
        Returns:

        """
        processed_uncovered_lines = {}
        crud_operations = self.analysis.get_all_crud_operations()
        # Get all the uncovered lines
        uncovered_lines = self.__execute_http_requests(
            [f"curl -X GET http://localhost:{jacoco_port_number}/uncovered"]
        )[0]
        try:
            coverage_details = json.loads(uncovered_lines[1])

            # Go through each of the class
            for klazz in coverage_details:
                # Remove Test classes
                class_name = klazz.split('.')[-1]
                if (not class_name.startswith('Test') and
                        not class_name.startswith('Tests') and
                        not class_name.endswith('Test') and
                        not klazz.endswith('Tests')):
                    methods_in_class = {}

                    # Get all the methods in the class
                    methods = self.analysis.get_methods_in_class(qualified_class_name=klazz)

                    # Store the method details
                    for method in methods:
                        db_lines_per_method = [crud_operation.line_number
                                               for crud_operation in methods[method].crud_operations]
                        # Add all the method call on Entity objects
                        for call_site in methods[method].call_sites:
                            if call_site.receiver_type is not None:
                                receiver_class = self.analysis.get_class(call_site.receiver_type)
                                if receiver_class:
                                    if any(annotation in ['@Entity']
                                           for annotation in receiver_class.annotations):
                                        db_lines_per_method.append(call_site.start_line)

                        # Add method calls where the callee method has annotation @Transactional (applicable for mybatis)
                        for call_site in methods[method].call_sites:
                            callee_method = self.analysis.get_method(
                                qualified_class_name=call_site.receiver_type,
                                qualified_method_name=EMBReachability.process_callee_signature(
                                    call_site.callee_signature))
                            if callee_method:
                                if any(annotation in ['@Transactional']
                                       for annotation in callee_method.annotations):
                                    db_lines_per_method.append(call_site.start_line)

                        db_lines_per_method = list(set(db_lines_per_method))
                        methods_in_class[method] = [methods[method].start_line,
                                                    methods[method].end_line,
                                                    db_lines_per_method]
                    # Get uncovered line details
                    for method in coverage_details[klazz]:
                        method_name = method.split(':')[0]
                        line_number = method.split(':')[-1]
                        for existing_methods in methods_in_class:
                            # JaCoCo returns the covered line, which may not be start line of the method
                            if methods_in_class[existing_methods][0] <= int(line_number) <= \
                                    methods_in_class[existing_methods][1]:
                                uncovered_lines = coverage_details[klazz][method]

                                # Capture database uncovered lines
                                db_uncovered_lines = []
                                db_lines_per_method = methods_in_class[existing_methods][2]
                                db_line_coverage = 0

                                # Go through each database interaction point
                                for line in db_lines_per_method:
                                    if line not in uncovered_lines:
                                        db_line_coverage += 1
                                    else:
                                        db_uncovered_lines.append(line)
                                method_dict = {
                                    "method_signature": existing_methods,
                                    "total_db_line_count": len(db_lines_per_method),
                                    "db_line_coverage": db_line_coverage / len(db_lines_per_method) * 100.0 if
                                    len(db_lines_per_method) > 0 else -100.0,
                                    "db_uncovered_lines": db_uncovered_lines
                                }
                                if klazz not in processed_uncovered_lines:
                                    processed_uncovered_lines[klazz] = [method_dict]
                                else:
                                    processed_uncovered_lines[klazz].append(method_dict)
            return processed_uncovered_lines
        except JSONDecodeError:
            return []

    def __get_method_coverage(self) -> str:
        """
        Computes and returns the method-level coverage using coverage monitoring agent
        Args:

        Returns:
            str: string representation of the json format response
        """
        uncovered_lines = self.__execute_http_requests(
            [f"curl -X GET http://localhost:{self.jacoco_port_number}/methodcoverage"]
        )[0]

        coverage_details = json.loads(uncovered_lines[1])
        return coverage_details
