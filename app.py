import os
import json
import uuid
import pytz
from flask import Flask, render_template_string, request, redirect, jsonify, send_file
from datetime import datetime, timedelta

app = Flask(__name__)

# --- TÜRKİYE SAATİ AYARI ---
TR_TZ = pytz.timezone('Europe/Istanbul')

# --- KALICI HAFIZA (JSON VERİTABANI) ---
DB_FILE = "alarmlar_db.json"

def load_alarms():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_alarms(alarms_list):
    with open(DB_FILE, "w") as f:
        json.dump(alarms_list, f)

alarmlar = load_alarms()

# --- SES KÜTÜPHANESİ ---
SESLER = {
    "Digital Watch": "https://actions.google.com/sounds/v1/alarms/digital_watch_alarm_long.ogg",
    "Bugle Radar": "https://actions.google.com/sounds/v1/alarms/bugle_tune.ogg",
    "Beep Warning": "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
}

yeni_alarm_taslagi = {"sound_name": "Digital Watch", "sound_url": SESLER["Digital Watch"]}

sistem_durumu = {
    "state": "IDLE", 
    "current_ringing_time": None,
    "current_ringing_sound": None,
    "current_delay": 15,
    "check_time": None,
    "penalty_time": None
}

# --- HTML ŞABLONLARI ---

ANA_MENU_HTML = """
<!DOCTYPE html>
<html class="dark" lang="en"><head>
<meta charset="utf-8"/><meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Dashboard</title>
<script src="https://cdn.tailwindcss.com?plugins=forms"></script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
<script>tailwind.config = { darkMode: "class", theme: { extend: { colors: { "primary": "#135bec", "background-dark": "#101622", "surface-dark": "#1c2230" } } } }</script>
</head>
<body class="bg-background-dark text-white min-h-screen flex flex-col items-center p-4">
<div class="relative w-full max-w-md h-[800px] flex flex-col bg-background-dark border-8 border-slate-800 rounded-[2rem] overflow-hidden shadow-2xl">
    <div class="flex items-center justify-between px-4 py-6">
        <h2 class="text-xl font-bold">Alarms</h2>
        <a href="/add_alarm" class="text-primary hover:bg-slate-800 p-2 rounded-full"><span class="material-symbols-outlined">add</span></a>
    </div>
    <div class="flex flex-col items-center justify-center py-6">
        <h1 class="text-6xl font-bold tracking-tight text-white drop-shadow-[0_0_15px_rgba(19,91,236,0.3)]">{{ su_an }}</h1>
        <div class="mt-4 flex items-center gap-2 rounded-full bg-surface-dark px-4 py-2 shadow-inner border border-slate-700">
            <span class="material-symbols-outlined text-primary text-[20px]">info</span>
            <span class="text-sm font-semibold text-slate-200">{{ mesaj }}</span>
        </div>
        <a href="/test_alarm" class="mt-4 bg-red-600/20 text-red-400 border border-red-600/50 px-4 py-2 rounded-lg text-sm font-bold hover:bg-red-600/40 transition">Hızlı Test (5 Saniye)</a>
    </div>
    <div class="flex-1 overflow-y-auto px-4 pb-24 flex flex-col gap-4">
        {% for alarm in alarmlar %}
        <div class="flex items-center justify-between bg-surface-dark p-4 rounded-xl border {% if alarm.is_active %}border-primary/50{% else %}border-slate-800 opacity-60{% endif %} transition-all">
            <div class="flex items-center gap-4">
                <div class="flex h-12 w-12 items-center justify-center rounded-full bg-slate-800 {% if alarm.is_active %}text-primary{% else %}text-slate-500{% endif %}">
                    <span class="material-symbols-outlined">alarm</span>
                </div>
                <div>
                    <div class="flex items-baseline gap-2">
                        <span class="text-2xl font-bold text-white">{{ alarm.time }}</span>
                    </div>
                    <p class="text-xs {% if alarm.is_active %}text-primary{% else %}text-slate-500{% endif %} font-bold">
                        {% if alarm.is_active %}Aktif{% else %}Kapalı{% endif %} • {{ alarm.sound_name }}
                    </p>
                </div>
            </div>
            <input type="checkbox" {% if alarm.is_active %}checked{% endif %} onchange="window.location.href='/toggle_alarm/{{ alarm.id }}'" class="h-6 w-12 rounded-full appearance-none {% if alarm.is_active %}bg-primary{% else %}bg-slate-700{% endif %} relative cursor-pointer outline-none {% if alarm.is_active %}checked:after:translate-x-6{% endif %} after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:h-5 after:w-5 after:rounded-full after:transition-transform">
            <a href="/delete_alarm/{{ alarm.id }}" class="ml-2 text-slate-600 hover:text-red-500 transition"><span class="material-symbols-outlined text-sm">delete</span></a>
        </div>
        {% else %}
        <div class="text-center text-slate-500 mt-10">
            <span class="material-symbols-outlined text-5xl mb-2 opacity-50">alarm_off</span>
            <p>Henüz alarm kurmadın.</p>
        </div>
        {% endfor %}
    </div>
</div>
<script>
setInterval(function() {
    fetch('/api/status').then(r => r.json()).then(data => {
        if(data.state === 'RINGING' && window.location.pathname !== '/ringing') window.location.href = '/ringing';
        if(data.state === 'CHECK_QUESTION' && window.location.pathname !== '/awake_check') window.location.href = '/awake_check';
        if(data.state === 'PENALTY' && window.location.pathname !== '/penalty') window.location.href = '/penalty';
    });
}, 1000);
</script>
</body></html>
"""

