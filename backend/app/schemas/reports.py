from datetime import datetime
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator


class ReportCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['confirm_existing','report_removed','report_damaged','correct_class','correct_location','update_evidence']
    image_id:str=Field(min_length=1,max_length=36)
    comment:str=Field(min_length=3,max_length=2000)
    proposed_class:int|None=Field(None,ge=0,le=9,strict=True)
    latitude:float|None=Field(None,ge=-90,le=90,allow_inf_nan=False)
    longitude:float|None=Field(None,ge=-180,le=180,allow_inf_nan=False)

    @model_validator(mode='after')
    def validate_action(self):
        self.comment=self.comment.strip()
        if len(self.comment)<3: raise ValueError('Describe the observed evidence')
        if (self.action=='correct_class') != (self.proposed_class is not None):
            raise ValueError('Only a class correction requires proposed_class')
        if self.action=='correct_location':
            if self.latitude is None or self.longitude is None: raise ValueError('Location correction needs both coordinates')
        elif self.latitude is not None or self.longitude is not None:
            raise ValueError('Coordinates only apply to a location correction')
        return self


class ReportResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str
    record_id:str
    image_id:str
    created_by:str
    action:str
    comment:str
    base_revision:int
    proposed_class:int|None
    latitude:float|None
    longitude:float|None
    status:str
    created_at:datetime
    reviewed_by:str|None
    reviewed_at:datetime|None
    review_comment:str|None


class PolicyUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmation_days:int=Field(ge=1,le=365,strict=True)
