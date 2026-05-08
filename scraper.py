"""
AlternaMatch — Scraper GitHub Actions
======================================
Ce script est lancé automatiquement par GitHub toutes les 2 heures.
Les offres vues sont mémorisées dans un fichier JSON du dépôt.
"""

import requests
from bs4 import BeautifulSoup
import smtplib
import json
import os
import time
import hashlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ============================================================
#  CONFIGURATION — Modifiez uniquement cette section
# ============================================================
KEYWORDS = [
    # QHSE & Risques industriels
    "alternance ingénieur QHSE",
    "stage QHSE génie industriel",
    "alternance HSE industrie",
    "stage gestion risques industriels",
    # Amélioration continue & Lean
    "alternance amélioration continue Lean",
    "stage ingénieur méthodes industrielles",
    "alternance Lean Manufacturing DMAIC",
    "stage ingénieur qualité industrie",
    # Data & Performance industrielle
    "alternance ingénieur performance industrielle",
    "stage Power BI industrie",
    "alternance pilotage KPI industrie",
    # Logistique & Supply Chain
    "alternance ingénieur logistique supply chain",
    "stage optimisation logistique",
    # Management industriel
    "alternance management industriel",
    "stage ingénieur génie industriel",
]
VILLE = ""               # Vide = toute la France
TYPES = ["alternance", "stage"]
# ============================================================

# Les secrets email viennent des variables GitHub (configurées une seule fois)
EMAIL_DESTINATAIRE = os.environ.get("EMAIL_DESTINATAIRE", "")
EMAIL_EXPEDITEUR   = os.environ.get("EMAIL_EXPEDITEUR", "")
EMAIL_MOT_DE_PASSE = os.environ.get("EMAIL_MOT_DE_PASSE", "")

SEEN_FILE = "offres_vues.json"


def charger_offres_vues():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def sauvegarder_offres_vues(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False)


def id_offre(titre, entreprise):
    texte = f"{titre}{entreprise}".lower().strip()
    return hashlib.md5(texte.encode()).hexdigest()


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def scraper_indeed(keyword, ville):
    offres = []
    try:
        q = keyword.replace(" ", "+")
        l = (ville or "France").replace(" ", "+")
        url = f"https://fr.indeed.com/jobs?q={q}&l={l}&fromage=1"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", class_="job_seen_beacon")[:8]:
            titre_el     = card.find("h2", class_="jobTitle")
            entreprise_el = card.find("span", {"data-testid": "company-name"})
            lieu_el      = card.find("div", {"data-testid": "text-location"})
            lien_el      = card.find("a", class_="jcs-JobTitle")
            offres.append({
                "titre":      titre_el.get_text(strip=True) if titre_el else "—",
                "entreprise": entreprise_el.get_text(strip=True) if entreprise_el else "—",
                "lieu":       lieu_el.get_text(strip=True) if lieu_el else ville,
                "lien":       "https://fr.indeed.com" + lien_el["href"] if lien_el else url,
                "site":       "Indeed France",
            })
    except Exception as e:
        print(f"[Indeed] Erreur : {e}")
    return offres


def scraper_hellowork(keyword, ville):
    offres = []
    try:
        q = keyword.replace(" ", "-")
        l = (ville or "france").lower().replace(" ", "-")
        url = f"https://www.hellowork.com/fr-fr/emploi/recherche.html?k={q}&l={l}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("li", {"data-id": True})[:8]:
            titre_el     = card.find("a", class_="tw-typo-l")
            entreprise_el = card.find("span", class_="tw-typo-m")
            offres.append({
                "titre":      titre_el.get_text(strip=True) if titre_el else "—",
                "entreprise": entreprise_el.get_text(strip=True) if entreprise_el else "—",
                "lieu":       ville or "France",
                "lien":       "https://www.hellowork.com" + titre_el["href"] if titre_el else url,
                "site":       "HelloWork",
            })
    except Exception as e:
        print(f"[HelloWork] Erreur : {e}")
    return offres


def scraper_wttj(keyword, ville):
    offres = []
    try:
        q = keyword.replace(" ", "%20")
        url = f"https://www.welcometothejungle.com/fr/jobs?query={q}&page=1"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("li", {"data-testid": "search-results-list-item-wrapper"})[:8]:
            titre_el    = card.find("h4")
            lien_el     = card.find("a", href=True)
            offres.append({
                "titre":      titre_el.get_text(strip=True) if titre_el else "—",
                "entreprise": "—",
                "lieu":       ville or "France",
                "lien":       "https://www.welcometothejungle.com" + lien_el["href"] if lien_el else url,
                "site":       "Welcome to the Jungle",
            })
    except Exception as e:
        print(f"[WTTJ] Erreur : {e}")
    return offres


