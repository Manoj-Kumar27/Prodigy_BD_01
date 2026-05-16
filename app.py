from flask import Flask, request, jsonify
import uuid
import re

app = Flask(__name__)

# Task 01 Requirement: In-memory data structure for storage
users = {}

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

    user_id = str(uuid.uuid4())
    new_user = {"id": user_id, "name": data['name'], "email": data['email'], "age": data['age']}
    users[user_id] = new_user
    
    return jsonify(new_user), 201

@app.route('/users', methods=['GET'])
def get_users():
    return jsonify(list(users.values())), 200

@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    user = users.get(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify(user), 200

@app.route('/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    if user_id not in users:
        return jsonify({"error": "User not found."}), 404

    data = request.get_json()
    user = users[user_id]

    if 'email' in data and not EMAIL_REGEX.match(data['email']):
        return jsonify({"error": "Invalid email format."}), 400
    if 'age' in data and (not isinstance(data['age'], int) or data['age'] < 0):
        return jsonify({"error": "Age must be a positive integer."}), 400

    user['name'] = data.get('name', user['name'])
    user['email'] = data.get('email', user['email'])
    user['age'] = data.get('age', user['age'])

    return jsonify(user), 200

@app.route('/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    if user_id not in users:
        return jsonify({"error": "User not found."}), 404

    del users[user_id]
    return jsonify({"message": "User deleted successfully."}), 200

if __name__ == '__main__':
    app.run(debug=True)