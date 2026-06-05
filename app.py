import os
import io
import json
import logging
import secrets
import hashlib
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_file, render_template_string, session, redirect, Response
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY     = os.environ.get("OPENAI_API_KEY", "")
UPSTASH_URL        = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN      = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel - selkeä englanti
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "speakup2026")

REDIS_HEADERS = {
    "Authorization": f"Bearer {UPSTASH_TOKEN}",
    "Content-Type": "application/json"
}

# ── Redis ────────────────────────────────────────────────────────────────
def redis_get(key):
    try:
        r = requests.post(UPSTASH_URL, headers=REDIS_HEADERS, json=["GET", key], timeout=5)
        data = r.json()
        return json.loads(data["result"]) if data.get("result") else None
    except Exception as e:
        log.error(f"Redis get error: {e}")
        return None

def redis_set(key, value, ttl=None):
    try:
        cmd = ["SET", key, json.dumps(value)]
        if ttl:
            cmd += ["EX", ttl]
        requests.post(UPSTASH_URL, headers=REDIS_HEADERS, json=cmd, timeout=5)
    except Exception as e:
        log.error(f"Redis set error: {e}")

def redis_keys(pattern):
    try:
        r = requests.post(UPSTASH_URL, headers=REDIS_HEADERS, json=["KEYS", pattern], timeout=5)
        return r.json().get("result", [])
    except:
        return []

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_email" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated

# ── Scenarios ────────────────────────────────────────────────────────────
SCENARIOS = [
    {"id": "restaurant", "emoji": "🍽️", "title": "At a Restaurant", "desc": "Order food, ask about the menu, make requests"},
    {"id": "airport", "emoji": "✈️", "title": "At the Airport", "desc": "Check-in, security, boarding gates"},
    {"id": "job_interview", "emoji": "💼", "title": "Job Interview", "desc": "Answer questions about your experience and skills"},
    {"id": "shopping", "emoji": "🛍️", "title": "Shopping", "desc": "Ask about products, prices, sizes"},
    {"id": "doctor", "emoji": "🏥", "title": "At the Doctor", "desc": "Describe symptoms, understand advice"},
    {"id": "hotel", "emoji": "🏨", "title": "Hotel Check-in", "desc": "Book a room, ask about facilities"},
    {"id": "directions", "emoji": "🗺️", "title": "Asking Directions", "desc": "Find your way around a new city"},
    {"id": "free", "emoji": "💬", "title": "Free Conversation", "desc": "Talk about anything you like"},
]

SCENARIO_PROMPTS = {
    "restaurant": "You are a friendly restaurant waiter in an English-speaking country. The customer may have limited English. Be patient, speak clearly, and help them order food. Keep responses short (1-3 sentences).",
    "airport": "You are a helpful airport staff member. The traveler may have limited English. Help them with check-in, directions, and boarding. Keep responses short (1-3 sentences).",
    "job_interview": "You are a friendly HR interviewer. The candidate may have limited English. Ask simple interview questions and encourage them. Keep responses short (1-3 sentences).",
    "shopping": "You are a helpful shop assistant. The customer may have limited English. Help them find products and answer questions about prices and sizes. Keep responses short (1-3 sentences).",
    "doctor": "You are a patient and clear doctor. The patient may have limited English. Ask about their symptoms and explain advice simply. Keep responses short (1-3 sentences).",
    "hotel": "You are a friendly hotel receptionist. The guest may have limited English. Help them check in and answer questions about the hotel. Keep responses short (1-3 sentences).",
    "directions": "You are a friendly local helping a tourist. The tourist may have limited English. Give clear, simple directions. Keep responses short (1-3 sentences).",
    "free": "You are a friendly English conversation partner. The user may have limited English. Have a natural conversation on any topic they choose. Keep responses short (1-3 sentences).",
}

FEEDBACK_PROMPT = """You are an English language coach for adult learners. 
The student just said: "{speech}"

Their target scenario: {scenario}

Analyze their English and provide feedback in this exact JSON format:
{{
  "corrected": "The corrected version of what they said (if needed, otherwise same)",
  "feedback": "One short, encouraging sentence about their English (max 15 words)",
  "errors": ["error1 if any", "error2 if any"],
  "score": 85
}}

Score 0-100 based on grammar, vocabulary and clarity.
If their English was good, say so! Be encouraging.
Respond ONLY with the JSON object."""

