"""Default demo universe. Users can add or remove companies at runtime; nothing downstream depends on this list.

Tickers were validated against Yahoo Finance on 2026-11-03. TATAMOTORS.NS no longer resolves after
the demerger, so the passenger-vehicle successor TMPV (which kept BSE code 500570) stands in for it.
"""

PORTFOLIO = [
    # symbol, name, sector, size bucket
    ("TCS", "Tata Consultancy Services", "IT", "large"),
    ("INFY", "Infosys", "IT", "large"),
    ("WIPRO", "Wipro", "IT", "large"),
    ("HDFCBANK", "HDFC Bank", "Banking", "large"),
    ("ICICIBANK", "ICICI Bank", "Banking", "large"),
    ("SBIN", "State Bank of India", "Banking", "large"),
    ("RELIANCE", "Reliance Industries", "Energy", "large"),
    ("ONGC", "Oil & Natural Gas Corporation", "Energy", "large"),
    ("NTPC", "NTPC", "Energy", "large"),
    ("TMPV", "Tata Motors Passenger Vehicles", "Automobile", "large"),
    ("MARUTI", "Maruti Suzuki India", "Automobile", "large"),
    ("ITC", "ITC", "FMCG", "large"),
    ("HINDUNILVR", "Hindustan Unilever", "FMCG", "large"),
    ("SUNPHARMA", "Sun Pharmaceutical Industries", "Pharma", "large"),
    ("CIPLA", "Cipla", "Pharma", "large"),
    ("LT", "Larsen & Toubro", "Infrastructure", "large"),
    ("BHARTIARTL", "Bharti Airtel", "Telecom", "large"),
    ("TITAN", "Titan Company", "Consumer", "large"),
    ("SUZLON", "Suzlon Energy", "Renewables", "mid"),
    ("MTARTECH", "MTAR Technologies", "Defence & Aerospace", "small"),
]

RESEARCH_PICKS = [
    ("HAL", "Hindustan Aeronautics", "Defence & Aerospace", "large"),
    ("BEL", "Bharat Electronics", "Defence & Aerospace", "large"),
    ("ASIANPAINT", "Asian Paints", "Consumer", "large"),
    ("COALINDIA", "Coal India", "Mining", "large"),
    ("POWERGRID", "Power Grid Corporation of India", "Utilities", "large"),
]
