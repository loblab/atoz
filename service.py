import os
import time
import os.path
from flask import Flask
from flask import send_file
from flask import jsonify, request
import logging
from influxdb import InfluxDBClient

app = Flask(__name__)
db = None
logging.basicConfig(level=logging.DEBUG)

def init_db():
    global db
    host = "influxdb"
    port = 8086
    user = ""
    pswd = ""
    data = "atoz"
    db = InfluxDBClient(host, port, user, pswd, data, timeout=5)

def close_db():
    global db
    db.close()

def write_db(points):
    global db
    db.write_points(points)

def query_db(q):
    global db
    return db.query(q)

def count_db(cond):
    q = "select count(val) from speed where %s" % cond
    #app.logger.info(q)
    r = query_db(q)
    points = r.get_points()
    for point in points:
        #app.logger.info(point)
        return point["count"]
    return 0

@app.route("/")
def main():
    return send_file('typespeed.htm')

@app.route('/favicon.ico')
def favicon():
    return send_file('favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route("/dev")
def dev_ver():
    return send_file('dev.htm')

@app.route('/api/debug', methods=['POST'])
def echo():
    req = request.json
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    req["ip"] = ip
    app.logger.info(req)
    return jsonify(req)

@app.route('/api/score', methods=['POST'])
def api_score():
    now = time.time()
    ts = int(now * 1e9)
    init_db()
    req = request.json
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    keys = req["keys"]
    resp = {}
    try:
        dur = save_score(ts, keys, req["durs"], ip)
        (rank, total) = query_rank(keys, dur)
        if rank == 1:
            save_record(ts, keys, dur, ip)
        resp["total"] = total
        resp["rank"] = rank
        resp["status"] = "OK"
    except Exception as e:
        msg = str(e)
        app.logger.error(msg)
        resp["status"] = "ERR"
        resp["msg"] = msg
    close_db()
    return jsonify(resp)


def save_score(ts, keys, durs, ip):
    points = []

    #app.logger.info(ip)
    #app.logger.info(keys)
    #app.logger.info(durs)
    total = 0
    for i in range(0, len(durs)):
        key = keys[i:i+2]
        val = int(durs[i])
        total += val
        #app.logger.info("%s: %d ms", key, val)
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

    #app.logger.info("%s: %d ms", keys, total)
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
    #app.logger.info(points)
    write_db(points)
    return total

def save_record(ts, keys, dur, ip):
    app.logger.info("Record of %s: %d ms", keys, dur)
    points = [{
        "measurement": "record",
        "time": ts,
        "tags": {
            "ip": ip,
            "key": keys
        },
        "fields": {
            "val": dur
        }
    }]
    write_db(points)

@app.route('/api/rank/<key>/<dur>', methods=['GET'])
def api_rank(key, dur):
    init_db()
    resp = {}
    try:
        (rank, total) = query_rank(key, dur)
        resp["status"] = "OK"
        resp["total"] = total
        resp["rank"] = rank
    except Exception as e:
        msg = str(e)
        app.logger.error(msg)
        resp["status"] = "ERR"
        resp["msg"] = msg
    close_db();
    return jsonify(resp)

def query_rank(key, dur):
    cond = "\"key\"='%s'" % key
    total = count_db(cond)
    cond += " and \"val\"<=%s" % dur
    rank = count_db(cond)
    return (rank, total)

