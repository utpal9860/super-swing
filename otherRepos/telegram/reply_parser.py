"""
Parser for Telegram reply messages that modify trades.
Detects instructions like "cancel order", "book profits", "keep scalping profits"
"""
import re
from typing import Dict, Optional


def parse_reply_instruction(message_text: str) -> Optional[Dict]:
    """
    Parse reply message for trade modification instructions.
    
    Args:
        message_text: The text content of the reply message
    
    Returns:
        Dict with "action" key:
        - {"action": "cancel"} for cancel instructions
        - {"action": "book_profits"} for book profits/scalping instructions
        - None if not a modification instruction
    """
    if not message_text:
        return None
    
    text = message_text.upper().strip()
    
    # Cancel keywords
    cancel_patterns = [
        r"\bCANCEL\b",
        r"\bCANCELLED\b",
        r"\bCANCEL\s+ORDER\b",
        r"\bDON'?T\s+TAKE\b",
        r"\bSKIP\b",
        r"\bIGNORE\b",
        r"\bNO\s+ENTRY\b",
        r"\bDON'?T\s+ENTER\b",
    ]
    
    # Book profits / scalping keywords
    book_profits_patterns = [
        r"\bBOOK\s+PROFITS?\b",
        r"\bBOOKING\s+PROFITS?\b",
        r"\bSCALPING\s+PROFITS?\b",
        r"\bKEEP\s+BOOKING\b",
        r"\bKEEP\s+SCALPING\b",
        r"\bEXIT\s+NOW\b",
        r"\bSQUARE\s+OFF\b",
        r"\bCLOSE\s+POSITION\b",
        r"\bTAKE\s+PROFIT\b",
        r"\bBOOK\s+AND\s+EXIT\b",
    ]
    
    # Check for cancel instructions first (more specific)
    for pattern in cancel_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return {"action": "cancel"}
    
    # Check for book profits instructions
    for pattern in book_profits_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return {"action": "book_profits"}
    
    return None


def is_reply_modification(message_text: str) -> bool:
    """
    Quick check if message might be a trade modification instruction.
    Returns True if any modification keywords are found.
    """
    return parse_reply_instruction(message_text) is not None


