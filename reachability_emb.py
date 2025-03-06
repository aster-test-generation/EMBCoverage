import re
from typing import List

from cldk.analysis.java import JavaAnalysis


class EMBReachability:

    def __init__(self, analysis: JavaAnalysis):
        self.analysis = analysis
        self.__reachable_methods: List[dict] = []

    def get_reachable_methods(self, qualified_class_name: str, method_signature: str,
                              depth: int = 2,
                              is_recursive: bool = False) -> List[dict]:
        """
        Computes all the methods reachable from the endpoint
        Args:
            qualified_class_name:
            method_signature:
            depth:
            is_recursive:

        Returns:
            List[dict]: list of dictionaries, where each element has class_name, method_signature, start_line,
            and end_line.
        """
        # initialize reachable methods field on first (non-recursive) call
        if not is_recursive:
            self.__reachable_methods = list()
        if depth <= 0:
            return []
        if method_signature.startswith(qualified_class_name.split('.')[-1] + '('):
            method_signature = method_signature.replace(qualified_class_name.split('.')[-1] + '(', '<init>(')
        method_details = self.analysis.get_method(qualified_class_name, method_signature)
        if method_details is None:
            # RichLog.error(f"Could not find {qualified_class_name} class and {method_signature}")
            return self.__reachable_methods
        current_method = {"qualified_class_name": qualified_class_name, "method_signature": method_signature,
                          "start_line": method_details.start_line, "end_line": method_details.end_line,
                          "method_code": method_details.declaration + '\n' + method_details.code,
                          "fields": tuple(method_details.accessed_fields)}
        if current_method not in self.__reachable_methods:
            self.__reachable_methods.append(current_method)

            # Check if any receiver type of the call site is an interface
            interface_class_method_pairs = {}

            for call_site in method_details.call_sites:
                class_details = self.analysis.get_class(call_site.receiver_type)
                if class_details:
                    if class_details.is_interface:
                        if call_site.receiver_type not in interface_class_method_pairs:
                            interface_class_method_pairs[call_site.receiver_type] = [self.process_callee_signature(call_site.callee_signature)]
                        else:
                            interface_class_method_pairs[call_site.receiver_type].append(self.process_callee_signature(call_site.callee_signature))

            # Map the concrete class and the interface methods
            concrete_class_methods_map = {}
            for interface_class in interface_class_method_pairs:
                # Get the concrete classes
                concrete_classes = self.get_concrete_classes(interface_class=interface_class)
                for concrete_class in concrete_classes:
                    concrete_class_methods_map[concrete_class] = interface_class_method_pairs[interface_class]

            # Add call to each of the concrete class
            if len(concrete_class_methods_map) > 0:
                for concrete_class in concrete_class_methods_map:
                    for method_signature in concrete_class_methods_map[concrete_class]:
                        self.get_reachable_methods(concrete_class, method_signature, depth - 1, True)

            callees = self.analysis.get_callees(source_class_name=qualified_class_name,
                                                source_method_declaration=method_signature)
            if 'callee_details' in callees:
                for callee in callees['callee_details']:
                    callee_class_name = callee['callee_method'].klass
                    callee_method_signature = callee['callee_method'].method.signature
                    self.get_reachable_methods(callee_class_name, callee_method_signature, depth - 1, True)
        # else:
        #     RichLog.info(f"Method {qualified_class_name}.{method_signature} already exists in reachable list")
        # Remove duplicates
        # self.__reachable_methods = [dict(y) for y in set(tuple(x.items()) for x in self.__reachable_methods)]
        return self.__reachable_methods

    def get_concrete_classes(self, interface_class: str) -> List[str]:
        """
        Returns a list of concrete classes that implement the given interface class
        Args:
            interface_class:

        Returns:
            List[str]: List of concrete classes that implements the given interface class
        """
        all_classes_in_application = self.analysis.get_classes()
        concrete_classes = []
        for klazz in all_classes_in_application:
            class_details = all_classes_in_application[klazz]
            if class_details is not None:
                if hasattr(class_details, 'is_interface') and hasattr(class_details, 'modifiers'):
                    if class_details.is_interface is not None and class_details.modifiers is not None:
                        if not class_details.is_interface and 'abstract' not in class_details.modifiers:
                            if interface_class in class_details.implements_list:
                                concrete_classes.append(klazz)
        return concrete_classes

    @staticmethod
    def process_callee_signature(callee_signature: str) -> str:
        """
        Processes callee signature
        Args:
            callee_signature:

        Returns:

        """
        pattern = r"\b(?:[a-zA-Z_][\w\.]*\.)+([a-zA-Z_][\w]*)\b|<[^>]*>"

        # Find the part within the parentheses
        start = callee_signature.find("(") + 1
        end = callee_signature.rfind(")")

        # Extract the elements inside the parentheses
        elements = callee_signature[start:end].split(",")

        # Apply the regex to each element
        simplified_elements = [re.sub(pattern, r"\1", element.strip()) for element in elements]

        # Reconstruct the string with simplified elements
        return f"{callee_signature[:start]}{', '.join(simplified_elements)}{callee_signature[end:]}"

