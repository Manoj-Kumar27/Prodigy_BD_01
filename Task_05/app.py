from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import uuid
import os
import datetime
import jwt
import bcrypt
from functools import wraps

# Force Flask to use the current folder for the database
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, instance_path=basedir)

# Security & DB Configurations
app.config['SECRET_KEY'] = 'prodigy_hotel_secret_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hotel_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- 1. USER TABLE ---
class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user') # 'admin' or 'user'
    
    bookings = db.relationship('Booking', backref='user', lazy=True)

# --- 2. ROOM TABLE ---
class Room(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_number = db.Column(db.String(10), unique=True, nullable=False)
    room_type = db.Column(db.String(50), nullable=False)
    price_per_night = db.Column(db.Float, nullable=False)
    
    bookings = db.relationship('Booking', backref='room', lazy=True)

    def to_dict(self):
        return {
            "id": self.id, 
            "room_number": self.room_number, 
            "room_type": self.room_type, 
            "price_per_night": self.price_per_night
        }

# --- 3. BOOKING TABLE ---
class Booking(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.String(36), db.ForeignKey('room.id'), nullable=False)
    
    check_in_date = db.Column(db.String(20), nullable=False)
    check_out_date = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Confirmed')

    def to_dict(self):
        return {
            "booking_id": self.id,
            "user_id": self.user_id,
            "room_id": self.room_id,
            "room_number": self.room.room_number, # Fetches automatically via backref!
            "check_in_date": self.check_in_date,
            "check_out_date": self.check_out_date,
            "status": self.status
        }

# Initialize the Database
with app.app_context():
    db.create_all()

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

# --- AUTHENTICATION ROUTES ---
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not all(k in data for k in ('name', 'email', 'password')):
        return jsonify({"error": "Missing required fields"}), 400
    
    hashed_pw = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    new_user = User(name=data['name'], email=data['email'], password=hashed_pw, role=data.get('role', 'user'))
    
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User registered successfully!"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    
    if user and bcrypt.checkpw(data['password'].encode('utf-8'), user.password.encode('utf-8')):
        token = jwt.encode(
            {'user_id': user.id, 'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)}, 
            app.config['SECRET_KEY'], 
            algorithm="HS256"
        )
        return jsonify({"token": token, "role": user.role, "message": "Login successful!"}), 200
        
    return jsonify({"error": "Invalid credentials!"}), 401

# --- ROOM MANAGEMENT ROUTES ---
@app.route('/rooms', methods=['POST'])
@token_required
def add_room(current_user):
    if current_user.role != 'admin':
        return jsonify({"error": "Admin access required to add rooms."}), 403
        
    data = request.get_json()
    if not data or not all(k in data for k in ('room_number', 'room_type', 'price_per_night')):
        return jsonify({"error": "Missing room details"}), 400
        
    if Room.query.filter_by(room_number=data['room_number']).first():
        return jsonify({"error": "Room number already exists!"}), 400
        
    new_room = Room(room_number=data['room_number'], room_type=data['room_type'], price_per_night=data['price_per_night'])
    db.session.add(new_room)
    db.session.commit()
    return jsonify({"message": f"Room {new_room.room_number} added successfully!"}), 201

@app.route('/rooms', methods=['GET'])
def get_rooms():
    rooms = Room.query.all()
    return jsonify([room.to_dict() for room in rooms]), 200

# --- NEW: BOOKING ENGINE ROUTES ---
@app.route('/bookings', methods=['POST'])
@token_required
def create_booking(current_user):
    data = request.get_json()
    if not data or not all(k in data for k in ('room_id', 'check_in_date', 'check_out_date')):
        return jsonify({"error": "Missing booking details"}), 400
        
    # Verify the room actually exists before booking it
    room = db.session.get(Room, data['room_id'])
    if not room:
        return jsonify({"error": "The requested room does not exist."}), 404
        
    # Create the relational link
    new_booking = Booking(
        user_id=current_user.id, # Extracted securely from the token bouncer
        room_id=data['room_id'],
        check_in_date=data['check_in_date'],
        check_out_date=data['check_out_date']
    )
    
    db.session.add(new_booking)
    db.session.commit()
    return jsonify({"message": "Room booked successfully!", "booking_details": new_booking.to_dict()}), 211

@app.route('/bookings', methods=['GET'])
@token_required
def get_bookings(current_user):
    # Smart Visibility: Admins see ALL bookings; regular users only see their own bookings
    if current_user.role == 'admin':
        all_bookings = Booking.query.all()
    else:
        all_bookings = Booking.query.filter_by(user_id=current_user.id).all()
        
    return jsonify([b.to_dict() for b in all_bookings]), 200

if __name__ == '__main__':
    app.run(debug=True, port=5001)
