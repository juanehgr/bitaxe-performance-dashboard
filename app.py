import websocket
import threading
import time
import re
import sqlite3
import requests
import math
from collections import defaultdict
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

BITAXES = {
    "gamma": "192.168.1.208",
    "nerd": "192.168.1.212"
}

DB_FILE = "bitaxe.db"
MIN_DIFF = 100_000

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

miners = {}
last_store = {}
last_diff_seen = {}   # 🔥 FIX NUEVO (evitar duplicados)

COINS = {
    "BTC": {"diff_url": "https://blockchain.info/q/getdifficulty","price_id": "bitcoin","reward": 3.125},
    "BSV": {"diff_url": "https://api.whatsonchain.com/v1/bsv/main/chain/info","price_id": "bitcoin-cash-sv","reward": 6.25},
    "FCH": {"diff_url": "https://explorer.fch.network/api/getdifficulty","price_id": "freecash","reward": 6.25}
}

current_coin = {"name": "BSV"}
network_data = {"difficulty": 0,"price": 0,"block_reward": 0}

# ===== UTILS =====

def format_diff(n):
    if n >= 1e9: return f"{n/1e9:.0f}G"
    if n >= 1e6: return f"{n/1e6:.1f}M"
    if n >= 1e3: return f"{n/1e3:.1f}k"
    return str(int(n))

def parse_unit_value(v):
    if isinstance(v, (int,float)): return float(v)
    if isinstance(v,str):
        m = re.match(r"([\d\.]+)([GMK]?)", v)
        if m:
            n=float(m.group(1));u=m.group(2)
            return n*({"G":1e9,"M":1e6,"K":1e3}.get(u,1))
    return 0

def parse_diff(line):
    m = re.search(r"diff\s+([\d\.]+)", line)
    return float(m.group(1)) if m else None

def classify_share(d):
    if d >= 1e9: return "1G+"
    elif d >= 1e8: return "100M+"
    elif d >= 1e7: return "10M+"
    elif d >= 1e6: return "1M+"
    elif d >= 1e5: return "100k+"
    else: return None

# ===== DB =====

