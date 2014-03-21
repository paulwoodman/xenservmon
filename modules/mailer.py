# -*- coding: utf-8 -*-
"""
Created on Wed Jun 13 21:24:00 2012

@author: colpanic
"""

import config, smtplib
from email.mime.text import MIMEText
from config import logger as log

class msg_class:
    subject = ""
    body = ""
    greeter_admin = "You are receiving this email because you are listed as an administrator for the Xen Server Monitor daemon monitoring your network infrastructure.\n\n"
    greeter_user = "You are receiving this email because your system administrator wishes you to be notified when there are problems connecting to services on your network.\n\n"

class msg_host_reset_sub_class:
    failed_subject_mod = ""
    body_mod_failing = ""
    body_mod_failed = ""


message = msg_class()
#message.headers = """From: %s
#To: %s
#Subject:""" % (config.email_conf().sender, ', '.join(config.email_conf().recipients))

def msg_host_reset_method(method, errors=(True, True, False, False)):
    # List email responses as written after statement "If the connection is NOT reestablished, Xen Server Monitor will..."
    mod = msg_host_reset_sub_class()
    if method == "arduino" and errors == (True, True, False, False):
        mod.failed_subject_mod = "Arduino Reset Initiated"
        mod.body_mod_failing = "issue a reset command to your connected Arduino device. Assuming this device is connected to your server hardware correctly, this should hard reset the failed server."
        mod.body_mod_failed = "As per the configuration for this host, Xen Server Monitor has " + mod.body_mod_failing[0:5] + 'd' + mod.body_mod_failing[5:]
        return mod
    elif method == "arduino" and errors != (True, True, False, False):
        mod.failed_subject_mod = "Arduino Reset Failed"
        mod.body_mod_failed = """As per the configuration for this host, Xen Server Monitor has issued a reset command to your connected Arduino device. Unfortunately the command failed somewhere along the line. Here is some debuggin information for you:
            Command Acknowledged = %s
            Action Performed = %s
            Error - Invalid Command = %s
            Error - Invalid Response = %s
            
            As the reset command failed, you or someone else will need to physically reset the machine. You will receive no more email updates about this host or any attached Xen guests until after the connection has been reestablished.""" % (errors[0], errors[1], errors[2], errors[3])
        return mod
    else:
        mod.failed_subject_mod = "Please Repair ASAP"
        mod.body_mod_failing = "send you another email notifying you of the failure as you or someone else will need to hard reset the machine. No further reports regarding this machine or any attached Xen guests will be sent to you after that point until after the connection has been reestablished."
        mod.body_mod_failed = "As no method of automatic recovery is configured for this host, you or someone else will need to physically reset the machine. You will receive no more email updates about this host or any attached Xen guests until after the connection has been reestablished."
        return mod

def msg_host_failing(host_name, method):
    message.subject = "Host Server %s Not Responding, Stand By" % host_name
    message.body = """The host server, %s, has stopped responding to ping. Xen Server Monitor will attempt to regain the connection for approx. %d minute(s).

If the connection is reestablished, Xen Server Monitor will email you again to let you know, and then continue to run as normal. However, if the connection is NOT reestablished during this time, Xen Server monitor will %s""" % (host_name, config.fail_conf().cycle_time * config.fail_conf().cycle_count / 60, msg_host_reset_method(method).body_mod_failing)
    return message

def msg_host_poorcon(host_name):
    message.subject = "Host Server %s Encountering Connection Problems" % host_name
    message.body = """The host server, %s, is having difficulty responding to ping, with the number of lost packets dropping below the test threshold (currently set to %d%%).

If this is a vital connection, you may wish to try and find the cause and see if you can improve latency.""" % (host_name, config.fail_conf().poorcon_thresh)
    return message

def msg_host_failed(host_name, method, errors):
    message.subject = "Host Server %s Not Responding, %s" % (host_name, msg_host_reset_method(method, errors).failed_subject_mod)
    message.body = """The host server, %s, has stopped responding to ping and has not come back online in at least the past %d minute(s).

%s""" % (host_name, config.fail_conf().cycle_time * config.fail_conf().cycle_count / 60, msg_host_reset_method(method, errors).body_mod_failed)
    return message

def msg_host_resume(host_name):
    message.subject = "Host Server %s Responding Again" % host_name
    message.body = """The host server, %s, has started responding to ping again, either as a result of the Xen Server Monitor rebooting the system or by the problem resolving itself by other means.

Xen Server Monitor will continue to monitor this server as normal.""" % (host_name)
    return message

def msg_host_really_failed(host_name):
    message.subject = "Host Server %s Not Responding, Reset Method Not Effective" % host_name
    message.body = """The host server, %s, has stopped responding to ping and has not come back online in at least the past %d minutes.

A reset command was issued to the hardware device configured to reset this server, however after %d minute(s) the server is still not responding. You may need to examine the server yourself to determine the cause of the failure. No new emails relating to this server or any of its configured Xen guests will be sent until after it has come back online.""" % (host_name, (config.fail_conf().cycle_time * config.fail_conf().cycle_count / 60) + (config.fail_conf().totalfail_timeout / 60), config.fail_conf().totalfail_timeout / 60)
    return message

