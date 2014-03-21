# -*- coding: utf-8 -*-
"""
Created on Wed Jun 13 13:57:28 2012

@author: sean.mackedie
"""
import ConfigParser, scrapz, multilog, multiprocessing
    
class host_class:
    name = ""
    addr = ""
    user = ""
    pwd = ""
    ssh_port = 22
    reset_method = None
        
class guest_class:
    name = ""
    addr = ""
    host = ""
    xen_name = ""

class email_class:
    admin_recipients = ['']
    user_recipients = ['']
    sender = "root"
    smtp_server = ""
    smtp_port = 25
    smtp_conn = None
    smtp_user = None
    smtp_pass = None

class fail_class:
    cycle_time = 60
    cycle_count = 2
    report = False
    report_failing = False
    report_poorcon = False
    poorcon_thresh = 40
    guest_reset = "xm reset"
    totalfail_timeout = 300
    
class log_class:
    logfile = "/var/log/xenservmon.log"
    logsize = 1048576
    loghistory = 5
    loglevel = "WARNING"

def option_list(section):
    return conf._sections[section].iteritems()

#def default_msg(option, section, )

def ping_count():
    try:
        return int(conf.get('options', 'ping_count'))
    except:
        logger.info("Item 'ping_count' under 'options' section of the configuration file is missing or invalid. Using default value instead: 5")
        return int(5)
    
def ping_timeout():
    try:
        return float(conf.get('options', 'ping_timeout'))
    except:
        return float(1)

def log_conf():
    l = log_class()
    try:
        x = str(conf.get('options', 'log_level')).upper()
        if x in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            l.loglevel = x
        else:
            raise LookupError('Log level provided in configuration is invalid')
    except:
        l.loglevel = "WARNING"
    return l
    
def cycle_time():
    try:
        x = int(conf.get('options', 'cycle_time'))
        if x < 30:
            x = int(30)
        return x
    except:
        return int(300)
        
def fail_conf():
    fail = fail_class()
    try:
        fail.cycle_time = int(conf.get('options', 'fail_cycle_time'))
    except:
        pass
    try:
        fail.cycle_count = int(conf.get('options', 'fail_cycle_count'))
    except:
        pass
    try:
        if email_conf().admin_recipients != '' or email_conf().user_recipients != '':
            fail.report = conf.getboolean('options', 'report')
    except:
        pass
    try:
        if email_conf().admin_recipients != '':
            fail.report_failing = conf.getboolean('options', 'report_failing')
    except:
        pass
    try:
        if email_conf().admin_recipients != '':
            fail.report_poorcon = conf.getboolean('options', 'report_poorcon')
    except:
        pass
    try:
        fail.poorcon_thresh = int(conf.get('options', 'poorcon_thresh'))
    except:
        pass
    try:
        fail.guest_reset = str(conf.get('options', 'guest_reset_cmd'))
    except:
        pass
    try:
        fail.totalfail_timeout = int(conf.get('options', 'totalfail_timeout'))
    except:
        pass
    return fail
    
def host_conf(host_config):
    host = host_class()
    host.name = host_config[0].upper()
    try:
        host_config[1].split('@')[1]
    except:
        host.addr = scrapz.multisplit(host_config[1], ':', ',')[0]
        host.user = 'root'
        host.pwd = None
    else:
        host.addr = scrapz.multisplit(host_config[1], '@', ':', ',')[1]
        host.user = scrapz.multisplit(host_config[1], '@', '/')[0]
        try:
            host_config[1].split('/')[1]
        except:
            host.pwd = None
        else:
            host.pwd = scrapz.multisplit(host_config[1], '@', '/', ':')[1]
    try:
        host.ssh_port = int(scrapz.multisplit(host_config[1], ':', ',')[1])
    except:
        pass
    try:
        host.reset_method = [x.strip() for x in host_config[1].split(',')][1].lower()
    except:
        pass
    return host
    
def guest_conf(guest_config):
    guest = guest_class()
    guest.name = guest_config[0].upper()
    guest.addr = guest_config[1].split(',')[0]
    guest.host = [x.strip() for x in guest_config[1].split(',')][1].upper()
    try:
        guest.xen_name = [x.strip() for x in guest_config[1].split(',')][2]
    except:
        print """
        Server %s is configured as a Xen guest, but no Xen domain name has been provided. It will be assumed the domain name is the same as the host name.
        
        If there are any problems regarding this program sending commands to the Xen host for this server, please ensure the correct domain name is configured in /etc/xenservmon.conf.
        """  % guest.name
        guest.xen_name = guest_config[0]
    return guest

def email_conf():
    email_config = email_class()
    try:
        email_config.admin_recipients = list(set([x.strip() for x in conf.get('email', 'admin_recipients').split(',')]))
    except:
        pass
    try:
        email_config.user_recipients = list(set([x.strip() for x in conf.get('email', 'user_recipients').split(',')]))
    except:
        pass
    try:
        email_config.sender = conf.get('email', 'sender')
    except:
        pass
    email_config.smtp_server = conf.get('email', 'smtp_server')
    try:
        email_config.smtp_conn = conf.get('email', 'smtp_conn').lower()
    except:
        pass
    try:    
        email_config.smtp_port = conf.get('email', 'smtp_port')
    except:
        if email_config.smtp_conn == 'tls':
            email_config.smtp_port = 587
        elif email_config.smtp_conn == 'ssl':
            email_config.smtp_port = 465
        else:
            pass
    try:
        email_config.smtp_user = conf.get('email', 'smtp_user')
    except:
        pass
    try:
        email_config.smtp_pass = conf.get('email', 'smtp_pass')
    except:
        pass
    return email_config
    
#Load config file
conf = ConfigParser.ConfigParser()
conf.optionxform = str
conf.readfp(open('default.conf'))
conf.read(['/etc/xenservmon.conf'])
if conf.has_section('hosts') is False:
    conf.add_section('hosts')
if conf.has_section('guests') is False:
    conf.add_section('guests')
if conf.has_section('email') is False:
    conf.add_section('email')

#begin logging process
queue = multiprocessing.Queue(-1)
listener = multiprocessing.Process(target=multilog.listener_process, args=(queue, multilog.listener_configurer(log_conf().logfile, log_conf().logsize, log_conf().loghistory)))
listener.start()
logger = multilog.logging.getLogger()
logger.setLevel(log_conf().loglevel)
