from dataclasses import dataclass, field
from functools import partial
from inspect import signature
from typing import Any, Callable, Dict, Literal, Optional, TypedDict, Union

import litellm
import yaml
from langchain_community.utilities import SQLDatabase
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, create_engine, text
from rich.traceback import install

install()


class Message(TypedDict):
    role: Literal["user", "system"]
    content: str


@dataclass
class State:
    question: Optional[str] = None
    messages: list[Message] = field(default_factory=list)
    sql: Optional[str] = None


@dataclass
class Input:
    """User provides the connection details and the question"""

    question: str


@dataclass
class Output:
    """User provides the connection details and the question"""

    sql: str
    result: str


class SQLGenConfig(BaseModel):
    db_url: str = Field(description="DB connection string")
    engine: Engine = Field(description="DB connection")
    db: SQLDatabase = Field(description="Basic schema info")
    system_message_tpl: str = Field(description=r"Templated sys msg {}")
    llm: Dict[str, Union[str, Dict[str, str]]]

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    @classmethod
    def from_yaml(cls, path: str, **overrides: Any) -> "SQLGenConfig":
        with open(path, "r") as fp:
            config: Dict[str, Any] = yaml.safe_load(fp)
            config.update(**overrides)
            db_url = config["db_url"]
            engine = create_engine(db_url)
            db = SQLDatabase(engine=engine)
            return SQLGenConfig(
                db_url=db_url,
                engine=engine,
                db=db,
                system_message_tpl=config.get("prompt"),
                llm=config.get("llm"),
            )


def init(
    initial: Input,
) -> State:
    """Initializes the state"""

    return State(
        question=initial.question,
    )


def prompt_gen(state: State, sql_gen_config: SQLGenConfig):
    """Formats the prompt"""
    system_message_content = sql_gen_config.system_message_tpl.format(
        dialect=sql_gen_config.db.dialect,
        top_k=10,
        table_info=sql_gen_config.db.get_table_info(),
    )
    state.messages.extend(
        [
            {"role": "system", "content": system_message_content},
            {"role": "user", "content": state.question},
        ]
    )
    return state


class SQLOutput(BaseModel):
    sql: str = Field(description="The SQL query")
    explanation: str = Field(description="The explanation of the query")


def call_llm(state: State, sql_gen_config: SQLGenConfig) -> State:
    response = litellm.completion(
        model=sql_gen_config.llm["model"],
        messages=state.messages,
        response_format=SQLOutput,
    )
    state.sql = SQLOutput.model_validate_json(response.choices[0].message.content).sql

    return state


def exec_sql(state: State, sql_gen_config: SQLGenConfig) -> Output:
    with sql_gen_config.engine.connect() as conn:
        result = conn.execute(text(state.sql))
        try:
            results = str(result.fetchall())
        except Exception as error:
            results = str(error)

    assert state.sql is not None
    return Output(sql=state.sql, result=results)


class ConfigAwareStateGraph(StateGraph):
    """StateGraph extension that supports config injection using functools.partial."""

    def __init__(
        self, *args, sql_gen_config: Optional[BaseModel] = None, **kwargs: Any
    ):
        super().__init__(**kwargs)
        self.sql_gen_config = sql_gen_config

    def add_node(self, key: str, node: Callable, **kwargs: Any) -> None:
        """Add a node with automatic config injection if needed."""
        sig = signature(node)
        if "sql_gen_config" in sig.parameters and self.sql_gen_config is not None:
            node = partial(node, sql_gen_config=self.sql_gen_config)

        super().add_node(key, node, **kwargs)


sql_gen_config: SQLGenConfig = SQLGenConfig.from_yaml("./config.yaml")
graph_builder = ConfigAwareStateGraph(
    input_schema=Input,
    state_schema=State,
    output_schema=Output,
    sql_gen_config=sql_gen_config,
)

#
# Nodes
graph_builder.add_node("init", init)
graph_builder.add_node("prompt_gen", prompt_gen)
graph_builder.add_node("call_llm", call_llm)
graph_builder.add_node("exec_sql", exec_sql)
# Edges
graph_builder.add_edge(START, "init")
graph_builder.add_edge("init", "prompt_gen")
graph_builder.add_edge("prompt_gen", "call_llm")
graph_builder.add_edge("call_llm", "exec_sql")
graph_builder.add_edge("exec_sql", END)
graph = graph_builder.compile()

if __name__ == "__main__":
    result = graph.invoke(
        Input(
            question="How many schools with an average score in Math greater than 400 in the SAT test are exclusively virtual?",
        )
    )

    print(f"Answer: {result}")
