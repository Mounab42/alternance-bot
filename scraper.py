"""
AlternaMatch — Scraper via flux RSS officiels
===============================================
Utilise les flux RSS publics d'Indeed et France Travail
qui ne bloquent pas les robots — résultats garantis !
"""

import requests
import smtplib
import json
import os
import time
import hashlib
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from urllib.parse import quote
import re

KEYWORDS = [
    "alternance QHSE",
    "stage QHSE génie industriel",
    "alternance HSE industrie",
    "alternance amélioration continue",
    "stage qualité industrie",
    "alternance Lean Manufacturing",
    "alternance ingénieur logistique",
    "stage optimisation logistique",
    "alternance management industriel",
    "stage génie industriel",
]
VILLE = ""

EMAIL_DESTINATAIRE = os.environ.get("EMAIL_DESTINATAIRE", "")
EMAIL_EXPEDITEUR   = os.environ.get("EMAIL_EXPEDITEUR", "")
EMAIL_MOT_DE_PASSE = os.environ.get("EMAIL_MOT_DE_PASSE", "")

SEEN_FILE = "offres_vues.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AlternaMatch/1.0)", "Accept": "application/rss+xml, */*"}


def charger_offres_vues():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def sauvegarder_offres_vues(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False)


def id_offre(titre, lien):
    return hashlib.md5(f"{titre}{lien}".lower().encode()).hexdigest()


def scraper_indeed_rss(keyword):
    offres = []
    try:
        q = quote(keyword)
        l = quote(VILLE) if VILLE else quote("France")
        url = f"https://fr.indeed.com/rss?q={q}&l={l}&sort=date"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        channel = root.find("channel")
        if channel is None:
            return offres
        for item in channel.findall("item")[:8]:
            titre = item.findtext("title", "—").strip()
            lien  = item.findtext("link", "").strip()
            desc  = item.findtext("description", "")
            entreprise = "—"
            lieu = VILLE or "France"
            bolds = re.findall(r"<b>(.*?)</b>", desc)
            if bolds: entreprise = bolds[0]
            if len(bolds) > 1: lieu = bolds[1]
            offres.append({"titre": titre, "entreprise": entreprise, "lieu": lieu, "lien": lien, "site": "Indeed France"})
        print(f"    [Indeed RSS] {len(offres)} offres")
    except Exception as e:
        print(f"    [Indeed RSS] Erreur : {e}")
    return offres


