"""
Simple script to try the text2sql generation on top of
BIRD minidev dataset.

"""

import ast
from dataclasses import dataclass, field
from functools import partial
from typing import (
    Any,
    Dict,
    Literal,
    Optional,
    TypedDict,
    Union,
)

import click
import litellm
import yaml
from langchain_community.utilities import SQLDatabase
from langgraph.graph import END, START, StateGraph
from litellm.caching.caching import Cache
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from rich.traceback import install
from sqlalchemy import Engine, create_engine, text

install()


# start snippet state
class Message(TypedDict):
    """Message to pass to litellm"""

    role: Literal["user", "system"]
    content: str


@dataclass
class State:
    question: Optional[str] = None
    messages: list[Message] = field(default_factory=list)
    sql: Optional[str] = None


# end snippet state


# start snippet input
@dataclass
class Input:
    """User provides the connection
    details and the question"""

    question: str


# end snippet input


# start snippet output
@dataclass
class Output:
    """SQL result and
    LLM explanation"""

    sql: str
    result: str


# end snippet output


# start snippet cfg
class SQLGenConfig(BaseModel):
    db_url: str = Field(description="DB connection string")
    engine: Engine = Field(description="DB connection")
    db: SQLDatabase = Field(description="Basic schema info")
    system_message_tpl: str = Field(
        description=r"Templated sys msg {}", repr=False
    )
    llm: Dict[
        str, Union[str, Dict[str, str], int, BaseModel]
    ]
    structured: bool = Field(
        description="Enable/disable JSON Schema"
    )
    extra_context: Dict[str, str] = Field(
        default_factory=dict
    )
    # ...
    # end snippet cfg

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    @classmethod
    def from_yaml(
        cls, path: str, **overrides: Any
    ) -> "SQLGenConfig":
        """Read config from YAML file"""
        with open(path, "r", encoding="utf-8") as fp:
            config: Dict[str, Any] = yaml.safe_load(fp)
            db_url = config["db_url"]
            engine = create_engine(db_url)
            db = SQLDatabase(engine=engine)
            cfg = SQLGenConfig(
                db_url=db_url,
                engine=engine,
                db=db,
                system_message_tpl=config.get("prompt"),
                llm=config.get("llm"),
                structured=config.get("structured", True),
            )

            for key, value in overrides.items():
                logger.info(
                    f"Setting CLI override of config to {key}={value}"
                )
                setattr(cfg, key, value)
            return cfg


# start snippet init_
def init(
    initial: Input,
) -> State:
    """Initializes the state"""
    return State(
        question=initial.question,
    )


# end snippet init_


# start snippet prompt_gen
def prompt_gen(state: State, sql_gen_config: SQLGenConfig):
    """Formats the prompt"""
    system_message_content = (
        sql_gen_config.system_message_tpl.format(
            dialect=sql_gen_config.db.dialect,
            top_k=10,
            table_info=sql_gen_config.db.get_table_info(),
            extra_context=sql_gen_config.extra_context,
        )
    )
    state.messages.extend(
        [
            {
                "role": "system",
                "content": system_message_content,
            },
            {"role": "user", "content": state.question},
        ]
    )
    return state


# end snippet prompt_gen


class SQLOutput(BaseModel):
    sql: str = Field(description="The SQL query")
    explanation: str = Field(
        description="The explanation of the query"
    )


# start snippet call_llm
def call_llm(
    state: State, sql_gen_config: SQLGenConfig
) -> State:
    response = litellm.completion(
        messages=state.messages,
        response_format=SQLOutput
        if sql_gen_config.structured
        else None,
        **sql_gen_config.llm,  # model here
    )
    if sql_gen_config.structured:
        state.sql = SQLOutput.model_validate_json(
            response.choices[0].message.content
        ).sql
    else:
        state.sql = response.choices[0].message.content
    logger.info(
        f"Generated SQL: {sql_gen_config.structured=} {state.sql=}"
    )
    return state


# end snippet call_llm


# start snippet exec_sql
def exec_sql(
    state: State, sql_gen_config: SQLGenConfig
) -> Output:
    logger.info(f"Executing SQL {state=}")
    with sql_gen_config.engine.connect() as conn:
        result = conn.execute(text(state.sql))
        try:
            results = str(result.fetchall())
        except Exception as error:
            results = str(error)

    assert state.sql is not None
    return Output(sql=state.sql, result=results)


# end snippet exec_sql


def create_graph(sql_gen_config: SQLGenConfig):
    graph_builder = StateGraph(
        input_schema=Input,
        state_schema=State,
        output_schema=Output,
    )

    # start snippet graph
    graph_builder.add_node("init", init)

    graph_builder.add_node(
        "prompt_gen",
        partial(prompt_gen, sql_gen_config=sql_gen_config),
    )
    graph_builder.add_node(
        "call_llm",
        partial(call_llm, sql_gen_config=sql_gen_config),
    )
    graph_builder.add_node(
        "exec_sql",
        partial(exec_sql, sql_gen_config=sql_gen_config),
    )

    graph_builder.add_edge(START, "init")
    graph_builder.add_edge("init", "prompt_gen")
    graph_builder.add_edge("prompt_gen", "call_llm")
    graph_builder.add_edge("call_llm", "exec_sql")
    graph_builder.add_edge("exec_sql", END)
    graph = graph_builder.compile()
    # end snippet graph
    return graph


def parse_key_value_with_literal_eval(ctx, param, values):
    """Parse key-value pairs and convert values using ast.literal_eval."""
    result = {}
    if not values:
        return result

    for value in values:
        try:
            if "=" not in value:
                ctx.fail(
                    f"Expected format 'key=value', got: {value}"
                )

            key, val = value.split("=", 1)

            # Convert the value using ast.literal_eval
            try:
                parsed_val = ast.literal_eval(val)
            except (SyntaxError, ValueError):
                # Fall back to string if literal_eval fails
                parsed_val = val

            result[key] = parsed_val

        except Exception as e:
            ctx.fail(f"Error parsing '{value}': {str(e)}")
    return result


@click.command()
@click.argument(
    "config_pth",
    type=click.Path(file_okay=True),
    default="config.yaml",
)
@click.option(
    "-c/--cache",
    "use_cache",
    default=False,
    help="Enable litellm cache (disk for now)",
)
@click.option(
    "-d",
    "cache_dir",
    default=".litellm_chache",
    type=click.STRING,
    help="Configure directory if cache is enabled",
)
@click.option(
    "-o",
    "--overrides",
    multiple=True,
    callback=parse_key_value_with_literal_eval,
    help="Set options in format key=value where value is parsed with ast.literal_eval",
)
def main(
    config_pth,
    use_cache,
    cache_dir,
    overrides,
):
    logger.info(f"Using config file: {config_pth}")
    sql_gen_config: SQLGenConfig = SQLGenConfig.from_yaml(
        config_pth, **overrides
    )
    logger.info(sql_gen_config)
    if use_cache:
        logger.info(
            f"Enabling cache (disk_cache_dir={cache_dir})"
        )
        litellm.cache = Cache(
            type="disk", disk_cache_dir=cache_dir
        )

    graph = create_graph(sql_gen_config=sql_gen_config)
    result = graph.invoke(
        Input(
            question="How many schools with an average score in Math greater than 400 in the SAT test are exclusively virtual?",
        )
    )

    print(f"Answer: {result}")


if __name__ == "__main__":
    main()
