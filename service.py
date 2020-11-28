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

@app.route('/api/score', methods=['POST'])
def api_score():
    req = request.json
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    resp = {}
    try:
        save_score(req["keys"], req["score"], ip)
        resp["status"] = "OK"
    except Exception as e:
        msg = str(e)
        app.logger.error(msg)
        resp["status"] = "ERR"
        resp["msg"] = msg
    return jsonify(resp)

from influxdb import InfluxDBClient

def save_score(keys, score, ip):
    host = "influxdb"
    port = 8086
    user = ""
    pswd = ""
    data = "atoz"
    db = InfluxDBClient(host, port, user, pswd, data, timeout=5)

    now = time.time()
    ts = int(now * 1e9)
    points = []

    app.logger.info(ip)
    app.logger.info(keys)
    app.logger.info(score)
    total = 0
    for i in range(0, len(score)):
        key = keys[i:i+2]
        val = score[i]
        total += val
        app.logger.info("%s: %d ms", key, val)
        point = {
            "measurement": "speed",
            "time": ts,
            "tags": {
                "ip": ip,
                "key": key
            },
            "fields": {
                "val": val
            }
        }
        points.append(point)

    app.logger.info("%s: %d ms", keys, total)
    point = {
        "measurement": "speed",
        "time": ts,
        "tags": {
            "ip": ip,
            "key": keys
        },
        "fields": {
            "val": total
        }
    }
    points.append(point)
    app.logger.info(points)
    db.write_points(points)
    db.close()