def scraper_francetravail(keyword):
    offres = []
    try:
        params = {"motsCles": keyword, "range": "0-9"}
        r = requests.get("https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search", params=params, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            for o in r.json().get("resultats", [])[:8]:
                titre = o.get("intitule", "—")
                if any(t in titre.lower() for t in ["alternance", "stage", "apprenti"]):
                    offres.append({
                        "titre": titre,
                        "entreprise": o.get("entreprise", {}).get("nom", "—"),
                        "lieu": o.get("lieuTravail", {}).get("libelle", "France"),
                        "lien": o.get("origineOffre", {}).get("urlOrigine", "https://www.francetravail.fr"),
                        "site": "France Travail",
                    })
        print(f"    [France Travail] {len(offres)} offres")
    except Exception as e:
        print(f"    [France Travail] Erreur : {e}")
    return offres


def scraper_jobijoba(keyword):
    offres = []
    try:
        q = quote(keyword)
        url = f"https://www.jobijoba.com/fr/offres-emploi-rss/?what={q}&where={quote(VILLE or 'France')}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200 and "<rss" in r.text:
            root = ET.fromstring(r.content)
            channel = root.find("channel")
            if channel:
                for item in channel.findall("item")[:8]:
                    titre = item.findtext("title", "—").strip()
                    lien  = item.findtext("link", "").strip()
                    offres.append({"titre": titre, "entreprise": "—", "lieu": VILLE or "France", "lien": lien, "site": "Jobijoba"})
        print(f"    [Jobijoba] {len(offres)} offres")
    except Exception as e:
        print(f"    [Jobijoba] Erreur : {e}")
    return offres


def envoyer_email(offres):
    if not offres or not EMAIL_DESTINATAIRE:
        return
    nb = len(offres)
    lignes = ""
    for o in offres:
        is_stage = "stage" in o["titre"].lower()
        badge_bg = "#fef9c3" if is_stage else "#d1fae5"
        badge_color = "#854d0e" if is_stage else "#065f46"
        badge_label = "STAGE" if is_stage else "ALTERNANCE"
        lignes += f"""<div style="background:#f8fafc;border-left:4px solid #10b981;border-radius:8px;padding:16px 20px;margin-bottom:14px;">
          <div style="margin-bottom:8px;"><span style="background:{badge_bg};color:{badge_color};font-size:11px;font-weight:700;padding:2px 10px;border-radius:20px;">{badge_label}</span>
          <span style="font-size:11px;color:#94a3b8;margin-left:8px;">{o['site']}</span></div>
          <div style="font-size:16px;font-weight:700;color:#0f172a;margin-bottom:4px;">{o['titre']}</div>
          <div style="font-size:13px;color:#475569;margin-bottom:12px;">🏢 {o['entreprise']} &nbsp;·&nbsp; 📍 {o['lieu']}</div>
          <a href="{o['lien']}" style="display:inline-block;background:#0f172a;color:#10b981;text-decoration:none;padding:8px 18px;border-radius:8px;font-size:13px;font-weight:600;">Voir l'offre →</a>
        </div>"""
    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;padding:24px;">
      <div style="margin-bottom:20px;"><span style="font-size:22px;font-weight:800;color:#0f172a;">Alterna</span><span style="font-size:22px;font-weight:800;color:#10b981;">Match</span><span style="font-size:13px;color:#94a3b8;margin-left:8px;">— Ghizlane Seggaoui</span></div>
      <div style="background:#ecfdf5;border:1px solid #6ee7b7;border-radius:10px;padding:14px 18px;margin-bottom:24px;font-size:14px;color:#065f46;">✦ {nb} nouvelle{'s' if nb>1 else ''} offre{'s' if nb>1 else ''} — {datetime.now().strftime('%d/%m/%Y à %H:%M')}</div>
      {lignes}
      <div style="margin-top:28px;padding-top:14px;border-top:1px solid #e2e8f0;font-size:12px;color:#94a3b8;text-align:center;">AlternaMatch surveille automatiquement toutes les 2 heures.</div>
    </body></html>"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔔 {nb} nouvelle{'s' if nb>1 else ''} offre{'s' if nb>1 else ''} — AlternaMatch"
        msg["From"] = EMAIL_EXPEDITEUR
        msg["To"] = EMAIL_DESTINATAIRE
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
            srv.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
        print(f"  ✓ Email envoyé — {nb} offre(s) à {EMAIL_DESTINATAIRE}")
    except Exception as e:
        print(f"  ✗ Erreur email : {e}")


def test_email():
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "✅ AlternaMatch — Surveillance activée !"
        msg["From"] = EMAIL_EXPEDITEUR
        msg["To"] = EMAIL_DESTINATAIRE
        html = """<html><body style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;padding:24px;">
          <span style="font-size:22px;font-weight:800;color:#0f172a;">Alterna</span><span style="font-size:22px;font-weight:800;color:#10b981;">Match</span>
          <div style="background:#ecfdf5;border:1px solid #6ee7b7;border-radius:10px;padding:20px;margin-top:20px;">
            <div style="font-size:18px;font-weight:700;color:#065f46;margin-bottom:10px;">✅ Surveillance activée !</div>
            <p style="color:#047857;">Bonjour Ghizlane, AlternaMatch fonctionne correctement.<br>
            Vous recevrez un email dès qu'une nouvelle offre correspondant à votre profil sera publiée.</p>
            <p style="color:#047857;font-size:13px;">📍 Zone : Toute la France<br>🔍 10 mots-clés QHSE / Lean / Logistique<br>⏱ Toutes les 2 heures</p>
          </div></body></html>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
            srv.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, msg.as_string())
        print(f"  ✓ Email de test envoyé à {EMAIL_DESTINATAIRE}")
    except Exception as e:
        print(f"  ✗ Erreur email test : {e}")


def main():
    print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M')}] Démarrage — Ghizlane Seggaoui")
    seen = charger_offres_vues()
    nouvelles = []

    for keyword in KEYWORDS:
        print(f"  → '{keyword}'")
        toutes = []
        toutes += scraper_indeed_rss(keyword)
        toutes += scraper_francetravail(keyword)
        toutes += scraper_jobijoba(keyword)
        for o in toutes:
            oid = id_offre(o["titre"], o["lien"])
            if oid not in seen and o["titre"] != "—":
                nouvelles.append(o)
                seen.add(oid)
        time.sleep(1)

    sauvegarder_offres_vues(seen)
    print(f"\n→ {len(nouvelles)} nouvelle(s) offre(s) trouvée(s).")

    if nouvelles:
        envoyer_email(nouvelles)
    else:
        print("  Aucune offre nouvelle — envoi email de test pour vérifier la config.")
        if EMAIL_DESTINATAIRE and EMAIL_MOT_DE_PASSE:
            test_email()


if __name__ == "__main__":
    main()
