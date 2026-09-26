"""AI sales chatbot package."""

from .sales_bot import SalesBot, PRODUCTS, score_lead
from .lead_capture import validate_lead, save_lead

__all__ = ["SalesBot", "PRODUCTS", "score_lead", "validate_lead", "save_lead"]
__version__ = "1.0.0"