def init_db():
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS shares (
        id INTEGER PRIMARY KEY,
        miner TEXT,
        diff REAL,
        hashrate REAL,
        temp REAL,
        timestamp INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS big_shares (
        id INTEGER PRIMARY KEY,
        miner TEXT,
        diff REAL,
        bucket TEXT,
        hashrate REAL,
        temp REAL,
        percent REAL,
        remaining REAL,
        timestamp INTEGER
    )""")

    conn.commit()
    conn.close()

def save_share(miner,diff,hr,temp):
    now=int(time.time())

    if miner not in last_store:
        last_store[miner]=0

    if now-last_store[miner]<10:
        return

    last_store[miner]=now

    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()

    c.execute("INSERT INTO shares VALUES (NULL,?,?,?,?,?)",
              (miner,diff,hr,temp,now))

    conn.commit()
    conn.close()

def save_big_share(miner,diff,bucket,hr,temp,percent,remaining):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()

    c.execute("INSERT INTO big_shares VALUES (NULL,?,?,?,?,?,?,?,?)",
              (miner,diff,bucket,hr,temp,percent,remaining,int(time.time())))

    conn.commit()
    conn.close()

def get_history(miner):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()

    c.execute("""
        SELECT timestamp, hashrate, temp
        FROM shares
        WHERE miner=?
        ORDER BY id DESC LIMIT 100
    """,(miner,))

    r=c.fetchall()
    conn.close()

    return list(reversed(r))

def get_big_shares(miner):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()

    c.execute("""
        SELECT diff,bucket,hashrate,temp,percent,remaining,timestamp
        FROM big_shares
        WHERE miner=?
        ORDER BY id DESC
        LIMIT 1000
    """,(miner,))

    r=c.fetchall()
    conn.close()
    return r

# ===== INIT =====

def init_stats():
    return {
        "hashrate":0,
        "temp":0,
        "best_diff":0,
        "best_diff_fmt":"0",
        "last_percent":0,
        "share_buckets":defaultdict(int)
    }

for n in BITAXES:
    miners[n]=init_stats()
    last_diff_seen[n]=0   # 🔥 INIT

# ===== NETWORK =====

def fetch_network():
    while True:
        try:
            coin=COINS[current_coin["name"]]

            r=requests.get(coin["diff_url"],timeout=5)
            network_data["difficulty"]=r.json()["difficulty"] if current_coin["name"]=="BSV" else float(r.text)

            r=requests.get(
                f"https://api.coingecko.com/api/v3/simple/price?ids={coin['price_id']}&vs_currencies=usd",
                timeout=5
            )

            network_data["price"]=r.json()[coin["price_id"]]["usd"]
            network_data["block_reward"]=coin["reward"]

        except:
            pass

        time.sleep(10)

# ===== FETCH =====

def fetch_stats(name,ip):
    while True:
        try:
            d=requests.get(f"http://{ip}/api/system/info",timeout=3).json()

            miners[name]["hashrate"]=float(d.get("hashRate",0))/1000
            miners[name]["temp"]=d.get("temp",0)

            b=parse_unit_value(d.get("bestDiff",0))
            miners[name]["best_diff"]=b
            miners[name]["best_diff_fmt"]=format_diff(b)

        except:
            pass

        time.sleep(2)

# ===== WS =====

def ws_thread(name,ip):
    def on_message(ws,msg):
        if "asic_result" in msg.lower():
            d=parse_diff(msg)

            if not d:
                return

            # 🔥 EVITAR DUPLICADOS
            if d == last_diff_seen[name]:
                return
            last_diff_seen[name] = d

            m=miners[name]

            save_share(name,d,m["hashrate"],m["temp"])

            bucket = classify_share(d)
            if bucket:
                m["share_buckets"][bucket] += 1

            if d >= MIN_DIFF:
                net=network_data["difficulty"]

                prob=d/net if net else 0
                percent=(1-math.exp(-prob))*100
                rem=net-d if net else 0

                save_big_share(
                    name,
                    d,
                    bucket,
                    m["hashrate"],
                    m["temp"],
                    percent,
                    rem
                )

                m["last_percent"]=percent

    while True:
        try:
            websocket.WebSocketApp(
                f"ws://{ip}/api/ws",
                on_message=on_message
            ).run_forever()
        except:
            time.sleep(3)

# ===== API =====

@app.route("/history/<m>")
def history(m):
    return jsonify(get_history(m))

@app.route("/big/<m>")
def big(m):
    return jsonify(get_big_shares(m))

@app.route("/set_coin",methods=["POST"])
def set_coin():
    c=request.json["coin"]
    if c in COINS:
        current_coin["name"]=c
    return {"ok":True}

@app.route("/buckets/<miner>")
def buckets(miner):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT diff FROM shares WHERE miner=?", (miner,))
    rows = c.fetchall()
    conn.close()

    result = {"1G+":0,"100M+":0,"10M+":0,"1M+":0,"100k+":0}

    for (d,) in rows:
        if d >= 1e9: result["1G+"] += 1
        elif d >= 1e8: result["100M+"] += 1
        elif d >= 1e7: result["10M+"] += 1
        elif d >= 1e6: result["1M+"] += 1
        elif d >= 1e5: result["100k+"] += 1

    return jsonify(result)
    
@app.route("/big_count/<miner>")
def big_count(miner):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()

    c.execute("SELECT COUNT(*) FROM big_shares WHERE miner=?", (miner,))
    count = c.fetchone()[0]

    conn.close()
    return {"count": count}

# ===== EMIT =====

def build_payload():
    return{
        "miners":miners,
        "total":{"hashrate":round(sum(m["hashrate"] for m in miners.values()),2)},
        "network":{
            "coin":current_coin["name"],
            "difficulty_fmt":format_diff(network_data["difficulty"]),
            "price":network_data["price"],
            "block_value":network_data["block_reward"]*network_data["price"]
        }
    }

def emit_loop():
    while True:
        socketio.emit("update",build_payload())
        time.sleep(1)

# ===== MAIN =====

@app.route("/")
def index():
    return render_template("index.html")

if __name__=="__main__":
    init_db()

    threading.Thread(target=fetch_network,daemon=True).start()

    for n,ip in BITAXES.items():
        threading.Thread(target=fetch_stats,args=(n,ip),daemon=True).start()
        threading.Thread(target=ws_thread,args=(n,ip),daemon=True).start()

    socketio.start_background_task(emit_loop)  # 🔥 FIX CLAVE

    socketio.run(app,host="0.0.0.0",port=5000)