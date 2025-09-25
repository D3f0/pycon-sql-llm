import json
import os
from pathlib import Path

import litellm
from litellm.caching.caching import Cache
from pydantic import BaseModel, Field

from langgraph.graph import START, END, StateGraph

litellm.cache = Cache(type="disk")


with Path("messages.json").open("r") as fp:
    messages = json.load(fp)

from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine, text

base = Path("./minidev/MINIDEV/dev_databases/california_schools/")
db = base / "california_schools.sqlite"
descriptions = []
for desc_file in (base / "database_description").glob("*"):
    descriptions.append(desc_file.read_text())
full_description = "\n".join(descriptions)

content = messages[0]["content"]
content = f"{content}\n\n{descriptions}"

messages[0]["content"] = content
print(messages)


class SQLOutput(BaseModel):
    sql: str
    explanation: str


model = os.getenv("MODEL", "watsonx/ibm/granite-3-2-8b-instruct")
# model = "watsonx/ibm/granite-34b-sql-gen"
model = "watsonx/mistralai/mistral-medium-2505"
print("model: [bold]model[/bold]")

# litellm._turn_on_debug()
response = litellm.completion(
    # model="watsonx/meta-llama/granite-20b-code-base-sql-gen",
    model=model,
    messages=messages,
    response_format=SQLOutput,
    base_url=os.getenv("WATSONX_API_BASE"),
)
result = SQLOutput.model_validate_json(response.choices[0].message.content)
from IPython.display import display

display(result)


engine = create_engine(f"sqlite:///{db}")
# engine

with engine.connect() as c:
    resp = c.execute(text(result.sql))
    try:
        print(resp.fetchall())
    except OperationalError as e:
        print(f"Error: {e}")