def msg_guest_failing(host_name):
    message.subject = "Xen Guest Server %s Not Responding, Stand By" % host_name
    message.body = """The Xen guest server, %s, has stopped responding to ping. Xen Server Monitor will attempt to regain the connection for approx. %d minute(s).

If the connection is reestablished, Xen Server Monitor will email you again to let you know, and then continue to run as normal. However, if the connection is NOT reestablished during this time, Xen Server monitor will attempt to issue the reset command to the appropriate Domain 0 host via SSH.""" % (host_name, config.fail_conf().cycle_time * config.fail_conf().cycle_count / 60)
    return message

def msg_guest_failed(host_name):
    message.subject = "Xen Guest Server %s Not Responding, Xen Reset Command Issued" % host_name
    message.body = """The Xen guest server, %s, has stopped responding to ping and has not come back online in at least the past %d minutes.

A Xen reset command has been issued to the relevant host through SSH. Once the server is back online you will receive another email to confirm. Alternatively, you will receive an email if the server has NOT come back online after approx. %d minute(s).""" % (host_name, config.fail_conf().cycle_time * config.fail_conf().cycle_count / 60, config.fail_conf().totalfail_timeout / 60)
    return message

def msg_guest_poorcon(host_name):
    message.subject = "Xen Guest Server %s Encountering Connection Problems" % host_name
    message.body = """The Xen guest server, %s, is having difficulty responding to ping, with the number of lost packets dropping below the test threshold (currently set to %d%%).

If this is a vital connection, you may wish to try and find the cause and see if you can improve latency.""" % (host_name, config.fail_conf().poorcon_thresh)
    return message

def msg_guest_resume(host_name):
    message.subject = "Xen Guest Server %s Responding Again" % host_name
    message.body = """The Xen guest server, %s, has started responding to ping again, either as a result of the Xen Server Monitor rebooting the system or by the problem resolving itself by other means.

Xen Server Monitor will continue to monitor this server as normal.""" % (host_name)
    return message

def msg_guest_really_failed(host_name):
    message.subject = "Xen Guest Server %s Not Responding, Xen Reset Command Not Effective" % host_name
    message.body = """The Xen guest server, %s, has stopped responding to ping and has not come back online in at least the past %d minutes.

A Xen reset command was issued to the configured host, however after %d minute(s) the server is still not responding. You may need to examine the server yourself to determine the cause of the failure. No new emails relating to this server will be sent until after it has come back online.""" % (host_name, (config.fail_conf().cycle_time * config.fail_conf().cycle_count / 60) + (config.fail_conf().totalfail_timeout / 60), config.fail_conf().totalfail_timeout / 60)
    return message
    
def msg_user_notify(host_name):
    message.subject = "Server %s Not Responding - Please Stand By" % host_name
    message.body = """One of the servers being monitored, %s, has stopped responding. This will be impacting your ability to connect to services offered by this server, and may also affect services on other systems if they are interlinked.

If you SysAdmin has configured as such, this monitoring program should have issued a reset command at this time which will hopefully automatically restore services shortly. If not, your SysAdmin will be made aware and will resolve the problem as soon as possible.

Thank you for your patience.""" % (host_name)
    return message
    
def msg_user_notify_resume(host_name):
    message.subject = "Server %s Back Online" % host_name
    message.body = """The server %s has come back online. You should hopefully now be able to resume normal use of this server.
    
Thank you for your patience.""" % (host_name)
    return message

def send_email(msg, recipients):
    flag = True
    while flag:
        if config.fail_conf().report == True:
            if recipients == "admins":
                if config.email_conf().admin_recipients == ['']:
                    try:
                        raise LookupError("No administrator emails configured, sending mail failed.")
                    except:
                        log.exception("No administrator emails configured, sending mail failed.")
                        flag = False
                        break
                message = MIMEText(msg.greeter_admin + msg.body)
                message['To'] = ', '.join(config.email_conf().admin_recipients)
            elif recipients == "users":
                if config.email_conf().user_recipients == ['']:
                    try:
                        raise LookupError("No user emails configured, sending mail failed.")
                    except:
                        log.exception("No user emails configured, sending mail failed.")
                        flag = False
                        break
                message = MIMEText(msg.greeter_user + msg.body)
                message['To'] = ', '.join(config.email_conf().user_recipients)
            message['From'] = config.email_conf().sender
            message['Subject'] = msg.subject
            if config.email_conf().smtp_conn in ('ssl', 'tls'):
                if config.email_conf().smtp_user == None or config.email_conf().smtp_pass == None:
                    log.warning("SMTP Connection type is configured as %s, but a username and password hasn't been configured. This method require login credentials. Trying plain text connection instead." % config.email_conf().smtp_conn.upper())
                    config.email_conf().smtp_conn = None
            try:
                if config.email_conf().smtp_conn == 'ssl':
                    send = smtplib.SMTP_SSL(config.email_conf().smtp_server, config.email_conf().smtp_port)
                else:
                    send = smtplib.SMTP(config.email_conf().smtp_server, config.email_conf().smtp_port)
                if config.email_conf().smtp_conn == 'tls':
                    send.ehlo()
                    send.starttls()
                    send.ehlo()
                    try:
                        send.login(config.email_conf().smtp_user, config.email_conf().smtp_pass)
                    except:
                        pass
                send.sendmail(config.email_conf().sender, message['To'], message.as_string())
                send.close()
            except:
                log.exception("SMTPLIB failed to send email, please check your connection and configuration")
            flag = False