"""Saved Clinical Workspace runs, artifacts, notices, and audit events."""
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Integer,
                        Text, ForeignKey, select, insert, update)


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


metadata = MetaData()
runs = Table("workflow_executions", metadata,
    Column("id", String(36), primary_key=True), Column("session_id", String(36), index=True),
    Column("study_id", String(100), index=True),
    Column("parent_id", String(36), ForeignKey("workflow_executions.id")),
    Column("status", String(32)), Column("version", Integer), Column("request", Text),
    Column("created_at", String(40)), Column("updated_at", String(40)))
artifacts = Table("workflow_artifacts", metadata,
    Column("id", String(36), primary_key=True),
    Column("workflow_id", String(36), ForeignKey("workflow_executions.id"), index=True),
    Column("stage", String(40)), Column("version", Integer), Column("payload", Text),
    Column("created_at", String(40)))
events = Table("workflow_events", metadata,
    Column("id", String(36), primary_key=True),
    Column("workflow_id", String(36), ForeignKey("workflow_executions.id"), index=True),
    Column("kind", String(40)), Column("payload", Text), Column("created_at", String(40)))
notifications = Table("workflow_notifications", metadata,
    Column("id", String(180), primary_key=True),
    Column("workflow_id", String(36), ForeignKey("workflow_executions.id"), index=True),
    Column("message", Text), Column("is_read", Integer, default=0), Column("created_at", String(40)))


class Store:
    def __init__(self, url=None, engine=None):
        self.engine = engine if engine is not None else create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
        metadata.create_all(self.engine)

    def create(self, request, parent=None):
        id = uid()
        with self.engine.begin() as c:
            c.execute(insert(runs).values(id=id, session_id=parent["session_id"] if parent else uid(),
                study_id=request["study_id"], parent_id=parent["id"] if parent else None,
                status="QUEUED", version=1, request=json.dumps(request), created_at=now(), updated_at=now()))
        return self.get(id)

    def get(self, id):
        with self.engine.connect() as c:
            row = c.execute(select(runs).where(runs.c.id == id)).mappings().first()
        if not row:
            raise KeyError(id)
        result = dict(row)
        result["request"] = json.loads(result["request"])
        return result

    def list(self):
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(select(runs).order_by(runs.c.created_at.desc())).mappings()]

    def status(self, id, status, version=None):
        values = {"status": status, "updated_at": now()}
        if version is not None:
            values["version"] = version
        with self.engine.begin() as c:
            c.execute(update(runs).where(runs.c.id == id).values(**values))

    def artifact(self, workflow, stage, version, payload):
        id = uid()
        encoded = json.dumps(payload, allow_nan=False, default=str)
        with self.engine.begin() as c:
            c.execute(insert(artifacts).values(id=id, workflow_id=workflow, stage=stage, version=version,
                                              payload=encoded, created_at=now()))
        return id

    def read_artifact(self, id):
        with self.engine.connect() as c:
            row = c.execute(select(artifacts).where(artifacts.c.id == id)).mappings().one()
        return json.loads(row["payload"])

    def event(self, workflow, kind, payload):
        with self.engine.begin() as c:
            c.execute(insert(events).values(id=uid(), workflow_id=workflow, kind=kind,
                payload=json.dumps(payload, default=str), created_at=now()))

    def history(self, workflow):
        with self.engine.connect() as c:
            return [{**dict(r), "payload": json.loads(r["payload"])} for r in c.execute(
                select(events).where(events.c.workflow_id == workflow).order_by(events.c.created_at)).mappings()]

    def notify(self, workflow, key, message):
        id = f"{workflow}:{key}"
        with self.engine.begin() as c:
            if not c.execute(select(notifications.c.id).where(notifications.c.id == id)).first():
                c.execute(insert(notifications).values(id=id, workflow_id=workflow, message=message,
                                                     is_read=0, created_at=now()))

    def notices(self, workflow):
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(select(notifications).where(notifications.c.workflow_id == workflow)).mappings()]

    def acknowledge(self, workflow, id):
        with self.engine.begin() as c:
            c.execute(update(notifications).where(notifications.c.id == id,
                notifications.c.workflow_id == workflow).values(is_read=1))

    def latest_artifact(self, workflow, stage):
        with self.engine.connect() as c:
            row = c.execute(select(artifacts.c.payload).where(artifacts.c.workflow_id == workflow,
                artifacts.c.stage == stage).order_by(artifacts.c.created_at.desc(), artifacts.c.id.desc()).limit(1)).first()
        if row is None: raise KeyError(workflow)
        return json.loads(row[0])
