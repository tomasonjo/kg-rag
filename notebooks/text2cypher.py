import neo4j
from schema_utils import get_schema
from typing import Literal
from utils import chat


class Text2Cypher:
    def __init__(self, driver: neo4j.Driver):
        self.driver = driver
        self.dynamic_sections = {}
        self.required_sections = ["question"]
        self.prompt_template = prompt_template

        schema_string = get_schema(driver)
        self.set_prompt_section("schema", schema_string)

    def set_prompt_section(
        self,
        section: Literal["terminology", "examples", "schema", "question"],
        value: str,
    ):
        self.dynamic_sections[section] = value

    def get_full_prompt(self):
        prompt = self.prompt_template["static"]["instructions"]
        # loop through the prompt_template["dynamic"] and add the values from self.dynamic_sections
        for section in self.prompt_template["dynamic"]:
            if section in self.dynamic_sections:
                prompt += self.prompt_template["dynamic"][section].format(
                    self.dynamic_sections[section]
                )
        return prompt

    def generate_cypher(self):
        # check if required sections are set
        for section in self.required_sections:
            if section not in self.dynamic_sections:
                raise ValueError(
                    f"Section {section} is required to generate a prompt. Use set_prompt_section to set it."
                )
        prompt = self.get_full_prompt()
        cypher = chat(messages=[{"role": "user", "content": prompt}])
        return cypher


prompt_template = {
    "static": {
        "instructions": """
    Instructions: 
    Generate Cypher statement to query a graph database to get the data to answer the user question below.

    Format instructions:
    Do not include any explanations or apologies in your responses.
    Do not respond to any questions that might ask anything else than for you to 
    construct a Cypher statement.
    Do not include any text except the generated Cypher statement.
    ONLY RESPOND WITH CYPHER, NO CODEBLOCKS.
    Make sure to name RETURN variables as requested in the user question.
    """
    },
    "dynamic": {
        "schema": """
    Graph Database Schema:
    Use only the provided relationship types and properties in the schema.
    Do not use any other relationship types or properties that are not provided in the schema.
    {}
    """,
        "terminology": """
    Terminology mapping:
    This section is helpful to map terminology between the user question and the graph database schema.
    {}
    """,
        "examples": """
    Examples:
    The following examples provide useful patterns for querying the graph database.
    {}
    """,
        "question": """
    User question: {}
    """,
    },
}
