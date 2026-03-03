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

# ---------------------------------------------------------
# BURAYA KENDİ HTML DEĞİŞKENLERİNİ YAPIŞTIR (ANA_MENU_HTML, ALARM_KURMA_HTML vb.)
# ---------------------------------------------------------

def zaman_kontrol_motoru():
    global sistem_durumu
    su_an = datetime.now(TR_TZ) # SUNUCU SAATİ YERİNE TR SAATİ
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
    save_alarms(alarmlar) # YENİ: ALARMI JSON'A KAYDET
    return redirect("/")

@app.route("/toggle_alarm/<alarm_id>")
def toggle_alarm(alarm_id):
    for alarm in alarmlar:
        if alarm["id"] == alarm_id:
            alarm["is_active"] = not alarm["is_active"]
            save_alarms(alarmlar) # YENİ: DEĞİŞİKLİĞİ KAYDET
            break
    return redirect("/")

@app.route("/delete_alarm/<alarm_id>")
def delete_alarm(alarm_id):
    global alarmlar
    alarmlar = [a for a in alarmlar if a["id"] != alarm_id]
    save_alarms(alarmlar) # YENİ: SİLİNENİ KAYDET
    return redirect("/")

@app.route("/test_alarm")
def test_alarm():
    test_zamani = (datetime.now(TR_TZ) + timedelta(seconds=5)).strftime("%H:%M")
    test_alarm = {
        "id": "test_id", "time": test_zamani, "is_active": True,
        "check_delay_minutes": 0.25, "sound_name": "Test", "sound_url": SESLER["Digital Watch"]
    }
    alarmlar.append(test_alarm)
    save_alarms(alarmlar)
    return redirect("/")

# ... Diğer rotalar (add_alarm, ringing, stop, awake_check vb.) tamamen aynı kalacak.
# Lütfen önceki koddan o rotaları kopyalayıp buraya yapıştır ...

if __name__ == "__main__":
    # Render'ın verdiği portu otomatik yakalaması için güncellendi
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
