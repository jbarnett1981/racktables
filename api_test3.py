#!/usr/bin/python
'''
info here
'''
import hashlib
import pymysql
from flask import Flask, jsonify, abort, request, make_response, url_for
from flask_httpauth import HTTPBasicAuth

from sqlalchemy.orm import mapper, sessionmaker, clear_mappers
from sqlalchemy import create_engine, MetaData, Table, exc, text
# from sqlalchemy import *

rtables_host = 'racktables.example.lan'
rtables_db = 'racktables_db'
rtables_db_user = 'USERNAME'
rtables_db_pass = 'USERNAME'

api_version ='1.0'

# uri = 'mysql://%s:%s@%s/%s' % (rtables_db_user,rtables_db_pass, rtables_host, rtables_db)

# try:
#     db = create_engine(uri, pool_recycle=3600)
#     connection = db.connect()
#     print("Access granted for %s" % rtables_db_user)
# except exc.OperationalError as e:
#     if "Access denied" in e[0]:
#         print("Access denied for %s" % rtables_db_user)

# metadata = MetaData(db)

# objects = Table('Object', metadata, autoload=true)

def run(stmt):
    rs = stmt.execute()
    for row in rs:
        print row

class RObject(object):
        pass

# class ConnectMe:
#     '''
#     Connection to db
#     '''
#     def __init__(self):
uri = 'mysql://%s:%s@%s/%s' % (rtables_db_user,rtables_db_pass, rtables_host, rtables_db)
try:
    engine = create_engine(uri, pool_recycle=3600)
    connection = engine.connect()
    print("Access granted for %s" % rtables_db_user)
except exc.OperationalError as e:
    if "Access denied" in e[0]:
        print("Access denied for %s" % rtables_db_user)
metadata = MetaData(engine)
Objects = Table('Object', metadata, autoload=True)
mapper(RObject, Objects)
Session = sessionmaker(bind=engine)
session = Session()
# return session
def get_hostsa():
    res = session.query(RObject).all()
    clear_mappers()
    # res = session.query(RObject).all()
    items = [{ 'id':str(x.id), 'name': x.name, 'asset_no': x.asset_no} for x in res]
    return items
def get_hosta(host_id):
    s = Objects.select(Objects.c.id == host_id)
    run(s)
    # res = session.query(RObject).from_statement(text("select * from Object where id=:id")).params(id=str(host_id)).all()
    clear_mappers()
    # items = [{ 'id':str(x.id), 'name': x.name, 'asset_no': x.asset_no} for x in res]
    # return items

app = Flask(__name__)
auth = HTTPBasicAuth()

@auth.get_password
def get_password(username):
    db = pymysql.connect(host=rtables_host, user=rtables_db_user, passwd=rtables_db_pass, db=rtables_db)
    cur = db.cursor()
    cur.execute("""select user_name, user_realname from UserAccount where user_name=%s""", username)
    try:
        result = cur.fetchone()
        user = result[0]
        global realname
        realname = result[1]
    except TypeError:
        return None
    if username == user:
        cur.execute("""select user_password_hash from UserAccount where user_name=%s""", username)
        password_hash = cur.fetchone()[0]
        return password_hash
    return None

def make_public_host(host):
    new_host = {}
    for field in host:
        if field == 'id':
            new_host['uri'] = url_for('get_host', host_id=host['id'],
                                      _external=True)
            new_host['id'] = host['id']
        else:
            new_host[field] = host[field]
    return new_host

@auth.hash_password
def hash_pw(password):
    return hashlib.sha1(b'%s' % password).hexdigest()

@auth.error_handler
def unauthorized():
    # return 403 instead of 401 to prevent browsers from displaying the default
    # auth dialog
    return make_response(jsonify({'error': 'Unauthorized access'}), 403)

@app.errorhandler(400)
def bad_request(error):
    return make_response(jsonify({'error': 'Bad request'}), 400)


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

@app.route('/')
@auth.login_required
def index():
    return "Hello, %s!\n" % realname

@app.route('/api/v%s/hosts/' % api_version, methods=['GET'])
@auth.login_required
def get_hosts():
    hosts = get_hostsa()
    return jsonify({'hosts': [make_public_host(host) for host in hosts]})

@app.route('/api/v%s/hosts/<int:host_id>' % api_version, methods=['GET'])
@auth.login_required
def get_host(host_id):

    host = get_hosta(host_id)
    # host = [host for host in connect.get_hosts() if host['id'] == host_id]
    # if len(host) == 0:
    #     abort(404)
    return jsonify({'host': make_public_host(host)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
