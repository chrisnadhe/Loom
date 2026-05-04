from jinja2 import Environment, FileSystemLoader, Template
import os

class TemplateEngine:
    def __init__(self, search_path="templates"):
        self.env = Environment(loader=FileSystemLoader(search_path))

    def list_available_templates(self):
        return [f for f in os.listdir("templates") if f.endswith(".j2")]

    def get_template_variables(self, template_name: str):
        from jinja2 import meta
        template_source = self.env.loader.get_source(self.env, template_name)[0]
        parsed_content = self.env.parse(template_source)
        return list(meta.find_undeclared_variables(parsed_content))

    def render(self, template_name: str, data: dict):
        template = self.env.get_template(template_name)
        return template.render(**data)

    @staticmethod
    def render_from_string(template_content: str, data: dict):
        template = Template(template_content)
        return template.render(**data)
