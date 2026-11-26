"""
Pydantic schemas for SEC filing extraction.

NOTE: Financial metrics (revenue, margins, EPS) are NOT extracted here.
      They come from FMP API (income_statement.json, balance_sheet.json, cash_flow.json).

      This module extracts QUALITATIVE information only:
      - Risk factors
      - Management guidance
      - Key events
      - Sentiment/tone
"""
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from enum import Enum


class RiskCategory(str, Enum):
    """Categories of risk factors."""
    COMPETITION = "competition"
    REGULATORY = "regulatory"
    SUPPLY_CHAIN = "supply_chain"
    CYBERSECURITY = "cybersecurity"
    MACROECONOMIC = "macroeconomic"
    MARKET = "market"  # Market conditions, volatility, pricing
    CREDIT = "credit"  # Credit risk, defaults, counterparty
    LIQUIDITY = "liquidity"  # Liquidity, funding, capital
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    INVESTMENT = "investment"
    LEGAL = "legal"
    ENVIRONMENTAL = "environmental"
    GEOPOLITICAL = "geopolitical"
    TECHNOLOGY = "technology"
    REPUTATION = "reputation"
    STRATEGIC = "strategic"
    LABOR = "labor"  # Workforce, unions, hiring, retention
    OTHER = "other"


class Severity(str, Enum):
    """Severity levels for risks."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Sentiment(str, Enum):
    """
    Management sentiment/tone (5-point scale for sensitivity).

    Scale designed for realistic corporate communications:
    - Management rarely uses truly negative language in SEC filings
    - This scale captures nuances between "confident" and "concerned"
    """
    CONFIDENT = "confident"      # Strong positive: "exceeded expectations", "record performance"
    OPTIMISTIC = "optimistic"    # Moderate positive: "expect growth", "well-positioned"
    NEUTRAL = "neutral"          # Factual, balanced: no strong sentiment either way
    CAUTIOUS = "cautious"        # Hedging: "uncertain environment", "monitoring closely"
    CONCERNED = "concerned"      # Acknowledging issues: "challenging", "headwinds", "restructuring"


class RiskFactor(BaseModel):
    """A single risk factor from SEC filing."""
    category: RiskCategory = Field(description="Risk category")
    severity: Severity = Field(description="Severity level based on language used")
    description: str = Field(description="Brief description (1-2 sentences)")
    is_new: bool = Field(default=False, description="True if this is a NEW risk not in prior filings")


class Guidance(BaseModel):
    """Management guidance/outlook from the filing."""
    direction: Optional[Sentiment] = Field(default=None, description="Overall direction: positive/negative/neutral")
    statement: Optional[str] = Field(default=None, description="Key guidance statement (direct quote or paraphrase)")
    revenue_outlook: Optional[str] = Field(default=None, description="Revenue guidance if mentioned - ONLY if specific numbers given")
    earnings_outlook: Optional[str] = Field(default=None, description="Earnings guidance if mentioned - ONLY if specific numbers given")


class KeyEvent(BaseModel):
    """Significant event or change mentioned in filing."""
    event_type: str = Field(description="Type: acquisition, divestiture, restructuring, litigation, product_launch, etc.")
    description: str = Field(description="Brief description of the event")
    impact: Optional[str] = Field(default=None, description="Stated or implied impact")


class ExtractedFacts(BaseModel):
    """
    Qualitative facts extracted from SEC filing.

    NOTE: Financial numbers come from FMP API, not from this extraction.
    This focuses on QUALITATIVE information that LLM excels at:
    - Risk analysis
    - Management tone/sentiment
    - Forward-looking statements
    - Key events
    """
    # Metadata
    ticker: str = Field(description="Stock ticker symbol")
    filing_date: str = Field(description="Filing date (YYYY-MM-DD)")
    filing_type: str = Field(description="Filing type: 10-K or 10-Q")
    fiscal_period: str = Field(description="Fiscal period: Q1/Q2/Q3/Q4 YYYY or FY YYYY")

    # Risk factors (from Item 1A)
    risk_factors: List[RiskFactor] = Field(
        default_factory=list,
        description="Key risk factors identified (top 5-10)"
    )
    risk_summary: Optional[str] = Field(
        default=None,
        description="One sentence summary of overall risk profile"
    )

    # Management guidance (from MD&A)
    guidance: Optional[Guidance] = Field(
        default=None,
        description="Forward-looking statements from management"
    )

    # Overall sentiment (from MD&A tone)
    sentiment: Sentiment = Field(
        default=Sentiment.NEUTRAL,
        description="Overall sentiment/tone of MD&A section"
    )
    sentiment_rationale: Optional[str] = Field(
        default=None,
        description="Brief explanation of sentiment assessment"
    )

    # Key events
    key_events: List[KeyEvent] = Field(
        default_factory=list,
        description="Major events: M&A, restructuring, litigation, etc."
    )

    # Competitive position
    competitive_position: Optional[str] = Field(
        default=None,
        description="Management's view on competitive position (1-2 sentences)"
    )

    # Extraction metadata
    extraction_confidence: Optional[str] = Field(
        default=None,
        description="LLM's confidence in extraction: high/medium/low"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "AMZN",
                "filing_date": "2024-02-01",
                "filing_type": "10-K",
                "fiscal_period": "FY 2023",
                "risk_factors": [
                    {
                        "category": "competition",
                        "severity": "high",
                        "description": "Intense competition in cloud services from Microsoft Azure and Google Cloud",
                        "is_new": False
                    },
                    {
                        "category": "regulatory",
                        "severity": "medium",
                        "description": "Increased antitrust scrutiny in US and EU markets",
                        "is_new": True
                    }
                ],
                "risk_summary": "Primary risks are competitive pressure in cloud and regulatory scrutiny",
                "guidance": {
                    "direction": "optimistic",
                    "statement": "Management expects continued growth driven by AWS and advertising",
                    "revenue_outlook": "Q1 2024 revenue between $138B-$143.5B",
                    "earnings_outlook": "Operating income between $8B-$12B"
                },
                "sentiment": "optimistic",
                "sentiment_rationale": "Uses phrases like 'strong momentum' and 'well-positioned for growth'",
                "key_events": [
                    {
                        "event_type": "restructuring",
                        "description": "Completed workforce reduction of 27,000 employees",
                        "impact": "Expected annual savings of $2B"
                    }
                ],
                "competitive_position": "Maintains market leadership in e-commerce and cloud computing",
                "extraction_confidence": "high"
            }
        }