ALARM_KURMA_HTML = """
<!DOCTYPE html>
<html class="dark" lang="en"><head>
<meta charset="utf-8"/><meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Add Alarm</title>
<script src="https://cdn.tailwindcss.com?plugins=forms"></script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
<script>tailwind.config = { darkMode: "class", theme: { extend: { colors: { "primary": "#135bec", "background-dark": "#101622", "surface-dark": "#1c2230" } } } }</script>
</head>
<body class="bg-background-dark text-white min-h-screen flex flex-col items-center p-4">
<div class="relative w-full max-w-md h-[800px] flex flex-col bg-background-dark border-8 border-slate-800 rounded-[2rem] overflow-hidden shadow-2xl">
    <form action="/set_alarm" method="POST" class="h-full flex flex-col">
        <div class="flex items-center justify-between px-4 py-6 border-b border-slate-800">
            <a href="/" class="text-primary font-medium hover:text-white transition">İptal</a>
            <h2 class="text-lg font-bold">Yeni Alarm</h2>
            <button type="submit" class="text-primary font-bold hover:text-white transition">Kaydet</button>
        </div>
        <div class="flex flex-col items-center justify-center py-10 gap-4">
            <p class="text-slate-400 font-medium">Uyanış Vaktini Belirle</p>
            <input type="time" name="time_val" required class="bg-surface-dark text-white text-5xl font-black p-4 rounded-3xl border-2 border-slate-700 outline-none focus:border-primary transition">
        </div>
        <div class="px-4 py-2 space-y-4">
            <div>
                <p class="text-xs text-slate-500 uppercase tracking-widest font-bold mb-2 ml-2">Kontrol / Ceza Süresi</p>
                <select name="check_delay" class="w-full bg-surface-dark rounded-xl border border-slate-800 p-4 text-white font-medium outline-none focus:border-primary">
                    <option value="0.25">15 Saniye (Hızlı Test)</option>
                    <option value="1">1 Dakika Sonra</option>
                    <option value="5">5 Dakika Sonra</option>
                    <option value="15" selected>15 Dakika Sonra</option>
                    <option value="30">30 Dakika Sonra</option>
                </select>
            </div>
            <div>
                <p class="text-xs text-slate-500 uppercase tracking-widest font-bold mb-2 ml-2">Alarm Sesi</p>
                <a href="/sound_select" class="bg-surface-dark rounded-xl border border-slate-800 p-4 flex items-center justify-between hover:bg-slate-800 transition block">
                    <div class="flex items-center gap-4">
                        <span class="material-symbols-outlined text-primary">music_note</span>
                        <span class="font-medium text-lg">Sound</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="text-sm text-slate-400 font-medium truncate w-24 text-right">{{ sound_name }}</span>
                        <span class="material-symbols-outlined text-slate-500">chevron_right</span>
                    </div>
                </a>
            </div>
        </div>
    </form>
</div>
</body></html>
"""

