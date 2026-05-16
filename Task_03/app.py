from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import uuid
import re
import os
import jwt
import bcrypt
import datetime
from functools import wraps

# Force Flask to use the current folder for the database
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, instance_path=basedir)

# Security Configurations
app.config['SECRET_KEY'] = 'prodigy_super_secret_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Table with Password and Role fields
class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) 
    age = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user') # 'admin' or 'user'

    def to_dict(self):
        # SECURITY: Never return the hashed password back to the client!
        return {"id": self.id, "name": self.name, "email": self.email, "age": self.age, "role": self.role}

with app.app_context():
    db.create_all()

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# --- AUTHENTICATION MIDDLEWARE ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Check if the Authorization header is present
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "Token is missing! Please log in."}), 401

        try:
            # Decode the token to find out who the user is
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = db.session.get(User, data['user_id'])
            if not current_user:
                raise Exception("User not found")
        except Exception as e:
            return jsonify({"error": "Token is invalid or expired!"}), 401

        # Pass the verified user object to the route
        return f(current_user, *args, **kwargs)
    return decorated

# --- PUBLIC ROUTES: REGISTER & LOGIN ---
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not all(k in data for k in ('name', 'email', 'age', 'password')):
        return jsonify({"error": "Missing required fields."}), 400
    if not EMAIL_REGEX.match(data['email']):
        return jsonify({"error": "Invalid email format."}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email already exists."}), 400

    role = data.get('role', 'user')

    # Hash the password securely using bcrypt
    hashed_pw = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    new_user = User(name=data['name'], email=data['email'], age=data['age'], password=hashed_pw, role=role)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User registered successfully!"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Missing email or password."}), 400

    user = User.query.filter_by(email=data['email']).first()

    # Check if user exists and password matches the hash
    if user and bcrypt.checkpw(data['password'].encode('utf-8'), user.password.encode('utf-8')):
        # Generate JWT valid for 1 hour
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }, app.config['SECRET_KEY'], algorithm="HS256")

        return jsonify({"token": token, "message": "Login successful!"}), 200

    return jsonify({"error": "Invalid credentials!"}), 401

# --- PROTECTED CRUD ROUTES ---
@app.route('/users', methods=['GET'])
@token_required # <--- This enforces the JWT check!
def get_users(current_user):
    users = User.query.all()
    return jsonify([user.to_dict() for user in users]), 200

@app.route('/users/<user_id>', methods=['GET'])
@token_required
def get_user(current_user, user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify(user.to_dict()), 200

@app.route('/users/<user_id>', methods=['DELETE'])
@token_required
def delete_user(current_user, user_id):
    # RBAC: ONLY admins can delete accounts
    if current_user.role != 'admin':
        return jsonify({"error": "Admin access required to delete users."}), 403

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted successfully."}), 200

if __name__ == '__main__':
    app.run(debug=True)
