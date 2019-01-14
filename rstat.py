#!/usr/bin/python

'''
Created `06/05/2014 11:57`
Updated `11/02/2015 02:36`

@author jbarnett@tableau.com
@version 0.3

rstat.py: add, update, import, delete and query hosts from Racktables.

TODO:

1. convert all crappy php API functions to use mysql db instead - 1/2 complete
2. Fix query for location so it returns nested Location (i.e. if location is Cage B02, should also return Internap SEF003 as parent location)
3. Fix issue where some uint_values for attr_id=2 in AttributeValue table contain values for Server OS type (chapter_id=13) instead of chapter_id=11
4. create --cleartags option for hosts
'''
import sys
from nstat import StartConnect, parse_regex, get_ip

from racktables_api import RacktablesClient, RacktablesClientException
from getpass import getpass
import platform, json, rac, argparse, re, base64, pymysql, csv, os, urllib2, pdb, paramiko, socket
from colorama import Fore, init
from datetime import datetime

def print_ok(string, var):
    print(string + ":\t" + Fore.GREEN + var).expandtabs(12)

def main():
    # Enable printing color reset after each print
    init(autoreset=True)

    args = usage()

    try:
        if args['name']:
            args['name'] = args['name'].lower() ##convert incoming names to lowercase, to match the host names returned from all the functions in the Rtables class
    except KeyError:
        pass

    # List of Mac hostname prefixes
    apple_prefixes = ['dvbldpm', 'dvatompm', 'infrabuildmac', 'dvbvtpm', '1krkdvpmbld']

    if args['which'] == 'query':
        if args['name']:
            # create Rtables object
            rt = Rtables()
            hosts = rt.get_wildcard_hosts(args['name'])
            for host in hosts:
                #create vars
                try:
                    host_id = rt.get_id(host)
                    status = rt.get_host_status(host_id)
                    cabinet_info = rt.get_cabinet_info(host_id)
                    serial_no = rt.get_serial_num(host_id)
                    hw_type = rt.get_hwtype(host_id)
                    OS = rt.get_ostype(host_id)
                    cabinet = cabinet_info[0]
                    location = cabinet_info[3]
                    row = cabinet_info[2]
                    RU = cabinet_info[1]
                    port_info = rt.get_port_info(host_id)

                    #print the stuff
                    print
                    print_ok("Hostname", host)
                    print_ok("Status", str(status))
                    print_ok("Serial No", serial_no)
                    print_ok("Hardware", hw_type)
                    print_ok("OS", OS)
                    print_ok("Location", location)
                    print_ok("Cabinet", cabinet)
                    print_ok("Row", row)
                    print_ok("RU", str(RU))
                    print
                    print("Ports:")
                    for port in port_info:
                        if port_info[port][3] == "0":
                            print(Fore.GREEN + port + Fore.RESET + "\t" + "unlinked")
                        else:
                            print(Fore.GREEN + port + Fore.RESET + "\t" + "remote: " + Fore.GREEN + port_info[port][1] + Fore.RESET + "   remote port: " + Fore.GREEN + port_info[port][2] + Fore.RESET)
                except KeyError:
                    print("Host: " + Fore.RED + "{0}".format(host) + Fore.RESET + " does not exist.")

        elif args['rack_info']:
            # open Racktables API connection with your credentials
            rt = Rtables()
            rack_info = rt.get_rack_info(args['rack_info'])
            for k,v in rack_info.items():
                print("RU: " + Fore.GREEN + "{0}".format(str(k)) + Fore.RESET + " Hostname: " + Fore.GREEN + "{0}".format(v['hostname']) + Fore.RESET + " Serial Number: " + Fore.GREEN + "{0}".format(v['serial_num']) + Fore.RESET)

        elif args['serial_num']:
            # open Racktables API connection with your credentials
            rt = Rtables()
            hostname = rt.get_hostname(args['serial_num'])
            print(hostname)


    elif args['which'] == 'update':
        # open Racktables API connection with your credentials
        rt = Rtables()
        realpath = os.path.dirname(os.path.realpath(__file__))
        if args['csv']:
            # open file and read in hostnames
            hosts = [line.rstrip('\n') for line in open(args['csv'])]
            for host in hosts:
                try:
                    if any(k in host for k in apple_prefixes):
                        print("\nAcquiring serial number for Mac server: {0}...".format(host))
                        serial_num = rt.get_mac_serial(host)

                    else:
                        racname = host + "-drac.dev.tsi.lan"
                        print("\nAcquiring asset tag for Dell host: {0}...".format(host))
                        racadm = racConnect(racname, rt.drac_user, rt.drac_pass, certfile=realpath + "/certs/dvcertauth.pem")
                        serial_num = racadm.get_tag()
                        rid = rt.get_id(host)
                        rt.update_serial_num(rid, serial_num)
                    print("\nHostname: " + Fore.GREEN + "{0}".format(host) + Fore.RESET)
                    print("Asset Tag: " + Fore.GREEN + "{0}\n".format(serial_num) + Fore.RESET)
                except urllib2.URLError:
                    print("Cannot resolve hostname")

        elif args['name'] and not args['tags'] and not args['link_port'] and not args['add_port'] and not args['unlink_port'] and not args['del_port'] and not args['serial_num'] and not args['status']:
            hosts = rt.get_wildcard_hosts(args['name'])
            for host in hosts:
                try:
                    if any(k in host for k in apple_prefixes):
                        print("\nAcquiring serial number for Mac server: {0}...".format(host))
                        serial_num = rt.get_mac_serial(host)

                    else:
                        print("\nAcquiring asset tag for Dell host: {0}...".format(host))
                        racname = host + "-drac.dev.tsi.lan"
                        racadm = racConnect(racname, rt.drac_user, rt.drac_pass, certfile=realpath + "/certs/dvcertauth.pem")
                        serial_num = racadm.get_tag()
                    rid = rt.get_id(host)
                    rt.update_serial_num(rid, serial_num)
                    print("\nHostname: " + Fore.GREEN + "{0}".format(host) + Fore.RESET)
                    print("Asset Tag: " + Fore.GREEN + "{0}\n".format(serial_num) + Fore.RESET)
                except urllib2.URLError as e:
                    print("Cannot resolve hostname: {0}".format(e[0][1]))

        elif args['name'] and args['tags']:
            hosts = rt.get_wildcard_hosts(args['name'])
            taglist = [tag.strip() for tag in args['tags'].split(",")]
            for host in hosts:
                hostid = rt.get_id(host)
                updated = rt.set_object_tags(hostid, taglist, args['replace'])
                if len(updated[1]) > 0:
                    print("The following tags don't exist and cannot be assigned: " + Fore.RED + "{0}".format(', '.join(updated[1])) + Fore.RESET)
                if len(updated[0]) > 0:
                    print("Successfully updated tags " + Fore.GREEN + "{0}".format(', '.join(updated[0])) + Fore.RESET)
                if len(updated[2]) > 0:
                    print("The following tags already exists: " + Fore.YELLOW + "{0}".format(', '.join(updated[2])) + Fore.RESET)


        elif args['name'] and args['link_port']:
            hostname = args['name']
            interface = args['link_port'][0]
            remote_device = args['link_port'][1]
            remote_int = args['link_port'][2]
            rt.set_linked_port(rt, hostname, interface, remote_device, remote_int)

        elif args['name'] and args['unlink_port']:
            hosts = rt.get_wildcard_hosts(args['name'])
            port_name = args['unlink_port']
            for host in hosts:
                rt.unlink_port(rt, host, port_name)


        elif args['name'] and args['add_port']:
            hosts = rt.get_wildcard_hosts(args['name'])
            port = args['add_port']
            for host in hosts:
                rt.add_port(host, port, port_type="24")

        elif args['name'] and args['del_port']:
            hosts = rt.get_wildcard_hosts(args['name'])
            port = args['del_port']
            for host in hosts:
                rt.del_port(host, port)

        elif args['name'] and args['serial_num']:
            hosts = rt.get_wildcard_hosts(args['name'])
            serial_num = args['serial_num']
            for host in hosts:
                hostid = rt.get_id(host)
                rt.update_serial_num(hostid, serial_num)
                print("Successfully updated serial number on " + Fore.GREEN + "{0}".format(host) + Fore.RESET + " to " + Fore.BLUE + "{0}".format(serial_num) + Fore.RESET)

        elif args['name'] and args['status']:
            hosts = rt.get_wildcard_hosts(args['name'])
            status = args['status']
            for host in hosts:
                hostid = rt.get_id(host)
                rt.set_status(hostid, status)
                print("Successfully updated status to " + Fore.GREEN + "{0}".format(host) + Fore.RESET + " to " + Fore.BLUE + "{0}".format(status) + Fore.RESET)



    elif args['which'] == 'import':
        if args['csv']:
            # open Racktables API connection with your credentials
            rt = Rtables()
            f = open(args['csv'], "r")
            reader = csv.reader(f, delimiter=',')
            reader.next() #skip first commented header row
            for row in reader:
                hostname = row[0].lower()
                asset_tag = row[1]
                domain = row[2]
                datacenter = row[3]
                drow = row[4]
                cabinet = row[5]
                rack_loc = int(row[6])
                hw_type = row[7]
                tags = row[8]
                contact = row[9]
                operating_system = row[10]
                height = int(row[11])
                switch_name = row[12]
                switch_port = row[13]
                vlan = row[14]
                comments = row[15]
                fqdn = hostname+"."+domain
                if any(k in hostname for k in apple_prefixes):
                    dracfqdn = None
                else:
                    dracfqdn = hostname+"-drac.dev.tsi.lan"
                # Get domain ID
                domainid = rt.get_domain_id(domain)
                # Add server to racktables
                try:
                    host_id = rt.add_server(name=hostname, asset_tag=asset_tag, obj_type=4, hw_type=hw_type, os=operating_system, fqdn=fqdn, dracfqdn=dracfqdn, contact=contact, datacenter=datacenter, tags=tags, cabinet=cabinet, rack_loc=rack_loc, height=height, domain=domainid)
                    print("Successfully added " + Fore.GREEN + "{0}".format(hostname) + Fore.RESET + " to Racktables...\n")
                except TypeError as e:
                    print(e)
                    #print("The host already exists or the asset tag is already in use.")
                # Configure switch port if specified
                if switch_name is not "0":
                    cisco_username = raw_input("Enter cisco username: ")
                    cisco_password = getpass("enter cisco password: ")
                    conns = StartConnect(cisco_username, cisco_password)
                    conns.client_connect(switch_name)
                    shell = conns.connections[0].invoke_shell()
                    router_shell_output = shell.recv(1000)
                    conns.disable_paging(shell)
                    shell.settimeout(30)
                    conns.client_int_conf(shell, switch_port, hostname, vlan)
                    if conns.connections:
                        for conn in conns.connections:
                            conn.close()

                if comments is not "0":
                    rt.add_comments(host_id, comments)

            f.close() #close file


    elif args['which'] == 'link':
        #print("test")
        # open Racktables API connection with your credentials
        rt = Rtables()
        rt.link_objects(args['child'], args['parent']) #still need to put some error checking in here
        print("Successfully linked " + Fore.GREEN + "{0}".format(args['child']) + Fore.RESET + " to " + Fore.GREEN + "{0}".format(args['parent']) + Fore.RESET + "\n")


    elif args['which'] == 'add':
        # open Racktables API connection with your credentials
        rt = Rtables()
        fqdn = args['name'] + "." + args['domain']
        # Get domain ID
        domainid = rt.get_domain_id(args['domain'])
        status_id = rt.get_status_id(args['status'])
        if any(k in args['name'] for k in apple_prefixes):
            dracfqdn = None
        else:
            dracfqdn = "idrac-" + args['asset_tag'] + ".dev.tsi.lan"
        try:
            host_id = rt.add_server(name=args['name'], asset_tag=args['asset_tag'], obj_type=args['obj_type'], hw_type=args['hw_type'], os=args['os'], fqdn=fqdn, dracfqdn=dracfqdn, contact=args['contact'], datacenter=args['datacenter'], tags=args['tags'], cabinet=args['cabinet'], rack_loc=args['rack_loc'], height=args['height'], domain=domainid, status=status_id)
            print("Successfully added " + Fore.GREEN + "{0}".format(args['name']) + Fore.RESET + " to Racktables...\n")
        except TypeError as e:
            print(e)


    elif args['which'] == 'delete':
        # open Racktables API connection with your credentials
        rt = Rtables()
        hosts = rt.get_wildcard_hosts(args['name'])
        for host in hosts:
            try:
                host_id = rt.get_id(host)
                rt.delete_server(host_id)
                print("Successfully deleted " + Fore.GREEN + "{0}".format(host) + Fore.RESET + " from Racktables\n")
            except KeyError:
                    print("Host: " + Fore.RED + "{0}".format(host) + Fore.RESET + " does not exist.")

    elif args['sync_tags']:
        # open Racktables API connection with your credentials
        rt = Rtables()
        # do stuff
        print("This may take awhile...")
        for id in rt.depot:
            hostname = str(rt.depot[id]['name'])
            oldtag = rt.get_custom_tag(rtables_host, rtables_db_user, rtables_db_pass, rtables_db, hostname)
            if oldtag != None:
                rt.update_serial_num(id, oldtag)
                print("Updated {0}\n".format(hostname))

