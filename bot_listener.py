# bot_listener.py (Versión Final y Completa para Replit)
# Este script actúa como el "Oído" y la "Boca" del bot.

import discord
import os
import requests
from flask import Flask, request, jsonify
from threading import Thread

# --- 1. CONFIGURACIÓN DEL SERVIDOR WEB ---
# Este servidor tiene dos propósitos:
#   A) Mantener el Repl despierto 24/7 con UptimeRobot (ruta '/').
#   B) Recibir órdenes de notificación desde PythonAnywhere (ruta '/send_notification').

app = Flask('')

@app.route('/')
def home():
    """Ruta para el ping de UptimeRobot."""
    return "Bot 'La Velada' está activo y escuchando."

@app.route('/send_notification', methods=['POST'])
def send_notification():
    """Ruta segura para que el 'Cerebro' (PythonAnywhere) nos ordene enviar un MD."""
    data = request.json
    # Medida de seguridad: la clave debe coincidir con la de PythonAnywhere
    if request.headers.get('X-Secret-Key') != os.environ.get('REPLIT_SECRET_KEY'):
        print("ADVERTENCIA: Intento de notificación no autorizado.")
        return jsonify({"error": "No autorizado"}), 403

    target_user_id = data.get('target_user_id')
    message = data.get('message')

    if not target_user_id or not message:
        return jsonify({"error": "Faltan datos en la petición de notificación"}), 400

    # Creamos una tarea en el bucle de eventos del bot para enviar el mensaje de forma segura
    client.loop.create_task(send_dm_from_task(int(target_user_id), message))
    return jsonify({"status": "Notificación encolada."})

def run_web_server():
    """Función que se ejecutará en un hilo separado para no bloquear el bot."""
    app.run(host='0.0.0.0', port=8080)

async def send_dm_from_task(user_id, msg):
    """Función asíncrona segura para enviar mensajes desde una tarea."""
    try:
        user = await client.fetch_user(user_id)
        await user.send(msg)
        print(f"Notificación enviada con éxito a {user.name}")
    except Exception as e:
        print(f"ERROR CRÍTICO: No se pudo enviar DM desde una tarea a {user_id}: {e}")

# --- 2. CONFIGURACIÓN DEL BOT DE DISCORD ---

# Definir los "intentos" o permisos que necesita el bot
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True # Permiso para leer el contenido de los MDs

# Crear la instancia del cliente del bot
client = discord.Client(intents=intents)

# Leer las URLs y claves secretas desde los Secrets de Replit
BRAIN_URL = "https://laveladadelano.eu.pythonanywhere.com"
SECRET_KEY = os.environ.get('REPLIT_SECRET_KEY')

@client.event
async def on_ready():
    """Se ejecuta una vez cuando el bot se conecta con éxito a Discord."""
    print('----------------------------------------------------')
    print(f'¡CONECTADO! El bot "{client.user}" está online y listo.')
    print(f'ID de Usuario del Bot: {client.user.id}')
    print('----------------------------------------------------')

@client.event
async def on_message(message):
    """Se ejecuta cada vez que el bot ve un mensaje."""
    # Ignorar mensajes del propio bot
    if message.author == client.user:
        return

    # Procesar únicamente mensajes directos (MDs)
    if isinstance(message.channel, discord.DMChannel):
        print(f"Mensaje recibido de {message.author} (ID: {message.author.id}): '{message.content}'")

        # Indicar al usuario que el bot está "pensando"
        async with message.channel.typing():
            try:
                # Enviar el mensaje al "Cerebro" en PythonAnywhere
                response = requests.post(
                    f"{BRAIN_URL}/bot_handler",
                    json={"user_id": str(message.author.id), "message": message.content},
                    headers={"X-Secret-Key": SECRET_KEY},
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()

                # Procesar la respuesta del Cerebro
                response_text = data.get("text")
                if response_text:
                    await message.channel.send(response_text)

                if data.get("action_required") and "actions" in data:
                    for action in data["actions"]:
                        if action["type"] == "SEND_DM":
                            await send_dm_from_task(int(action["target_user_id"]), action["message_content"])

            except Exception as e:
                print(f"Error en el ciclo on_message: {e}")
                await message.channel.send("Lo siento, ocurrió un error procesando tu petición.")

@client.event
async def on_interaction(interaction: discord.Interaction):
    """Se ejecuta cada vez que un usuario interactúa con un componente (ej. un botón)."""
    if interaction.type == discord.InteractionType.component:
        # 1. Acuse de recibo inmediato (dentro de 3 segundos) para evitar "Interacción fallida"
        await interaction.response.defer()

        custom_id = interaction.data["custom_id"]
        action_parts = custom_id.split('_')
        action, fight_id = action_parts[0], action_parts[-1]

        print(f"Interacción de botón recibida de {interaction.user.name}: Acción='{action}', Pelea ID='{fight_id}'")

        # 2. Enviar la orden al "Cerebro" en PythonAnywhere
        try:
            response = requests.post(
                f"{BRAIN_URL}/fight_action_discord",
                json={
                    "user_id": str(interaction.user.id),
                    "fight_id": int(fight_id),
                    "action": action
                },
                headers={"X-Secret-Key": SECRET_KEY},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # 3. Procesar la respuesta y enviar las notificaciones
            if data.get("confirmation_text"):
                await interaction.followup.send(data["confirmation_text"], ephemeral=True)

            if data.get("notification_text") and data.get("notify_user_id"):
                await send_dm_from_task(int(data["notify_user_id"]), data["notification_text"])

            # 4. Editar el mensaje original para desactivar los botones
            await interaction.edit_original_response(view=None)

        except Exception as e:
            print(f"Error procesando interacción: {e}")
            await interaction.followup.send("Hubo un error al procesar tu acción.", ephemeral=True)

# --- 3. ARRANQUE DEL SISTEMA ---
print("Iniciando el bot...")

# Iniciar el servidor web "Keep Alive" en un hilo secundario
web_thread = Thread(target=run_web_server)
web_thread.start()
print("Servidor 'Keep Alive' y Webhook iniciados.")

# Iniciar el bot de Discord
bot_token = os.environ.get('DISCORD_BOT_TOKEN')
if not bot_token or not SECRET_KEY:
    print("¡ERROR CRÍTICO! Asegúrate de que DISCORD_BOT_TOKEN y REPLIT_SECRET_KEY están en los Secrets.")
else:
    print("Conectando a Discord...")
    client.run(bot_token)
