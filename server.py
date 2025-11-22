import asyncio
import websockets
import random
import sqlite3

# --- Configuración ---
PORT = 8000
DB_NAME = "chat.db"
connected_clients = {}

# --- Base de Datos ---
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS mensajes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        mensaje TEXT
    )
''')
conn.commit()
print(f"🔄 Servidor iniciado en puerto {PORT}. Base de datos lista.")

def guardar_mensaje(usuario, mensaje):
    cursor.execute("INSERT INTO mensajes (usuario, mensaje) VALUES (?, ?)", (usuario, mensaje))
    conn.commit()

def obtener_historial():
    cursor.execute("SELECT usuario, mensaje FROM mensajes ORDER BY id DESC LIMIT 20")
    filas = cursor.fetchall()
    return filas[::-1]

# --- WebSocket Logic ---
async def broadcast_message(message, sender_socket=None):
    if not connected_clients: return
    tasks = []
    for client_ws in connected_clients:
        if client_ws != sender_socket:
             tasks.append(client_ws.send(message))
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)

async def chat_handler(websocket):
    username = ""
    try:
        # PASO 1: Esperar el primer mensaje (Protocolo de Handshake)
        # El cliente enviará el nombre apenas se conecte.
        nombre_recibido = await websocket.recv()

        # PASO 2: Decidir el nombre
        # Si viene vacío o es la palabra clave "ANONIMO", asignamos random
        if not nombre_recibido or nombre_recibido == "ANONIMO":
            username = f"Usuario_{random.randint(1000, 9999)}"
        else:
            username = nombre_recibido

        # PASO 3: Registrar y enviar historial
        connected_clients[websocket] = username
        print(f"➕ Login: {username}")
        
        # Enviar historial al nuevo usuario
        historial = obtener_historial()
        for user, msg in historial:
            await websocket.send(f"{user}: {msg}")
            
        # Avisar al resto
        await broadcast_message(f"🔵 {username} se ha unido al chat.")

        # PASO 4: Bucle de Chat normal
        async for message in websocket:
            print(f"Mensaje de {username}: {message}")
            guardar_mensaje(username, message)
            
            # Reenviar a todos
            await broadcast_message(f"{username}: {message}", sender_socket=websocket)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Desconexión
        if websocket in connected_clients:
            del connected_clients[websocket]
            print(f"➖ Salida: {username}")
            await broadcast_message(f"🔴 {username} ha salido del chat.")

# --- Main ---
async def main():
    async with websockets.serve(chat_handler, "localhost", PORT):
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApagando servidor...")
        conn.close()