class racConnect:
    def __init__(self, dracname, drac_user, drac_pass, certfile=None):
        self.admin = rac.RAC(dracname, drac_user, drac_pass, certfile)

    def get_tag(self):
        '''
        Returns the Dell Service Tag for a given hostname.
        '''
        return self.admin.run_command("getsvctag")

class Rtables:
    def __init__(self):
        # determine OS type and create config dir
        operating_system = platform.system()
        home_dir = os.path.expanduser("~")
        if operating_system == "Darwin" or operating_system == "Linux":
            config_dir = home_dir + "/.rstat/"

        elif operating_system == "Windows":
            config_dir = home_dir + "\\AppData\\Local\\rstat\\"

        config_file = config_dir + "creds.json"

        #collect credentials from config file
        cred_data = json.loads(open(config_file).read())
        self.username = cred_data['creds']['user']['username']
        self.password = cred_data['creds']['user']['password']
        self.rtables_host = cred_data['creds']['racktables']['server']
        self.rtables_api = "https://" + cred_data['creds']['racktables']['server'] + "/api.php"
        self.rtables_db_user = cred_data['creds']['racktables']['db_user']
        self.rtables_db_pass = cred_data['creds']['racktables']['db_pass']
        self.rtables_db = cred_data['creds']['racktables']['db']
        self.drac_user = cred_data['creds']['racinfo']['racuser']
        self.drac_pass = cred_data['creds']['racinfo']['racpass']
        self.admin = RacktablesClient(self.rtables_api, username=self.username, password=self.password)

    def get_domain_id(self, domainname):
        '''
        Retrieves the racktables ID for a particular domain name
        '''
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select dict_key from Dictionary where chapter_id=10002 and dict_value=%s""", domainname)
        result = cur.fetchone()
        try:
            return int(result[0])
        except TypeError:
            #return "tsi.lan" by default
            return 50056

    def get_id(self, hostname):
        '''
        Returns the racktables object id for a given hostname.
        '''
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select id from Object where name=%s""", hostname)
        result = cur.fetchone()
        try:
            return int(result[0])
        except TypeError:
            #return "None" if host doesn't exist
            return None

    def get_wildcard_hosts(self, wildcardstring):
        '''
        Returns the hostnames matching a hostname wildcard as a list
        '''
        if not "*" in wildcardstring and not '%' in wildcardstring and not '?' in wildcardstring and not '_' in wildcardstring:
            host = wildcardstring
        else:
            host = wildcardstring.replace('*', '%')
            host = host.replace('?', '_')

        hosts = []
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select name from Object where name like %s""", host)
        result = cur.fetchall()
        for host in sorted(result):
            hosts.append(host[0])
        return hosts

    def get_hostname(self, serial_num):
        '''
        Returns the object hostname for a given serial number.
        '''
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select t1.name from Object t1 left join AttributeValue t2 on t1.id=t2.object_id where t2.string_value = %s and t2.attr_id=1""", serial_num)
        result = cur.fetchone()[0]
        return result

    def get_serial_num(self, hostid):
        '''
        Returns the "OEM S/N - Service Tag" custom field for a given hostname.
        '''
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select string_value from AttributeValue where object_id = %s and attr_id = 1""", hostid)
        try:
            return cur.fetchone()[0]
        except TypeError:
            return "None"

    def get_mac_serial(self, hostname):
        '''
        SSH to host and execute remote command to get serial number in OSX
        '''
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname, username="it", password="k9isa2th")
            stdin, stdout, stderr = client.exec_command("ioreg -l | awk '/IOPlatformSerialNumber/ { print $4;}'")
            serialnum = stdout.readlines()
            return serialnum[0].strip("\n")[1:-1]
        except socket.error as e:
            print(e)

    def get_cabinet_info(self, hostid):
        '''
        Returns the cabinet #, RU# and row name of a hostname in the rack.
        '''
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select distinct t1.name, unit_no, row_name, t3.name as location_name from Rack t1 left join RackSpace t2 on t1.id=t2.rack_id left join Location t3 on t1.location_id=t3.id where t2.object_id=%s""", hostid)
        cab_info = cur.fetchone()
        if cab_info != None:
            return cab_info
        else:
            return ("None", "None", "None", "None")

    def get_rack_info(self, rackid):
        '''
        Returns a list of assets in a particular rack.
        '''
        rack_data = {}
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select distinct(t2.unit_no), t1.id, t1.name from Object t1 left join RackSpace t2 on t1.id=t2.object_id where t2.rack_id = %s""", rackid)
        rack_info = cur.fetchall()
        for hostid in rack_info:
            host_id = hostid[1]
            hostname = hostid[2]
            serial_num = self.get_serial_num(host_id)
            RU = hostid[0]
            rack_data[RU] = {'hostname': hostname, 'serial_num': serial_num}
        return rack_data

    def get_hwtype(self, hostid):
        '''
        Returns the hardware type of a particular hostname.
        '''
        hw_type = ""
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select distinct t4.dict_value hw_type from Object t1 left join AttributeValue t2 on t1.id=t2.object_id left join TagStorage t3 on t1.id=t3.entity_id left join Dictionary t4 on t2.uint_value=t4.dict_key where t1.id=%s and t2.attr_id=2""", hostid)
        try:
            hw_type = cur.fetchone()[0]
            return hw_type
        except TypeError:
            return "None"

    def get_ostype(self, hostid):
        '''
        Returns the OS type of a particular hostname.
        '''
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select t2.dict_value os_type from AttributeValue t1 left join Dictionary t2 on t1.uint_value=t2.dict_key where t1.attr_id=4 and t1.object_id=%s""", hostid)
        try:
            ostype = cur.fetchone()[0]
            return ostype
        except TypeError:
            return "None"

    def get_host_status(self, hostid):
        '''
        Returns the Status for a particular hostname.
        '''
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select t2.dict_value status from AttributeValue t1 left join Dictionary t2 on t1.uint_value=t2.dict_key where t1.attr_id=10005 and t1.object_id=%s""", hostid)
        try:
            status = cur.fetchone()[0]
            return status
        except TypeError:
            return None

    def get_status_id(self, statusname):
        '''
        Returns the status ID for a given string in the Dictionary.
        '''
        # Get the dict_key for the desired status
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select dict_key from Dictionary where chapter_id=10003 and dict_value=%s""", statusname)
        try:
            status_id = cur.fetchone()[0]
            return status_id
        except TypeError:
            return None

    def set_status(self, hostid, statusname):
        '''
        Sets the Status for a particular hostname.
        '''
        # Get Status ID
        status_id = self.get_status_id(statusname)
        # Get status: if None insert record, otherwise update existing
        try:
            status_exists = self.get_host_status(hostid)
        except TypeError:
            pass
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        if status_exists == None:
            cur.execute("""insert into AttributeValue (object_id, object_tid, attr_id, string_value, uint_value, float_value) values (%s,4,10005,NULL,%s,NULL) on duplicate key update object_id=object_id""", (hostid, status_id))
        else:
            cur.execute("""update AttributeValue set uint_value=%s where attr_id=10005 and object_id=%s""", (status_id, hostid))
        db.commit()
        cur.close()


    def update_serial_num(self, hostid, serial_num):
        '''
        Update the serial number of a given host id.
        '''
        #self.admin.edit_object(id, object_name=hostname, object_asset_no=asset_tag)
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select string_value from AttributeValue where attr_id=1 and object_id=%s""", hostid)
        try:
            serial_exists = cur.fetchone()[0]
        except TypeError:
            serial_exists = False
        if serial_exists == False:
            cur.execute("""insert into AttributeValue (object_id, object_tid, attr_id, string_value, uint_value, float_value) values (%s,4,1,%s,NULL,NULL) on duplicate key update object_id=object_id""", (hostid, serial_num))
        else:
            cur.execute("""update AttributeValue set string_value=%s where attr_id=1 and object_id=%s""", (serial_num, hostid))
        db.commit()
        cur.close()

    def add_comments(self, host_id, comments):
        '''
        Add comments to object (currently used to add PO# data)
        '''
        #self.depot = self.admin.get_objects()
        #host_id = self.get_id(hostname)
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""update RackObject set comment=%s where id=%s""", (comments, host_id))
        db.commit()
        cur.close()

    def add_server(self, **kwargs):
        '''
        Add an object to Racktables with any number of parameters.
        '''
        host = self.admin.add_object(kwargs['name'], object_type_id=kwargs['obj_type'], attrs={'1':kwargs['asset_tag'], '2':kwargs['hw_type'], '4': kwargs['os'], '3': kwargs['fqdn'], '10000': kwargs['dracfqdn'], '14': kwargs['contact'], '10002':kwargs['domain'], '10005': kwargs['status']})
        if 'errors' in host:
            raise TypeError(host['errors']['0'])
        if kwargs['tags']:
            print(host)
            tags = [i.strip() for i in kwargs['tags'].split(',')]
            if kwargs['datacenter']:
                tags.append(kwargs['datacenter'])
            self.admin.update_object_tags(host['id'], new_tags=filter(None, tags))

        if kwargs['cabinet'] and kwargs['rack_loc'] and kwargs['height']:
            k = (0, 1, 2)
            v = (u'T',)*3
            ru = dict(zip(k,v))
            rack_locations = tuple(range(int(kwargs['rack_loc']), int(kwargs['rack_loc'])+kwargs['height']))
            rdict = {}
            rdict[kwargs['cabinet']] = dict(zip((rack_locations), (ru,)*kwargs['height']))
            self.admin.update_object_allocation(host['id'], racks = rdict)
        return int(host['id'])

    def set_object_tags(self, hostid, tags, replace=False):
        '''
        Update the object tags for a host.
        '''
        tags_added = []
        tags_ignored = []
        tags_exist = []
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""select id, tag from TagTree""")
        result = cur.fetchall()
        d = {key: value for (key,value) in result}

        if replace:
        # delete all current tags
            cur.execute("""delete from TagStorage where entity_id=%s""", hostid)
        for tag in tags:
            if tag in d.values():
                # get tagid
                tagid = [i for i, t in d.items() if t == tag][0]
                tag_exists = False
                try:
                    # check if tag already exists
                    cur.execute("""select * from TagStorage where entity_id=%s and tag_id=%s""", (hostid, str(tagid)))
                    tag_exists = cur.fetchone()[0]
                except TypeError:
                    pass

                if tag_exists == False:
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cur.execute("""insert into TagStorage (entity_realm, entity_id, tag_id, tag_is_assignable, user, date) values ('object',%s,%s,'yes',%s,%s)""", (hostid, tagid, self.username, now))
                    tags_added.append(tag)
                else:
                    tags_exist.append(tag)
            else:
                tags_ignored.append(tag)
        db.commit()
        cur.close()
        return tags_added, tags_ignored, tags_exist


    def get_port_info(self, hostid):
        '''
        Returns a dict containing port names as keys, and a list of values containing id, remote_object_name, remote_name and linked status.
        '''
        ports = sorted(self.admin.get_object(hostid)['ports'].keys())
        port_ids = {}
        for port in ports:
            portinfo = self.admin.get_object(hostid)['ports'][port]
            port_ids[portinfo['name']] = [portinfo['id'], portinfo['remote_object_name'], portinfo['remote_name'], portinfo['linked']]
        return port_ids


    def delete_server(self, hostid):
        '''
        Delete an object from Racktables given an object id. Also deletes any/all association in TagStorage, ObjectLog, ObjectHistory
        '''
        #self.admin.delete_object(id)
        db = pymysql.connect(host=self.rtables_host, user=self.rtables_db_user, passwd=self.rtables_db_pass, db=self.rtables_db)
        cur = db.cursor()
        cur.execute("""delete from Object where id=%s""", hostid)
        cur.execute("""delete from TagStorage where entity_id=%s""", hostid)
        cur.execute("""delete from ObjectLog where object_id=%s""", hostid)
        cur.execute("""delete from ObjectHistory where id=%s""", hostid)
        db.commit()
        cur.close()

    def add_port(self, host, port_name, port_type="1642"):
        '''
        Add a port to a racktables object
        '''
        host_id = self.get_id(host)
        try:
            self.admin.add_object_port(host_id, port_name, "", port_type_id=port_type, label="")
            print("Successfully added {0} on ".format(port_name) + Fore.GREEN + "{0}".format(host) + Fore.RESET)
        except KeyError:
            print("KeyError: {0} might already exist on {1}.".format(port_name, host))

    def link_objects(self, child_id, parent_id):
        '''
        Link a child to a parent. VM -> Hypervisor or adding a host into a shelf object
        '''
        child_id = self.get_id(child_id)
        parent_id = self.get_id(parent_id)
        self.admin.link_entities(child_id, parent_id)


    def set_linked_port(self, rt, host, interface, remote_device, remote_int):
        '''
        Link a remote network port to a local object interface.
        '''
        remote_device_id = int(self.get_id(remote_device))
        try:
            local_port_id = int(rt.get_port_info(host)[interface][0])
            remote_device_ports = self.admin.get_object(remote_device_id)['ports']
            for port in remote_device_ports.keys():
                if remote_device_ports[port]['name'] == remote_int:
                    self.admin.link_port(local_port_id, remote_device_ports[port]['id'])
                    print("Successfully linked {0} on ".format(interface) + Fore.GREEN + "{0}".format(host) + Fore.RESET + " to {0} on ".format(remote_int) + Fore.GREEN + "{0}".format(remote_device) + Fore.RESET)
        except KeyError:
            print("Error: Verify port {0} exists on {1}.".format(interface, host))

    def unlink_port(self, rt, host, port_name):
        '''
        Unlink a port from a racktables object.
        '''
        ports = rt.get_port_info(host)
        port_id = ports[port_name][0]
        self.admin.unlink_port(port_id)
        print("Successfully unlinked {0} on ".format(port_name) + Fore.GREEN + "{0}".format(host) + Fore.RESET)

    def del_port(self, host, port_name):
        '''
        Delete a port on an object by name.
        '''
        host_id = self.get_id(host)
        ports = self.admin.get_object(host_id)['ports']
        for port in ports.keys():
            if port_name in ports[port]['name']:
                self.admin.delete_object_port(host_id, ports[port]['id'])
                print("Successfully deleted port {0} on ".format(port_name) + Fore.GREEN + "{0}".format(host) + Fore.RESET)


