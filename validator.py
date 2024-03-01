#!/usr/bin/env python3

import jsonschema
import json
import sys
import glob
import os
import yaml
from yaml.loader import SafeLoader
from jinja2 import Environment
from jinja2.nodes import Node as JinjaNode
import time
import logging
import coloredlogs
from typing import Any

ROOT = "/data/"

coloredlogs.install(level="INFO", stream=sys.stdout)
# coloredlogs.install(level="ERROR", stream=sys.stderr)


class DesignSystem:
    def __init__(self, root_path: str):
        self.root_path = root_path
        self.artifacts = {
            "component": "components",
            "style": "styles",
            "theme": "themes",
            "variable": "variables",
            "example": "examples",
            "library": "libraries",
        }
        self.data = self._get_full_definition()

    def _get_full_definition(self) -> dict[str, Any]:
        data = self._load_main_file()
        for artifact in self.artifacts:
            # Examples:
            # - color.style.yml
            # - examples/album.example.yml
            # - components/card/card.component.yml
            pattern = os.path.join(self.root_path, "**", "*." + artifact + ".yml")
            for path in sorted(glob.glob(pattern, recursive=True)):
                data = self._load_file_with_single_item(path, data)
            # Examples:
            # - styles.yml
            # - libraries.yml
            plural = self.artifacts[artifact]
            pattern = os.path.join(self.root_path, "**", plural + ".yml")
            for path in sorted(glob.glob(pattern, recursive=True)):
                data = self._load_file_with_multiple_items(path, data)
            # Examples:
            # - colors.styles.yml
            # - whatever/background.variables.yml
            pattern = os.path.join(self.root_path, "**", "*." + plural + ".yml")
            for path in sorted(glob.glob(pattern, recursive=True)):
                data = self._load_file_with_multiple_items(path, data)
        data = self._fix_integer_keys(data)
        data = self._add_missing_component_id_to_examples(data)
        return data

    def _fix_integer_keys(self, data: dict[str, Any]) -> dict[str, Any]:
        new = {}
        for key, value in data.items():
            if isinstance(value, dict):
                value = self._fix_integer_keys(value)
            new[str(key)] = value
        return new

    def _load_main_file(self) -> dict[str, Any]:
        with open(self.root_path + "/info.yml") as file:
            data = yaml.load(file, Loader=SafeLoader)
            return dict(data)

    def _load_file_with_multiple_items(
        self, path: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        filename = os.path.basename(path)
        parts = filename.split(".")
        if len(parts) == 3:
            whatever, artifact_plural, extension = parts
        if len(parts) == 2:
            artifact_plural, extension = parts
        if not artifact_plural:
            return data
        with open(path) as file:
            if artifact_plural not in data.keys():
                data[artifact_plural] = {}
            items = yaml.load(file, Loader=SafeLoader)
            if not items:
                return data
            for item_id, item in items.items():
                item = self._add_missing_ids(item_id, artifact_plural, item)
                data[artifact_plural][item_id] = item
        return data

    def _add_missing_ids(
        self, item_id: str, artifact_plural: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        if "id" in data.keys() and data["id"] != item_id:
            logging.error("%s %s has conflicting IDs", item_id, artifact_plural)
        data = {"id": item_id} | data
        subs = {
            "components": ["variants", "slots", "props", "examples"],
            "styles": [
                "options",
            ],
        }
        if artifact_plural not in subs.keys():
            return data
        for sub in subs[artifact_plural]:
            if sub not in data.keys():
                continue
            for sub_id, sub_item in data[sub].items():
                data[sub][sub_id] = self._add_missing_ids(sub_id, sub, sub_item)
        if artifact_plural != "components":
            return data
        if "library" not in data.keys():
            return data
        if "id" not in data["library"].keys():
            data["library"]["id"] = item_id
        return data

    def _load_file_with_single_item(
        self, path: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        filename = os.path.basename(path)
        item_id, artifact, extension = filename.split(".")
        plural = self.artifacts[artifact]
        with open(path) as file:
            if plural not in data.keys():
                data[plural] = {}
            item = yaml.load(file, Loader=SafeLoader)
            item = self._add_missing_ids(item_id, plural, item)
            data[plural][item_id] = item
        return data

    def _add_missing_component_id_to_examples(
        self, data: dict[str, Any]
    ) -> dict[str, Any]:
        if "components" not in data.keys():
            return data
        for component_id, component in data["components"].items():
            if "examples" not in component.keys():
                continue
            for example_id, example in component["examples"].items():
                renderable = (
                    example["renderable"] if "renderable" in example.keys() else {}
                )
                renderable = {"@component": component_id} | renderable
                data["components"][component_id]["examples"][example_id][
                    "renderable"
                ] = renderable
        return data


class DefinitionsValidator:
    def __init__(self) -> None:
        self.schema = self._get_schema()

    def _get_schema(self) -> dict[str, Any]:
        basepath = os.path.dirname(__file__)
        path = os.path.join(basepath, "definitions.schema.json")
        with open(path) as schema_file:
            schema = schema_file.read()
            schema = self._resolve_external_refs(schema)
            return dict(json.loads(schema))
        return {}

    def _resolve_external_refs(self, schema: str) -> str:
        path = "file://" + os.path.dirname(__file__)
        return schema.replace(
            "renderable.schema.json", path + "/renderable.schema.json"
        )

    def _check_single_variants(self, definitions: dict[str, Any]) -> None:
        if "components" not in definitions.keys():
            return
        for component in definitions["components"].values():
            if "variants" not in component.keys():
                continue
            if len(component["variants"]) == 1:
                logging.warning("%s: Only one variant", component["id"])

    def validate(self, definitions: dict[str, Any]) -> list[str]:
        """Validate definitions according to definitions.schema.json"""
        error = validate(self.schema, definitions)
        self._check_single_variants(definitions)
        if error:
            return [definitions["id"] + ": " + error]
        return []


class JinjaAstDumper:
    def __init__(self) -> None:
        self.env = Environment()
        self.stored_variables: list[str] = []
        self.loaded_variables: list[str] = []
        self.stored_callables: list[str] = []
        self.loaded_callables: list[str] = []

    def dump(self, template_path: str) -> dict[str, Any]:
        """Dump Jinja AST as nested dicts"""
        with open(template_path) as template:
            ast = self.env.parse(template.read())
            self.stored_variables = []
            self.loaded_variables = []
            self.stored_callables = []
            self.loaded_callables = []
            return self._dig(ast, None, "")

    def _dig(
        self, node: JinjaNode, parent: JinjaNode | None, rel: str
    ) -> dict[str, Any]:
        node_id = str(node.__class__.__name__)
        dump = {"@node": node_id}
        for key, field in node.iter_fields():
            dump = self._parse_field(key, field, dump, node)
        if node_id == "Macro":
            self.stored_callables.append(dump["name"])
        if node_id == "Name":
            self._dig_name(dump, parent, rel)
        return dump

    def _dig_name(
        self, dump: dict[str, Any], parent: JinjaNode | None, rel: str
    ) -> None:
        if dump["ctx"] == "store":
            self.stored_variables.append(dump["name"])
        if dump["ctx"] == "param":
            self.stored_variables.append(dump["name"])
        if dump["ctx"] == "load":
            if parent and parent.__class__.__name__ == "Call" and rel == "node":
                self.loaded_callables.append(dump["name"])
                return
            self.loaded_variables.append(dump["name"])

    def _is_node(self, field: JinjaNode | list[str] | str) -> bool:
        if self._is_list(field):
            for item in field:
                if self._is_node(item):
                    return True
        return hasattr(field, "__module__") and field.__module__ == "jinja2.nodes"

    def _is_list(self, field: JinjaNode | list[str] | str) -> bool:
        return field.__class__ == list

    def _parse_field(
        self,
        key: str,
        field: JinjaNode | list[str] | str,
        dump: dict[str, Any],
        node: JinjaNode,
    ) -> dict[str, Any]:
        if field is None:
            return dump
        if not self._is_node(field):
            dump[key] = field
            return dump
        if self._is_node(field) and not self._is_list(field):
            dump[key] = self._dig(field, node, key)
            return dump
        if self._is_node(field) and self._is_list(field):
            dump[key] = [self._dig(item, node, key) for item in field]
            return dump
        return dump


class TemplatesValidator:
    def __init__(self, design_system: DesignSystem) -> None:
        self.design_system = design_system
        self.dumper = JinjaAstDumper()
        self.schema = self._get_schema()

    def _get_schema(self) -> dict[str, Any]:
        basepath = os.path.dirname(__file__)
        path = os.path.join(basepath, "template.schema.json")
        with open(path) as schema:
            return dict(json.loads(schema.read()))
        return {}

    def validate(self, path: str) -> list[str]:
        """Load template from path and validate it"""
        errors: list[str] = []
        if path.endswith(".jinja"):
            paths = [path]
        else:
            path = os.path.join(path, "**", "*.jinja")
            paths = sorted(glob.glob(path, recursive=True))
        for path in paths:
            errors = errors + self._process_file(path)
        return errors

    def _get_expected_variables(self, component_id: str) -> set[str]:
        component = self._get_component_definition(component_id)
        expected = self.dumper.stored_variables
        expected.append("attributes")
        if "slots" in component.keys():
            expected.extend(component["slots"].keys())
        if "props" in component.keys():
            expected.extend(component["props"].keys())
        if "variants" in component.keys() and component["variants"]:
            expected.append("variant")
        return set(expected)

    def _compare_variables(self, component_id: str) -> list[str]:
        expected = self._get_expected_variables(component_id)
        found = set(self.dumper.loaded_variables)
        if "loop" in found and "loop" not in expected:
            found = found.difference({"loop"})
        if "sequence" in found and "sequence" not in expected:
            found = found.difference({"sequence"})
        found = set(found)
        shared = expected & found
        results = []
        if len(expected) > len(shared):
            delta = set(expected) - shared
            results.append("Some variables are not used: " + ", ".join(delta))
        if len(found) > len(shared):
            delta = set(found) - shared
            results.append("Some variables are not defined: " + ", ".join(delta))
        return results

    def _compare_callables(self) -> list[Any]:
        expected = set(self.dumper.stored_callables)
        found = set(self.dumper.loaded_callables)
        if "random" in found and "random" not in expected:
            found = found.difference({"random"})
        if "range" in found and "range" not in expected:
            found = found.difference({"range"})
        found = set(found)
        shared = expected & found
        results = []
        if len(expected) > len(shared):
            delta = set(expected) - shared
            results.append("Some callables are not used: " + ", ".join(delta))
        if len(found) > len(shared):
            delta = set(found) - shared
            results.append("Some callables are not defined: " + ", ".join(delta))
        return results

    def _get_component_definition(self, component_id: str) -> dict[str, Any]:
        data = self.design_system.data
        if "components" not in data.keys():
            return {}
        if component_id not in data["components"].keys():
            return {}
        return data["components"][component_id]

    def _get_component_id(self, path: str) -> str:
        filename = os.path.basename(path)
        return filename.replace(".jinja", "")

    def _process_file(self, path: str) -> list[str]:
        start = time.perf_counter()
        dump = self.dumper.dump(path)
        errors = [validate(self.schema, dump)]
        component_id = self._get_component_id(path)
        errors = errors + self._compare_variables(component_id)
        errors = errors + self._compare_callables()
        stop = time.perf_counter()
        timing = round((stop - start) * 1000)
        errors = [error for error in errors if error]
        for index, error in enumerate(errors):
            errors[index] = path + ": " + error
        if not errors and timing > 1000:
            logging.warning("%s validated in %s ms", path, str(timing))
            return []
        if not errors and timing < 1001:
            logging.info("%s validated in %s ms", path, str(timing))
            return []
        return errors


class RenderableValidator:
    def __init__(self) -> None:
        self.schema = self._get_schema()

    def _get_schema(self) -> dict[str, Any]:
        basepath = os.path.dirname(__file__)
        path = os.path.join(basepath, "renderable.schema.json")
        with open(path) as schema:
            return dict(json.loads(schema.read()))
        return {}

    def validate(self, payload: dict[str, Any]) -> list[str]:
        """Validate a renderable according to renderable.schema.json"""
        result = validate(self.schema, payload)
        if result:
            return [result]
        return []


def validate(schema: dict[str, Any], data: dict[str, Any]) -> str:
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.exceptions.ValidationError as error:
        if error.path:
            path = [str(step) for step in error.path]
            return error.message + " in /" + "/".join(path)
        else:
            return "Instance is not valid under any of the given schemas"
    else:
        return ""


def run_definitions() -> list[str]:
    errors: list[str] = []
    pattern = os.path.join(ROOT, "**", "info.yml")
    found = False
    for path in sorted(glob.glob(pattern, recursive=True)):
        target = os.path.dirname(path)
        found = True
        logging.info("Check definitions, design system found in: %s", target)
        design_system = DesignSystem(target)
        validator = DefinitionsValidator()
        errors = errors + validator.validate(design_system.data)

    if not found:
        logging.critical("No definition found!")
        sys.exit()
    return errors


def run_templates() -> list[str]:
    errors: list[str] = []
    pattern = os.path.join(ROOT, "**", "info.yml")
    found = False
    for path in sorted(glob.glob(pattern, recursive=True)):
        target = os.path.dirname(path)
        found = True
        logging.info("Check templates, design system found in: %s", target)
        design_system = DesignSystem(target)
        validator = TemplatesValidator(design_system)
        errors = errors + validator.validate(target)

    if not found:
        logging.critical("No templates found!")
        sys.exit()
    return errors


if __name__ == "__main__":
    errors = []
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        errors = run_definitions()
        errors = errors + run_templates()
    elif len(sys.argv) > 1 and sys.argv[1] == "definitions":
        errors = run_definitions()
    elif len(sys.argv) > 1 and sys.argv[1] == "templates":
        errors = run_templates()
    elif len(sys.argv) > 1 and sys.argv[1] == "renderable":
        content = sys.stdin.read()
        payload = json.loads(content)
        validator = RenderableValidator()
        errors = validator.validate(payload)
    elif len(sys.argv) > 1:
        logging.critical("Unknown command: %s", sys.argv[1])
        sys.exit()
    else:
        logging.critical("Missing command")
        sys.exit()

    if errors:
        for error in errors:
            logging.error(error)
    else:
        logging.info("Validation done with no errors!")
        sys.exit(0)