SES_SECME_HTML = """
<!DOCTYPE html>
<html class="dark" lang="en"><head>
<meta charset="utf-8"/><meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Select Sound</title>
<script src="https://cdn.tailwindcss.com?plugins=forms"></script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
<script>tailwind.config = { darkMode: "class", theme: { extend: { colors: { "primary": "#135bec", "background-dark": "#101622", "surface-dark": "#1c2230" } } } }</script>
</head>
<body class="bg-background-dark text-white min-h-screen flex flex-col items-center p-4">
<div class="relative w-full max-w-md h-[800px] flex flex-col bg-background-dark border-8 border-slate-800 rounded-[2rem] overflow-hidden shadow-2xl">
    <div class="flex items-center px-4 py-6 border-b border-slate-800">
        <a href="/add_alarm" class="flex items-center text-primary font-medium hover:text-white transition">
            <span class="material-symbols-outlined">chevron_left</span> Geri
        </a>
        <h2 class="text-lg font-bold mx-auto pr-8">Ses Seçimi</h2>
    </div>
    <div class="flex-1 overflow-y-auto px-4 py-6 flex flex-col gap-4">
        <div class="bg-surface-dark p-4 rounded-xl border border-primary/50 mb-2 shadow-lg shadow-primary/10">
            <h3 class="text-sm font-bold text-primary mb-3 flex items-center gap-2"><span class="material-symbols-outlined">upload_file</span>Kendi Sesini Yükle</h3>
            <form action="/upload_sound" method="POST" enctype="multipart/form-data" class="flex flex-col gap-3">
                <input type="file" name="audio_file" accept="audio/*" required class="text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-bold file:bg-slate-800 file:text-primary hover:file:bg-slate-700 outline-none">
                <button type="submit" class="w-full bg-primary text-white font-bold py-2 rounded-lg hover:bg-blue-600 transition">Yükle ve Kullan</button>
            </form>
        </div>
        <p class="text-xs text-slate-500 uppercase tracking-widest font-bold ml-2">Varsayılan Sesler</p>
        {% for name, url in sesler.items() %}
        <a href="/set_sound/{{ name }}" class="flex items-center justify-between bg-surface-dark p-4 rounded-xl border {% if name == current_sound %}border-primary{% else %}border-slate-800{% endif %} hover:bg-slate-800 transition">
            <span class="font-medium text-lg">{{ name }}</span>
            {% if name == current_sound %}
            <span class="material-symbols-outlined text-primary">check_circle</span>
            {% endif %}
        </a>
        {% endfor %}
    </div>
</div>
</body></html>
"""

