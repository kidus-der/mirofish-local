"""Stand-ins for zep_cloud.external_clients.ontology (used to declare entity/edge types)."""

from pydantic import BaseModel

EntityText = str


class EntityModel(BaseModel):
    pass


class EdgeModel(BaseModel):
    pass
