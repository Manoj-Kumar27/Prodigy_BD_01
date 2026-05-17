from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import uuid
import re
import os
import jwt
import bcrypt
import datetime
import time
import json
import redis
from functools import wraps

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, instance_path=basedir)

# Configurations
app.config['SECRET_KEY'] = 'prodigy_super_secret_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Initialize Redis Connection (Connecting to your soon-to-be WSL server)
# decode_responses=True automatically converts Redis bytes to Python strings
cache = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)

class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) 
    age = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "age": self.age, "role": self.role}

with app.app_context():
    db.create_all()

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# --- AUTHENTICATION MIDDLEWARE ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "Token is missing!"}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = db.session.get(User, data['user_id'])
            if not current_user:
                raise Exception("User not found")
        except Exception:
            return jsonify({"error": "Token is invalid or expired!"}), 401

        return f(current_user, *args, **kwargs)
    return decorated

# --- ROUTES ---
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not all(k in data for k in ('name', 'email', 'age', 'password')):
        return jsonify({"error": "Missing fields"}), 400
    
    hashed_pw = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    new_user = User(name=data['name'], email=data['email'], age=data['age'], password=hashed_pw, role=data.get('role', 'user'))
    
    db.session.add(new_user)
    db.session.commit()
    
    # CACHE INVALIDATION: If a new user joins, the old cache is outdated!
    cache.delete('all_users')
    
    return jsonify({"message": "User registered successfully!"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    if user and bcrypt.checkpw(data['password'].encode('utf-8'), user.password.encode('utf-8')):
        token = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)}, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({"token": token, "message": "Login successful!"}), 200
    return jsonify({"error": "Invalid credentials!"}), 401

# --- THE CACHED ROUTE ---
@app.route('/users', methods=['GET'])
@token_required
def get_users(current_user):
    start_time = time.time() # Start stopwatch
    
    # 1. Check if data is already in Redis
    cached_users = cache.get('all_users')
    
    if cached_users:
        # CACHE HIT: Return data immediately from RAM
        users_list = json.loads(cached_users)
        source = "Redis Cache"
    else:
        # CACHE MISS: Fetch from Database
        users = User.query.all()
        users_list = [user.to_dict() for user in users]
        
        # Save a copy to Redis for next time. Set TTL (expiration) to 5 minutes (300 seconds)
        cache.setex('all_users', 300, json.dumps(users_list))
        source = "SQLite Database"

    end_time = time.time() # Stop stopwatch
    response_time_ms = round((end_time - start_time) * 1000, 2)
    
    return jsonify({
        "source": source,
        "response_time_ms": response_time_ms,
        "data": users_list
    }), 200

@app.route('/users/<user_id>', methods=['DELETE'])
@token_required
def delete_user(current_user, user_id):
    if current_user.role != 'admin':
        return jsonify({"error": "Admin access required."}), 403

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    
    db.session.delete(user)
    db.session.commit()
    
    # CACHE INVALIDATION: Someone was deleted, so wipe the outdated cache!
    cache.delete('all_users')
    
    return jsonify({"message": "User deleted successfully."}), 200

if __name__ == '__main__':
    app.run(debug=True)