def scraper_francetravail(keyword, ville):
    offres = []
    try:
        params = {
            "motsCles": keyword,
            "lieuTravail.libelle": ville,
            "range": "0-9",
        }
        url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            for o in r.json().get("resultats", []):
                offres.append({
                    "titre":      o.get("intitule", "—"),
                    "entreprise": o.get("entreprise", {}).get("nom", "—"),
                    "lieu":       o.get("lieuTravail", {}).get("libelle", ville),
                    "lien":       o.get("origineOffre", {}).get("urlOrigine", "https://www.francetravail.fr"),
                    "site":       "France Travail",
                })
    except Exception as e:
        print(f"[France Travail] Erreur : {e}")
    return offres


def scraper_apec(keyword, ville):
    """Scrape l'Apec — idéal pour profils ingénieur Bac+5."""
    offres = []
    try:
        q = keyword.replace(" ", "%20")
        loc = f"&lieux={ville}" if ville else ""
        url = f"https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles={q}{loc}&typesContrat=143684"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", class_="card-offer")[:8]:
            titre_el     = card.find("a", class_="card-title")
            entreprise_el = card.find("span", class_="card-offer__company")
            lieu_el      = card.find("span", class_="card-offer__location")
            offres.append({
                "titre":      titre_el.get_text(strip=True) if titre_el else "—",
                "entreprise": entreprise_el.get_text(strip=True) if entreprise_el else "—",
                "lieu":       lieu_el.get_text(strip=True) if lieu_el else ville or "France",
                "lien":       "https://www.apec.fr" + titre_el["href"] if titre_el and titre_el.get("href") else url,
                "site":       "Apec",
            })
    except Exception as e:
        print(f"[Apec] Erreur : {e}")
    return offres


def scraper_cadremploi(keyword, ville):
    """Scrape Cadremploi — bons profils ingénieur."""
    offres = []
    try:
        q = keyword.replace(" ", "+")
        loc = ville.replace(" ", "+") if ville else "France"
        url = f"https://www.cadremploi.fr/emploi/liste_offres.html?kw={q}&lieuTravail={loc}&typeContrat=ALT"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("article", class_="c-card-job")[:8]:
            titre_el     = card.find("h2")
            entreprise_el = card.find("span", class_="c-card-job__company")
            lieu_el      = card.find("span", class_="c-card-job__location")
            lien_el      = card.find("a", href=True)
            offres.append({
                "titre":      titre_el.get_text(strip=True) if titre_el else "—",
                "entreprise": entreprise_el.get_text(strip=True) if entreprise_el else "—",
                "lieu":       lieu_el.get_text(strip=True) if lieu_el else ville or "France",
                "lien":       "https://www.cadremploi.fr" + lien_el["href"] if lien_el else url,
                "site":       "Cadremploi",
            })
    except Exception as e:
        print(f"[Cadremploi] Erreur : {e}")
    return offres


def scraper_jobteaser(keyword, ville):
    """Scrape JobTeaser — spécialisé étudiants grandes écoles."""
    offres = []
    try:
        q = keyword.replace(" ", "%20")
        url = f"https://www.jobteaser.com/fr/job-offers?q={q}&contract_type[]=alternance&contract_type[]=stage"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("article")[:8]:
            titre_el     = card.find("h2") or card.find("h3")
            entreprise_el = card.find("span", class_=lambda c: c and "company" in str(c).lower())
            lien_el      = card.find("a", href=True)
            offres.append({
                "titre":      titre_el.get_text(strip=True) if titre_el else "—",
                "entreprise": entreprise_el.get_text(strip=True) if entreprise_el else "—",
                "lieu":       ville or "France",
                "lien":       "https://www.jobteaser.com" + lien_el["href"] if lien_el and lien_el["href"].startswith("/") else (lien_el["href"] if lien_el else url),
                "site":       "JobTeaser",
            })
    except Exception as e:
        print(f"[JobTeaser] Erreur : {e}")
    return offres


def scraper_jooble(keyword, ville):
    """Scrape Jooble — agrégateur avec beaucoup d'offres."""
    offres = []
    try:
        q = keyword.replace(" ", "%20")
        loc = ville.replace(" ", "%20") if ville else "France"
        url = f"https://fr.jooble.org/emploi-{q.replace('%20', '-')}/{loc}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("article")[:8]:
            titre_el     = card.find("h2") or card.find("h1")
            entreprise_el = card.find("span", class_=lambda c: c and "company" in str(c).lower())
            lien_el      = card.find("a", href=True)
            offres.append({
                "titre":      titre_el.get_text(strip=True) if titre_el else "—",
                "entreprise": entreprise_el.get_text(strip=True) if entreprise_el else "—",
                "lieu":       ville or "France",
                "lien":       lien_el["href"] if lien_el else url,
                "site":       "Jooble",
            })
    except Exception as e:
        print(f"[Jooble] Erreur : {e}")
    return offres


