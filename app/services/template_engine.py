from jinja2 import Environment, FileSystemLoader, Template
import os

class TemplateEngine:
    def __init__(self, search_path="templates"):
        self.env = Environment(
            loader=FileSystemLoader(search_path),
            trim_blocks=True,
            lstrip_blocks=False
        )

    def list_available_templates(self):
        return [f for f in os.listdir("templates") if f.endswith(".j2")]

    def get_template_variables(self, template_name: str):
        from jinja2 import meta, nodes
        template_source = self.env.loader.get_source(self.env, template_name)[0]
        parsed_content = self.env.parse(template_source)
        
        # Standard undeclared variables
        variables = set(meta.find_undeclared_variables(parsed_content))
        
        # Look for attributes used on loop variables (e.g., intf.Interface)
        # We look for nodes like GetAttr(Name('intf'), 'Interface')
        for for_node in parsed_content.find_all(nodes.For):
            if isinstance(for_node.target, nodes.Name):
                loop_var = for_node.target.name
                # Find all attributes used on this loop variable
                for attr_node in for_node.find_all((nodes.Getattr, nodes.Getitem)):
                    if isinstance(attr_node.node, nodes.Name) and attr_node.node.name == loop_var:
                        if isinstance(attr_node, nodes.Getattr):
                            variables.add(f"{loop_var}.{attr_node.attr}")
                        elif isinstance(attr_node, nodes.Getitem) and isinstance(attr_node.arg, nodes.Const):
                            variables.add(f"{loop_var}['{attr_node.arg.value}']")
        
        # Remove 'interfaces' itself if it has sub-attributes, as it's the list
        # Actually, let's keep it but handle it in the UI.
        
        return sorted(list(variables))

    def render(self, template_name: str, data: dict):
        template = self.env.get_template(template_name)
        return template.render(**data)

    @staticmethod
    def render_from_string(template_content: str, data: dict):
        template = Template(template_content)
        return template.render(**data)
