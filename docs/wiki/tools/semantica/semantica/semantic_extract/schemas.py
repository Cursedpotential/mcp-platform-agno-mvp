from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

class EntityOut(BaseModel):
    """Canonical schema for entity extraction output."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    text: str = Field(..., description="The text content of the entity")
    label: str = Field(..., description="The type or label of the entity (e.g., PERSON, ORG)")
    start: int = Field(0, description="Start character index", alias="start_char")
    end: int = Field(0, description="End character index", alias="end_char")
    confidence: float = Field(0.9, description="Confidence score between 0 and 1")
    metadata: dict = Field(default_factory=dict, description="Additional metadata including provenance")

    @field_validator("text", mode="before")
    @classmethod
    def clean_text(cls, v):
        if isinstance(v, str):
            return v.strip()
        return str(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v):
        if isinstance(v, str):
            try:
                v = float(v)
            except ValueError:
                return 0.9
        if isinstance(v, (int, float)):
            return max(0.0, min(1.0, float(v)))
        return 0.9
    
    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data):
        if isinstance(data, dict):
            # Handle 'type' as alias for 'label'
            if "label" not in data and "type" in data:
                data["label"] = data["type"]
            # Handle 'value' or 'span' as alias for 'text'
            if "text" not in data:
                if "value" in data:
                    data["text"] = data["value"]
                elif "span" in data:
                    data["text"] = data["span"]
        return data

class RelationOut(BaseModel):
    """Canonical schema for relation extraction output."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    subject: str = Field(..., description="Source entity text")
    object: str = Field(..., description="Target entity text")
    predicate: str = Field(..., description="Relation type or predicate")
    confidence: float = Field(0.9, description="Confidence score between 0 and 1")
    metadata: dict = Field(default_factory=dict, description="Additional metadata including provenance")

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data):
        if isinstance(data, dict):
            if "subject" not in data and "source" in data:
                data["subject"] = data["source"]
            if "object" not in data and "target" in data:
                data["object"] = data["target"]
            if "predicate" not in data and "label" in data:
                data["predicate"] = data["label"]
        return data

    @property
    def source(self):
        return self.subject
        
    @property
    def target(self):
        return self.object
        
    @property
    def label(self):
        return self.predicate

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v):
        if isinstance(v, str):
            try:
                v = float(v)
            except ValueError:
                return 0.9
        if isinstance(v, (int, float)):
            return max(0.0, min(1.0, float(v)))
        return 0.9

class TripletOut(BaseModel):
    """Canonical schema for triplet extraction output."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    subject: str = Field(..., description="Subject of the triplet")
    predicate: str = Field(..., description="Predicate or relation")
    object: str = Field(..., description="Object of the triplet")
    confidence: float = Field(0.9, description="Confidence score between 0 and 1")
    metadata: dict = Field(default_factory=dict, description="Additional metadata including provenance")

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v):
        if isinstance(v, str):
            try:
                v = float(v)
            except ValueError:
                return 0.9
        if isinstance(v, (int, float)):
            return max(0.0, min(1.0, float(v)))
        return 0.9

class EntitiesResponse(BaseModel):
    """Wrapper for list of entities."""
    entities: List[EntityOut] = Field(default_factory=list)

class RelationsResponse(BaseModel):
    """Wrapper for list of relations."""
    relations: List[RelationOut] = Field(default_factory=list)

class TripletsResponse(BaseModel):
    """Wrapper for list of triplets."""
    triplets: List[TripletOut] = Field(default_factory=list)
