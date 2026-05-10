"""
Jinja2 template engine wrapper for rendering network configuration templates.
"""

import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, Template, nodes, meta

# Absolute path to the /templates directory at project root
_TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "templates",
)


class TemplateEngine:

    def __init__(self, search_path: str | None = None) -> None:
        resolved_path = search_path or _TEMPLATES_DIR
        self.env = Environment(
            loader=FileSystemLoader(resolved_path),
            trim_blocks=True,
            lstrip_blocks=False,
        )

        def _raise(msg: str) -> None:
            raise Exception(msg)

        self.env.globals["now"] = datetime.now().replace(microsecond=0)
        self.env.globals["raise"] = _raise

    # ------------------------------------------------------------------

    def list_available_templates(self) -> list[str]:
        return [f for f in os.listdir(_TEMPLATES_DIR) if f.endswith(".j2")]

    def get_template_variables(self, template_name: str) -> list[str]:
        """
        Extract all variables referenced in a Jinja2 template, including
        loop-variable attribute access (e.g. ``vlan.id``, ``port.name``).
        """
        source = self.env.loader.get_source(self.env, template_name)[0]
        parsed = self.env.parse(source)

        variables: set[str] = set(meta.find_undeclared_variables(parsed))

        for for_node in parsed.find_all(nodes.For):
            if not isinstance(for_node.target, nodes.Name):
                continue
            loop_var = for_node.target.name
            for attr_node in for_node.find_all((nodes.Getattr, nodes.Getitem)):
                if not (
                    isinstance(attr_node.node, nodes.Name)
                    and attr_node.node.name == loop_var
                ):
                    continue
                if isinstance(attr_node, nodes.Getattr):
                    variables.add(f"{loop_var}.{attr_node.attr}")
                elif isinstance(attr_node, nodes.Getitem) and isinstance(
                    attr_node.arg, nodes.Const
                ):
                    variables.add(f"{loop_var}['{attr_node.arg.value}']")

        return sorted(variables)

    def render(self, template_name: str, data: dict) -> str:
        template = self.env.get_template(template_name)
        return template.render(**data)

    @staticmethod
    def render_from_string(template_content: str, data: dict) -> str:
        template = Template(template_content)
        return template.render(**data)
