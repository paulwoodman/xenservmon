import os, sys, time, multiprocessing, tempfile, datetime, shelve
from modules import ping, config, mailer, paramiko, arduino
from modules.config import logger as log

def prog():
    pid = os.fork()
    if(pid == 0):
        os.setsid()
        pid = os.fork()
        if(pid ==0):

            def packetloss(server):
                return ping.quiet_ping(server, count=config.ping_count(), timeout=config.ping_timeout())[0]

            def poorcon_report(lasttime):
                if lasttime == False:
                    return True
                else:
                    delta = datetime.datetime.now() - lasttime
                    if delta > datetime.timedelta(hours=2):
                        return True
                    else:
                        return False

            def host_ping_test(host):
                pid = os.getppid()
                log.debug('Host Thread Loaded for %s' % host.name)

                # Set up process-specific variables
                fail_counter = 0
                poorcon_reptime = False
                broken = False
                fail_timer = 0
                users_notified = 0

                # Begin ping test cycle
                while True:
                    # Kill child if if orphaned
                    if pid != os.getppid():
                        log.debug('Parent process died! Attempting suicide')
                        os._exit(1)
                    status_file = tempfile.gettempdir() + "/xenservmon-status"
                    status_tmp = shelve.open(status_file, flag='r')
                    pstatus = status_tmp[host.name]
                    status_tmp.close()
                    log.debug('Host Cycle Start for %s' % host.name)
                    lost = packetloss(host.addr)
                    errors = (True, True, False, False)
                    if pstatus == True:
                        if 100 - lost < config.fail_conf().poorcon_thresh and 100 - lost > 0:
                            log.info('Host %s good -> poor connection; %d%% packets lost' % (host.name, lost))
                            if config.fail_conf().report_poorcon == True and poorcon_report(poorcon_reptime) == True:
                                mailer.send_email(mailer.msg_host_poorcon(host.name), "admins")
                            poorcon_reptime = datetime.datetime.now()
                            time.sleep(config.cycle_time())
                        elif 100 - lost == 0:
                            log.info('Host %s good -> NO connection' % host.name)
                            if config.fail_conf().report_failing == True:
                                mailer.send_email(mailer.msg_host_failing(host.name, host.reset_method), "admins")
                            pstatus = False
                            status_tmp = shelve.open(status_file)
                            status_tmp[host.name] = pstatus
                            status_tmp.close()
                            time.sleep(config.fail_conf().cycle_time)
                        else:
                            log.debug('Host %s has good connection' % host.name)
                            time.sleep(config.cycle_time())
                    elif pstatus == False:
                        if 100 - lost < config.fail_conf().poorcon_thresh and 100 - lost > 0:
                            log.info('Host %s no -> poor connection; %d%% packets lost' % (host.name, lost))
                            if config.fail_conf().report_failing == True:
                                mailer.send_email(mailer.msg_host_poorcon(host.name), "admins")
                            pstatus = True
                            status_tmp = shelve.open(status_file)
                            status_tmp[host.name] = pstatus
                            status_tmp.close()
                            fail_counter = 0
                            time.sleep(config.cycle_time())
                        elif 100 - lost == 0:
                            if fail_counter < config.fail_conf().cycle_count:
                                log.debug('Host %s still has NO connection' % host.name)
                                fail_counter += 1
                            elif fail_counter == config.fail_conf().cycle_count:
                                log.info('Host %s still has NO connection; sending email and attempting configured reset function if available' % host.name)
                                if host.reset_method == 'arduino':
                                    log.debug('Arduino reset command issued for %s' % host.name)
                                    errors = arduino.cmd_send('1', arduino.find_arduino())
                                    if errors != (True, True, False, False):
                                        log.info('Arduino Reset Command Failed for host %s - CMD ACK = %s; CMD Acted = %s, Invalid CMD = %s, Invalid Resp = %s' % (host.name, errors[0], errors[1], errors[2], errors[3]))
                                mailer.send_email(mailer.msg_host_failed(host.name, host.reset_method, errors), "admins")
                                if config.email_conf().user_recipients != "":
                                    log.debug('Sending failure email to users for %s' % host.name)
                                    mailer.send_email(mailer.msg_user_notify(host.name), "users")
                                    users_notified = 1
                                fail_counter +=1
                                fail_timer = datetime.datetime.now()
                            elif fail_counter > config.fail_conf().cycle_count and broken == False and host.reset_method != None and errors == (True, True, False, False) and datetime.timedelta(seconds=config.fail_conf().totalfail_timeout) <= datetime.datetime.now() - fail_timer:
                                log.info('Host %s is really broken; sending email to sysadmins' % host.name)
                                mailer.send_email(mailer.msg_host_really_failed(host.name), "admins")
                                broken = True
                            time.sleep(config.fail_conf().cycle_time)
                        else:
                            if (config.fail_conf().report_failing == True)  or (fail_counter > config.fail_conf().cycle_count):
                                mailer.send_email(mailer.msg_host_resume(host.name), "admins")
                                if (config.email_conf().user_recipients != "") and (users_notified == 1):
                                    log.debug('Sending resume email to users for %s' % host.name)
                                    mailer.send_email(mailer.msg_user_notify_resume(host.name), "users")
                                    users_notified = 0
                            fail_counter, fail_timer = 0, 0
                            pstatus, broken = True, False
                            status_tmp = shelve.open(status_file)
                            status_tmp[host.name] = pstatus
                            status_tmp.close()
                            log.info('Host %s no -> good connection' % host.name)
                            time.sleep(config.cycle_time())

            def guest_ping_test(guest):
                pid = os.getppid()
                log.debug('Guest Thread Loaded for %s' % guest.name)

                # Set up process-specific variables
                fail_counter = 0
                prev_alive = True
                poorcon_reptime = False
                fail_timer = 0
                broken = False
                users_notified = 0
                time.sleep(15)

                # Begin ping test cycle
                while True:
                    # Kill child if if orphaned
                    if pid != os.getppid():
                        log.debug('Parent process died! Attempting suicide')
                        os._exit(1)
                    # Open temp files and check status of host
                    link_file = tempfile.gettempdir() + "/xenservmon-link"
                    lfile = shelve.open(link_file, flag='r')
                    link = lfile[guest.name]
                    lfile.close()
                    status_file = tempfile.gettempdir() + "/xenservmon-status"
                    sfile = shelve.open(status_file, flag='r')
                    status = sfile[link]
                    sfile.close()
                    log.debug('Guest Cycle Start for %s' % guest.name)
                    if status == False:
                        log.info('Skip testing %s because host is reported as dead' % guest.name)
                        time.sleep(config.cycle_time())
                    elif status == True:
                        lost = packetloss(guest.addr)
                        if prev_alive == True:
                            if 100 - lost < config.fail_conf().poorcon_thresh and 100 - lost > 0:
                                log.info('Guest %s good -> poor connection; %d%% packets lost' % (guest.name, lost))
                                if config.fail_conf().report_poorcon == True and poorcon_report(poorcon_reptime) == True:
                                    mailer.send_email(mailer.msg_guest_poorcon(guest.name), "admins")
                                poorcon_reptime = datetime.datetime.now()
                                time.sleep(config.cycle_time())
                            elif 100 - lost == 0:
                                log.info('Guest %s good -> NO connection' % guest.name)
                                if config.fail_conf().report_failing == True:
                                    mailer.send_email(mailer.msg_guest_failing(guest.name), "admins")
                                prev_alive = False
                                time.sleep(config.fail_conf().cycle_time)
                            else:
                                log.debug('Guest %s has good connection' % guest.name)
                                time.sleep(config.cycle_time())
                        elif prev_alive == False:
                            if 100 - lost < config.fail_conf().poorcon_thresh and 100 - lost > 0:
                                log.info('Guest %s no -> poor connection; %d%% packets lost' % (guest.name, lost))
                                if config.fail_conf().report_failing == True:
                                    mailer.send_email(mailer.msg_guest_poorcon(guest.name), "admins")
                                prev_alive = True
                                fail_counter, fail_timer = 0, 0
                                time.sleep(config.cycle_time())
                                broken = False
                            elif 100 - lost == 0:
                                if fail_counter < config.fail_conf().cycle_count:
                                    log.debug('Guest %s still has NO connection' % guest.name)
                                    fail_counter += 1
                                elif fail_counter == config.fail_conf().cycle_count:
                                    log.debug('Guest %s still has NO connection; sending email and attempting configured reset function if available' % guest.name)
                                    mailer.send_email(mailer.msg_guest_failed(guest.name), "admins")
                                    reset = multiprocessing.Process(target=guest_reset, args=(guest,))
                                    reset.start()
                                    if config.email_conf().user_recipients != "":
                                        log.debug('Sending email to users for %s' % guest.name)
                                        mailer.send_email(mailer.msg_user_notify(guest.name), "users")
                                        users_notified = 1
                                    fail_counter += 1
                                    fail_timer = datetime.datetime.now()
                                elif fail_counter > config.fail_conf().cycle_count and broken == False and datetime.timedelta(seconds=config.fail_conf().totalfail_timeout) <= (datetime.datetime.now() - fail_timer):
                                    log.info('Guest %s is really broken; sending email to sysadmins' % guest.name)
                                    mailer.send_email(mailer.msg_guest_really_failed(guest.name), "admins")
                                    broken = True
                                time.sleep(config.fail_conf().cycle_time)
                            else:
                                if (config.fail_conf().report_failing == True)  or (fail_counter > config.fail_conf().cycle_count):
                                    mailer.send_email(mailer.msg_guest_resume(guest.name), "admins")
                                    if (config.email_conf().user_recipients != "") and (users_notified == 1):
                                        log.debug('Sending resume email to users for %s' % guest.name)
                                        mailer.send_email(mailer.msg_user_notify_resume(guest.name), "users")
                                        users_notified = 0
                                fail_counter, fail_timer = 0, 0
                                prev_alive, broken = True, False
                                log.info('Guest %s no -> good connection' % guest.name)
                                time.sleep(config.cycle_time())


            def guest_reset(guest):
                # Initiate SSH connection to Xen host to send reset command for guest
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                guest_host = config.host_conf((guest.host, config.conf.get('hosts', guest.host)))
                try:
                    ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
                except:
                    log.debug("Local SSH host keys couldn't be loaded, should be fine though")
                try:
                    ssh.connect(guest_host.addr, port=guest_host.ssh_port, username=guest_host.user, password=guest_host.pwd, timeout=120)
                    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(config.fail_conf().guest_reset + ' ' + guest.xen_name)
                except:
                    log.exception("Error connecting to %s via SSH" % guest.host)
                else:
                    log.debug('SSH Command issued to %s' % guest.name)
                ssh.close()
                sys.exit()

            # Check to make sure configuration sections are complete
            if config.conf.items('hosts') == [] and config.conf.items('guests') == []:
                print 'Servers have not been defined in the config file!'
                print ''
                print 'Please add servers to monitor to the /etc/xenservmon.conf file'
                log.critical("Error: HOSTS/GUESTS configuration empty, check conf file")
                os._exit(1)
            elif config.conf.items('hosts') == []:
                count = 0
                for x in [y for y in config.option_list('guests') if y[1] != 'guests' and [z.strip() for z in y[1].split(',')][1].lower() != 'localhost']:
                    count += 1
                if count != 0:
                    print "Xen guest servers are configured, however host servers are not! Xen servers can't be recovered if host settings aren't configured."
                    print ''
                    print 'Please add host servers to monitor to the /etc/xenservmon.conf file, or alternatively move the Xen guest servers to the hosts section'
                    log.critical("Error: HOSTS configuration empty, check conf file")
                    os._exit(1)
            for guest in [x for x in config.option_list('guests') if x[1] != 'guests']:
                try:
                    if [x.strip() for x in guest[1].split(',')][1].upper() not in [x.upper() for x in config.conf.options('hosts')]:
                        print 'Server %s is configured as a Xen guest, but the Domain 0 hostname provided is not listed in the Hosts section.' % guest[0].upper()
                        print ''
                        print 'Please edit the /etc/xenservmon.conf file to reflect information for this host, or move this server to the Hosts section instead.'
                        log.critical('ERROR: Configured host for Xen guest %s not found in HOSTS section'  % guest[0].upper())
                        os._exit(1)
                except IndexError:
                    print 'Server %s is configured as a Xen guest, but has no host assigned to it.' % guest[0].upper()
                    print ''
                    print 'Please edit the /etc/xenservmon.conf file to reflect the correct host name for this guest, or add this server to the Hosts section instead.'
                    log.critical('ERROR: No host provided for Xen guest %s in configuration'  % guest[0].upper())
                    os._exit(1)

            # Check for already existing PID lock file
            if os.access("/var/lock/xenservmon.pid", os.F_OK):
                pidfile = open("/var/lock/xenservmon.pid", "r")
                pidfile.seek(0)
                old_pid = pidfile.readline()
                if os.path.exists("/proc/%s" % old_pid):
                    print "You already have an instance of the program running"
                    print "It is running as process %s," % old_pid
                    os._exit(1)
                else:
                    print "Removing stale lock file for %s" % old_pid
                    os.remove("/var/lock/xenservmon.pid")

            # Create new PID lock file
            pidfile = open("/var/lock/xenservmon.pid", "w")
            pidfile.write("%s" % os.getpid())
            pidfile.close

            #Initiate host-guest links and create temp files
            link_file = tempfile.gettempdir() + "/xenservmon-link"
            try:
                os.remove(link_file)
            except:
                pass
            if config.conf.items('guests') != []:
                guest_host_link = shelve.open(link_file, flag='n')
                for guest_config in [x for x in config.option_list('guests') if x[1] != 'guests']:
                    guest = config.guest_conf(guest_config)
                    guest_host_link[guest.name] = guest.host
                guest_host_link.close()
            status_file = tempfile.gettempdir() + "/xenservmon-status"
            try:
                os.remove(status_file)
            except:
                pass
            host_status = shelve.open(status_file, flag='n')
            for host_config in [x for x in config.option_list('hosts') if x[1] !='hosts']:
                host = config.host_conf(host_config)
                host_status[host.name] = True
            host_status.close()

            # Start the main thread
            log.critical('Xen Server Monitor started')

            # Start child processes for each configured host
            for host_config in [x for x in config.option_list('hosts') if x[1] !='hosts']:
                host = config.host_conf(host_config)
                proc = multiprocessing.Process(target=host_ping_test, args=(host,))
                proc.start()

            # Start child processes for each configured Xen guest
            for guest_config in [x for x in config.option_list('guests') if x[1] != 'guests']:
                guest = config.guest_conf(guest_config)
                proc = multiprocessing.Process(target=guest_ping_test, args=(guest,))
                proc.start()
            print "Xen Server Monitor Started"
    #        config.queue.put_nowait(None)
    #        config.listener.join()
        else:
            os._exit(0)
    else:
        os._exit(0)

