import websocket
import json

IP = "192.168.1.208"

def on_message(ws, message):
    print("\n--- RAW ---")
    print(message)

    try:
        data = json.loads(message)
        print("\n--- JSON ---")
        print(json.dumps(data, indent=2))
    except:
        print("\n(no es JSON)")

def on_open(ws):
    print("Conectado!")

    # 🔥 prueba varios tipos de suscripción
    ws.send(json.dumps({"action": "subscribe"}))
    ws.send(json.dumps({"type": "stats"}))
    ws.send(json.dumps({"op": "subscribe"}))

def on_error(ws, error):
    print("ERROR:", error)

def on_close(ws, a, b):
    print("CERRADO")

ws = websocket.WebSocketApp(
    f"ws://{IP}/api/ws",
    on_message=on_message,
    on_open=on_open,
    on_error=on_error,
    on_close=on_close
)

ws.run_forever()