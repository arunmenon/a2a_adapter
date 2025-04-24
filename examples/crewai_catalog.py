from types import SimpleNamespace
from a2a_adapter import skill, register_agent

@skill(name="searchCatalog", inputs=["text"], outputs=["json"])
def search_catalog(query:str):
    return {"sku":"12345","name":"Widget","query":query}

# Minimal stand-in for a CrewAI Agent object
agent = SimpleNamespace(name="Catalog Agent", tasks=[search_catalog])

if __name__=="__main__":
    register_agent(agent, host="0.0.0.0", port=8080)
