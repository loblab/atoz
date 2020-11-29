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

DB_NAME = "atoz"
TAB_NAME = "score"

def init_db():
    global db
    host = "influxdb"
    port = 8086
    user = ""
    pswd = ""
    data = DB_NAME
    db = InfluxDBClient(host, port, user, pswd, data, timeout=5)

def close_db():
    global db
    db.close()

def write_db(points):
    global db
    db.write_points(points, time_precision='u')

def query_db(q):
    global db
    return db.query(q)

def count_db(cond):
    q = "select count(val) from %s where %s" % (TAB_NAME, cond)
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
def api_put_score():
    now = time.time()
    ts = int(now * 1e6)
    init_db()
    req = request.json
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    keys = req["keys"]
    resp = {}
    try:
        dur = save_score(ts, keys, req["durs"], ip)
        (rank, total) = query_rank(keys, dur)
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
    for i in range(len(durs)):
        key = keys[i:i+2]
        val = int(durs[i])
        total += val
        #app.logger.info("%s: %d ms", key, val)
        point = {
            "measurement": TAB_NAME,
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
        "measurement": TAB_NAME,
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

@app.route('/api/record/<key>', methods=['GET'])
def api_record(key):
    init_db()
    resp = {}
    try:
        ts, dur, durs = query_record(key)
        resp["status"] = "OK"
        resp["time"] = ts
        resp["dur"] = dur
        resp["keys"] = key
        resp["durs"] = durs
    except Exception as e:
        msg = str(e)
        app.logger.error(msg)
        resp["status"] = "ERR"
        resp["msg"] = msg
    close_db();
    return jsonify(resp)

def query_record(key):
    cond = "\"key\"='%s'" % key
    q = "select min(\"val\") as dur from %s where %s" % (TAB_NAME, cond)
    #app.logger.debug(q)
    r = query_db(q)
    points = r.get_points()
    for point in points:
        #app.logger.info(point)
        dur = point["dur"]
        ts = point["time"]
        durs = query_score(ts, key)
        return (ts, dur, durs)
    return 0

def query_score(ts, keys):
    cond = " \"time\"='%s'" % ts
    q = "select \"key\", \"val\" from %s where %s" % (TAB_NAME, cond)
    #app.logger.debug(q)
    r = query_db(q)
    points = r.get_points()
    tmp = {}
    for point in points:
        #app.logger.debug(point)
        dur = point["val"]
        key = point["key"]
        tmp[key] = dur
        #app.logger.debug("%s => %d" % (key, dur))
    #app.logger.debug(tmp)
    durs = []
    for i in range(len(keys) - 1):
        key = keys[i:i+2]
        val = tmp[key]
        durs.append(val)
    #app.logger.debug(durs)
    return durs