def usage():
    parser = argparse.ArgumentParser(description='%(prog)s help')
    parser.add_argument("--sync_tags", action="store_true", help="sync custom tag fields to asset tag field")
    parser.add_argument("--version", action="version", version="%(prog)s 0.3")

    subparsers = parser.add_subparsers()

    parser_query = subparsers.add_parser('query', help='query a racktables object', formatter_class=argparse.RawDescriptionHelpFormatter, epilog="syntax:\nrstat query --name host1\nrstat query --name dvcrash*")
    group_query = parser_query.add_mutually_exclusive_group(required=True)
    group_query.set_defaults(which='query')
    group_query.add_argument('--name', help='name of object')
    group_query.add_argument('--rack_info', metavar="RACK_ID", help='get server and asset tag info by rack id')
    group_query.add_argument('--serial_num', help='serial of object')

    parser_create = subparsers.add_parser('add', help='add a racktables object', formatter_class=argparse.RawDescriptionHelpFormatter, epilog="syntax:\nrstat add --name host1 --asset_tag 12345 --domain tsi.lan --datacenter 'Internap SEF003' --cabinet 662 --rack_loc 32 --hw_type 1690 --tags 'Build, DevIT' --contact 'Julian Barnett' --os 1812\nrstat add --name 'testshelf' --obj_type 3 --datacenter 'Internap SEF003' --cabinet 1645 --rack_loc 44 --height 1")
    parser_create.set_defaults(which='add')
    parser_create.add_argument('--name', required=True, help='name of object')
    parser_create.add_argument('--status', required=False, default='Inventory', choices=['Inventory', 'Production', 'Decommissioned', 'Maintenance', 'Ordered', 'To Be Decommissioned'], help='status of object (default = "Inventory")')
    parser_create.add_argument('--asset_tag', required=False, default="None", help='asset tag')
    parser_create.add_argument('--obj_label', required=False, default=None, help='object label')
    parser_create.add_argument('--obj_type', required=False, default='4', type=int, help='object type (default = 4 -> Server | 3 -> Shelf)')
    parser_create.add_argument('--domain', required=False, default="tsi.lan", help='domain (default = tsi.lan)')
    parser_create.add_argument('--datacenter', required=False, default='Internap SEF003', type=str, help='datacenter')
    parser_create.add_argument('--row', required=False, help='row')
    parser_create.add_argument('--cabinet', required=False, help='cabinet')
    parser_create.add_argument('--rack_loc', required=False, help='rack location')
    parser_create.add_argument('--height', required=False, default=1, type=int, help='ru height')
    parser_create.add_argument('--hw_type', required=False, help='hardware type')
    parser_create.add_argument('--tags', required=False, help='racktables tags')
    parser_create.add_argument('--contact', required=False, help='contact person')
    parser_create.add_argument('--os', required=False, help='OS')

    parser_import = subparsers.add_parser('import', help='import racktables objects from csv file', formatter_class=argparse.RawDescriptionHelpFormatter, epilog="syntax:\nrstat import --csv hosts.csv")
    parser_import.set_defaults(which='import')
    parser_import.add_argument('--csv', required=True, help='import from csv file')

    parser_link = subparsers.add_parser('link', help='link a child object to a parent object', formatter_class=argparse.RawDescriptionHelpFormatter, epilog="syntax:\nrstat link --child vm1 --parent hypervisor1")
    parser_link.set_defaults(which='link')
    parser_link.add_argument('--child', required=True, help='child object name')
    parser_link.add_argument('--parent', required=True, help='parent object name')

    parser_delete = subparsers.add_parser('delete', help='delete a racktables object', formatter_class=argparse.RawDescriptionHelpFormatter, epilog="syntax:\nrstat delete --name host1")
    parser_delete.set_defaults(which='delete')
    parser_delete.add_argument('--name', required=True, help='name of object to delete')

    parser_update = subparsers.add_parser('update', help='update a racktables object asset tag from racadm', formatter_class=argparse.RawDescriptionHelpFormatter, epilog="syntax:\nrstat update --name host1\nrstat update --csv hosts.csv\nrstat update --name host1 --tags 'Internap SEF003, DevIT'\nrstat update --name dvcrash* --tags 'Internap SEF003, DevIT'\nrstat update --name dvcrash* --tags 'Internap SEF003, DevIT' --replace\nrstat update --name dvopenpl002 --add_port mgmt0\nrstat update --name dvopenpl002 --link_port mgmt0 tssea-dev-sw-6 Eth121/1/37\nrstat update --name dvopenpl002 --unlink_port mgmt0")
    parser_update.set_defaults(which='update')
    # parser_update.add_argument('--csv', help='name of hosts file. ex. hosts.txt')
    # parser_update.add_argument('--name', help='name of host. Wildcards accepted using *. Example: 1krkdvpwbld*')
    # parser_update.add_argument('--serial_num', help='serial number of host')
    group_update = parser_update.add_mutually_exclusive_group(required=True)
    group_update.set_defaults(which='update')
    group_update.add_argument('--csv', help='name of hosts file. ex. hosts.txt')
    group_update.add_argument('--name', help='name of host. Wildcards accepted using *. Example: 1krkdvpwbld*')
    group_update.add_argument('--serial_num', help='serial number of host')
    parser_update.add_argument('--tags', help='update object with list of tags')
    parser_update.add_argument('--add_port', metavar="PORT_NAME", help='add port to racktables object')
    parser_update.add_argument('--del_port', metavar="PORT_NAME", help='delete a port on a racktables object')
    parser_update.add_argument('--link_port', nargs=3, metavar=("HOST_PORT", "REMOTE_DEVICE", "REMOTE_PORT"), help='update object with linked port')
    parser_update.add_argument('--unlink_port', metavar="PORT_NAME", help='unlink port to racktables object')
    parser_update.add_argument('--replace', required=False, action='store_true', help='replace tags with new list of tags')
    parser_update.add_argument('--status', required=False, choices=['Inventory', 'Production', 'Decommissioned', 'Maintenance', 'Ordered', 'To Be Decommissioned'], help='status of object')


    args = vars(parser.parse_args())
    return args


if __name__ == "__main__":
    main()

