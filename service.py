import os
import time
import os.path
from flask import Flask
from flask import send_file
from flask import jsonify, request
import logging
from influxdb import InfluxDBClient
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
db = None
logging.basicConfig(level=logging.WARNING)

DB_NAME = "atoz"
TAB_NAME = "score"
RECENT = "1d"

TIME_FILTER = " and time > now() - %s" % RECENT

# App is behind one proxy that sets the -For and -Host headers.
#app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)
# https://flask.palletsprojects.com/_/downloads/en/1.1.x/pdf/
app.wsgi_app = ProxyFix(app.wsgi_app)

def open_db():
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
    r = query_db(q)
    points = r.get_points()
    for point in points:
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
    return jsonify(req)

@app.route('/api/score', methods=['POST'])
def api_put_score():
    now = time.time()
    ts = int(now * 1e6)
    open_db()
    req = request.json
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    ua = request.user_agent.string
    keys = req["keys"]
    resp = {}
    try:
        dur = save_score(ts, keys, req["durs"], ip, ua)
        (rank, samples) = query_rank(keys, dur)
        record = query_record(keys)
        #limit = stat_keys("min", keys)
        latest = query_latest(keys, ip, ua, ts * 1000)
        resp["samples"] = samples
        resp["rank"] = rank
        resp["record"] = record
        resp["latest"] = latest
        #resp["limit"] = limit
        resp["status"] = "OK"
    except Exception as e:
        msg = str(e)
        app.logger.error(msg)
        resp["status"] = "ERR"
        resp["msg"] = msg
    close_db()
    return jsonify(resp)

def save_score(ts, keys, durs, ip, ua):
    if len(keys) != len(durs) + 1:
        raise ValueError("Invalid data")
    if len(keys) < 3:
        raise ValueError("Too short data")
    points = []

    total = 0
    for i in range(len(durs)):
        key = keys[i:i+2]
        val = int(durs[i])
        total += val
        point = {
            "measurement": TAB_NAME,
            "time": ts,
            "tags": {
                "key": key,
                "ip": ip
            },
            "fields": {
                "val": val
            }
        }
        points.append(point)

    point = {
        "measurement": TAB_NAME,
        "time": ts,
        "tags": {
            "key": keys,
            "ip": ip,
            "ua": ua
        },
        "fields": {
            "val": total
        }
    }
    points.append(point)
    write_db(points)
    return total

@app.route('/api/rank/<key>/<dur>', methods=['GET'])
def api_rank(key, dur):
    open_db()
    resp = {}
    try:
        (rank, samples) = query_rank(key, dur)
        resp["status"] = "OK"
        resp["samples"] = samples
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
    cond += TIME_FILTER
    total = count_db(cond)
    cond += " and \"val\"<=%s" % dur
    rank = count_db(cond)
    return (rank, total)

@app.route('/api/record/<key>', methods=['GET'])
def api_record(key):
    open_db()
    resp = {}
    try:
        durs = query_record(key)
        resp["status"] = "OK"
        resp["keys"] = key
        resp["durs"] = durs
        resp["dur"] = sum(durs)
    except Exception as e:
        msg = str(e)
        app.logger.error(msg)
        resp["status"] = "ERR"
        resp["msg"] = msg
    close_db();
    return jsonify(resp)

def query_record(key):
    cond = "\"key\"='%s'" % key
    cond += TIME_FILTER
    q = "select min(\"val\") as dur from %s where %s" % (TAB_NAME, cond)
    r = query_db(q)
    points = r.get_points()
    for point in points:
        dur = point["dur"]
        ts = point["time"]
        durs = query_score(ts, key)
        return durs
    return None

@app.route('/api/latest/<key>', methods=['GET'])
def api_latest(key):
    open_db()
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    ua = request.user_agent.string
    resp = {}
    try:
        durs = query_latest(key, ip, ua)
        resp["status"] = "OK"
        resp["keys"] = key
        resp["durs"] = durs
    except Exception as e:
        msg = str(e)
        app.logger.error(msg)
        resp["status"] = "ERR"
        resp["msg"] = msg
    close_db();
    return jsonify(resp)

def query_latest(key, ip, ua, now=None):
    cond = "\"key\"='%s' and \"ip\"='%s' and \"ua\"='%s'" % (key, ip, ua)
    if now is not None:
        cond += " and \"time\" < %d" % now
    cond += TIME_FILTER
    only1 = "order by time desc limit 1"
    q = "select val from %s where %s %s" % (TAB_NAME, cond, only1)
    r = query_db(q)
    points = r.get_points()
    for point in points:
        dur = point["val"]
        ts = point["time"]
        durs = query_score(ts, key)
        return durs
    return None

def query_score(ts, keys):
    cond = " \"time\"='%s'" % ts
    q = "select \"key\", \"val\" from %s where %s" % (TAB_NAME, cond)
    r = query_db(q)
    points = r.get_points()
    tmp = {}
    for point in points:
        dur = point["val"]
        key = point["key"]
        tmp[key] = dur
    durs = []
    for i in range(len(keys) - 1):
        key = keys[i:i+2]
        val = tmp[key]
        durs.append(val)
    return durs

def stat_key(func, key):
    cond = "\"key\"='%s'" % key
    q = "select %s(\"val\") as dur from %s where %s" % (func, TAB_NAME, cond)
    r = query_db(q)
    points = r.get_points()
    for point in points:
        dur = point["dur"]
        return dur
    return None

def stat_keys(func, keys):
    durs = []
    for i in range(len(keys) - 1):
        key = keys[i:i+2]
        val = stat_key(func, key)
        durs.append(val)
    return durs

@app.route('/api/<func>/<key>', methods=['GET'])
def api_stat(func, key):
    open_db()
    resp = {}
    try:
        durs = stat_keys(func, key)
        resp["status"] = "OK"
        resp["keys"] = key
        resp["durs"] = durs
        resp["dur"] = sum(durs)
    except Exception as e:
        msg = str(e)
        app.logger.error(msg)
        resp["status"] = "ERR"
        resp["msg"] = msg
    close_db();
    return jsonify(resp)
