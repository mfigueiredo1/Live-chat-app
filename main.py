# imports

import os
import random
import logging
from datetime import datetime
from typing import Dict

from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.middleware.proxy_fix import ProxyFix

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s = %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class Config:
    SECRET_KEY = os.environ.get("SECTRET_KEY") or os.urandom(24)
    DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() in ('true', "1", "t")
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

    # Chat rooms
    CHAT_ROOMS = [
        "General",
        "Zero to Knowing",
        "Code with Josh",
        "The Nerd Nook"
    ]

app = Flask(__name__)
app.config.from_object(Config)

# Handle Reverse Proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


# Set up the Socket
socketIO = SocketIO(
    app,
    cors_allowed_origins=app.config["CORS_ORIGINS"],
    logger=True,
    engineio_logger=True
)


 # Make a database / Dict
active_users: Dict[str, dict] = {}

# Make a User
def generate_guest_username() -> str:
    timestamp = datetime.now().strftime('%H%M')

    return f"Guest{timestamp}{random.randint(1000, 9999)}"


@app.route("/")
def index():
    if 'username' not in session:
        session['username'] = generate_guest_username()
        logger.info(f"New user session make: {session['username']}")
            
    return render_template(
        'index.html',
        username=session['username'],
        rooms=app.config["CHAT_ROOMS"]
    )


# Make a connection
@socketIO.event
def connect():
    try:
        if 'username' not in session:
            session['username'] = generate_guest_username()
        
        active_users[request.sid] = {
            'username': session['username'],
            'connected_at': datetime.now().isoformat()
        }

        emit('active_users',{
            'users':[user['username'] for user in active_users.values()],
        }, boradcast=True)
        
        logger.info(f"User connected: {session['username']}")

    except Exception as e:
        logger.error(f"Error in connect: {str(e)}")
        return False
    

# Disconnect from session 
@socketIO.event
   
def disconnect():
    try:
        if request.sid in active_users:
            username = active_users[request.sid]['username']
            del active_users[request.sid]   
      

            emit('active_users',{
                'users':[user['username'] for user in active_users.values()],
            }, boradcast=True)
        
            logger.info(f"User connected: {session['username']}")

    except Exception as e:
        logger.error(f"Disconnection Error {str(e)}")
        


@ socketIO.event('join')
def on_join(data:dict):
    try:
        username = session['username']
        room = data['room']

        if room not in app.config["CHAT_ROOMS"]:
            logger.warning(f"No room available")
            return 
        
        join_room(room)
        active_users[request.sid]['room'] = room

        emit('status', {
            'msg': f"{username} has joined the room!",
            'type': 'join',
            'timestamp': datetime.now().isoformat(),
            'room': room
        }, room=room)

        logger.infro(f"User {username} has joined")
    except Exception as e:
        logger.error(f"Error in join: {str(e)}")

@socketIO.event('leave')
def on_leave(data:dict):
    try:
        username = session['username']
        room = data['room']

        leave_room(room)
        if request.side in active_users:
            active_users[request.sid].pop('room', None)
        
        emit('status', {
            'msg': f"{username} has left the room!",
            'type': 'leave',
            'timestamp': datetime.now().isoformat(),
            'room': room
        }, room=room)

        logger.info(f"User {username} has left the room")
    except Exception as e:
        logger.error(str(e))

@socketIO.event
def handle_messages(data:dict):

    try:
        username = session['username']
        room = data.get('room' , 'Gneral')
        msg_type = data.get('type', 'message')
        message = data.get('msg', "").strip()

        if not message:
            return
        

        timestamp = datetime.now().isoformat()

        if msg_type == 'private':
            target_user = data.get('target')
            if not target_user:
                return
            for sid, user_data in active_users.items():
                if user_data['username'] == target_user:
                    emit('private_message', {
                    'msg': message,
                    'from': username,
                    'to': target_user,
                    'timestamp': timestamp
                    }, room=sid)
                    return
            else:
                if room not in app.config["CHAT_ROOMS"]:
                    return
                emit('message', {
                    'msg': message,
                    'username': username,
                    'room': target_user,
                    'timestamp': timestamp
                }, room=room)
    except Exception as e:
        logger.error(str(e))



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketIO.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=app.config["DEBUG"],
        use_reloader=app.config["DEBUG"]
    )
