from flask import Flask, render_template, redirect, request, session, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Message

app = Flask(__name__)
app.secret_key = 'secret123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
socketio = SocketIO(app)
login_manager = LoginManager()
login_manager.init_app(app)

online_users = set()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect('/chat')
    else:
        return redirect('/login')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=username).first():
            return "User already exists"
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        return redirect('/login')
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        user = User.query.filter_by(username=username).first()
        print(check_password_hash(user.password, request.form['password']))
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect('/chat')
        return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    current_user.is_online = False
    db.session.commit()
    logout_user()
    return redirect('/login')

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html', username=current_user.username)

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        online_users.add(current_user.username)
        current_user.is_online = True
        db.session.commit()
        emit('user_list', list(online_users), broadcast=True)
        messages = Message.query.order_by(Message.timestamp.asc()).all()
        for msg in messages:
            emit('chat_message', {'user': msg.username, 'message': msg.content})

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        online_users.discard(current_user.username)
        current_user.is_online = False
        db.session.commit()
        emit('user_list', list(online_users), broadcast=True)

@socketio.on('chat_message')
def handle_message(data):
    msg = Message(user_id=current_user.id, username=current_user.username, content=data['message'])
    db.session.add(msg)
    db.session.commit()
    emit('chat_message', {'user': current_user.username, 'message': data['message']}, broadcast=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='10.10.10.50', port=5000, debug=True)
