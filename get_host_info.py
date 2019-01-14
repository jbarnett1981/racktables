#!/usr/bin/python
"""
Created `01/05/2015 01:06`
@author jbarnett@tableausoftware.com
@version 0.1

get_hostname.py: standalone script that grabs serial number from machine and returns hostname from racktables
"""
import re
import urllib
import json
import subprocess
import platform
import argparse
import pymysql
import random
import string

username = "USERNAME"
password = "PASSWORD"

db_host = 'host.example.lan'
db_name = 'racktables_db'
db_username = 'USERNAME'
db_password = 'PASSWORD'

class Rtables:
    def __init__(self, username, password, api="https://racktables.dev.tsi.lan/api.php"):
        self.username = username
        self.password = password
        # inject username and password if given
        if username is not None and password is not None:
            m = re.search('^(https?://)(.*)$', api)
            api             = m.group(1) + username + ':' + password + '@' + m.group(2)
            no_password_api = m.group(1) + username + ':*PASSWORD*@'       + m.group(2)

        self.api             = api
        self.no_password_api = no_password_api

    def get_hostname_from_serial_db(self, serial_num):
        '''
        Gets the hostname and id in racktables from the serial number
        '''
        db = pymysql.connect(host=db_host, user=db_username, passwd=db_password, db=db_name)
        cur = db.cursor()
        #cur.execute("""select name from tab_devit_custom_full where serial_no = %s""", serial_num)
        cur.execute("""select t1.id, t1.name from Object t1 left join AttributeValue t2 on t1.id=t2.object_id where t2.attr_id=1 and t2.string_value=%s""", serial_num)
        result = cur.fetchone()
        return result

    def get_domain_from_serial_db(self, host_id):
        '''
        Retrieves the domain for a particular host id
        '''
        db = pymysql.connect(host=db_host, user=db_username, passwd=db_password, db=db_name)
        cur = db.cursor()
        cur.execute("""select t2.dict_value from AttributeValue t1 left join Dictionary t2 on t1.uint_value=t2.dict_key where t1.object_id=%s and t1.attr_id=10002""", host_id)
        result = cur.fetchone()
        try:
            return result[0]
        except TypeError:
            return "tsi.lan"


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def get_serial():
    '''
    get serial number from OS
    '''
    operating_system = platform.system()
    if operating_system == "Darwin":
        serial_num = subprocess.check_output("ioreg -l | awk '/IOPlatformSerialNumber/ { print $4;}'", shell=True)
        return serial_num.strip("\n")[1:-1].upper()

    elif operating_system == "Windows":
        pass #not yet implemented

    elif operating_system == "Linux":
        serial_num = subprocess.Popen(['dmidecode', '-s', 'system-serial-number'], stdout=subprocess.PIPE)
        sn = serial_num.communicate()[0].strip("\n").upper()
        if sn == 'NOT SPECIFIED' or 'vmware' in sn.lower():
            return 'openvm-' + id_generator()
        else:
            return sn


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='%(prog)s help')
    parser.add_argument("--get_hostname", action="store_true", help="get hostname")
    parser.add_argument("--get_domainname", action="store_true", help="get domain name")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1")

    args = vars(parser.parse_args())

    rt = Rtables(username, password)
    serial_num = get_serial()
    host_info = rt.get_hostname_from_serial_db(serial_num)

    if args['get_hostname']:
        if host_info == None:
            hostname = serial_num
        else:
            hostname = host_info[1]
        print(hostname)
    if args['get_domainname']:
        if host_info == None:
            domain = "tsi.lan"
        else:
            host_id = host_info[0]
            domain = rt.get_domain_from_serial_db(host_id)
        print(domain)