AKTIF_ALARM_HTML = """
<!DOCTYPE html>
<html class="dark" lang="en"><head>
<meta charset="utf-8"/><meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Ringing</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
<script>tailwind.config = { darkMode: "class", theme: { extend: { colors: { "primary": "#135bec", "background-dark": "#101622" } } } }</script>
<style>.neon-glow { text-shadow: 0 0 30px rgba(19,91,236,0.6), 0 0 60px rgba(19,91,236,0.3); }</style>
</head>
<body class="bg-background-dark text-white h-screen flex flex-col items-center justify-center">
    <audio id="alarmAudio" autoplay loop src="{{ sound_url }}"></audio>
    <div class="flex flex-col items-center space-y-12 w-full">
        <div class="flex flex-col items-center">
            <span class="material-symbols-outlined text-primary text-5xl mb-4 animate-bounce">alarm</span>
            <h1 class="text-[80px] font-black neon-glow leading-none">{{ alarm_time }}</h1>
            <h2 class="text-xl text-slate-400 font-bold mt-4 tracking-widest uppercase">Uyanma Vakti!</h2>
        </div>
        <div class="flex flex-col items-center gap-6 mt-10 w-full px-8">
            <a href="/action/snooze" class="group relative flex items-center justify-center w-28 h-28 rounded-full bg-slate-800 border-4 border-slate-700 hover:border-primary transition shadow-xl">
                <div class="flex flex-col items-center gap-1">
                    <span class="material-symbols-outlined text-primary text-4xl group-hover:scale-110 transition">snooze</span>
                    <span class="text-xs font-bold text-slate-400 tracking-wide">ERTELE (1 Dk)</span>
                </div>
            </a>
            <a href="/action/stop" class="w-full bg-primary text-white py-5 rounded-2xl font-black text-xl shadow-[0_0_20px_rgba(19,91,236,0.4)] hover:bg-blue-600 transition text-center mt-6 tracking-wide">
                DURDUR (KAPAT)
            </a>
            <p class="text-xs text-slate-500 font-medium text-center">Durdurduğunda {{ delay }} sonra uyanıklık testi başlar.</p>
        </div>
    </div>
<script>
    var audio = document.getElementById("alarmAudio");
    audio.play().catch(e => console.log("Ekrana dokununca ses başlayacak."));
    document.body.addEventListener('click', () => audio.play());
</script>
</body></html>
"""

UYANIKLIK_TESTI_HTML = """
<!DOCTYPE html>
<html class="dark" lang="en"><head>
<meta charset="utf-8"/><meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Awake Check</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
<script>tailwind.config = { darkMode: "class", theme: { extend: { colors: { "background-dark": "#101622" } } } }</script>
</head>
<body class="bg-background-dark text-white h-screen flex flex-col items-center justify-center p-6 text-center">
    <div class="bg-[#1c2230] border-4 border-yellow-500/50 p-8 rounded-3xl w-full max-w-sm flex flex-col items-center shadow-[0_0_40px_rgba(234,179,8,0.2)]">
        <span class="material-symbols-outlined text-7xl text-yellow-500 mb-6 animate-pulse">warning</span>
        <h1 class="text-3xl font-black mb-4">Gerçekten Uyandın Mı?</h1>
        <p class="text-slate-400 mb-6 font-medium">Cevap vermek için <span id="timer" class="text-white font-bold text-xl px-2">30</span> saniyen kaldı!</p>
        <a href="/action/awake" class="w-full bg-yellow-500 text-black py-5 rounded-2xl font-black text-xl hover:bg-yellow-400 transition shadow-lg shadow-yellow-500/30 tracking-wider">
            EVET, UYANDIM!
        </a>
    </div>
<script>
let timeLeft = 30;
setInterval(() => { if(timeLeft > 0) { timeLeft--; document.getElementById('timer').innerText = timeLeft; } }, 1000);
setInterval(() => { fetch('/api/status').then(r => r.json()).then(data => { if(data.state === 'PENALTY') window.location.href = '/penalty'; }); }, 1000);
</script>
</body></html>
"""

