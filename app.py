import os
import io
import json
import logging
import base64
import secrets
from flask import Flask, request, jsonify, send_file, render_template_string, Response
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY     = os.environ.get("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

SYSTEM_PROMPT = """You are an expert health advisor specializing in insulin resistance, diabetes prevention, and metabolic health. You work for InsuliiniCheck.fi, a Finnish company that sells home insulin testing devices.

Your expertise includes:
- Insulin resistance and its causes
- Type 2 diabetes prevention
- The importance of insulin testing vs blood sugar testing
- Diet and nutrition for metabolic health
- Exercise and lifestyle changes
- Medications like metformin
- How to interpret insulin test results
- The InsuliiniCheck home testing device (399€) and test strips (15€ each)
- The test takes approximately 10 minutes, NOT 1 minute — never say it takes 1 minute

IMPORTANT RULES:
- Always detect the language the user is writing/speaking in and respond in the SAME language
- Keep answers clear, simple and encouraging — not too long
- Always recommend consulting a doctor for personal medical advice
- When relevant, mention that home insulin testing with InsuliiniCheck can help monitor progress
- Be warm, supportive and motivating
- Never diagnose diseases — give educational information only
- NEVER use Markdown formatting like #, ##, **, *, -, or bullet points. Write in plain text only."""

HTML = """<!DOCTYPE html>
<html lang="fi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>InsuliiniCheck — Mittaa insuliinisi kotona</title>
<meta name="description" content="Insuliiniresistenssi on diabeteksen esiaste. Mittaa insuliinisi kotona ennen kuin on liian myöhäistä.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,300;0,400;0,600;0,700;1,300&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root {
  --cream: #faf7f2; --warm: #f5ede0; --brown: #3d2b1f; --brown2: #6b4c3b;
  --accent: #c4622d; --accent2: #e8a87c; --green: #2d6a4f; --green2: #52b788;
  --red: #c1121f; --text: #2a1f1a; --text2: #7a6055; --border: rgba(61,43,31,0.1);
}
* { margin:0; padding:0; box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { font-family:'DM Sans',sans-serif; background:var(--cream); color:var(--text); overflow-x:hidden; }

/* NAV */
.nav { position:fixed; top:0; left:0; right:0; z-index:100; padding:16px 24px; display:flex; align-items:center; justify-content:space-between; background:rgba(61,43,31,0.95); backdrop-filter:blur(12px); border-bottom:1px solid rgba(255,255,255,0.08); }
.nav-logo { font-family:'Fraunces',serif; font-size:20px; color:var(--accent2); font-weight:600; }
.nav-cta { background:var(--accent); color:white; padding:8px 18px; border-radius:100px; font-size:13px; font-weight:500; text-decoration:none; }

/* HERO */
.hero { min-height:100vh; background:var(--brown); display:flex; flex-direction:column; align-items:center; justify-content:center; padding:80px 24px 60px; position:relative; overflow:hidden; text-align:center; }
.hero::before { content:''; position:absolute; width:600px; height:600px; background:radial-gradient(circle,rgba(196,98,45,0.3) 0%,transparent 70%); top:-100px; right:-100px; pointer-events:none; }
.hero-badge { display:inline-block; background:rgba(196,98,45,0.2); border:1px solid rgba(196,98,45,0.4); color:var(--accent2); padding:6px 16px; border-radius:100px; font-size:12px; font-weight:500; letter-spacing:1.5px; text-transform:uppercase; margin-bottom:24px; }
.hero h1 { font-family:'Fraunces',serif; font-size:clamp(36px,7vw,64px); line-height:1.1; color:white; margin-bottom:20px; font-weight:600; }
.hero h1 em { font-style:italic; color:var(--accent2); }
.hero p { font-size:18px; color:rgba(255,255,255,0.7); line-height:1.7; margin-bottom:40px; max-width:580px; }
.hero-buttons { display:flex; gap:12px; justify-content:center; flex-wrap:wrap; }
.btn-primary { background:var(--accent); color:white; padding:16px 32px; border-radius:100px; font-size:15px; font-weight:500; text-decoration:none; box-shadow:0 8px 32px rgba(196,98,45,0.4); }
.btn-secondary { background:rgba(255,255,255,0.1); color:white; padding:16px 32px; border-radius:100px; font-size:15px; font-weight:500; text-decoration:none; border:1px solid rgba(255,255,255,0.2); }
.hero-stats { display:flex; gap:40px; justify-content:center; margin-top:60px; flex-wrap:wrap; }
.stat-num { font-family:'Fraunces',serif; font-size:36px; color:var(--accent2); font-weight:700; }
.stat-label { font-size:12px; color:rgba(255,255,255,0.5); text-transform:uppercase; letter-spacing:1px; margin-top:4px; }
.stat-sub { font-size:11px; color:rgba(255,255,255,0.4); margin-top:2px; }

/* SECTIONS */
section { padding:80px 24px; max-width:900px; margin:0 auto; }
.section-label { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:2px; color:var(--accent); margin-bottom:12px; }
.section-title { font-family:'Fraunces',serif; font-size:clamp(28px,5vw,44px); line-height:1.2; color:var(--brown); margin-bottom:20px; font-weight:600; }
.section-title em { font-style:italic; color:var(--accent); }
.section-text { font-size:17px; line-height:1.8; color:var(--text2); max-width:640px; }

/* PROBLEM */
.problem-section { background:var(--warm); padding:80px 24px; }
.problem-inner { max-width:900px; margin:0 auto; }
.problem-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:20px; margin-top:40px; }
.problem-card { background:white; border-radius:20px; padding:28px; border:1px solid var(--border); }
.problem-icon { font-size:32px; margin-bottom:16px; }
.problem-card h3 { font-family:'Fraunces',serif; font-size:20px; color:var(--brown); margin-bottom:10px; font-weight:600; }
.problem-card p { font-size:14px; line-height:1.7; color:var(--text2); }
.warning-box { background:rgba(193,18,31,0.06); border:1px solid rgba(193,18,31,0.2); border-radius:16px; padding:24px 28px; margin:40px 0; display:flex; gap:16px; align-items:flex-start; }
.warning-icon { font-size:28px; flex-shrink:0; }
.warning-text h4 { font-family:'Fraunces',serif; font-size:18px; color:var(--red); margin-bottom:8px; }
.warning-text p { font-size:14px; line-height:1.7; color:var(--text2); }

/* COMPARISON */
.comparison { display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-top:40px; }
.comp-card { border-radius:20px; padding:28px; }
.comp-bad { background:rgba(193,18,31,0.05); border:1px solid rgba(193,18,31,0.15); }
.comp-good { background:rgba(45,106,79,0.05); border:1px solid rgba(45,106,79,0.2); }
.comp-label { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:1.5px; margin-bottom:16px; }
.comp-bad .comp-label { color:var(--red); }
.comp-good .comp-label { color:var(--green); }
.comp-card h3 { font-family:'Fraunces',serif; font-size:22px; margin-bottom:12px; }
.comp-bad h3 { color:var(--red); }
.comp-good h3 { color:var(--green); }
.comp-list { list-style:none; }
.comp-list li { font-size:14px; line-height:1.6; color:var(--text2); padding:6px 0; border-bottom:1px solid var(--border); display:flex; gap:8px; }
.comp-list li:last-child { border-bottom:none; }

/* SOLUTIONS */
.solution-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-top:40px; }
.solution-card { background:white; border-radius:16px; padding:24px; border:1px solid var(--border); text-align:center; }
.solution-emoji { font-size:36px; margin-bottom:12px; }
.solution-card h3 { font-family:'Fraunces',serif; font-size:16px; color:var(--brown); margin-bottom:8px; font-weight:600; }
.solution-card p { font-size:13px; line-height:1.6; color:var(--text2); }

/* PRODUCT */
.product-section { background:var(--brown); padding:80px 24px; }
.product-inner { max-width:900px; margin:0 auto; }
.product-inner .section-title { color:white; }
.product-inner .section-label { color:var(--accent2); }
.product-grid { display:grid; grid-template-columns:1fr 1fr; gap:24px; margin-top:40px; }
.product-card { background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.1); border-radius:24px; padding:32px; }
.product-card.featured { background:var(--accent); border-color:var(--accent); grid-column:span 2; }
.product-img { width:100%; height:200px; background:rgba(255,255,255,0.1); border-radius:16px; display:flex; align-items:center; justify-content:center; font-size:64px; margin-bottom:20px; overflow:hidden; }
.product-img img { width:100%; height:100%; object-fit:contain; padding:16px; }
.product-name { font-family:'Fraunces',serif; font-size:22px; color:white; margin-bottom:8px; font-weight:600; }
.product-desc { font-size:14px; color:rgba(255,255,255,0.65); line-height:1.6; margin-bottom:20px; }
.product-price { font-family:'Fraunces',serif; font-size:32px; color:var(--accent2); margin-bottom:4px; }
.product-card.featured .product-price { color:white; }
.product-price-sub { font-size:13px; color:rgba(255,255,255,0.5); margin-bottom:20px; }
.product-features { list-style:none; margin-bottom:24px; }
.product-features li { font-size:13px; color:rgba(255,255,255,0.7); padding:6px 0; display:flex; gap:8px; border-bottom:1px solid rgba(255,255,255,0.08); }
.product-features li:last-child { border-bottom:none; }
.btn-buy { width:100%; padding:14px; border-radius:12px; border:none; font-family:'DM Sans',sans-serif; font-size:15px; font-weight:600; cursor:pointer; text-decoration:none; display:block; text-align:center; }
.btn-buy-primary { background:white; color:var(--brown); }
.btn-buy-secondary { background:rgba(255,255,255,0.1); color:white; border:1px solid rgba(255,255,255,0.2); }

/* FAQ */
.faq-section { background:var(--warm); padding:80px 24px; }
.faq-inner { max-width:700px; margin:0 auto; }
.faq-list { margin-top:40px; display:flex; flex-direction:column; gap:12px; }
.faq-item { background:white; border-radius:16px; border:1px solid var(--border); overflow:hidden; }
.faq-q { padding:20px 24px; font-size:16px; font-weight:500; color:var(--brown); cursor:pointer; display:flex; justify-content:space-between; align-items:center; }
.faq-icon { font-size:20px; transition:transform 0.2s; color:var(--accent); }
.faq-item.open .faq-icon { transform:rotate(45deg); }
.faq-a { padding:0 24px; max-height:0; overflow:hidden; transition:all 0.3s; font-size:14px; line-height:1.7; color:var(--text2); }
.faq-item.open .faq-a { max-height:300px; padding:0 24px 20px; }

/* CTA */
.cta-section { background:linear-gradient(135deg,var(--accent) 0%,#a0522d 100%); padding:80px 24px; text-align:center; }
.cta-section h2 { font-family:'Fraunces',serif; font-size:clamp(28px,5vw,44px); color:white; margin-bottom:16px; font-weight:600; }
.cta-section p { font-size:17px; color:rgba(255,255,255,0.8); margin-bottom:36px; max-width:500px; margin-left:auto; margin-right:auto; }
.btn-cta { background:white; color:var(--accent); padding:18px 40px; border-radius:100px; font-size:16px; font-weight:600; text-decoration:none; display:inline-block; }

/* FOOTER */
footer { background:var(--brown); padding:40px 24px; text-align:center; }
.footer-logo { font-family:'Fraunces',serif; font-size:22px; color:var(--accent2); margin-bottom:16px; }
footer p { font-size:13px; color:rgba(255,255,255,0.4); line-height:1.8; }

/* ── CHAT WIDGET ── */
.chat-fab { position:fixed; bottom:24px; right:24px; z-index:1000; width:60px; height:60px; border-radius:50%; background:linear-gradient(135deg,var(--accent),#a0522d); border:none; cursor:pointer; font-size:28px; box-shadow:0 8px 32px rgba(196,98,45,0.5); display:flex; align-items:center; justify-content:center; transition:transform 0.2s; }
.chat-fab:hover { transform:scale(1.1); }
.chat-fab.open { background:linear-gradient(135deg,#6b4c3b,var(--brown)); }

.chat-window { position:fixed; bottom:96px; right:24px; z-index:999; width:360px; max-width:calc(100vw - 48px); background:var(--cream); border-radius:20px; box-shadow:0 20px 60px rgba(0,0,0,0.2); border:1px solid var(--border); display:none; flex-direction:column; overflow:hidden; max-height:520px; }
.chat-window.open { display:flex; }

.chat-header { background:var(--brown); padding:16px 20px; display:flex; align-items:center; gap:12px; }
.chat-avatar { width:36px; height:36px; border-radius:50%; background:var(--accent); display:flex; align-items:center; justify-content:center; font-size:18px; }
.chat-header-text h3 { font-family:'Fraunces',serif; font-size:15px; color:white; font-weight:600; }
.chat-header-text p { font-size:11px; color:rgba(255,255,255,0.6); }
.chat-close { margin-left:auto; background:none; border:none; color:rgba(255,255,255,0.6); font-size:20px; cursor:pointer; }

.chat-messages { flex:1; overflow-y:auto; padding:16px; display:flex; flex-direction:column; gap:12px; min-height:200px; }
.msg { max-width:85%; padding:10px 14px; border-radius:16px; font-size:14px; line-height:1.5; }
.msg-ai { background:white; color:var(--text); border-radius:16px 16px 16px 4px; border:1px solid var(--border); align-self:flex-start; }
.msg-user { background:var(--accent); color:white; border-radius:16px 16px 4px 16px; align-self:flex-end; }
.msg-typing { background:white; border:1px solid var(--border); border-radius:16px 16px 16px 4px; align-self:flex-start; padding:12px 16px; }
.typing-dots { display:flex; gap:4px; }
.typing-dots span { width:6px; height:6px; background:var(--text2); border-radius:50%; animation:bounce 1.2s infinite; }
.typing-dots span:nth-child(2){animation-delay:0.2s;}
.typing-dots span:nth-child(3){animation-delay:0.4s;}
@keyframes bounce{0%,60%,100%{transform:translateY(0);}30%{transform:translateY(-6px);}}

.chat-input-row { padding:12px 16px; border-top:1px solid var(--border); display:flex; gap:8px; align-items:center; background:white; }
.chat-input { flex:1; border:1px solid var(--border); border-radius:10px; padding:10px 14px; font-size:14px; font-family:'DM Sans',sans-serif; outline:none; background:var(--cream); }
.chat-input:focus { border-color:var(--accent); }
.chat-send { width:38px; height:38px; border-radius:10px; border:none; background:var(--accent); color:white; font-size:16px; cursor:pointer; flex-shrink:0; display:flex; align-items:center; justify-content:center; }
.chat-mic { width:38px; height:38px; border-radius:10px; border:none; background:var(--warm); color:var(--brown); font-size:16px; cursor:pointer; flex-shrink:0; display:flex; align-items:center; justify-content:center; border:1px solid var(--border); }
.chat-mic.recording { background:var(--red); color:white; animation:pulse 1s infinite; }
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:0.6;}}

.chat-play { width:100%; margin-top:8px; padding:8px; border-radius:8px; border:none; background:linear-gradient(135deg,var(--accent),#a0522d); color:white; font-size:13px; font-weight:600; cursor:pointer; display:none; }

@media(max-width:400px){ .chat-window{right:12px;left:12px;width:auto;} }
@media(max-width:600px){ .comparison{grid-template-columns:1fr;} .product-grid{grid-template-columns:1fr;} .product-card.featured{grid-column:span 1;} }
</style>
</head>
<body>

<nav class="nav">
  <div class="nav-logo">InsuliiniCheck</div>
  <a href="#tilaa" class="nav-cta">Tilaa nyt</a>
</nav>

<div class="hero">
  <div class="hero-badge">🩸 Uusi kotimittauslaite</div>
  <h1>Mittaa insuliinisi <em>ennen</em> kuin on liian myöhäistä</h1>
  <p>Lääkärit mittaavat vain verensokeria. Mutta insuliini kertoo totuuden — jopa 10 vuotta ennen diabetesta. Nyt voit mitata sen kotona.</p>
  <div class="hero-buttons">
    <a href="#tilaa" class="btn-primary">🛒 Tilaa mittauslaite</a>
    <a href="#miksi" class="btn-secondary">Lue lisää</a>
  </div>
  <div class="hero-stats">
    <div><div class="stat-num">1/3</div><div class="stat-label">Suomalaisista</div><div class="stat-sub">insuliiniresistenssiä</div></div>
    <div><div class="stat-num">10v</div><div class="stat-label">Ennen diabetesta</div><div class="stat-sub">kehittyy hiljalleen</div></div>
    <div><div class="stat-num">95%</div><div class="stat-label">Ehkäistävissä</div><div class="stat-sub">oikeilla toimilla</div></div>
  </div>
</div>

<div class="problem-section" id="miksi">
  <div class="problem-inner">
    <div class="section-label">Ongelma</div>
    <h2 class="section-title">Miksi sokerin mittaus <em>ei riitä?</em></h2>
    <p class="section-text">Verensokeri nousee vasta kun haima on jo ylikuormittunut vuosia. Insuliini sen sijaan alkaa nousta jo kauan ennen.</p>
    <div class="warning-box">
      <div class="warning-icon">⚠️</div>
      <div class="warning-text">
        <h4>Tiedätkö tämän?</h4>
        <p>Voit olla täysin "normaali" sokeritesteissä mutta silti kärsitä vakavasta insuliiniresistenssistä vuosia — ja tietämättäsi kehittää tyypin 2 diabetesta.</p>
      </div>
    </div>
    <div class="problem-grid">
      <div class="problem-card"><div class="problem-icon">🍬</div><h3>Insuliiniresistenssi</h3><p>Solut lakkaavat reagoimasta insuliiniin. Haima pumppaa enemmän insuliinia — verensokeri pysyy normaalina, mutta vahinko kasvaa.</p></div>
      <div class="problem-card"><div class="problem-icon">📈</div><h3>Hiljainen kehitys</h3><p>Ei oireita vuosiin. Väsymys, ylipaino ja keskivartalolihavuus voivat olla merkkejä — mutta ne ohitetaan usein.</p></div>
      <div class="problem-card"><div class="problem-icon">🏥</div><h3>Lääkäri ei mittaa</h3><p>Rutiinitesteissä mitataan vain verensokeri ja HbA1c. Insuliinia ei mitata — vaikka se antaisi varhaisen varoituksen.</p></div>
    </div>
  </div>
</div>

<section>
  <div class="section-label">Vertailu</div>
  <h2 class="section-title">Sokeri vs. <em>Insuliini</em></h2>
  <div class="comparison">
    <div class="comp-card comp-bad">
      <div class="comp-label">❌ Pelkkä sokeri</div>
      <h3>Liian myöhään</h3>
      <ul class="comp-list">
        <li>🔴 Nousee vasta kun haima ylikuormittunut</li>
        <li>🔴 Ei kerro insuliiniresistenssistä</li>
        <li>🔴 Näyttää "normaalin" liian kauan</li>
        <li>🔴 Diagnoosi tulee liian myöhään</li>
      </ul>
    </div>
    <div class="comp-card comp-good">
      <div class="comp-label">✅ Insuliinitesti</div>
      <h3>Varhainen varoitus</h3>
      <ul class="comp-list">
        <li>🟢 Paljastaa resistenssin jopa 10v. ennen</li>
        <li>🟢 Näyttää kuinka kovasti haima työskentelee</li>
        <li>🟢 Mahdollistaa ajoissa puuttumisen</li>
        <li>🟢 Nyt mitattavissa kotona</li>
      </ul>
    </div>
  </div>
</section>

<div style="background:var(--warm);padding:80px 24px;">
  <section style="padding:0">
    <div class="section-label">Ratkaisu</div>
    <h2 class="section-title">Miten <em>korjata</em> insuliiniresistenssi?</h2>
    <div class="solution-grid">
      <div class="solution-card"><div class="solution-emoji">🥗</div><h3>Ruokavalio</h3><p>Vähemmän nopeita hiilihydraatteja, enemmän proteiinia ja hyviä rasvoja.</p></div>
      <div class="solution-card"><div class="solution-emoji">🏃</div><h3>Liikunta</h3><p>Jo 30 min/päivä parantaa insuliiniherkkyyttä merkittävästi.</p></div>
      <div class="solution-card"><div class="solution-emoji">😴</div><h3>Uni ja stressi</h3><p>Univaje ja stressi heikentävät insuliiniherkkyyttä suoraan.</p></div>
      <div class="solution-card"><div class="solution-emoji">💊</div><h3>Lääkitys</h3><p>Tarvittaessa lääkäri voi määrätä esim. metformiinin.</p></div>
      <div class="solution-card"><div class="solution-emoji">⚖️</div><h3>Painonhallinta</h3><p>Jo 5–10% painonlasku parantaa insuliiniherkkyyttä huomattavasti.</p></div>
      <div class="solution-card"><div class="solution-emoji">📊</div><h3>Seuranta</h3><p>Mittaa insuliinisi säännöllisesti ja seuraa edistymistä.</p></div>
    </div>
  </section>
</div>

<div class="product-section" id="tilaa">
  <div class="product-inner">
    <div class="section-label">Tuotteet</div>
    <h2 class="section-title">Tilaa InsuliiniCheck</h2>
    <div class="product-grid">
      <div class="product-card featured">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:center;">
          <div class="product-img" id="deviceImage">📱</div>
          <div>
            <div style="font-size:11px;color:rgba(255,255,255,0.6);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;">⭐ Suosituimmat</div>
            <div class="product-name">InsuliiniCheck Laite</div>
            <div class="product-desc">Ammattitason insuliinimittaus kotona.</div>
            <div class="product-price">399 €</div>
            <div class="product-price-sub">Sisältää 5 testiä • Kerta-investointi</div>
            <ul class="product-features">
              <li>✓ Laboratoriotasoinen tarkkuus</li>
              <li>✓ Tulos 15 minuutissa</li>
              <li>✓ Helppo käyttää kotona</li>
              <li>✓ Ei tarvita lähetteitä</li>
            </ul>
            <a href="mailto:penttivet@gmail.com?subject=Tilaus: InsuliiniCheck Laite 399€&body=Hei,%0A%0AHaluaisin tilata InsuliiniCheck-laitteen (399€).%0A%0ANimeni:%0ASähköpostini:%0APuhelinnumeroni:%0AOsoitteeni:%0A%0ATerveisin," class="btn-buy btn-buy-primary">🛒 Tilaa laite — 399 €</a>
          </div>
        </div>
      </div>
      <div class="product-card">
        <div class="product-img">🧪</div>
        <div class="product-name">Insuliinitesti</div>
        <div class="product-desc">Yksittäinen insuliinitesti laitteellesi.</div>
        <div class="product-price">15 €</div>
        <div class="product-price-sub">per testi • min. 5 kpl</div>
        <ul class="product-features"><li>✓ Nopea ja helppo</li><li>✓ Pienestä verinäytteestä</li><li>✓ Tulkintaohje mukana</li></ul>
        <a href="mailto:penttivet@gmail.com?subject=Tilaus: Insuliinitestit 15€/kpl&body=Hei,%0A%0AHaluaisin tilata insuliinitestejä.%0A%0AKappalemäärä:%0ANimeni:%0ASähköpostini:%0A%0ATerveisin," class="btn-buy btn-buy-secondary">Tilaa testejä</a>
      </div>
      <div class="product-card">
        <div class="product-img">📦</div>
        <div class="product-name">Vuosipaketti</div>
        <div class="product-desc">Laite + 12 testiä. Mittaa kerran kuukaudessa.</div>
        <div class="product-price">549 €</div>
        <div class="product-price-sub">Säästät 30 € • Suositellaan</div>
        <ul class="product-features"><li>✓ Laite + 12 testiä</li><li>✓ Seurantaohjelma</li><li>✓ Asiantuntijatuki</li></ul>
        <a href="mailto:penttivet@gmail.com?subject=Tilaus: Vuosipaketti 549€&body=Hei,%0A%0AHaluaisin tilata Vuosipaketin.%0A%0ANimeni:%0ASähköpostini:%0A%0ATerveisin," class="btn-buy btn-buy-secondary">Tilaa vuosipaketti</a>
      </div>
    </div>
  </div>
</div>

<div class="faq-section">
  <div class="faq-inner">
    <div class="section-label">UKK</div>
    <h2 class="section-title">Usein kysytyt <em>kysymykset</em></h2>
    <div class="faq-list">
      <div class="faq-item"><div class="faq-q" onclick="toggleFaq(this)">Kenelle insuliinitesti sopii?<span class="faq-icon">+</span></div><div class="faq-a">Kaikille aikuisille, erityisesti jos sinulla on ylipaino, väsymystä, makeanhimo tai diabetesta suvussa.</div></div>
      <div class="faq-item"><div class="faq-q" onclick="toggleFaq(this)">Tarvitseeko lääkärin lähetteen?<span class="faq-icon">+</span></div><div class="faq-a">Ei tarvita. Voit tilata laitteen suoraan meiltä ja testata kotona.</div></div>
      <div class="faq-item"><div class="faq-q" onclick="toggleFaq(this)">Mitä normaalit insuliiniarvot ovat?<span class="faq-icon">+</span></div><div class="faq-a">Paastoinsuliini alle 10 mIU/L on hyvä. 10–25 viittaa alkavaan resistenssiin. Yli 25 mIU/L on selkeä merkki insuliiniresistenssistä.</div></div>
      <div class="faq-item"><div class="faq-q" onclick="toggleFaq(this)">Kuinka usein pitäisi mitata?<span class="faq-icon">+</span></div><div class="faq-a">Aloitustilanteen kartoitukseen kerran. Elämäntapamuutosten seurannassa 1–3 kuukauden välein.</div></div>
    </div>
  </div>
</div>

<div class="cta-section">
  <h2>Ota terveytesi haltuun tänään</h2>
  <p>Älä odota lääkärin diagnoosta. Mittaa insuliinisi kotona.</p>
  <a href="#tilaa" class="btn-cta">🛒 Tilaa InsuliiniCheck</a>
</div>

<footer>
  <div class="footer-logo">InsuliiniCheck</div>
  <p>penttivet@gmail.com<br>© 2026 InsuliiniCheck.fi<br><small>Tämä sivusto ei korvaa lääkärin neuvontaa.</small></p>
</footer>

<!-- CHAT FAB -->
<button class="chat-fab" id="chatFab" onclick="toggleChat()">💬</button>

<!-- CHAT WINDOW -->
<div class="chat-window" id="chatWindow">
  <div class="chat-header">
    <div class="chat-avatar">🩺</div>
    <div class="chat-header-text">
      <h3>InsuliiniCheck Asiantuntija</h3>
      <p>Kysy mitä tahansa insuliinista</p>
    </div>
    <button class="chat-close" onclick="toggleChat()">✕</button>
  </div>
  <div class="chat-messages" id="chatMessages">
    <div class="msg msg-ai">Hei! 👋 Olen InsuliiniCheckin terveysasiantuntija. Voit kysyä minulta mitä tahansa insuliiniresistenssistä, diabeteksen ehkäisystä tai terveellisistä elämäntavoista. Voit myös puhua mikrofoniin! 🎙️</div>
  </div>
  <div class="chat-input-row">
    <input class="chat-input" id="chatInput" placeholder="Kirjoita kysymys..." onkeydown="if(event.key==='Enter')sendMessage()">
    <button class="chat-mic" id="micBtn" onclick="toggleVoice()" title="Puhu mikrofoniin">🎙️</button>
    <button class="chat-send" onclick="sendMessage()">➤</button>
  </div>
  <button class="chat-play" id="chatPlayBtn" onclick="playResponse()">🔊 Kuuntele vastaus</button>
</div>

<script>
let chatOpen = false;
let chatHistory = [];
let mediaRecorder = null, audioChunks = [], isRecording = false;
let lastAudioUrl = null;

function toggleChat() {
  chatOpen = !chatOpen;
  document.getElementById('chatWindow').classList.toggle('open', chatOpen);
  document.getElementById('chatFab').classList.toggle('open', chatOpen);
  document.getElementById('chatFab').textContent = chatOpen ? '✕' : '💬';
}

function toggleFaq(el) {
  el.parentElement.classList.toggle('open');
}

function addMessage(role, text) {
  const msgs = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'msg ' + (role === 'user' ? 'msg-user' : 'msg-ai');
  div.textContent = text;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function showTyping() {
  const msgs = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'msg-typing';
  div.id = 'typingIndicator';
  div.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById('typingIndicator');
  if (el) el.remove();
}

async function sendMessage() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  addMessage('user', text);
  chatHistory.push({role:'user', content:text});
  showTyping();
  document.getElementById('chatPlayBtn').style.display = 'none';
  try {
    const resp = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text, history: chatHistory})
    });
    const data = await resp.json();
    hideTyping();
    addMessage('ai', data.reply);
    chatHistory.push({role:'assistant', content:data.reply});
    if (data.audio_url) {
      lastAudioUrl = data.audio_url;
      document.getElementById('chatPlayBtn').style.display = 'block';
    }
    chatHistory = chatHistory.slice(-20);
  } catch(e) {
    hideTyping();
    addMessage('ai', 'Pahoittelen, tekninen ongelma. Yritä uudelleen.');
  }
}

async function toggleVoice() {
  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio:true});
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstop = () => processVoice(new Blob(audioChunks, {type:'audio/webm'}));
      mediaRecorder.start();
      isRecording = true;
      document.getElementById('micBtn').classList.add('recording');
      document.getElementById('micBtn').textContent = '⏹️';
    } catch(e) { alert('Mikrofoni ei ole käytettävissä.'); }
  } else {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
    isRecording = false;
    document.getElementById('micBtn').classList.remove('recording');
    document.getElementById('micBtn').textContent = '🎙️';
  }
}

async function processVoice(blob) {
  addMessage('user', '🎙️ ...');
  showTyping();
  document.getElementById('chatPlayBtn').style.display = 'none';
  const formData = new FormData();
  formData.append('audio', blob, 'speech.webm');
  formData.append('history', JSON.stringify(chatHistory));
  try {
    const resp = await fetch('/voice-chat', {method:'POST', body:formData});
    const data = await resp.json();
    hideTyping();
    const msgs = document.getElementById('chatMessages');
    const last = msgs.querySelectorAll('.msg-user');
    if (last.length) last[last.length-1].textContent = data.transcript || '🎙️';
    addMessage('ai', data.reply);
    chatHistory.push({role:'user', content:data.transcript});
    chatHistory.push({role:'assistant', content:data.reply});
    if (data.audio_url) {
      lastAudioUrl = data.audio_url;
      document.getElementById('chatPlayBtn').style.display = 'block';
    }
    chatHistory = chatHistory.slice(-20);
  } catch(e) {
    hideTyping();
    addMessage('ai', 'Pahoittelen, tekninen ongelma.');
  }
}

function playResponse() {
  if (!lastAudioUrl) return;
  const audio = new Audio(lastAudioUrl);
  audio.play();
}
</script>

</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

def strip_markdown(text):
    import re
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"^[-•]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def clean_for_speech(text):
    """Remove punctuation and symbols that ElevenLabs reads aloud"""
    import re
    # Replace common punctuation with spaces or nothing
    text = text.replace("—", " ")
    text = text.replace("–", " ")
    text = text.replace("•", " ")
    text = text.replace("€", " euroa")
    text = re.sub(r'[;:,]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    message = data.get("message", "")
    history = data.get("history", [])

    history_for_api = history[-10:]

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "system": SYSTEM_PROMPT,
                "messages": history_for_api + [{"role": "user", "content": message}]
            },
            timeout=15
        )
        reply = strip_markdown(resp.json()["content"][0]["text"].strip())
    except Exception as e:
        log.error(f"Claude error: {e}")
        reply = "Pahoittelen, tekninen ongelma. Yritä uudelleen."

    audio_url = None
    if ELEVENLABS_API_KEY:
        try:
            tts = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
                headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
                json={"text": clean_for_speech(reply), "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": 0.95}},
                timeout=15
            )
            if tts.ok:
                b64 = base64.b64encode(tts.content).decode()
                from flask import session
                import secrets
                key = f"ic:audio:{secrets.token_hex(8)}"
                # Store in simple dict for now
                app.config.setdefault('AUDIO_CACHE', {})[key] = b64
                audio_url = f"/audio/{key.split(':')[-1]}"
                log.info("TTS success")
        except Exception as e:
            log.error(f"TTS error: {e}")

    return jsonify({"reply": reply, "audio_url": audio_url})

@app.route("/voice-chat", methods=["POST"])
def voice_chat():
    if "audio" not in request.files:
        return jsonify({"error": "No audio"}), 400

    audio_file = request.files["audio"]
    history = json.loads(request.form.get("history", "[]"))

    # Transcribe
    try:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": ("speech.webm", audio_file.read(), "audio/webm")},
            data={"model": "whisper-1"},
            timeout=60
        )
        transcript = resp.json().get("text", "").strip()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Get AI reply
    history_for_api = history[-10:]
    try:
        resp2 = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "system": SYSTEM_PROMPT,
                "messages": history_for_api + [{"role": "user", "content": transcript}]
            },
            timeout=15
        )
        reply = strip_markdown(resp2.json()["content"][0]["text"].strip())
    except Exception as e:
        reply = "Pahoittelen, tekninen ongelma."

    # TTS
    audio_url = None
    if ELEVENLABS_API_KEY:
        try:
            tts = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
                headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
                json={"text": clean_for_speech(reply), "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": 0.95}},
                timeout=15
            )
            if tts.ok:
                import secrets
                b64 = base64.b64encode(tts.content).decode()
                key = secrets.token_hex(8)
                app.config.setdefault('AUDIO_CACHE', {})[key] = b64
                audio_url = f"/audio/{key}"
        except Exception as e:
            log.error(f"TTS error: {e}")

    return jsonify({"transcript": transcript, "reply": reply, "audio_url": audio_url})

@app.route("/audio/<key>")
def serve_audio(key):
    cache = app.config.get('AUDIO_CACHE', {})
    b64 = cache.get(key)
    if not b64:
        return "", 404
    audio_data = base64.b64decode(b64)
    return Response(audio_data, mimetype="audio/mpeg")

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
