import os
import time
import os.path
from flask import Flask
from flask import send_file
from flask import jsonify, request
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

@app.route("/")
def main():
    return send_file('typespeed.htm')

@app.route('/favicon.ico')
def favicon():
    return send_file('favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/debug', methods=['POST'])
def echo():
    req = request.json
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    req["ip"] = ip
    app.logger.info(req)
    return jsonify(req)

@app.route('/score', methods=['POST'])
def api_score():
    req = request.json
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    save_score(req["keys"], req["score"], ip)
    return jsonify(req)

def save_score(keys, score, ip):
    app.logger.info(ip)
    app.logger.info(keys)
    app.logger.info(score)
    total = 0
    for i in range(0, len(score)):
        key = keys[i:i+2]
        val = score[i]
        total += val
        app.logger.info("%s: %d ms", key, val)
    app.logger.info("%s: %d ms", keys, total)

