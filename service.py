import os
import time
import os.path
from flask import Flask
from flask import send_file

app = Flask(__name__)

@app.route("/")
def main():
    return send_file('typespeed.htm')

@app.route('/favicon.ico')
def favicon():
    return send_file('favicon.ico', mimetype='image/vnd.microsoft.icon')

