from flask import Blueprint, jsonify


services = Blueprint("services", __name__)

@services.route('/api/')
def ping():
    return jsonify({'ping': 'pong'}, 200)

@services.route('/api/health/<message>')
def health(message):
    return jsonify({'response': message}, 200)