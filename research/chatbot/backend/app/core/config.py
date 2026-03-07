from pydantic_settings import BaseSettings
from typing import List, Dict, Optional

class Settings(BaseSettings):
    read_api_url: str
    groq_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    llm_model: str
    summarizer_llm_model: str
    max_tokens: int

    entity_kinds: List[Dict[str, str]] = [
        {"major": "Document", "minor": "extgztorg"},
        {"major": "Document", "minor": "extgztperson"},
        {"major": "Person", "minor": "citizen"},
        {"major": "Organisation", "minor": "cabinetMinister"},
        {"major": "Organisation", "minor": "stateMinister"},
        {"major": "Organisation", "minor": "department"},
        {"major": "Category", "minor": "parentCategory"},
        {"major": "Dataset", "minor": "tabular"}
    ]

    relationship_types: List[str] = [
        "AS_PRESIDENT",
        "AS_MINISTER",
        "AS_DEPARTMENT",
        "AS_APPOINTED",
        "RENAMED_TO",
        "AS_CATEGORY",
        "IS_ATTRIBUTE"
    ]

    special_entities: Dict[str, str] = {
        "governmentRoot": "gov_01"
    }

    graph_hierarchy: str = """
    Operational Graph Rules:
    1. HIERARCHY: Root ('gov_01') -> AS_PRESIDENT -> President -> AS_MINISTER -> Minister (Role- THIS IS JUST THE ROLE NOT THE PERSON, ALWAYS FOLLOW THE AS_APPOINTED RELATION TO GET THE PERSON) -> AS_APPOINTED -> Person.
    2. ROLES: 'Organisation.cabinetMinister' and 'Organisation.stateMinister' coexist. Search and include both levels for a complete answer.
    3. DEPARTMENTS: 'Organisation.department' nodes connect to Minister roles via 'AS_DEPARTMENT'. Since departments shift between ministries, always check for ALL incoming associations.
    4. CONTINUITY: Follow 'RENAMED_TO' relations on Minister roles and departments to track office history across name changes.
    5. ATTRIBUTES: To find metrics (found in 'Dataset' major kind), locate metadata nodes first. Use collective operations to find their parents via 'IS_ATTRIBUTE' incoming relations, and then resolve their values in parallel using the parent ID and the decoded metadata name.
    6. SEARCH & DISCOVERY: Always prioritize searching by 'name'. Use batch tools (for search, relations, and attributes) whenever you have multiple identifiers to optimize performance.
    """

    class Config:
        env_file = ".env"

settings = Settings()
