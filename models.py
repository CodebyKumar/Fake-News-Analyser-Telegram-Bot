from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from pathlib import Path

class NewsInput(BaseModel):
    text: Optional[str] = Field(
        None, description="The textual content of the news article or claim to be analyzed"
    )
    image_path: Optional[Path] = Field(
        None, description="Path to an image (e.g., screenshot of a news article)"
    )
    @model_validator(mode='after')
    def at_least_one_field_required(self): # Changed cls to self
        if not self.text and not self.image_path: #Used self
            raise ValueError("At least one of 'text' or 'image_path' must be provided.")
        return self

    class Config:
        json_schema_extra = {  # Corrected schema_extra to json_schema_extra
            "example": {
                "text": "Breaking: Chocolate cures COVID-19, says random blog.",
                "image_path": "screenshots/news.png"
            }
        }

class NewsAnalysisResult(BaseModel):
    verdict: str = Field(..., description="Verdict about the news: Real, Fake, or Uncertain")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    reason: str = Field(..., description="Explanation or reasoning for the verdict")
    references: Optional[List[str]] = Field(
        default=None,
        description="List of reference URLs or sources used to verify the news"
    )

    class Config:
        json_schema_extra = { # Corrected schema_extra to json_schema_extra
            "example": {
                "verdict": "Fake",
                "confidence": 0.92,
                "reason": "No credible news outlet has reported this claim. It originated from a satire website.",
                "references": [
                    "https://www.reuters.com/fact-check",
                    "https://snopes.com/fact-check/alien-landing-hoax"
                ]
            }
        }