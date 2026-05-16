from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import uuid
import re
import os

# Force Flask to use the current folder instead of trying to navigate Windows paths
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, instance_path=basedir)

# Configure the SQLite database connection
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database
db = SQLAlchemy(app)

# Define our Database Table (Task 02 Requirement: Persistent Storage)
class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    age = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "age": self.age}

# Create the table when the app starts
with app.app_context():
    db.create_all()

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    if not data or not all(k in data for k in ('name', 'email', 'age')):
        return jsonify({"error": "Missing required fields."}), 400
    if not EMAIL_REGEX.match(data['email']):
        return jsonify({"error": "Invalid email format."}), 400
    if not isinstance(data['age'], int) or data['age'] < 0:
        return jsonify({"error": "Age must be a positive integer."}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email already exists."}), 400

    new_user = User(name=data['name'], email=data['email'], age=data['age'])
    db.session.add(new_user)
    db.session.commit()
    return jsonify(new_user.to_dict()), 201

@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users]), 200

@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify(user.to_dict()), 200

@app.route('/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    data = request.get_json()
    
    if 'email' in data and not EMAIL_REGEX.match(data['email']):
        return jsonify({"error": "Invalid email format."}), 400
    if 'age' in data and (not isinstance(data['age'], int) or data['age'] < 0):
        return jsonify({"error": "Age must be a positive integer."}), 400

    user.name = data.get('name', user.name)
    user.email = data.get('email', user.email)
    user.age = data.get('age', user.age)
    db.session.commit()
    return jsonify(user.to_dict()), 200

@app.route('/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted successfully."}), 200

if __name__ == '__main__':
    app.run(debug=True)
