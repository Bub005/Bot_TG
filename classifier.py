def classify_article(title: str):
    title_lower = (title or "").lower()

    # Esempio minimale: qui puoi espandere mapping/keyword
    if any(k in title_lower for k in ["biotech", "bio", "nano", "robot", "automation", "automazione"]):
        return "Ingegneria", "Automazione"
    if any(k in title_lower for k in ["mechanical", "meccanica"]):
        return "Ingegneria", "Meccanica"
    if any(k in title_lower for k in ["crypto", "bitcoin", "ethereum", "criptovalute"]):
        return "Finanza", "Criptovalute"
    if any(k in title_lower for k in ["election", "elezioni", "parlamento", "government", "governo"]):
        return "Politica", "Locale"

    return "Generale", "Altro"
