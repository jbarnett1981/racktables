# racktables

# get_host_info.py: Standalone script used in the provisioning process to have a physical host verify its own serial number against racktables database and returns hostname and domain

# rstat.py

rstat 0.1
=====
author: Julian Barnett // jbarnett@tableausoftware.com

rstat is a command line tool to manage racktables via CLI.

Pre-Requisites:

You must install the following modules (available via pip). Script will fail without these:

rac (pip install rac) - to be able to use the DRAC capabilities.

pymysql (pip install pymysql) - to be able to query the racktables db for unsupported API features.


Manage credentials and server details via creds.json. Update this with your info and place this file in the following directory:

~/.rstat/creds.json (unix)

or

C:\Users\%USERNAME%\AppData\Local\rstat (Windows 2008 R2+)


```
{"creds": {
    "user": {
        "username": "USERNAME",
        "password": "PASSWORD"
    },
    "racinfo": {
        "racuser": "USERNAME",
        "racpass": "PASSWORD"
    },
    "racktables": {
        "server": "racktables.dev.tsi.lan",
        "db_user": "guest",
        "db_pass": "guest",
        "db": "racktables_db"
    }
}}
```

Type rstat --help for more information.