def scraper_stagefr(keyword, ville):
    """Scrape Stage.fr — dédié aux stages et alternances."""
    offres = []
    try:
        q = keyword.replace(" ", "+")
        url = f"https://www.stage.fr/offres-de-stage?search={q}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", class_="offer-card")[:8]:
            titre_el     = card.find("h2") or card.find("h3")
            entreprise_el = card.find("span", class_="company")
            lien_el      = card.find("a", href=True)
            offres.append({
                "titre":      titre_el.get_text(strip=True) if titre_el else "—",
                "entreprise": entreprise_el.get_text(strip=True) if entreprise_el else "—",
                "lieu":       ville or "France",
                "lien":       "https://www.stage.fr" + lien_el["href"] if lien_el and lien_el["href"].startswith("/") else (lien_el["href"] if lien_el else url),
                "site":       "Stage.fr",
            })
    except Exception as e:
        print(f"[Stage.fr] Erreur : {e}")
    return offres
    if not offres or not EMAIL_DESTINATAIRE:
        return
    nb = len(offres)
    sujet = f"🔔 {nb} nouvelle{'s' if nb > 1 else ''} offre{'s' if nb > 1 else ''} — AlternaMatch"

    lignes = ""
    for o in offres:
        is_stage = "stage" in o["titre"].lower()
        badge_color = "#854d0e" if is_stage else "#065f46"
        badge_bg    = "#fef9c3" if is_stage else "#d1fae5"
        badge_label = "STAGE" if is_stage else "ALTERNANCE"
        lignes += f"""
        <div style="background:#f8fafc;border-left:4px solid #6EE7B7;
                    border-radius:8px;padding:16px 20px;margin-bottom:14px;">
          <div style="margin-bottom:8px;">
            <span style="background:{badge_bg};color:{badge_color};font-size:11px;
                         font-weight:700;padding:2px 10px;border-radius:20px;">
              {badge_label}
            </span>
            <span style="font-size:11px;color:#94a3b8;margin-left:8px;">{o['site']}</span>
          </div>
          <div style="font-size:16px;font-weight:700;color:#0f172a;margin-bottom:4px;">
            {o['titre']}
          </div>
          <div style="font-size:13px;color:#475569;margin-bottom:12px;">
            🏢 {o['entreprise']} &nbsp;·&nbsp; 📍 {o['lieu']}
          </div>
          <a href="{o['lien']}"
             style="display:inline-block;background:#0f172a;color:#6EE7B7;
                    text-decoration:none;padding:8px 18px;border-radius:8px;
                    font-size:13px;font-weight:600;">
            Voir l'offre →
          </a>
        </div>"""

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;padding:24px;">
      <div style="margin-bottom:20px;">
        <span style="font-size:22px;font-weight:800;color:#0f172a;">Alterna</span>
        <span style="font-size:22px;font-weight:800;color:#10b981;">Match</span>
      </div>
      <div style="background:#ecfdf5;border:1px solid #6ee7b7;border-radius:10px;
                  padding:14px 18px;margin-bottom:24px;font-size:14px;color:#065f46;">
        ✦ {nb} nouvelle{'s' if nb > 1 else ''} offre{'s' if nb > 1 else ''}
        trouvée{'s' if nb > 1 else ''} — {datetime.now().strftime('%d/%m/%Y à %H:%M')}
      </div>
      {lignes}
      <div style="margin-top:28px;padding-top:14px;border-top:1px solid #e2e8f0;
                  font-size:12px;color:#94a3b8;text-align:center;">
        AlternaMatch surveille automatiquement toutes les 2 heures via GitHub Actions.
      </div>
    </body></html>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = sujet
        msg["From"]    = EMAIL_EXPEDITEUR
        msg["To"]      = EMAIL_DESTINATAIRE
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
            srv.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
        print(f"✓ Email envoyé — {nb} offre(s) à {EMAIL_DESTINATAIRE}")
    except Exception as e:
        print(f"✗ Erreur email : {e}")


def main():
    print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M')}] Démarrage du scan — Ghizlane Seggaoui")
    print(f"  Sites : Indeed, HelloWork, WTTJ, France Travail, Apec, Cadremploi, JobTeaser, Jooble, Stage.fr")
    print(f"  Zone  : Toute la France")
    print(f"  Mots-clés : {len(KEYWORDS)} recherches\n")

    seen = charger_offres_vues()
    nouvelles = []

    for keyword in KEYWORDS:
        print(f"  → '{keyword}'")
        toutes = []
        toutes += scraper_indeed(keyword, VILLE)
        toutes += scraper_hellowork(keyword, VILLE)
        toutes += scraper_wttj(keyword, VILLE)
        toutes += scraper_francetravail(keyword, VILLE)
        toutes += scraper_apec(keyword, VILLE)
        toutes += scraper_cadremploi(keyword, VILLE)
        toutes += scraper_jobteaser(keyword, VILLE)
        toutes += scraper_jooble(keyword, VILLE)
        toutes += scraper_stagefr(keyword, VILLE)

        for o in toutes:
            oid = id_offre(o["titre"], o["entreprise"])
            if oid not in seen:
                nouvelles.append(o)
                seen.add(oid)

        time.sleep(2)  # Pause pour éviter le blocage

    sauvegarder_offres_vues(seen)

    print(f"\n→ {len(nouvelles)} nouvelle(s) offre(s) trouvée(s).")
    if nouvelles:
        envoyer_email(nouvelles)
    else:
        print("  Aucune nouveauté cette fois.")


if __name__ == "__main__":
    main()
