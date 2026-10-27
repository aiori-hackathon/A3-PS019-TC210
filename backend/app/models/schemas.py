from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SQLConnection(BaseModel):
    dialect: str = "SQLite"          # SQLite 
    host: str = ""
    port: str = ""
    dbName: str = "data/sample.db"   # file path for SQLite, database name otherwise
    username: str = ""
    password: str = ""
    schema_name: str = Field("", alias="schema")

    model_config = {"populate_by_name": True}


class SQLScanRequest(BaseModel):
    connection: SQLConnection
    checklist: Dict[str, bool] = {}


class EvaluationRequest(BaseModel):
    true_labels: List[str]
    predicted_labels: List[str]


class ScanStartRequest(BaseModel):
    sourceType: str                   # "csv" | "sql" | "sqlite"
    sourceRef: Any                    # upload id (csv, sqlite) or SQLConnection dict (sql)
    checklist: Dict[str, bool] = {}


class RuleTestRequest(BaseModel):
    text: str = Field(..., max_length=10000)
    context: Optional[str] = None