CEZA_ALARMI_HTML = """
<!DOCTYPE html>
<html class="dark" lang="en"><head>
<meta charset="utf-8"/><meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Penalty</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
<script>tailwind.config = { darkMode: "class", theme: { extend: { colors: { "background-dark": "#101622" } } } }</script>
</head>
<body class="bg-red-950 text-white h-screen flex flex-col items-center justify-center p-6 text-center">
    <audio id="penaltyAudio" autoplay loop src="{{ sound_url }}"></audio>
    <span class="material-symbols-outlined text-8xl text-red-500 mb-6 animate-ping">local_fire_department</span>
    <h1 class="text-6xl font-black mb-4 text-red-500 tracking-tighter drop-shadow-[0_0_20px_rgba(239,68,68,0.8)]">UYUYAKALDIN!</h1>
    <p class="text-white/80 mb-12 text-xl font-medium">Ceza alarmı devrede. Hemen o yataktan çık!</p>
    <a href="/action/awake" class="w-full max-w-xs bg-red-600 border-4 border-red-400 text-white py-6 rounded-3xl font-black text-2xl hover:bg-red-500 transition shadow-[0_0_30px_rgba(239,68,68,0.6)]">
        SUSTUR & UYAN
    </a>
<script>
    var audio = document.getElementById("penaltyAudio");
    audio.play(); document.body.addEventListener('click', () => audio.play());
</script>
</body></html>
"""

# --- MOTOR VE ROTALAR ---

def zaman_kontrol_motoru():
    global sistem_durumu
    su_an = datetime.now(TR_TZ)
    su_an_saat_dk = su_an.strftime("%H:%M")
    
    if sistem_durumu["state"] == "IDLE":
        for alarm in alarmlar:
            if alarm["is_active"] and alarm["time"] == su_an_saat_dk:
                sistem_durumu["state"] = "RINGING"
                sistem_durumu["current_ringing_time"] = alarm["time"]
                sistem_durumu["current_ringing_sound"] = alarm["sound_url"]
                sistem_durumu["current_delay"] = alarm["check_delay_minutes"]
                break
            
    elif sistem_durumu["state"] == "CHECK_WAITING":
        if su_an >= sistem_durumu["check_time"]:
            sistem_durumu["state"] = "CHECK_QUESTION"
            sistem_durumu["penalty_time"] = su_an + timedelta(seconds=30)
            
    elif sistem_durumu["state"] == "CHECK_QUESTION":
        if su_an >= sistem_durumu["penalty_time"]:
            sistem_durumu["state"] = "PENALTY"

@app.route("/")
def ana_menu():
    zaman_kontrol_motoru()
    su_an = datetime.now(TR_TZ).strftime("%H:%M")
    aktif_sayi = sum(1 for a in alarmlar if a["is_active"])
    mesaj = f"{aktif_sayi} aktif alarm var." if aktif_sayi > 0 else "Aktif alarm yok."
    if sistem_durumu["state"] != "IDLE": mesaj = "Arka planda uyanıklık testi sürüyor!"
    return render_template_string(ANA_MENU_HTML, su_an=su_an, mesaj=mesaj, alarmlar=alarmlar)

@app.route("/api/status")
def status():
    zaman_kontrol_motoru()
    return jsonify({"state": sistem_durumu["state"]})

@app.route("/add_alarm")
def add_alarm():
    return render_template_string(ALARM_KURMA_HTML, sound_name=yeni_alarm_taslagi["sound_name"])

@app.route("/sound_select")
def sound_select():
    return render_template_string(SES_SECME_HTML, sesler=SESLER, current_sound=yeni_alarm_taslagi["sound_name"])

@app.route("/set_sound/<name>")
def set_sound(name):
    if name in SESLER:
        yeni_alarm_taslagi["sound_name"] = name
        yeni_alarm_taslagi["sound_url"] = SESLER[name]
    return redirect("/add_alarm")

@app.route("/upload_sound", methods=["POST"])
def upload_sound():
    file = request.files.get("audio_file")
    if file and file.filename != '':
        file.save("kendi_sesim.mp3")
        SESLER["Kendi Yüklediğim Ses"] = "/custom_audio"
        yeni_alarm_taslagi["sound_name"] = "Kendi Yüklediğim Ses"
        yeni_alarm_taslagi["sound_url"] = "/custom_audio"
    return redirect("/add_alarm")