if __name__ == "__main__":
        if len(sys.argv) == 2:
                if 'start' == sys.argv[1]:
                    print "Starting Xen Server Monitor..."
                    prog()
                elif 'stop' == sys.argv[1]:
                    if os.access("/var/lock/xenservmon.pid", os.F_OK):
                        print "Stopping Xen Server Monitor..."
                        pidfile = open("/var/lock/xenservmon.pid", "r")
                        pidfile.seek(0)
                        old_pid = int(pidfile.readline())
                        if os.path.exists("/proc/%s" % old_pid):
                            os.kill(old_pid, 9)
                        os.remove("/var/lock/xenservmon.pid")
                        os._exit(0)
                    else:
                        print "Xen Server Monitor is not running"
                    os._exit(0)
                elif 'restart' == sys.argv[1]:
                    if os.access("/var/lock/xenservmon.pid", os.F_OK):
                        print "Stopping Xen Server Monitor..."
                        pidfile = open("/var/lock/xenservmon.pid", "r")
                        pidfile.seek(0)
                        old_pid = int(pidfile.readline())
                        if os.path.exists("/proc/%s" % old_pid):
                            os.kill(old_pid, 9)
                        os.remove("/var/lock/xenservmon.pid")
                    else:
                        print "Xen Server Monitor is not running"
                    print "Starting Xen Server Monitor..."
                    prog()
                else:
                        print "Unknown command"
                        os._exit(2)
                sys.exit(0)
        else:
                print "usage: %s start|stop|restart" % sys.argv[0]
                os._exit(2)