# ── HTML ─────────────────────────────────────────────────────────────────
MAIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>SpeakUp — English Coach</title>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#0a0a0f">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
  :root {
    --bg: #0a0a0f;
    --surface: #13131a;
    --surface2: #1c1c28;
    --accent: #00e5a0;
    --accent2: #00b8ff;
    --warn: #ff6b35;
    --text: #f0f0f8;
    --text2: #7070a0;
    --border: rgba(255,255,255,0.06);
    --glow: rgba(0,229,160,0.15);
  }
  * { margin:0; padding:0; box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  body { font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; display:flex; flex-direction:column; align-items:center; }
  .header { width:100%; padding:18px 20px; display:flex; align-items:center; gap:12px; border-bottom:1px solid var(--border); background:rgba(10,10,15,0.9); backdrop-filter:blur(12px); position:sticky; top:0; z-index:100; }
  .logo { font-family:'Syne',sans-serif; font-weight:800; font-size:20px; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
  .tagline { font-size:12px; color:var(--text2); }
  .nav-link { margin-left:auto; font-size:13px; color:var(--text2); text-decoration:none; padding:6px 12px; border-radius:8px; border:1px solid var(--border); }
  .container { width:100%; max-width:500px; padding:20px 16px; flex:1; display:flex; flex-direction:column; gap:16px; }
  .section-title { font-family:'Syne',sans-serif; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:2px; color:var(--text2); margin-bottom:12px; }
  .scenarios { display:grid; grid-template-columns:repeat(2,1fr); gap:10px; }
  .scenario-card { background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:14px; cursor:pointer; transition:all 0.2s; display:flex; flex-direction:column; gap:6px; }
  .scenario-card:active { transform:scale(0.97); }
  .scenario-card.selected { border-color:var(--accent); background:rgba(0,229,160,0.08); box-shadow:0 0 20px var(--glow); }
  .scenario-emoji { font-size:24px; }
  .scenario-title { font-family:'Syne',sans-serif; font-size:13px; font-weight:600; }
  .scenario-desc { font-size:11px; color:var(--text2); line-height:1.4; }
  .record-card { background:var(--surface); border:1px solid var(--border); border-radius:20px; padding:24px; display:flex; flex-direction:column; align-items:center; gap:16px; }
  .record-btn { width:96px; height:96px; border-radius:50%; border:none; cursor:pointer; display:flex; align-items:center; justify-content:center; font-size:36px; transition:all 0.2s; background:linear-gradient(135deg,var(--accent),var(--accent2)); box-shadow:0 8px 32px rgba(0,229,160,0.3); }
  .record-btn.recording { background:linear-gradient(135deg,var(--warn),#ff3366); box-shadow:0 8px 32px rgba(255,107,53,0.4); animation:pulse 1.5s infinite; }
  .record-btn:disabled { opacity:0.4; cursor:not-allowed; }
  @keyframes pulse { 0%,100%{transform:scale(1);}50%{transform:scale(1.05);} }
  .record-hint { font-size:13px; color:var(--text2); text-align:center; }
  .timer { font-family:'Syne',sans-serif; font-size:32px; font-weight:700; color:var(--accent); display:none; }
  .timer.visible { display:block; }
  .wave { display:none; gap:4px; align-items:flex-end; height:28px; }
  .wave.visible { display:flex; }
  .wave span { width:4px; background:var(--warn); border-radius:2px; animation:wave 0.7s ease-in-out infinite; }
  .wave span:nth-child(2){animation-delay:0.1s;height:14px;}
  .wave span:nth-child(3){animation-delay:0.2s;height:20px;}
  .wave span:nth-child(4){animation-delay:0.3s;height:10px;}
  .wave span:nth-child(5){animation-delay:0.4s;height:18px;}
  @keyframes wave{0%,100%{transform:scaleY(0.4);}50%{transform:scaleY(1);}}

  /* Speaking animation */
  .speaking-indicator { display:none; align-items:center; gap:8px; font-size:13px; color:var(--accent2); }
  .speaking-indicator.visible { display:flex; }
  .speak-wave { display:flex; gap:3px; align-items:flex-end; height:20px; }
  .speak-wave span { width:3px; background:var(--accent2); border-radius:2px; animation:wave 0.6s ease-in-out infinite; }
  .speak-wave span:nth-child(2){animation-delay:0.1s;}
  .speak-wave span:nth-child(3){animation-delay:0.2s;}

  .ai-bubble { background:var(--surface2); border-radius:16px; padding:16px; font-size:14px; line-height:1.6; border-left:3px solid var(--accent2); display:none; }
  .ai-bubble.visible { display:block; }
  .ai-label { font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:1.5px; color:var(--accent2); margin-bottom:8px; display:flex; align-items:center; justify-content:space-between; }
  .replay-btn { background:rgba(0,184,255,0.1); border:1px solid rgba(0,184,255,0.2); color:var(--accent2); padding:4px 10px; border-radius:20px; font-size:11px; cursor:pointer; font-family:'DM Sans',sans-serif; }
  .replay-btn:hover { background:rgba(0,184,255,0.2); }

  .feedback-card { background:var(--surface); border:1px solid var(--border); border-radius:16px; padding:16px; display:none; flex-direction:column; gap:12px; }
  .feedback-card.visible { display:flex; }
  .score-row { display:flex; align-items:center; gap:12px; }
  .score-circle { width:56px; height:56px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-family:'Syne',sans-serif; font-weight:800; font-size:16px; flex-shrink:0; }
  .score-high { background:rgba(0,229,160,0.15); color:var(--accent); border:2px solid var(--accent); }
  .score-mid { background:rgba(0,184,255,0.15); color:var(--accent2); border:2px solid var(--accent2); }
  .score-low { background:rgba(255,107,53,0.15); color:var(--warn); border:2px solid var(--warn); }
  .feedback-text { font-size:14px; line-height:1.5; }
  .corrected-box { background:rgba(0,229,160,0.08); border-radius:10px; padding:12px; font-size:13px; border:1px solid rgba(0,229,160,0.2); }
  .corrected-label { font-size:10px; color:var(--accent); font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:6px; }
  .errors-list { display:flex; flex-direction:column; gap:6px; }
  .error-item { background:rgba(255,107,53,0.08); border-radius:8px; padding:8px 12px; font-size:12px; color:var(--warn); border:1px solid rgba(255,107,53,0.2); }
  .chat-history { display:flex; flex-direction:column; gap:10px; }
  .msg-user { background:linear-gradient(135deg,rgba(0,229,160,0.12),rgba(0,184,255,0.08)); border-radius:14px 14px 4px 14px; padding:12px 14px; font-size:14px; align-self:flex-end; max-width:85%; border:1px solid rgba(0,229,160,0.2); }
  .msg-ai { background:var(--surface2); border-radius:14px 14px 14px 4px; padding:12px 14px; font-size:14px; align-self:flex-start; max-width:85%; }
  .msg-label { font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:4px; }
  .msg-label.you { color:var(--accent); }
  .msg-label.ai { color:var(--accent2); }
  .error-msg { background:rgba(255,107,53,0.1); border:1px solid rgba(255,107,53,0.3); border-radius:10px; padding:12px; font-size:13px; color:var(--warn); display:none; }
  .error-msg.visible { display:block; }
  .btn { width:100%; padding:14px; border-radius:12px; border:none; font-family:'Syne',sans-serif; font-size:14px; font-weight:700; cursor:pointer; transition:all 0.2s; letter-spacing:0.5px; }
  .btn-primary { background:linear-gradient(135deg,var(--accent),var(--accent2)); color:#0a0a0f; }
  .btn-secondary { background:var(--surface2); color:var(--text); border:1px solid var(--border); }
  .btn:disabled { opacity:0.4; cursor:not-allowed; }
  .processing { display:none; flex-direction:column; gap:8px; }
  .processing.visible { display:flex; }
  .proc-step { display:flex; align-items:center; gap:10px; font-size:13px; color:var(--text2); padding:8px 0; }
  .proc-step.active { color:var(--text); }
  .proc-step.done { color:var(--accent); }
  .spinner { width:16px; height:16px; border:2px solid rgba(255,255,255,0.1); border-top-color:var(--accent); border-radius:50%; animation:spin 0.8s linear infinite; flex-shrink:0; }
  @keyframes spin { to{transform:rotate(360deg);} }
  @keyframes glow { 0%,100%{box-shadow:0 4px 20px rgba(0,184,255,0.4);}50%{box-shadow:0 4px 32px rgba(0,229,160,0.7);} }
</style>
</head>
<body>
<div class="header">
  <div>
    <div class="logo">SpeakUp</div>
    <div class="tagline">English Coach</div>
  </div>
  <a href="/logout" class="nav-link">Sign out</a>
</div>

<div class="container">
  <div id="scenarioSection">
    <div class="section-title">Choose a scenario</div>
    <div class="scenarios" id="scenarioGrid"></div>
  </div>

  <div class="record-card">
    <div class="timer" id="timer">00:00</div>
    <button class="record-btn" id="recordBtn" onclick="toggleRecording()" disabled>🎙️</button>
    <div class="wave" id="wave"><span></span><span></span><span></span><span></span><span></span></div>
    <div class="record-hint" id="recordHint">Select a scenario to start</div>
  </div>

  <div class="error-msg" id="errorMsg"></div>

  <div class="processing" id="processing">
    <div class="proc-step" id="proc1"><div class="spinner"></div><span>Listening to your speech...</span></div>
    <div class="proc-step" id="proc2"><div class="spinner" style="opacity:0.3"></div><span>AI is responding...</span></div>
    <div class="proc-step" id="proc3"><div class="spinner" style="opacity:0.3"></div><span>Analyzing your English...</span></div>
    <div class="proc-step" id="proc4"><div class="spinner" style="opacity:0.3"></div><span>Preparing voice response...</span></div>
  </div>

  <div class="ai-bubble" id="aiBubble">
    <div class="ai-label">🤖 Coach says</div>
    <div id="aiText"></div>
    <button id="playBtn" onclick="replayAudio()" style="display:none;width:100%;margin-top:14px;padding:16px;border-radius:12px;border:none;background:linear-gradient(135deg,#00b8ff,#00e5a0);color:#0a0a0f;font-size:16px;font-weight:700;cursor:pointer;letter-spacing:0.5px;animation:glow 1.5s ease-in-out infinite;">
      🔊 Tap to hear Coach speak
    </button>
    <div class="speaking-indicator" id="speakingIndicator" style="margin-top:8px;">
      <div class="speak-wave"><span></span><span></span><span></span></div>
      <span>Speaking...</span>
    </div>
  </div>

  <div class="feedback-card" id="feedbackCard">
    <div class="section-title">Your English feedback</div>
    <div class="score-row">
      <div class="score-circle" id="scoreCircle">--</div>
      <div class="feedback-text" id="feedbackText"></div>
    </div>
    <div class="corrected-box" id="correctedBox" style="display:none">
      <div class="corrected-label">✨ Better way to say it</div>
      <div id="correctedText"></div>
    </div>
    <div class="errors-list" id="errorsList"></div>
  </div>

  <div class="chat-history" id="chatHistory"></div>

  <button class="btn btn-secondary" id="nextBtn" onclick="nextTurn()" style="display:none">🎙️ Speak again</button>
  <button class="btn btn-secondary" onclick="resetAll()" style="margin-top:4px;display:none" id="resetBtn">🔄 New scenario</button>
</div>

<script>
let mediaRecorder=null, audioChunks=[], isRecording=false;
let timerInterval=null, seconds=0;
let selectedScenario=null, conversationHistory=[], audioBlob=null;
let currentAudio=null, lastAudioUrl=null;

const scenarios = {{ scenarios|tojson }};

const grid = document.getElementById('scenarioGrid');
scenarios.forEach(s => {
  const card = document.createElement('div');
  card.className = 'scenario-card';
  card.innerHTML = `<div class="scenario-emoji">${s.emoji}</div><div class="scenario-title">${s.title}</div><div class="scenario-desc">${s.desc}</div>`;
  card.onclick = () => selectScenario(s, card);
  grid.appendChild(card);
});

function selectScenario(s, card) {
  selectedScenario = s;
  document.querySelectorAll('.scenario-card').forEach(c => c.classList.remove('selected'));
  card.classList.add('selected');
  document.getElementById('recordBtn').disabled = false;
  document.getElementById('recordHint').textContent = `Tap to speak — ${s.title}`;
  conversationHistory = [];
  document.getElementById('chatHistory').innerHTML = '';
  document.getElementById('aiBubble').classList.remove('visible');
  document.getElementById('feedbackCard').classList.remove('visible');
  document.getElementById('nextBtn').style.display = 'none';
  document.getElementById('resetBtn').style.display = 'none';
}

function updateTimer() {
  seconds++;
  const m = String(Math.floor(seconds/60)).padStart(2,'0');
  const s = String(seconds%60).padStart(2,'0');
  document.getElementById('timer').textContent = m+':'+s;
}

async function toggleRecording() {
  if (!selectedScenario) return;
  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio:true});
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstop = () => { audioBlob = new Blob(audioChunks, {type:'audio/webm'}); processAudio(); };
      mediaRecorder.start();
      isRecording = true; seconds = 0;
      timerInterval = setInterval(updateTimer, 1000);
      document.getElementById('recordBtn').classList.add('recording');
      document.getElementById('recordBtn').textContent = '⏹️';
      document.getElementById('recordHint').textContent = 'Recording... tap to stop';
      document.getElementById('timer').classList.add('visible');
      document.getElementById('wave').classList.add('visible');
      hideError();
    } catch(e) { showError('Microphone not available. Please check permissions.'); }
  } else {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
    isRecording = false;
    clearInterval(timerInterval);
    document.getElementById('recordBtn').classList.remove('recording');
    document.getElementById('recordBtn').textContent = '🎙️';
    document.getElementById('recordBtn').disabled = true;
    document.getElementById('recordHint').textContent = 'Processing...';
    document.getElementById('timer').classList.remove('visible');
    document.getElementById('wave').classList.remove('visible');
  }
}

async function processAudio() {
  if (!audioBlob) return;
  document.getElementById('processing').classList.add('visible');
  document.getElementById('aiBubble').classList.remove('visible');
  document.getElementById('feedbackCard').classList.remove('visible');
  document.getElementById('nextBtn').style.display = 'none';

  setProc(1, 'active');

  const formData = new FormData();
  formData.append('audio', audioBlob, 'speech.webm');
  formData.append('scenario_id', selectedScenario.id);
  formData.append('history', JSON.stringify(conversationHistory));

  try {
    const resp = await fetch('/speak', {method:'POST', body:formData});
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Error');

    setProc(1, 'done');
    setProc(2, 'active');

    document.getElementById('aiText').textContent = data.ai_response;
    document.getElementById('aiBubble').classList.add('visible');
    setProc(2, 'done');
    setProc(3, 'active');

    const fb = data.feedback;
    const score = fb.score || 0;
    const circle = document.getElementById('scoreCircle');
    circle.textContent = score;
    circle.className = 'score-circle ' + (score >= 80 ? 'score-high' : score >= 60 ? 'score-mid' : 'score-low');
    document.getElementById('feedbackText').textContent = fb.feedback || '';

    if (fb.corrected && fb.corrected !== data.transcript) {
      document.getElementById('correctedText').textContent = fb.corrected;
      document.getElementById('correctedBox').style.display = 'block';
    } else {
      document.getElementById('correctedBox').style.display = 'none';
    }

    const errorsList = document.getElementById('errorsList');
    errorsList.innerHTML = '';
    if (fb.errors && fb.errors.length > 0) {
      fb.errors.forEach(e => {
        const div = document.createElement('div');
        div.className = 'error-item';
        div.textContent = '⚠️ ' + e;
        errorsList.appendChild(div);
      });
    }

    document.getElementById('feedbackCard').classList.add('visible');
    setProc(3, 'done');

    // Play voice if available
    if (data.audio_url) {
      setProc(4, 'active');
      lastAudioUrl = data.audio_url;
      await playAudio(data.audio_url);
      setProc(4, 'done');
      const pb = document.getElementById('playBtn');
      pb.style.display = 'block';
      setTimeout(() => pb.scrollIntoView({behavior:'smooth', block:'center'}), 100);
    } else {
      document.getElementById('proc4').style.display = 'none';
    }

    addChatMessage('you', data.transcript);
    addChatMessage('ai', data.ai_response);
    conversationHistory = data.updated_history;

    setTimeout(() => {
      document.getElementById('processing').classList.remove('visible');
      document.getElementById('nextBtn').style.display = 'block';
      document.getElementById('resetBtn').style.display = 'block';
    }, 500);

  } catch(e) {
    document.getElementById('processing').classList.remove('visible');
    document.getElementById('recordBtn').disabled = false;
    document.getElementById('recordHint').textContent = 'Tap to speak';
    showError(e.message);
  }
}

async function playAudio(url) {
  return new Promise((resolve) => {
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    const audio = new Audio(url);
    currentAudio = audio;
    document.getElementById('speakingIndicator').classList.add('visible');
    audio.onended = () => {
      document.getElementById('speakingIndicator').classList.remove('visible');
      currentAudio = null;
      resolve();
    };
    audio.onerror = () => {
      document.getElementById('speakingIndicator').classList.remove('visible');
      resolve();
    };
    audio.play().catch(resolve);
  });
}

function replayAudio() {
  if (lastAudioUrl) playAudio(lastAudioUrl);
}

function setProc(num, status) {
  const el = document.getElementById('proc'+num);
  if (!el) return;
  el.classList.remove('active','done');
  const spinner = el.querySelector('.spinner');
  if (status === 'active') {
    el.classList.add('active');
    if (spinner) spinner.style.opacity = '1';
  } else if (status === 'done') {
    el.classList.add('done');
    if (spinner) spinner.style.display = 'none';
    el.innerHTML = '✅ ' + el.textContent.trim();
  }
}

function addChatMessage(role, text) {
  const history = document.getElementById('chatHistory');
  const div = document.createElement('div');
  div.className = role === 'you' ? 'msg-user' : 'msg-ai';
  div.innerHTML = `<div class="msg-label ${role}">${role === 'you' ? '🎙️ You' : '🤖 Coach'}</div>${text}`;
  history.appendChild(div);
  div.scrollIntoView({behavior:'smooth'});
}

function nextTurn() {
  document.getElementById('recordBtn').disabled = false;
  document.getElementById('recordBtn').textContent = '🎙️';
  document.getElementById('recordHint').textContent = 'Tap to speak again';
  document.getElementById('nextBtn').style.display = 'none';
  document.getElementById('aiBubble').classList.remove('visible');
  document.getElementById('feedbackCard').classList.remove('visible');
  document.getElementById('playBtn').style.display = 'none';
}

function resetAll() {
  selectedScenario = null;
  conversationHistory = [];
  lastAudioUrl = null;
  document.querySelectorAll('.scenario-card').forEach(c => c.classList.remove('selected'));
  document.getElementById('recordBtn').disabled = true;
  document.getElementById('recordBtn').textContent = '🎙️';
  document.getElementById('recordHint').textContent = 'Select a scenario to start';
  document.getElementById('chatHistory').innerHTML = '';
  document.getElementById('aiBubble').classList.remove('visible');
  document.getElementById('feedbackCard').classList.remove('visible');
  document.getElementById('nextBtn').style.display = 'none';
  document.getElementById('resetBtn').style.display = 'none';
  document.getElementById('timer').classList.remove('visible');
  document.getElementById('playBtn').style.display = 'none';
  hideError();
}

function showError(msg) { const el = document.getElementById('errorMsg'); el.textContent = '⚠️ '+msg; el.classList.add('visible'); }
function hideError() { document.getElementById('errorMsg').classList.remove('visible'); }
</script>
</body>
</html>"""


ADMIN_HTML = """<!DOCTYPE html>
<html lang="fi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SpeakUp Admin</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
  :root { --bg:#0a0a0f; --surface:#13131a; --surface2:#1c1c28; --accent:#00e5a0; --accent2:#00b8ff; --text:#f0f0f8; --text2:#7070a0; --border:rgba(255,255,255,0.06); }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text); padding:24px; }
  .header { display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; flex-wrap:wrap; gap:12px; }
  h1 { font-family:'Syne',sans-serif; font-size:22px; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
  .stats { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:24px; }
  .stat { background:var(--surface); border-radius:12px; padding:14px 20px; border:1px solid var(--border); }
  .stat-num { font-family:'Syne',sans-serif; font-size:28px; font-weight:700; color:var(--accent); }
  .stat-label { font-size:12px; color:var(--text2); margin-top:2px; }
  .search { background:var(--surface2); border:1px solid var(--border); border-radius:10px; padding:10px 16px; color:var(--text); font-size:14px; width:100%; max-width:320px; outline:none; margin-bottom:16px; }
  .search:focus { border-color:var(--accent); }
  table { width:100%; border-collapse:collapse; background:var(--surface); border-radius:16px; overflow:hidden; border:1px solid var(--border); }
  th { background:var(--surface2); padding:12px 16px; text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--text2); font-weight:600; }
  td { padding:14px 16px; border-bottom:1px solid var(--border); font-size:14px; }
  tr:last-child td { border-bottom:none; }
  tr:hover td { background:rgba(0,229,160,0.03); }
  .logout { padding:8px 16px; background:var(--surface2); border:1px solid var(--border); border-radius:8px; color:var(--text); text-decoration:none; font-size:13px; }
  .empty { text-align:center; padding:48px; color:var(--text2); }
  .date { font-size:12px; color:var(--text2); }
</style>
</head>
<body>
<div class="header">
  <h1>🎙️ SpeakUp Admin</h1>
  <a href="/admin/logout" class="logout">Kirjaudu ulos</a>
</div>

<div class="stats">
  <div class="stat">
    <div class="stat-num">{{ total }}</div>
    <div class="stat-label">Käyttäjää yhteensä</div>
  </div>
  <div class="stat">
    <div class="stat-num">{{ today }}</div>
    <div class="stat-label">Tänään rekisteröityi</div>
  </div>
</div>

<input class="search" type="text" id="search" placeholder="🔍 Hae nimellä tai sähköpostilla..." oninput="filterTable()">

<table id="userTable">
  <thead>
    <tr>
      <th>Nimi</th>
      <th>Sähköposti</th>
      <th>Rekisteröityi</th>
    </tr>
  </thead>
  <tbody>
    {% for u in users %}
    <tr>
      <td><strong>{{ u.name or '—' }}</strong></td>
      <td>{{ u.email }}</td>
      <td class="date">{{ u.created[:10] if u.created else '—' }}</td>
    </tr>
    {% endfor %}
    {% if not users %}
    <tr><td colspan="3" class="empty">Ei käyttäjiä vielä.</td></tr>
    {% endif %}
  </tbody>
</table>

<script>
function filterTable() {
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('#userTable tbody tr').forEach(row => {
    row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}
</script>
</body>
</html>"""

ADMIN_LOGIN_HTML = """<!DOCTYPE html>
<html lang="fi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SpeakUp Admin</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');
  :root { --bg:#0a0a0f; --surface:#13131a; --surface2:#1c1c28; --accent:#00e5a0; --accent2:#00b8ff; --text:#f0f0f8; --text2:#7070a0; --border:rgba(255,255,255,0.06); --danger:#ff6b35; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; }
  .logo { font-family:'Syne',sans-serif; font-weight:800; font-size:28px; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; text-align:center; margin-bottom:32px; }
  .card { background:var(--surface); border-radius:20px; padding:28px; width:100%; max-width:360px; border:1px solid var(--border); }
  .card h2 { font-family:'Syne',sans-serif; font-size:18px; margin-bottom:20px; }
  .field { margin-bottom:14px; }
  label { font-size:11px; color:var(--text2); text-transform:uppercase; letter-spacing:1px; display:block; margin-bottom:6px; }
  input { background:var(--surface2); border:1px solid var(--border); border-radius:10px; padding:13px 16px; color:var(--text); font-size:15px; width:100%; outline:none; }
  input:focus { border-color:var(--accent); }
  button { width:100%; padding:14px; border-radius:12px; border:none; font-family:'Syne',sans-serif; font-size:15px; font-weight:700; cursor:pointer; background:linear-gradient(135deg,var(--accent),var(--accent2)); color:#0a0a0f; margin-top:8px; }
  .error { background:rgba(255,107,53,0.1); border:1px solid rgba(255,107,53,0.3); border-radius:8px; padding:10px 14px; font-size:13px; color:var(--danger); margin-bottom:16px; }
</style>
</head>
<body>
<div style="width:100%;max-width:360px">
  <div class="logo">SpeakUp Admin</div>
  <div class="card">
    <h2>Kirjaudu sisään</h2>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="POST">
      <div class="field"><label>Salasana</label><input type="password" name="password" autofocus></div>
      <button type="submit">Kirjaudu</button>
    </form>
  </div>
</div>
</body>
</html>"""


AUTH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SpeakUp — {title}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@300;400;500&display=swap');
  :root {{ --bg:#0a0a0f; --surface:#13131a; --surface2:#1c1c28; --accent:#00e5a0; --accent2:#00b8ff; --text:#f0f0f8; --text2:#7070a0; --border:rgba(255,255,255,0.06); --danger:#ff6b35; --success:#00e5a0; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:24px; }}
  .logo {{ font-family:'Syne',sans-serif; font-weight:800; font-size:32px; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:4px; text-align:center; }}
  .tagline {{ font-size:13px; color:var(--text2); text-align:center; margin-bottom:32px; }}
  .card {{ background:var(--surface); border-radius:20px; padding:28px; width:100%; max-width:380px; border:1px solid var(--border); }}
  .card h2 {{ font-family:'Syne',sans-serif; font-size:18px; margin-bottom:20px; }}
  .field {{ display:flex; flex-direction:column; gap:6px; margin-bottom:14px; }}
  label {{ font-size:11px; color:var(--text2); font-weight:500; text-transform:uppercase; letter-spacing:1px; }}
  input {{ background:var(--surface2); border:1px solid var(--border); border-radius:10px; padding:13px 16px; color:var(--text); font-family:'DM Sans',sans-serif; font-size:15px; width:100%; outline:none; }}
  input:focus {{ border-color:var(--accent); }}
  .btn {{ width:100%; padding:15px; border-radius:12px; border:none; font-family:'Syne',sans-serif; font-size:15px; font-weight:700; cursor:pointer; background:linear-gradient(135deg,var(--accent),var(--accent2)); color:#0a0a0f; margin-top:8px; }}
  .msg {{ padding:12px 14px; border-radius:10px; font-size:13px; margin-bottom:16px; }}
  .msg.error {{ background:rgba(255,107,53,0.1); border:1px solid rgba(255,107,53,0.3); color:var(--danger); }}
  .msg.success {{ background:rgba(0,229,160,0.1); border:1px solid rgba(0,229,160,0.3); color:var(--success); }}
  .link {{ text-align:center; margin-top:16px; font-size:13px; color:var(--text2); }}
  .link a {{ color:var(--accent); text-decoration:none; }}
</style>
</head>
<body>
<div class="logo">SpeakUp</div>
<div class="tagline">Learn English by speaking</div>
<div class="card"><h2>{title}</h2>{msg}{form}</div>
<div class="link">{link}</div>
</body>
</html>"""

# ── Routes ───────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template_string(MAIN_HTML, scenarios=SCENARIOS)

@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        user = redis_get(f"ec:user:{email}")
        if not user or user.get("password") != hash_password(password):
            msg = '<div class="msg error">❌ Incorrect email or password.</div>'
        else:
            session["user_email"] = email
            return redirect("/")
    form = '''<form method="POST">
      <div class="field"><label>Email</label><input type="email" name="email" required></div>
      <div class="field"><label>Password</label><input type="password" name="password" required></div>
      <button class="btn" type="submit">Sign in</button>
    </form>'''
    link = '<a href="/register">No account? Register free</a>'
    return render_template_string(AUTH_HTML.format(title="Sign in", msg=msg, form=form, link=link))

@app.route("/register", methods=["GET", "POST"])
def register():
    msg = ""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        if redis_get(f"ec:user:{email}"):
            msg = '<div class="msg error">❌ Email already in use.</div>'
        elif len(password) < 6:
            msg = '<div class="msg error">❌ Password must be at least 6 characters.</div>'
        else:
            redis_set(f"ec:user:{email}", {
                "name": name, "email": email,
                "password": hash_password(password),
                "created": datetime.now().isoformat()
            })
            session["user_email"] = email
            return redirect("/")
    form = '''<form method="POST">
      <div class="field"><label>Your name</label><input type="text" name="name" required></div>
      <div class="field"><label>Email</label><input type="email" name="email" required></div>
      <div class="field"><label>Password (min. 6 characters)</label><input type="password" name="password" required></div>
      <button class="btn" type="submit">Create free account</button>
    </form>'''
    link = '<a href="/login">Already have an account? Sign in</a>'
    return render_template_string(AUTH_HTML.format(title="Create account", msg=msg, form=form, link=link))

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/speak", methods=["POST"])
@login_required
def speak():
    if "audio" not in request.files:
        return jsonify({"error": "No audio"}), 400

    audio_file = request.files["audio"]
    scenario_id = request.form.get("scenario_id", "free")
    history = json.loads(request.form.get("history", "[]"))

    # Step 1: Transcribe with Whisper
    try:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": ("speech.webm", audio_file.read(), "audio/webm")},
            data={"model": "whisper-1", "language": "en"},
            timeout=60
        )
        if not resp.ok:
            return jsonify({"error": "Could not understand audio"}), 500
        transcript = resp.json().get("text", "").strip()
        if not transcript:
            return jsonify({"error": "No speech detected"}), 400
    except Exception as e:
        log.error(f"Whisper error: {e}")
        return jsonify({"error": str(e)}), 500

    # Step 2: Get AI response
    system_prompt = SCENARIO_PROMPTS.get(scenario_id, SCENARIO_PROMPTS["free"])
    history.append({"role": "user", "content": transcript})
    try:
        resp2 = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 150,
                "system": system_prompt,
                "messages": history
            },
            timeout=15
        )
        ai_response = resp2.json()["content"][0]["text"].strip()
        history.append({"role": "assistant", "content": ai_response})
    except Exception as e:
        log.error(f"Claude error: {e}")
        ai_response = "I understand. Please continue."

    # Step 3: Get feedback
    scenario_title = next((s["title"] for s in SCENARIOS if s["id"] == scenario_id), "conversation")
    feedback_prompt = FEEDBACK_PROMPT.format(speech=transcript, scenario=scenario_title)
    try:
        resp3 = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": feedback_prompt}]
            },
            timeout=15
        )
        raw = resp3.json()["content"][0]["text"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        feedback = json.loads(raw)
    except Exception as e:
        log.error(f"Feedback error: {e}")
        feedback = {"corrected": transcript, "feedback": "Good effort! Keep practicing.", "errors": [], "score": 70}

    # Step 4: Text-to-speech with ElevenLabs
    audio_url = None
    if ELEVENLABS_API_KEY:
        try:
            tts_resp = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "text": ai_response,
                    "model_id": "eleven_turbo_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "speed": 0.75
                    }
                },
                timeout=15
            )
            if tts_resp.ok:
                # Tallenna audio väliaikaisesti Redisiin base64-muodossa
                import base64
                audio_b64 = base64.b64encode(tts_resp.content).decode()
                audio_key = f"ec:audio:{session.get('user_email','anon')}:latest"
                redis_set(audio_key, audio_b64, ttl=300)  # 5 min TTL
                audio_url = "/audio/latest"
                log.info("ElevenLabs TTS success")
            else:
                log.error(f"ElevenLabs error: {tts_resp.status_code} {tts_resp.text[:200]}")
        except Exception as e:
            log.error(f"TTS error: {e}")

    return jsonify({
        "transcript": transcript,
        "ai_response": ai_response,
        "feedback": feedback,
        "audio_url": audio_url,
        "updated_history": history[-10:]
    })

@app.route("/audio/latest")
@login_required
def serve_audio():
    import base64
    audio_key = f"ec:audio:{session.get('user_email','anon')}:latest"
    audio_b64 = redis_get(audio_key)
    if not audio_b64:
        return "", 404
    audio_data = base64.b64decode(audio_b64)
    return Response(audio_data, mimetype="audio/mpeg")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")
        return render_template_string(ADMIN_LOGIN_HTML, error="Väärä salasana")
    if not session.get("admin"):
        return render_template_string(ADMIN_LOGIN_HTML, error=None)
    keys = redis_keys("ec:user:*")
    users = []
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = 0
    for key in keys:
        user = redis_get(key)
        if user:
            users.append(user)
            if user.get("created", "").startswith(today):
                today_count += 1
    users.sort(key=lambda x: x.get("created", ""), reverse=True)
    return render_template_string(ADMIN_HTML, users=users, total=len(users), today=today_count)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin")

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