@app.route("/custom_audio")
def custom_audio():
    if os.path.exists("kendi_sesim.mp3"):
        return send_file("kendi_sesim.mp3")
    return "Ses bulunamadı", 404

@app.route("/set_alarm", methods=["POST"])
def set_alarm():
    zaman = request.form.get("time_val")
    delay_val = float(request.form.get("check_delay", 15)) 
    yeni_alarm = {
        "id": str(uuid.uuid4()),
        "time": zaman,
        "is_active": True,
        "check_delay_minutes": delay_val,
        "sound_name": yeni_alarm_taslagi["sound_name"],
        "sound_url": yeni_alarm_taslagi["sound_url"]
    }
    alarmlar.append(yeni_alarm)
    alarmlar.sort(key=lambda x: x["time"])
    save_alarms(alarmlar)
    return redirect("/")

@app.route("/toggle_alarm/<alarm_id>")
def toggle_alarm(alarm_id):
    for alarm in alarmlar:
        if alarm["id"] == alarm_id:
            alarm["is_active"] = not alarm["is_active"]
            save_alarms(alarmlar)
            break
    return redirect("/")

@app.route("/delete_alarm/<alarm_id>")
def delete_alarm(alarm_id):
    global alarmlar
    alarmlar = [a for a in alarmlar if a["id"] != alarm_id]
    save_alarms(alarmlar)
    return redirect("/")

@app.route("/test_alarm")
def test_alarm():
    test_zamani = (datetime.now(TR_TZ) + timedelta(seconds=5)).strftime("%H:%M")
    test_alarm = {
        "id": str(uuid.uuid4()),
        "time": test_zamani,
        "is_active": True,
        "check_delay_minutes": 0.25,
        "sound_name": "Test Sesi",
        "sound_url": yeni_alarm_taslagi["sound_url"]
    }
    alarmlar.append(test_alarm)
    save_alarms(alarmlar)
    return redirect("/")

@app.route("/ringing")
def ringing():
    if sistem_durumu["state"] != "RINGING": return redirect("/")
    delay_val = sistem_durumu["current_delay"]
    display_delay = "15 Saniye" if delay_val == 0.25 else f"{int(delay_val)} Dakika"
    return render_template_string(AKTIF_ALARM_HTML, sound_url=sistem_durumu["current_ringing_sound"], alarm_time=sistem_durumu["current_ringing_time"], delay=display_delay)

@app.route("/action/snooze")
def snooze():
    yeni_zaman = (datetime.now(TR_TZ) + timedelta(minutes=1)).strftime("%H:%M")
    sistem_durumu["state"] = "IDLE"
    ertelenmis_alarm = {
        "id": str(uuid.uuid4()),
        "time": yeni_zaman,
        "is_active": True,
        "check_delay_minutes": sistem_durumu["current_delay"],
        "sound_name": "Ertelendi",
        "sound_url": sistem_durumu["current_ringing_sound"]
    }
    alarmlar.append(ertelenmis_alarm)
    save_alarms(alarmlar)
    return redirect("/")

@app.route("/action/stop")
def stop():
    delay_min = sistem_durumu["current_delay"]
    sistem_durumu["state"] = "CHECK_WAITING"
    sistem_durumu["check_time"] = datetime.now(TR_TZ) + timedelta(minutes=delay_min)
    return redirect("/")

@app.route("/awake_check")
def awake_check():
    if sistem_durumu["state"] != "CHECK_QUESTION": return redirect("/")
    return render_template_string(UYANIKLIK_TESTI_HTML)

@app.route("/penalty")
def penalty():
    if sistem_durumu["state"] != "PENALTY": return redirect("/")
    return render_template_string(CEZA_ALARMI_HTML, sound_url=sistem_durumu["current_ringing_sound"])

@app.route("/action/awake")
def awake():
    sistem_durumu["state"] = "IDLE"
    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
