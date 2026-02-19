# per ora semplicemente assegna macro e branch keyword-based
def classify_article(title):
    title_lower = title.lower()
    # Macro e branch semplificate
    if "biotech" in title_lower or "nano" in title_lower or "robot" in title_lower:
        return "Ingegneria", "Automazione"
    if "mechanical" in title_lower or "meccanica" in title_lower:
        return "Ingegneria", "Meccanica"
    return "Generale", "Altro"
