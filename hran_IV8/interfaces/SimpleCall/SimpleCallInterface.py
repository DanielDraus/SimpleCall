# -*- coding: utf-8 -*-
"""
:copyright: Nokia Networks
:author: Daniel Draus
:contact: daniel.draus@nokia.com
"""

import traceback
import sys
import re
import time
import socket
import base64
import threading
import random
import collections
import time
import subprocess
import platform
import tempfile

from paramiko import SSHClient, AutoAddPolicy, SSHException
from logging.handlers import RotatingFileHandler
import paramiko
from Utils import *
from ExceptionsClass import *
from iperf_app.iperf_app import IperfInstaller


rf_running = False

try:
    from robot.libraries.BuiltIn import RobotNotRunningError
    from robot.libraries.BuiltIn import BuiltIn

    BuiltIn().get_variables()
    from robot.output import librarylogger as mylibrarylogger
    rf_running = True
    class logger(object):
        def __init__(self, mylibrarylogger):
            self.librarylogger = mylibrarylogger

        def info(self, msg):
            self.librarylogger.info(msg, also_console=True)

        def error(self, msg):
            self.librarylogger.error(msg)

        def debug(self, msg):
            self.librarylogger.debug(msg)

        def warning(self, msg):
            self.librarylogger.warn(msg)

    paramiko.util.log_to_file('{}/SimpleCall_paramiko.log'.format(BuiltIn().get_variable_value("${OUTPUT DIR}")))
    mylogger = logger(mylibrarylogger)

except:
    import logging

    mylogger = logging.getLogger("SimpleCall")


class SimpleCallInterface(object):
    my_objects = []

    _iperf_path2 = "./data/data/com.magicandroidapps.iperf/bin/iperf"
    _iperf_path = "iperf"

    # init class variables
    _alias = ""
    _ip = ""
    _port = ""
    _username = ""
    _domain = ""
    _mypasswd = ""
    _iperf_ip = ""
    _iperf_uname = ""
    _iperf_passwd = ""
    _adb_path = ""
    _use_su = True

    def __init__(self, alias=None,
                 ip=None,
                 port=None,
                 uname=None,
                 domain=None,
                 passwd=None,
                 robot=False):

        if not rf_running:
            self._prepare_logger()
        self._myUes = []
        self._checksamba()
        self._ssh_client = SSHClient()
        self._ssh_client.__myname__ = "Main"
        # self._hran_ue_man = hran_uem.hran_uem()
        # init class variables
        self._alias = alias
        self._ip = ip
        self._port = port
        self._username = uname
        self._domain = domain
        self._mypasswd = passwd
        self._thm = ThM()
        self.iperf_installer = IperfInstaller(self._ip, self._username, self._mypasswd, mylogger)
        if self._use_su:
            self._su_str = "su -c {}".format(chr(34))
            self._su_str_end = "{}".format(chr(34))
        else:
            self._su_str = ""
            self._su_str_end = ""

    @staticmethod
    def _prepare_logger():
        if not mylogger.handlers:
            mylogger.setLevel(logging.DEBUG)
            ch = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            # add formatter to ch
            ch.setFormatter(formatter)
            ch.setLevel(logging.INFO)
            #fh = logging.FileHandler('/tmp/SimpleCall.log')
            #fh.setFormatter(formatter)
            #fh.setLevel(logging.DEBUG)

            logFile = '/tmp/SimpleCall.log'

            fh = RotatingFileHandler(logFile,
                                     mode='a',
                                     maxBytes=2 * 1024 * 1024,
                                     backupCount=3,
                                     encoding=None,
                                     delay=0)

            fh.setFormatter(formatter)
            fh.setLevel(logging.DEBUG)
            mylogger.addHandler(ch)
            mylogger.addHandler(fh)
            paramiko.util.log_to_file('/tmp/SimpleCall_paramiko.log')

    def get_uepc_alias(self):
        return self._alias

    def reboot_ue_pc(self):
        try:
            time_tick = 21
            mylogger.info('UE PC {!r} reboot started'.format(self._alias))

            cmd = 'net rpc shutdown -r -I {IP} -U {DOMAIN}/{UNAME}%{PASS}'.format(IP=self._ip, DOMAIN=self._domain,
                                                                                  UNAME=self._username,
                                                                                  PASS=self._mypasswd)

            mylogger.debug("_reboot_ue_pc,cmd={}".format(cmd))
            cmd = cmd.split()
            stdout = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            mylogger.debug("_reboot_ue_pc,{}".format(stdout))

            mylogger.debug("_reboot_ue_pc,cmd={}\nstdout={}".format(cmd, stdout))

            if self._wait_time_tic(time_tick, self._ping_ok, True, (self._ip)):
                mylogger.info('UE PC {!r} rebooted successfully wait for ping'.format(self._alias))

            if self._wait_time_tic(time_tick, self._ping_ok, False, (self._ip)):
                mylogger.info('UE PC {!r} avaliable'.format(self._alias))
                self._wait_sshd()
                return True
            else:
                raise UePcError('No ping_ok to UE PC {!r}'.format(self._alias))

        except Exception as e:
            mylogger.debug(str(e))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())
            raise UePcError('No connection to UE PC {!r}'.format(self._alias))

        finally:
            return False

    @staticmethod
    def _wait_time_tic(tic, func, reverse, *args):

        while tic > 0:
            if args is None:
                ret = func()
            else:
                ret = func(*args)
            if reverse:
                ret = not ret
            if ret:
                return True
            else:
                time.sleep(5)
                tic -= 1

        return False

    def _wait_sshd(self):
        try:
            mylogger.info('UE PC {!r} wait for ssh'.format(self._alias))
            time_tick = 31
            if self._wait_time_tic(time_tick, self._check_sshd_service, False):
                self._reboot_ues_by_at()
                mylogger.info('UE PC {!r} sshd avaliable'.format(self._alias))
                return True
            else:
                raise UePcError('No sshd not running on UE PC {!r}'.format(self._alias))
        except Exception as e:
            mylogger.debug(str(e))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())
            raise UePcError('No ssh connection to UE PC {!r}'.format(self._alias))

        finally:
            return False

    @staticmethod
    def _ping_ok(ip):
        try:
            output = subprocess.check_output(
                "ping -{} 1 {}".format('n' if platform.system().lower() == "windows" else 'c', ip),
                shell=True)
            mylogger.debug("ping -{} 1 {} out={}"
                           .format('n' if platform.system().lower() == "windows" else 'c', ip, output))

        except Exception:
            return False

        return True

    def get_ue_pc_services(self):
        try:
            cmd = 'net rpc service list -I {IP} -U {DOMAIN}/{UNAME}%{PASS}'.format(IP=self._ip, DOMAIN=self._domain,
                                                                                   UNAME=self._username,
                                                                                   PASS=self._mypasswd)
            mylogger.debug("get_ue_pc_services,cmd={}".format(cmd))
            stdout = subprocess.check_output(cmd.split())
            mylogger.debug("get_ue_pc_services,cmd={}\nstdout={}".format(cmd, stdout))
        except Exception as e:
            mylogger.debug(str(e))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())
            raise UePcError('Net rpc error UE PC {!r}'.format(self._alias))

    def _check_sshd_service(self):
        try:
            cmd = 'net rpc service status sshd -I {IP} -U {DOMAIN}/{UNAME}%{PASS}'.format(IP=self._ip,
                                                                                          DOMAIN=self._domain,
                                                                                          UNAME=self._username,
                                                                                          PASS=self._mypasswd)
            cmd = cmd.split()
            stdout = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            mylogger.debug("_check_sshd_service,cmd={}\nstdout={}".format(cmd, stdout))
            if 'service is running' in stdout:
                return True
            else:
                return False

        except subprocess.CalledProcessError as e:
            mylogger.debug("_check_sshd_service,cmd={}\nCalledProcessError={}".format(cmd, e.message))
            raise UePcError('NET RPC ERROR-Please-check-your-credentials,'
                            ' UE PC ip={} domain={} username{} password={}'
                            .format(self._ip, self._domain, self._username, self._mypasswd))

    @staticmethod
    def _checksamba():

        '''in case of run in MS Windows just return'''

        if platform.system().lower() == "windows":
            return
        try:
            cmd = 'net rpc --help'
            cmd = cmd.split()
            stdout = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            mylogger.debug("_checksamba,stdout={}".format(stdout))

        except Exception as e:
            mylogger.debug("_checksamba,cmd={}\nException={}".format(stdout, e.message))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())
            raise UePcError(
                "Package samba-common-bin is not installed !!! \tPLEASE install by apt-get")

    def _restart_sshd(self):
        if self._check_sshd_service():
            try:

                cmd = 'net rpc service stop sshd -I {IP} -U {DOMAIN}/{UNAME}%{PASS}'.format(IP=self._ip,
                                                                                            DOMAIN=self._domain,
                                                                                            UNAME=self._username,
                                                                                            PASS=self._mypasswd)
                cmd = cmd.split()
                stdout = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
                mylogger.debug("_restart_sshd,cmd={}\nstdout={}".format(cmd, stdout))

            except subprocess.CalledProcessError as e:
                mylogger.debug("_restart_sshd,cmd={}\nCalledProcessError={}".format(cmd, e.message))

        try:
            cmd = 'net rpc service start sshd -I {IP} -U {DOMAIN}/{UNAME}%{PASS}'.format(IP=self._ip,
                                                                                         DOMAIN=self._domain,
                                                                                         UNAME=self._username,
                                                                                         PASS=self._mypasswd)
            cmd = cmd.split()
            stdout = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            mylogger.debug("_restart_sshd,cmd={}\nstdout={}".format(cmd, stdout))

        except subprocess.CalledProcessError as e:
            mylogger.debug("_restart_sshd,cmd={}\nCalledProcessError={}".format(cmd, e.message))

            raise UePcError('NET RPC ERROR-Please-check-your-credentials,'
                            ' UE PC ip={} domain={} username{} password={}'.format(self._ip,
                                                                                   self._domain,
                                                                                   self._username,
                                                                                   self._mypasswd))

        finally:
            time.sleep(10)
            return self._check_sshd_service()

    @staticmethod
    def get_logger():
        return mylogger

    def _restart_adb_server(self):
        # command = 'ps -ef | grep adb | grep -v grep | awk "{print $2}" | xargs kill -9'
        self._run_command("ps -ef | grep adb | grep -v grep | awk '{print $2}' | xargs kill -9")
        self._run_command("cmd /c taskkill /f /t /im adb.exe")
        self._run_command("adb kill-server")
        return self._run_command("adb start-server")

    def _run_command(self, cmd, timeout=10):
        mylogger.debug("_run_command,cmd={}".format(cmd))
        stdout, stderr = self.start_process_by_ssh(cmd, 3, timeout=timeout)
        mylogger.debug("_run_command,cmd={}\nstdout={}\nstderr={}".format(cmd, stdout, stderr))

        return stdout, stderr

    def _run_command2(self, cmd, duration=10):
        self._ssh_client.set_missing_host_key_policy(AutoAddPolicy())
        self._ssh_client.connect(self._ip, username=self._username, password=self._mypasswd, look_for_keys=False)
        transport = self._ssh_client.get_transport()
        channel = transport.open_session()
        channel.setblocking(1)
        channel.settimeout(5.0)
        channel.set_combine_stderr(1)
        channel.exec_command(cmd)
        start_time = int(round(time.time() * 1000))
        end_time = start_time + (duration * 1000)
        current_time = 0
        output = ""
        while current_time < end_time:
            current_time = int(round(time.time() * 1000))
            try:
                if channel.recv_ready():
                    output += channel.recv(1024)

                if channel.exit_status_ready():
                        break

            except Exception as e:
                mylogger.debug("_run_command2,Exception={}".format(str(e)))
                mylogger.debug(sys.exc_type)
                mylogger.debug(traceback.format_exc())
                break
            time.sleep(2)

        self._ssh_client.close()
        return output

    def _install_iperf(self, adb_sn):
        if self.iperf_installer.install_iperf(adb_sn):
            mylogger.info("Iperf installed in /system/bin ")
        else:
            mylogger.info("Iperf Not installed")

    def _check_su(self, adb_sn):
        cmd = "{} -s {} shell su -c pwd".format(self._adb_path, adb_sn)
        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("_check_su,{}\n---stdout={}\n***\nstderr={}---\n\n".format(cmd, stdout, stderr))
        if not stdout:
            raise UemExtPhoneException("UE {} SuperUser Error. Please eneable super user on UE\n\tFollow instruction:"
                                       "https://confluence.int.net.nokia.com/pages/viewpage.action?pageId"
                                       "=706663048#UEsetupinstructions-UEAndroidapplicationsetup".format(adb_sn))
        else:
            if "su: not found" in "{}".format(stdout).lower():
                raise UemExtPhoneException(
                    "UE {} SuperUser Error. Please eneable super user on UE\n\tFollow instruction:"
                    "https://confluence.int.net.nokia.com/pages/viewpage.action?pageId"
                    "=706663048#UEsetupinstructions-UEAndroidapplicationsetup".format(adb_sn))

    def _run_ssh_command(self, command):
        "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        commands = '#!/usr/bin/expect -f\n'
        commands += "spawn ssh {}@{} {}{}{}\n".format(self._username,
                                                      self._ip,
                                                      chr(34),
                                                      command,
                                                      chr(34))

        commands += 'expect "assword:"\n'
        commands += 'send "{}{}r"\ninteract\n'.format(self._mypasswd, chr(92))
        mylogger.info("run_ssh_command,commands=".format(commands))
        my_bash = self._create_bash_cmd(commands)
        return [self._subprocess_exec_cmd(my_bash)]

    def _create_bash_cmd(self, file_content):

        mylogger.info("create_bash_cmd:{}".format(tempfile.gettempdir() + "/cmd.sh"))
        file = open(tempfile.gettempdir() + "/cmd.sh", "w")
        file.write(file_content)
        file.close()
        mylogger.info(self._subprocess_exec_cmd("chmod 777 {}".format(tempfile.gettempdir() + "/cmd.sh")))
        return tempfile.gettempdir() + "/cmd.sh"

    @staticmethod
    def _subprocess_exec_cmd(cmd):
        """Execute local command
            ret : sting stdout
        """
        s = ""
        try:
            s = subprocess.check_output(cmd.split())

        except Exception as ex:
            mylogger.info("_subprocess_exec_cmd,Exception:{}".format(ex.message))
            return ""
        return s,

    @staticmethod
    def subprocess_cmd(command):
        process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        proc_stdout = process.communicate()[0].strip()
        mylogger.debug(proc_stdout)
        return proc_stdout

    def start_process_by_ssh(self, command, cnt=3, timeout=10, adb_ssh=None):
        '''if command == 'reset_adb':
            return self._restart_adb_server()
        if "awk" not in command:
            return [self._run_ssh_command(command), ""]
        '''
        stdout = []
        stderr = []
        out = []
        try:
            mylogger.debug("start_process_by_ssh,{} ,timeout={}".format(command, timeout))

            if not adb_ssh:
                _ssh_client = self._ssh_client
            else:
                _ssh_client = adb_ssh

            if not isinstance(_ssh_client, SSHClient):
                _ssh_client = SSHClient()

            if not _ssh_client.get_transport() or not _ssh_client.get_transport().is_active():
                raise socket.error("Transport not active")

        except socket.error as e:
            mylogger.debug(
                "start_process_by_ssh,{}-start_process_by_ssh-reconnect-socket.error:command={}:\nsocket.error={}".
                    format( _ssh_client.__myname__ , command, str(e)))
            try:
                _ssh_client.set_missing_host_key_policy(AutoAddPolicy())
                _ssh_client.connect(self._ip, username=self._username, password=self._mypasswd,
                                    timeout=timeout, look_for_keys=False)  # , allow_agent=False)

                transport = _ssh_client.get_transport()
                transport.set_keepalive(0)

            except socket.error as e:
                if cnt > 2:
                    cnt -= 1
                    mylogger.debug("start_process_by_ssh,retry _run_ssh_command={}"
                                   .format(self._run_ssh_command(command)))

                    mylogger.debug("start_process_by_ssh,retry runcmd,socket.error.{}".format(cnt))
                    self.reboot_ue_pc()
                    return self.start_process_by_ssh(command, cnt, timeout, adb_ssh)
                if cnt > 1:
                    cnt -= 1
                    mylogger.debug("start_process_by_ssh,retry _run_ssh_command={}"
                                   .format(self._run_ssh_command(command)))

                    mylogger.debug("start_process_by_ssh,retry runcmd,socket.error.{}".format(cnt))
                    self._restart_sshd()
                    return self.start_process_by_ssh(command, cnt, timeout, adb_ssh)

                else:
                    mylogger.debug(
                        "start_process_by_ssh,{}-start_process_by_ssh-reconnect-socket.error:command={}:\nsocket.error={}".
                            format(_ssh_client.__myname__, command, str(e)))

                    raise UemExtSshCommandTimeout(str(e))

            except SSHException as ex:
                if cnt > 1:
                    cnt -= 1
                    mylogger.debug("start_process_by_ssh,retry _run_ssh_command={}"
                                   .format(self._run_ssh_command(command)))

                    mylogger.debug("start_process_by_ssh,retry runcmd,SSHException.cnt={}\n\t{}".format(cnt, ex))
                    self._restart_sshd()
                    return self.start_process_by_ssh(command, cnt, timeout, adb_ssh)

        except (UeThroughputError, ParameterError) as e:
            raise e

        except Exception as e:
            mylogger.debug(
                "start_process_by_ssh,{}:command={},Exception={}".format(_ssh_client.__myname__, command, e))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())

        if command == 'reset_adb':
            return self._restart_adb_server()

        mylogger.debug("start_process_by_ssh,cnt={}\n\tcommand={}".format(cnt, command))

        try:

            stdin, stdout, stderr = _ssh_client.exec_command(
                command,
                timeout=int(timeout))

            out = stdout.readlines()

            exit_status = str(stdout.channel.recv_exit_status())
            out += stdout.readlines()
            mylogger.debug("start_process_by_ssh,exit_status={}".format(exit_status))

            if int(exit_status) != 0 and cnt > 0:
                cnt -= 1
                mylogger.debug("start_process_by_ssh,retry runcmd,exit_status!=0")
                _ssh_client.close()
                return self.start_process_by_ssh(command, cnt, timeout, adb_ssh)
            elif int(exit_status) == 127 and cnt > 0:
                cnt -= 1
                mylogger.debug("start_process_by_ssh,retry runcmd,exit_status=127")
                self._restart_adb_server()
                self._reboot_ues_by_at()
                mylogger.debug("start_process_by_ssh,retry runcmd,wait for ues")
                time.sleep(60)
                _ssh_client.close()
                return self.start_process_by_ssh(command, cnt, timeout, adb_ssh)

            out += stdout.readlines()

        except SSHException as e:
            mylogger.debug("start_process_by_ssh,{}:\n\tcnt={}\n\tcommand={}\n\tSSHException:{}".
                           format(_ssh_client.__myname__, cnt, command, e))
            if cnt > 0:
                cnt -= 1
                mylogger.debug("start_process_by_ssh,retry runcmd,SSHException")
                _ssh_client.close()
                return self.start_process_by_ssh(command, cnt, timeout, adb_ssh)

        except Exception as e:
            mylogger.debug("start_process_by_ssh,{}:\n\tcnt={}\n\tcommand={}\n\tException:{}".
                           format(_ssh_client.__myname__, cnt, command, e))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())
            if cnt > 0:
                cnt -= 1
                mylogger.debug("start_process_by_ssh,retry runcmd,Exception")
                _ssh_client.close()
                return self.start_process_by_ssh(command, cnt, timeout, adb_ssh)
            # raise e
        # finally:
        # _ssh_client.close()
        retval = []
        if out.__len__() > 1 and "adb" in command:
            for a in out:
                mylogger.debug("start_process_by_ssh,stdout:check deamon,{}".format(a))
                if "daemon" not in a:
                    retval.append(a.rstrip())
            mylogger.debug("start_process_by_ssh,retval:check deamon={}".format(retval))
            return retval, stderr

        return out, stderr

    def get_screencap_text(self, ue):
        self._run_command('{} -s {} shell screencap /sdcard/screen.png'.format(self._adb_path, ue.adb_sn))
        self._run_command('{} -s {} pull /sdcard/screen.png /tmp/screen.png'.format(self._adb_path, ue.adb_sn))
        string = self.save_py_on_host_and_run().replace("\r", "")
        string = string.replace("\n", "")
        return string.decode('utf-8')

    def setup_ue(self, ue_alias, adb_sn, uepc_alias):
        mylogger.info("\n**** Setup UE={} sn={} UePc={} started ****".format(ue_alias, adb_sn, uepc_alias))
        self._chk_ue_in_adb_devices(ue_alias, adb_sn)
        try:
            self._check_su(adb_sn)
        except UemExtPhoneException as ex:
            mylogger.error(ex.message)

        ue = Ue(ue_alias, adb_sn)
        ue.model = self._phoneVer(ue.adb_sn)
        ue.model_fixed = ue.model.replace("-", "_")
        ue.build_version = self._get_build_version(ue.adb_sn)
        ue.no_of_sim_slots = self._get_number_of_sim_slots(adb_sn)
        ue.imei = self._get_dev_imei(ue)
        ue.ssh_client = SSHClient()
        ue.ssh_client.__myname__ = adb_sn
        self._myUes.append(ue)
        self._get_modems_imei()

    def setup_all_ues(self):
        for ue_adb in self.get_all_ues():
            try:
                self.setup_ue(ue_adb, ue_adb, self.get_uepc_alias())
            except Exception as e:
                print(e)

    def setup_ues(self, ue_adb_sn_list):
        mylogger.info("**** Setup UEs started ****")

        for ue_item in ue_adb_sn_list:
            self._chk_ue_in_adb_devices(ue_item["ue_alias"], ue_item["ue_adb_sn"])

            try:
                self._check_su(ue_item["ue_adb_sn"])
            except UemExtPhoneException as ex:
                mylogger.error(ex.message)

            ue = Ue(ue_item["ue_alias"], ue_item["ue_adb_sn"])
            ue.model = self._phoneVer(ue.adb_sn)
            ue.model_fixed = ue.model.replace("-", "_")
            ue.build_version = self._get_build_version(ue.adb_sn)
            ue.no_of_sim_slots = self._get_number_of_sim_slots(ue_item["ue_adb_sn"])
            ue.imei = self._get_dev_imei(ue)
            ue.ssh_client = SSHClient()
            ue.ssh_client.__myname__ = ue_item["ue_adb_sn"]
            self._myUes.append(ue)

        self._get_modems_imei()
        mylogger.info("**** Setup UEs finished ****")

        # hran_uem.endpoints.Ue(ue_adb_sn,
        #                              hran_uem.endpoints.UePc(self._ip, self._username, self._mypasswd,
        #                                                     self._port))

    def check_ssh(self, restart_ssh=False):
        try:
            stdout, _ = self.start_process_by_ssh('reset_adb', 3)
            mylogger.debug("check_ssh,reset_adb:stdout={}".format(stdout))
        except UemExtSshCommandTimeout:

            if restart_ssh:
                if self._restart_sshd():
                    self.check_ssh(False)
                else:
                    raise UemExtSshNotAvaliable("SSH not avaliable, Please check connection to :{}".format(self._ip))
            else:
                raise UemExtSshNotAvaliable("SSH not avaliable, Please check connection to :{}".format(self._ip))

    def teardown_ue(self, ue):
        try:
            mylogger.info("\nTeardown Ue-{} close all apps, amr calls, connections.\n".format(ue.adb_sn))
            self._end_call(ue)
            self._end_iperf(ue)
            ue.ssh_client.close()
            self._ssh_client.close()
        finally:
            pass

    def teardown(self):
        try:
            for ue in self._myUes:
                self.teardown_ue(ue)
        finally:
            pass

    def setup_pc(self, iperfclass):

        mylogger.info("\n**** Setup PC '{}' :{} started ****".format(self._alias, self._ip))
        self._iperf_ip = iperfclass.pc_host_ip
        self._iperf_uname = iperfclass.username
        self._iperf_passwd = iperfclass.password
        mylogger.debug("setup_pc,set_uepc_power_settings")
        self._set_uepc_power_settings()
        mylogger.debug("setup_pc,check_ssh")
        self.check_ssh(True)
        mylogger.debug("setup_pc,reset_modems")
        self.reset_modems()
        mylogger.debug("setup_pc,_get_adb_path")
        self._get_adb_path()
        mylogger.debug("setup_pc,_restart_adb_server")
        self._restart_adb_server()

        mylogger.info("****adb path={}****".format(self._adb_path))
        # self._reboot_ues_by_at()

        # self._hran_ue_man.register_ue_pc(self._alias, self._ip, self._port, self._username, self._mypasswd)
        # self._uePc = hran_uem.endpoints.UePc(self._ip, self._username, self._mypasswd, self._port)
        mylogger.info("**** Setup PC '{}' finished ****".format(self._alias))

    def setup_iperf_server(self, ip, uname, passwd):
        self._iperf_ip = ip
        self._iperf_uname = uname
        self._iperf_passwd = passwd
        mylogger.info("**** Setup Iperf server started ****")
        connection = SSH_CLS(self._iperf_ip, self._iperf_uname, self._iperf_passwd, "", mylogger)
        connection.sendCommand("pwd")
        mylogger.info("**** Setup Iperf server finished ****")

    def _get_adb_path(self):
        try:
            stdout, stderr = self.start_process_by_ssh('which adb', 3)
            self._adb_path = "".join(stdout).replace("\n", "").replace("\r", "")
            return
        except UemExtSshCommandTimeout:
            self._adb_path = "adb"
            raise UePcError("ADB not avaliable, Please check if adb is installed Pc ip :{}".format(self._ip))

    def _exec_command(self, cmd, timeout=10, adb_ssh=None):
        """Execute command by adb
            ret : sting stdout
        """
        try:
            mylogger.debug("_exec_command,{}".format(cmd))
            stdout, stderr = self.start_process_by_ssh(cmd, 3, timeout=timeout, adb_ssh=adb_ssh)
            mylogger.debug("_exec_command,\n\tcmd={}\n\tstdout={}\n\tstderr={}".format(cmd, stdout, stderr))

            return stdout
        except Exception as ex:
            mylogger.debug("_exec_command,{}\n---Exception:{}".format(cmd, ex))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())
            return []

    def _active_calls_by_at(self, myue, phone_number):
        '''AT+CLCC

                +CLCC: 1,0,0,1,0,"*98#",129
                +CLCC: 2,0,0,0,0,"0666002",129

                OK'''
        try:
            response = self.run_at_command(myue.adb_sn, [base64.b64encode("AT+CLCC")])[0].get("out")
        except Exception as ex:
            mylogger.debug("_active_calls_by_at,{}\n---Exception:{}".format("AT+CLCC", ex))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())
            response = None

        return phone_number in response

    def _active_calls(self, myue):
        cmd =  '{} -s {} shell "dumpsys telephony.registry | grep mCallState"'.format(self._adb_path, myue.adb_sn)
        out = self._exec_command(cmd)
        mylogger.debug("_active_calls,\n\tcmd={}\n\tout={}".format(cmd, out))
        return 'mCallState=2' in " ".join(out)

    def _start_call(self, myue, number):

        cmd =  "{} -s {} shell am start -a android.intent.action.CALL -d tel:{}".format(self._adb_path,
                                                                                        myue.adb_sn,
                                                                                        number)
        out = self._exec_command(cmd)
        mylogger.debug("_start_call,\n\tcmd={}\n\tout={}".format(cmd, out))

    def _end_call_key(self, myue, retries):
        #AT+CHUP
        self.run_at_command(myue.adb_sn, [base64.b64encode("AT+CHUP")])

        for i in range(retries):
            cmd =  "{} -s {} shell input keyevent KEYCODE_ENDCALL".format(self._adb_path, myue.adb_sn)
            self._exec_command(cmd)

    def _end_call(self, myue):
        self._end_call_key(myue, 2)

    def _end_iperf(self, myue):
        self._end_iperf_app(myue, 2)

    def _end_iperf_app(self, myue, retries):
        for i in range(retries):
            cmd = "{} -s {} shell am force-stop com.magicandroidapps.iperf".format(self._adb_path, myue.adb_sn)
            self._exec_command(cmd, adb_ssh=myue.ssh_client)
            cmd = "{} -s {} shell pkill iperf".format(self._adb_path, myue.adb_sn)
            self._exec_command(cmd, adb_ssh=myue.ssh_client)

    def _get_signal_stength_by_at(self, adb_sn):
        myue = self._get_ue__from_store_by_adb_sn(adb_sn)
        csq = self.run_at_command(adb_sn, [base64.b64encode("AT+CSQ")])
        mylogger.debug("_get_signal_stength_by_at,{}".format(csq))
        sig_str = None
        if csq:
            out = csq[0].get("out")
            mylogger.debug("_get_signal_stength_by_at,out={} {}".format(out, type(out)))
            #CSQ: 26
            if out:
                m = re.findall(r"\d+", out)
                if m:
                    mylogger.debug("_get_signal_stength_by_at,match={}".format(m))
                    sig_str = m[0]
                    mylogger.debug("_get_signal_stength_by_at,sig_str={}".format(sig_str))
                if sig_str:
                    return -113 + int(2 * int(sig_str))
                else:
                    return "Not known or not detectable"
            else:
                return "Not known or not detectable"
        else:
            return "Not known or not detectable"

    def _get_signal_stength(self, adb_sn):
        """int intdbm = -113 + 2
        * signalStrength.getGsmSignalStrength()dumpsys telephony.registry;
        SignalStrength: 29 99 -120 -160 -120 -1 -1 99 2147483647 2147483647 2147483647 2147483647 2147483647 0x4 gsm|lte
        """
        cmd = "{} -s {} shell dumpsys telephony.registry  | grep -i signalstrength".format(self._adb_path, adb_sn)
        s = self._exec_command(cmd)
        mylogger.debug("_get_signal_stength,{} \n {}".format(adb_sn, s))

        sim_cnt = self._get_number_of_sim_slots(adb_sn)

        mylogger.debug("_get_signal_stength,{}-Number of sim slots:{}".format(adb_sn, sim_cnt))
        for a in s:
            sig_str = re.findall(r"(?i)SignalStrength: \d+", a)
            if sig_str:
                mylogger.debug("_get_signal_stength,sig_str={}".format(sig_str))
                sig_str = re.findall(r"\d+", "".join(sig_str))
                mylogger.debug("_get_signal_stength,sig_str={}".format(sig_str))
                if int("".join(sig_str)) < 99:
                    mylogger.debug(
                        "_get_signal_stength,sim_cnt {},SignalStrength={}".format(sim_cnt, int("".join(sig_str))))
                    return -113 + int(2 * int("".join(sig_str)))
                else:
                    mylogger.debug("_get_signal_stength,sim_cnt {},SignalStrength={}".
                                   format(sim_cnt, int("".join(sig_str))))
                    sig_str = self._get_signal_stength_by_at(adb_sn)
                    return sig_str

                sim_cnt -= 1

                if sim_cnt == 0:
                    return self._get_signal_stength_by_at(adb_sn)
                    # "Not known or not detectable,sim0"

        return self._get_signal_stength_by_at(adb_sn)
        #"Not known or not detectable"

    def make_voice_call_for_rat(self, rat, number="0666002", duration=10):

        mylogger.info("Make Voice call for {} started".format(rat))
        if "LTE" in rat:
            raise UemExtPhoneException("AMR Call not possible for LTE")

        cell_list = self.get_bts_cells(rat)

        for ue in self._myUes:
            if rat in self._get_string_service_state(ue):
                cell_id = str(self.get_ue_cellid(ue.adb_sn))
                if cell_id not in cell_list:
                        #raise UemExtPhoneException \
                        mylogger.info("UE {} not connected to BTS, Ue cell {} , BTS cells {}".
                                      format(ue.adb_sn, cell_id, ["cellId:{},dw Freq:{}".
                                             format(x.get("cellId"),
                                                    x.get("downlinkFrequency")) for x in cell_list]))

                self.show_ue_table(ue.adb_sn)
                self.make_voice_call(ue.adb_sn,number, duration)

        mylogger.info("Make Voice call for {} finished".format(rat))

    def make_voice_call(self, ue_serial, number, duration):
        duration = int(duration)
        myue = self._get_ue__from_store_by_adb_sn(ue_serial)

        self._end_call(myue)

        self._start_call(myue, number)
        time.sleep(2)
        start_time = int(round(time.time() * 1000))
        rat = self._get_service_state(myue)

        if rat != 1 and rat != 2:
            raise UemExtPhoneException(
                    'AMR CALL: Call not possible on UE: Adb_sn:{}, IMEI:{}, Network type:{}'.
                        format(myue.adb_sn, myue.imei, self._get_string_service_state(myue)))

        if not self._active_calls(myue):
            if not self._active_calls_by_at(myue,number):
                raise UemExtPhoneException(
                        'AMR CALL: Call not started on UE: Adb_sn:{}, IMEI:{}, Network type:{}'.
                            format(myue.adb_sn, myue.imei, self._get_string_service_state(myue)))

        end_time = start_time + (duration * 1000)
        current_time = 0
        while current_time < end_time:
            current_time = int(round(time.time() * 1000))
            is_call_active = self._active_calls(myue)
            if not is_call_active:
                is_call_active = self._active_calls_by_at(myue, number)

            seconds_since_start = int(current_time - start_time) / 1000
            mylogger.info('AMR CALL : active {}s'.format(seconds_since_start))
            if is_call_active:
                time.sleep(1)
            elif (not is_call_active) and (seconds_since_start < duration):
                self.teardown_ue(myue)
                raise UemExtPhoneException('AMR CALL : Voice call has finished - unexpectedly after about {} sec.'
                                           .format(seconds_since_start))

        # self._end_call(myue)
        self.teardown_ue(myue)

    def _get_string_service_state(self, myue):
        out = self._get_service_state(myue)
        if 1 == out:
            return "GSM"
        elif 2 == out:
            return "WCDMA"
        elif 3 == out:
            return "LTE"
        else:
            return "Not known-{}".format(out)

    def _get_number_of_sim_slots(self, adb_sn):
        cmd =  "{} -s {} shell dumpsys telephony.registry  | grep -i 'phone id'".format(self._adb_path, adb_sn)
        s = self._exec_command(cmd)
        sim_cnt = 0
        for a in s:
            if "Phone Id=" in a:
                sim_cnt += 1

        mylogger.debug("_get_number_of_sim_slots,adb_sn={}:sim_cnt={}".format(adb_sn, sim_cnt))
        return sim_cnt

    def _get_service_state(self, myue):
        """Get connected RAT type by adb
                ret : NetType
            """
        sim_cnt = myue.no_of_sim_slots

        cmd = "{} -s {} shell dumpsys telephony.registry  | grep -i mservicestate".format(self._adb_path,
                                                                                          myue.adb_sn)
        s = self._exec_command(cmd)
        mylogger.debug("_get_service_state,sim_cnt={}\ncommand={},\nstdout={}".format(sim_cnt, cmd, s))
        for a in s:
            if "mServiceState=" in a:
                if "UMTS" in a:
                    return NetType.UMTS
                elif "LTE" in a:
                    return NetType.LTE
                elif "GSM" in a:
                    return NetType.GSM

                sim_cnt -= 1

                if sim_cnt == 0:
                    return NetType.UNKNOWN

        return NetType.UNKNOWN

    def _get_build_version(self, adb_sn):
        """Get android ver by adb
               ret : sting stdout
            """
        cmd = "{} -s {} shell getprop ro.build.version.release".format(self._adb_path, adb_sn)
        buid_ver = self._exec_command(cmd=cmd)

        mylogger.debug("_get_build_version,buid_ver={}:len={}".format(buid_ver,len(buid_ver)))

        if isinstance(buid_ver, collections.Sequence) and not isinstance(buid_ver, "".__class__) and len(buid_ver) > 0:
            buid_ver = buid_ver[0].replace("\n", "")
        else:
            buid_ver = buid_ver.replace("\n", "")

        return buid_ver

    def _get_dev_imei(self, myue):
        """Get phone IMEI by adb
                   ret : sting IMEI
                """
        imei = ""
        if "4.4.2" in myue.build_version:
            cmd = "{} -s {} shell dumpsys iphonesubinfo".format(self._adb_path, myue.adb_sn)
            s = self._exec_command(cmd, timeout=30)
            t = " ".join(s).split('Device ID = ')
            imei = t[1].replace("\r\r\n", "")
            mylogger.debug("_get_dev_imei,{}".format(imei))
            return "sim1={}".format(imei)

        cmd = "{} -s {} shell service call iphonesubinfo 1".format(self._adb_path, myue.adb_sn)
        s = self._exec_command(cmd, timeout=30)
        imei = ["sim1:{}".format("".join(re.findall(r'\d[.]', "".join(s))).replace(".", ""))]

        mylogger.debug("_get_dev_imei,1:{}".format(imei))

        if myue.no_of_sim_slots == 2:
            cmd = "{} -s {} shell service call iphonesubinfo 3".format(self._adb_path, myue.adb_sn)
            s = self._exec_command(cmd, timeout=30)
            if not "".join(re.findall(r'\d[.]', "".join(s))).replace(".", "") in imei:
                imei = ["".join(imei), "sim2:" + "".join(re.findall(r'\d[.]', "".join(s))).replace(".", "")]

            mylogger.debug("_get_dev_imei,2:{}".format(imei))

        return ','.join(imei)

    def _set_mtu_1358(self, myue):

        try:
            selected_phone = getattr(UePx, 'sam_' + myue.model_fixed + '_bsel_px')
        except AttributeError:
            mylogger.debug("Selected phone {} is not supported by library".format(myue.model_fixed))
            return

        if "SM-J250M" in selected_phone["model"]:
            mylogger.debug("_set_mtu_1358,SM-J250M")
            cmd = '{} -s {} shell {}ifconfig | grep rmnet_data | cut -d {} {} -f 1 {}'\
                      .format(self._adb_path, myue.adb_sn, self._su_str, chr(39), chr(39), self._su_str_end)

            stdout = self._exec_command(cmd=cmd)
            mylogger.debug("_set_mtu_1358,{}-rmnet_data interfaces :\t{}".format(myue.adb_sn, stdout))
            regex = r"rmnet_data+\d"
            matches = re.findall(regex, "".join(stdout))
            mylogger.debug("_set_mtu_1358,{}-rmnet_data match:\t{}".format(myue.adb_sn, matches))

            for match in matches:
                cmd = '{} -s {} shell {}ifconfig {} mtu 1358{}'.format(self._adb_path,
                                                                         myue.adb_sn,
                                                                         self._su_str,
                                                                         match,
                                                                         self._su_str_end)

                mylogger.debug("_set_mtu_1358,{},model={}-set {} mtu 1358 --".format(myue.adb_sn,
                                                                                     myue.model_fixed,
                                                                                     match))

                mylogger.debug("_set_mtu_1358,{}".format(self._exec_command(cmd=cmd)))

    def make_iperf_ex(self, myue):
        cmd = "{} -s {} shell su -c chmod 777 {}".format(self._adb_path, myue.adb_sn, self._iperf_path2)
        self._exec_command(cmd=cmd, adb_ssh=myue.ssh_client)
        cmd = "{} -s {} shell su -c chmod 777 {}".format(self._adb_path, myue.adb_sn, self._iperf_path)
        self._exec_command(cmd=cmd, adb_ssh=myue.ssh_client)

    def _get_ue_ip_by_at(self, adb_sn):
        #+CGPADDR: 1,10.9.170.189
        #+CGPADDR: 1,0.0.0.0
        try:
            response = self.run_at_command(adb_sn, [base64.b64encode("AT+CGPADDR")])[0]
        except IndexError as ex:
            mylogger.debug("_get_ue_ip_by_at,IndexError={}".format(ex))

        result = response.get("result")
        mylogger.debug("_get_ue_ip_by_at,result={}".format(result))
        if not result or "error" in result:
            return result

        out = response.get("out")
        mylogger.debug("_get_ue_ip_by_at,out={}".format(out))
        ip = re.findall(r"\d{1,3}[.]\d{1,3}[.]\d{1,3}[.]\d{1,3}", out)
        mylogger.debug("_get_ue_ip_by_at,ip={}".format(ip))

        if not ip:
            return None
        else:
            return ip[0] if not "0.0.0.0" in ip[0] else None

    def _get_ue_ip(self, myue, cnt=2, toggle_flag=False):
        """Get android IP by adb
        """
        ip = self._get_ue_ip_by_at(myue.adb_sn)
        if not ip:
            cmd = "{} -s {} shell ip addr".format(self._adb_path, myue.adb_sn)
            s = self._exec_command(cmd=cmd, adb_ssh=myue.ssh_client)
            start = False

            for line in s:
                if "rmnet" in line:
                    start = True
                if start:
                    if "inet" in line:
                        ip = re.findall(r"\d{1,3}[.]\d{1,3}[.]\d{1,3}[.]\d{1,3}", line)
                        mylogger.debug("_get_ue_ip,adb_sn={}-ip:len{}".format(myue.adb_sn, len(ip)))
                        return ip[0]
        else:
            return ip

        if cnt > 0 and toggle_flag:
            mylogger.info("**** Toggle data UE-{} ****".format(myue.ue_alias))
            self.ue_data_toggle(myue.adb_sn)
            time.sleep(3)
            cnt -= 1
            ip = self._get_ue_ip(myue, cnt, toggle_flag)
            if ip:
                return ip

    def _check_iperf2(self, myue):

        cmd = "{} -s {} shell {}".format(self._adb_path, myue.adb_sn, self._iperf_path2)
        stdout = self._run_command2(cmd)
        if not isinstance(stdout, list):
            ret = [stdout]

        mylogger.debug("_check_iperf2,cmd={}, ret='{}".format(cmd, stdout))

        if "iperf --help" in "".join(stdout).lower():
            return True
        else:
            return False

    def _check_iperf(self, myue):

        cmd = "{} -s {} shell {}".format(self._adb_path, myue.adb_sn, self._iperf_path)
        stdout = self._run_command2(cmd)
        if not isinstance(stdout, list):
            ret = [stdout]

        mylogger.debug("_check_iperf,cmd={}, ret='{}".format(cmd, stdout))

        if "iperf --help" in "".join(stdout).lower():
            myue.iperf_path = self._iperf_path
            return True
        else:
            if self._check_iperf2(myue):
                myue._iperf_path = self._iperf_path2

    @staticmethod
    def _parse_iperf(data, bits=True):
        n = 0
        tot = 0
        mult = 1

        if not type(data) in (list, tuple):
            data = data.splitlines()

        for line in data:
            if 'bits/sec' in line:
                if bits:
                    match = re.compile(r'.* (\S+)\sbits').match(line)
                else:
                    if "Kbits" in line:
                        mult = 0.001
                        match = re.compile(r'.* (\S+)\sKbits').match(line)
                    else:
                        match = re.compile(r'.* (\S+)\sMbits').match(line)

                if match:
                    mylogger.debug("_parse_iperf,{}".format(line))
                    tot += (float(match.group(1)) * mult)
                    n += 1
        if n > 0:
            return (round((tot / n), 2))
        else:
            return 0

    def iperf_download_test(self, myue, duration):
        """Make data transfer download test
        """
        mylogger.info("*********  Iperf Download UDP {}, duration={}s  *********\n".format(myue.adb_sn,duration))
        ret = ""
        ip = self._get_ue_ip(myue, toggle_flag=True)

        if not self._check_iperf(myue):
            self._install_iperf(myue.adb_sn)
            if not self._check_iperf(myue):
                mylogger.debug("iperf_download_test,iperf NOT Installed")
                raise UemExtIperfNotFound("NOT Installed app :{}".format(self._iperf_path))

        if ip:
            rat = self._get_service_state(myue)
            bandwidth = ["", "600K", "40M", "240M"][rat]
            port = str(random.randint(6001, 6099))
            connection = SSH_CLS(self._iperf_ip, self._iperf_uname, self._iperf_passwd, myue.adb_sn, mylogger)
            cmd = "{} -s {} shell {}echo  0 KBytes  0 bits/sec >/sdcard/datatransfer{}.log{}".format(self._adb_path,
                                                                                                    myue.adb_sn,
                                                                                                    self._su_str,
                                                                                                    myue.adb_sn,
                                                                                                    self._su_str_end)
            ret = self._exec_command(
                cmd=cmd,
                timeout=duration + 2, adb_ssh=myue.ssh_client)

            mylogger.debug(ret)
            # makeIperfEx(usbID)
            #cmd = self._adb_path + " -s " + myue.adb_sn + ' shell su -c ' + chr(
            cmd =  "{} -s {} shell {}{} -C -i 1 -s -u -p {} -f b >/sdcard/datatransfer{}.log{}".format(self._adb_path,
                                                                                                     myue.adb_sn,
                                                                                                     chr(34),
                                                                                                     myue.iperf_path,
                                                                                                     port,
                                                                                                     myue.adb_sn,
                                                                                                     chr(34))
            mylogger.debug("iperf_download_test,cmd={}".format(cmd))

            #cls, targetfunc, thname, loop, interval, *arglist
            #cmd, timeout=10, adb_ssh=None
            params = {"cmd" : cmd,"timeout" : duration + 20, "adb_ssh" : myue.ssh_client}

            ThM.run(targetfunc=self._exec_command,
                    thname=myue.adb_sn + "_adb",
                    loop=True,
                    interval=duration + 20,
                    arglist=[cmd, duration + 20, myue.ssh_client])

            # thread = threading.Thread(target=_execCommand_1,args=([cmd]))
            # thread.start()
            # connect to iperf FTP
            connection.sendCommand(
                "iperf -C -c {} -u -b {} -p {} -i 1 -t {} -f m".format(ip, bandwidth, port, duration))
            # kill iperf on UE
            # ret = _execCommand_1(self._adb_path + " -s " + usbID + " shell su -c pkill iperf")
            # print ret
            # read results
            ret = self._exec_command("{} -s {} shell {}set echo off &&"
                                     " test -f '/sdcard/datatransfer{}.log' &&"
                                     " echo 'File exists'{}".format(self._adb_path,
                                                                    myue.adb_sn,
                                                                    chr(34),
                                                                    myue.adb_sn,
                                                                    chr(34)))
            if not isinstance(ret, list):
                ret = [ret]
            ThM.stop_loop("{}_adb".format(myue.adb_sn))

            if 'file exists' not in "".join(ret).lower():
                raise UemExtCmdResponseEmpty(
                    "File /sdcard/datatransfer{}.log do not exist,please check".format(myue.adb_sn))

            ret = self._exec_command(
                 "{} -s {} shell {}cat /sdcard/datatransfer{}.log{}".format(self._adb_path,
                                                                            myue.adb_sn,
                                                                            chr(34),
                                                                            myue.adb_sn,
                                                                            chr(34))
                , adb_ssh=myue.ssh_client)

            if not isinstance(ret, list):
                ret = [ret]

            if not ret:
                mylogger.debug("iperf_download_test,{}".format(ret))
                time.sleep(5)
                ret = self._exec_command(
                     "{} -s {} shell {}cat /sdcard/datatransfer{}.log{}".format(self._adb_path,
                                                                                myue.adb_sn,
                                                                                chr(34),
                                                                                myue.adb_sn,
                                                                                chr(34)),
                    adb_ssh=myue.ssh_client)

                if not isinstance(ret, list):
                    ret = [ret]

                if not ret:
                    raise UemExtCmdResponseEmpty(
                        "Empty file /sdcard/datatransfer{}.log ,please check file content".format(myue.adb_sn))
                else:
                    mylogger.info('DL_datatransfer-{}\n{}'.format(myue.adb_sn,
                                                                  re.sub(r'\n+', '\n', "\n".join(ret)).strip()))
            else:
                mylogger.info('DL_datatransfer-{}\n{}'.format(myue.adb_sn,
                                                              re.sub(r'\n+', '\n', "\n".join(ret)).strip()))

            # print ret
            mylogger.info("{}--------- Download Average={} bits/sec ---------\n".
                          format(myue.adb_sn, self._parse_iperf("".join(ret))))

        else:
            mylogger.error("IP not found for {} IMEI:{}".format(myue.adb_sn, myue.imei))

        mylogger.info("*********  end Iperf Download UDP ,adb_sn={}  *********\n".format(myue.adb_sn))
        return self._parse_iperf("".join(ret))

    def iperf_upload_test(self, myue, test_time):
        """Make data transfer upload test
        """
        mylogger.info("*********  Iperf Upload UDP {}, duration={}s  *********\n".format(myue.adb_sn, test_time))

        ret = ""
        ip = self._get_ue_ip(myue, toggle_flag=True)

        if not self._check_iperf(myue):
            self.make_iperf_ex(myue)
            if not self._check_iperf(myue):
                mylogger.debug("iperf_upload_test,iperf NOT Installed")
                raise UemExtIperfNotFound("NOT Installed app :{}".format(self._iperf_path))
        if ip:
            # needed for srn-lte-jaguar
            self._set_mtu_1358(myue)
            rat = self._get_service_state(myue)
            bandwidth = ["","600K","40M","240M"][rat]

            port = str(random.randint(6001, 6099))
            connection = SSH_CLS(self._iperf_ip, self._iperf_uname, self._iperf_passwd, myue.adb_sn, mylogger)
            connection.sendCommand("echo '0 KBytes  0 bits/sec' >/tmp/UP_datatransfer{}.log".format(myue.adb_sn))

            #cmd = self._adb_path + " -s " + myue.adb_sn + ' shell su -c "' + myue.iperf_path + " -C -c " + \
            cmd = '{} -s {} shell "{} -C -c {}  -i 1 -u -b {} -p {} -t {} -f m"'.format(self._adb_path,
                                                                                          myue.adb_sn,
                                                                                          myue.iperf_path,
                                                                                          self._iperf_ip,
                                                                                          bandwidth,
                                                                                          port,
                                                                                          test_time)
            # cls, targetfunc, thname, loop, interval, *arglist
            ThM.run(targetfunc=connection.sendCommand,
                    thname=myue.adb_sn + "_adb",
                    loop=True,
                    interval=test_time,
                    arglist=["iperf -C -i 1 -s -u -p {} -f 'b'>/tmp/UP_datatransfer{}.log".
                    format(port, myue.adb_sn)])

            # thread = threading.Thread(target=connection.sendCommand,args=(["iperf  -C -i 1 -s -u -p " + port +
            #  " >/tmp/datatransfer" + usbID + ".log"]))
            # thread.start()
            # connect to iperf FTP
            ret = self._exec_command(cmd, timeout=test_time, adb_ssh=myue.ssh_client)
            mylogger.debug("iperf_upload_test,\n\tcmd={}\n\tret={}".format(cmd, ret))
            # kill iperf on UE
            # ret = _execCommand_1(self._adb_path + " -s " + usbID + " shell su -c 'pkill iperf'")
            # read results from FTP
            time.sleep(5)
            ret = connection.sendCommand('cat /tmp/UP_datatransfer{}.log'.format(myue.adb_sn))
            ThM.stop_loop(myue.adb_sn + "_adb")
            if not ret:
                ret = connection.sendCommand('cat /tmp/UP_datatransfer{}.log'.format(myue.adb_sn))

            if not ret:
                mylogger.debug("iperf_upload_test,ret={}".format(ret))
                time.sleep(5)
                ret = connection.sendCommand('cat /tmp/UP_datatransfer{}.log'.format(myue.adb_sn))

                if not ret:
                    raise UemExtCmdResponseEmpty(
                        'Empty file /tmp/UP_datatransfer{}.log ,please check file content'.format(myue.adb_sn))
                else:
                    if not isinstance(ret, list):
                        ret = [ret]

                    mylogger.info('UP_datatransfer-{}\n{}'.format(myue.adb_sn, "".join(ret)))
            else:
                if not isinstance(ret, list):
                    ret = [ret]
                mylogger.debug('UP_datatransfer-{}\n{}'.format(myue.adb_sn, ret))
                mylogger.info('UP_datatransfer-{}\n{}'.format(myue.adb_sn, "".join(ret)))

            mylogger.info("---------Ue {} Upload  Average={}s bits/sec ---------\n".
                          format(myue.adb_sn,self._parse_iperf("".join(ret))))

        else:
            mylogger.error("IP not found for {} IMEI:{}".format(myue.adb_sn, myue.imei))

        mylogger.info("*********  end Iperf Upload UDP ,adb_sn={}  *********\n".format(myue.adb_sn))
        return self._parse_iperf("".join(ret))

    def _iperf_by_sn(self, myue, test_time, dl_max="20", dl_min="14", ul_max="12", ul_min="9"):
        """Make download test by adb iperf app
            """
        ul_th = self.iperf_upload_test(myue, test_time)
        dl_th = self.iperf_download_test(myue, test_time)

        if int(ul_th) < int(ul_min):
            raise UeThroughputError("{}-UL Throughput to small : {}<{}".format(myue.adb_sn,ul_th,ul_min))
        elif int(ul_th) > int(ul_max):
            mylogger.warning("{}-UL Throughput to big : {}>{}".format(myue.adb_sn, ul_th, ul_max))

        if int(dl_th) < int(dl_min):
            raise UeThroughputError("{}-DL Throughput to small : {}<{}".format(myue.adb_sn, dl_th, dl_min))
        elif int(dl_th) > int(dl_max):
            mylogger.warning("{}-DL Throughput to big : {}>{}".format(myue.adb_sn, dl_th, dl_max))

        return

    @staticmethod
    def _ue_info(myue):
        return "{}-{}-{}-{}".format(myue.ue_alias, myue.adb_sn, myue.imei, myue.com_port)

    @staticmethod
    def _ue_cell_info(myue):
        return "{}-{}-{}".format(myue.ue_alias, myue.adb_sn, myue.cell_id)

    def get_all_ues_cellid(self):
        for ue in self._myUes:
            self.get_ue_cellid(ue.adb_sn)

        all_ues = map(self._ue_cell_info, self._myUes)

        return all_ues

    @staticmethod
    def get_bts_cells(rat):
        bts = BTS(mylogger)
        cell_info = []
        try:
            cell_info = bts.get_bts_cells_info(rat)
        except Exception as ex:
            mylogger.info("get_bts_cells,{}".format(ex))
            mylogger.info(sys.exc_type)
            mylogger.info(traceback.format_exc())

        return cell_info

    def make_ps_call_for_rat(self, rat, duration=10, protocol="udp", bandwidth="240", dl_max="2000000000", dl_min="14",
                     ul_max="120000000", ul_min="9", cnt=0):

        mylogger.info("Make PS call for {} started".format(rat))
        cell_list = self.get_bts_cells(rat)

        for ue in self._myUes:
            if rat in self._get_string_service_state(ue):
                cell_id = str(self.get_ue_cellid(ue.adb_sn))
                if cell_id not in cell_list:
                    # raise UemExtPhoneException \
                    mylogger.info("UE {} not connected to BTS, Ue cell {} , BTS cells {}".
                                               format(ue.adb_sn, cell_id, ["cellId:{},dw Freq:{}".
                                                      format(x.get("cellId"),
                                                             x.get("downlinkFrequency")) for x in cell_list]))
                self.show_ue_table(ue.adb_sn)
                self.make_ps_call(ue.adb_sn, duration, protocol, bandwidth, dl_max, dl_min, ul_max,
                                  ul_min, cnt)

        mylogger.info("Make PS call for {} finished".format(rat))

    def make_ps_call(self, ue_serial, duration, protocol="udp", bandwidth="240", dl_max="2000000000", dl_min="14", ul_max="120000000",
                     ul_min="9", cnt=0):  # ue_alias,srat=None,cnt=0):
        myue = self._get_ue__from_store_by_adb_sn(ue_serial)

        if cnt == 3:
            mylogger.info("**** Data call test started for {} ****".format(myue.ue_alias))

        try:
            service_state = self._get_service_state(myue)
            str_service_state = self._get_string_service_state(myue)
            mylogger.info("{}-imei={} ,RAT={}".format(myue.adb_sn, myue.imei,str_service_state))
            if not str_service_state:
                service_state = self._get_service_state(myue)
                mylogger.debug(
                    "make_ps_call,{}-imei={},service_state={}".format(myue.adb_sn, myue.imei, service_state))

            if service_state != 0:
                self._end_call(myue)
                self._data_transfer(myue.adb_sn, "enable")
                self._iperf_by_sn(myue, int(duration), dl_max=dl_max, dl_min=dl_min, ul_max=ul_max, ul_min=ul_min)
            else:
                mylogger.debug("make_ps_call,Data call not possible Unknown RAT {}".format(service_state))
                if cnt > 1:
                    cnt -= 1
                    mylogger.info("**** Try to recover network UE-{} ****{}".format(myue.ue_alias,cnt))
                    self.toogleAirplane(myue.adb_sn)
                    time.sleep(10)
                    service_state = self._get_service_state(myue)

                    if not service_state or service_state == 0:
                        self.make_ps_call(ue_serial, duration, protocol, bandwidth, dl_max, dl_min, ul_max, ul_min, cnt)

                elif cnt == 1:
                    cnt -= 1
                    mylogger.info("**** Reboot UE-{} ****".format(myue.ue_alias))
                    self.reboot_ue(myue)
                    time.sleep(10)
                    mylogger.info("**** UE-{} is reachable ****".format(myue.ue_alias))
                    service_state = self._get_service_state(myue)
                    if not service_state or service_state == 0:
                        raise UemExtPhoneException(
                            "Data call not possible Unknown RAT {}, Please check UE!".format(service_state))
                    else:
                        self.make_ps_call(ue_serial, duration, protocol, bandwidth, dl_max, dl_min, ul_max, ul_min, cnt)
                else:
                    raise UemExtPhoneException(
                        "Data call not possible Unknown RAT {}, Please check UE!".format(service_state))

        except Exception as a:
            mylogger.debug("make_ps_call,{}".format(a))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())
            self.teardown_ue(myue)
            raise a
        finally:
            mylogger.debug("**** Data call test {} ****".format(cnt))
            if cnt == 3:
                self.teardown_ue(myue)
                mylogger.info("**** Data call test finished for {} ****".format(myue.ue_alias))

    def set_band(self, ue_alias, sim_no, rat, band):

        ue = self._get_ue__from_store_by_alias(ue_alias)

        try:
            mylogger.info("Set band:{},{},{},{},{}\n".format(ue.model, ue.model_fixed, sim_no, rat, band))

            mylogger.debug("set_band,{}".format(self._bandMenu_set(ue, sim_no, rat, band)))
            self._hran_ue_man.show_ue_table(ue.ue_alias)
            print(self._hran_ue_man.get_cell_id(ue.ue_alias))

        except UemExtSshCommandTimeout as a:
            mylogger.error(a.message)
        except UemExtPhoneVerEmpty as a:
            mylogger.error(a.message)
        except UemExtRilServiceException as a:
            mylogger.error(a.message)
        except UemExtPhoneException as a:
            mylogger.error(a.message)
        except Exception as ex:
            mylogger.debug("set_band,Exception={}".format(ex))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())

    def _set_uepc_power_settings(self):
        content = """JHJlc3VsdCA9IHBvd2VyY2ZnIC9MDQoNCkZvckVhY2ggKCRsaW5lIGluICQoJHJlc3VsdCAtc3BsaXQgImByYG4iKSkNCnsN
        CiAgICBpZigkbGluZS50b0xvd2VyKCkuY29udGFpbnMoImhpZ2ggcGVyZm9ybWFuY2UiKSl7DQogICAgICAgICRwZXJmID0gJGxpbmUuc3Bsa
        XQoKVszXQ0KICAgICAgICBUcnkgew0KICAgICAgICAgICAgcG93ZXJjZmcgL1MgJHBlcmYNCiAgICAgICAgICAgICNwb3dlcmNmZyAvU0VUQU
        NWQUxVRUlOREVYIFNDSEVNRV9DVVJSRU5UIDJhNzM3NDQxLTE5MzAtNDQwMi04ZDc3LWIyYmViYmEzMDhhMyA0OGU2YjdhNi01MGY1LTQ3ODI
        tYTVkNC01M2JiOGYwN2UyMjYgMA0KICAgICAgICAgICAgI3Bvd2VyY2ZnIC9TRVRBQ1ZBTFVFSU5ERVggU0NIRU1FX0NVUlJFTlQgMDAxMmVl
        NDctOTA0MS00YjVkLTliNzctNTM1ZmJhOGIxNDQyIDY3MzhlMmM0LWU4YTUtNGE0Mi1iMTZhLWUwNDBlNzY5NzU2ZSA5OTk5OTk5OTk5OTk5O
        Tk5OTk5OQ0KICAgICAgICAgICAgcG93ZXJjZmcuZXhlIC1jaGFuZ2UgLW1vbml0b3ItdGltZW91dC1hYyAwDQoNCiAgICAgICAgICAgIHBvd2
        VyY2ZnLmV4ZSAtY2hhbmdlIC1tb25pdG9yLXRpbWVvdXQtZGMgMA0KDQogICAgICAgICAgICBwb3dlcmNmZy5leGUgLWNoYW5nZSAtZGlzay1
        0aW1lb3V0LWFjIDANCg0KICAgICAgICAgICAgcG93ZXJjZmcuZXhlIC1jaGFuZ2UgLWRpc2stdGltZW91dC1kYyAwDQoNCiAgICAgICAgICAg
        IHBvd2VyY2ZnLmV4ZSAtY2hhbmdlIC1zdGFuZGJ5LXRpbWVvdXQtYWMgMA0KDQogICAgICAgICAgICBwb3dlcmNmZy5leGUgLWNoYW5nZSAtc
        3RhbmRieS10aW1lb3V0LWRjIDANCg0KICAgICAgICAgICAgcG93ZXJjZmcuZXhlIC1jaGFuZ2UgLWhpYmVybmF0ZS10aW1lb3V0LWFjIDANCg
        0KICAgICAgICAgICAgcG93ZXJjZmcuZXhlIC1jaGFuZ2UgLWhpYmVybmF0ZS10aW1lb3V0LWRjIDANCiAgICAgICAgfSANCiAgICAgICAgY2F
        0Y2ggew0KCSAgICAgICAgZWNobyAiRXJyb3IgcG93ZXJjZmciDQoJICAgIH0NCiAgfQ0KDQp9DQppZiAoW3N0cmluZ106OklzTnVsbE9yRW1w
        dHkoJHBlcmYpKXsNCiAgICBlY2hvICJFcnJvciBwZXJmIg0KfQ0KDQo="""

        out = ""
        try:
            mylogger.info("-Set UePc Power Plan to 'high performance'")
            out = self.save_py_on_host_and_run_pow_shell(content).replace("\x00", "")
        except Exception as e:
            mylogger.debug("_set_uepc_power_settings,Exception={}".format(e))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())

        mylogger.debug("_set_uepc_power_settings,out={}".format(out))

    def reset_modems(self):
        content = """SWYgKC1OT1QgKFtTZWN1cml0eS5QcmluY2lwYWwuV2luZG93c1ByaW5jaXBhbF1bU2VjdXJpdHkuUHJpbmNpcGFsLldpbmRv
        d3NJZGVudGl0eV06OkdldEN1cnJlbnQoKSkuSXNJblJvbGUoW1NlY3VyaXR5LlByaW5jaXBhbC5XaW5kb3dzQnVpbHRJblJvbGVdICJBZG1pbm
        lzdHJhdG9yIikpDQp7IA0KICBlY2hvICIqIFJlc3Bhd25pbmcgUG93ZXJTaGVsbCBjaGlsZCBwcm9jZXNzIHdpdGggZWxldmF0ZWQgcHJpdmls
        ZWdlcyINCiAgJHBpbmZvID0gTmV3LU9iamVjdCBTeXN0ZW0uRGlhZ25vc3RpY3MuUHJvY2Vzc1N0YXJ0SW5mbw0KICAkcGluZm8uRmlsZU5hb
        WUgPSAicG93ZXJzaGVsbCINCiAgJHBpbmZvLkFyZ3VtZW50cyA9ICImICciICsgJE15SW52b2NhdGlvbi5NeUNvbW1hbmQuUGF0aCArICInIg
        0KICAkcGluZm8uVmVyYiA9ICJSdW5BcyINCiAgJHBpbmZvLlJlZGlyZWN0U3RhbmRhcmRFcnJvciA9ICRmYWxzZQ0KICAkcGluZm8uUmVkaXJ
        lY3RTdGFuZGFyZE91dHB1dCA9ICRmYWxzZQ0KICAkcGluZm8uVXNlU2hlbGxFeGVjdXRlID0gJHRydWUNCiAgJHAgPSBOZXctT2JqZWN0IFN5
        c3RlbS5EaWFnbm9zdGljcy5Qcm9jZXNzDQogICRwLlN0YXJ0SW5mbyA9ICRwaW5mbw0KICAkcC5TdGFydCgpIHwgT3V0LU51bGwNCiAgJHAuV
        2FpdEZvckV4aXQoKQ0KICBlY2hvICIqIENoaWxkIHByb2Nlc3MgZmluaXNoZWQiDQogIHR5cGUgJGVudjpURU1QIi90cmFuc2NyaXB0LnR4dC
        INCiAgUmVtb3ZlLUl0ZW0gJGVudjpURU1QIi90cmFuc2NyaXB0LnR4dCINCiAgRXhpdCAkcC5FeGl0Q29kZQ0KfSBFbHNlIHsNCiAgZWNobyA
        iQ2hpbGQgcHJvY2VzcyBzdGFydGluZyB3aXRoIGFkbWluIHByaXZpbGVnZXMiDQogIFN0YXJ0LVRyYW5zY3JpcHQgLVBhdGggJGVudjpURU1QI
        i90cmFuc2NyaXB0LnR4dCINCn0NCg0KDQokc0NvbVBvcnROdW1iZXIgPSBHZXQtV21pT2JqZWN0IFdpbjMyX1BvdHNNb2RlbSB8IGANCglXaGV
        yZS1PYmplY3QgeyRfLkRldmljZUlEIC1saWtlICJVU0JcVklEKiIgLWFuZCAkXy5TdGF0dXMgLWxpa2UgIk9LIn0gfCBgDQoJZm9yZWFjaCB7J
        F8uRGV2aWNlSUR9DQoNCmZvcmVhY2ggKCRlbGVtZW50IGluICRzQ29tUG9ydE51bWJlcikgew0KCSRiYmQgPSBHZXQtV21pT2JqZWN0ICBXaW4
        zMl9QblBFbnRpdHkgfCBXaGVyZS1PYmplY3QgeyRfLkRldmljZUlEIC1saWtlICIqJGVsZW1lbnQqIn0NCglJbnZva2UtV21pTWV0aG9kIC1uY
        W1lICJEaXNhYmxlIiAtSW5wdXRPYmplY3QgJGJiZA0KCVN0YXJ0LVNsZWVwIDINCglJbnZva2UtV21pTWV0aG9kIC1uYW1lICJFbmFibGUiIC1
        JbnB1dE9iamVjdCAkYmJkDQoJZWNobyAkYmJkDQp9DQo="""

        out = ""
        try:
            mylogger.info("-Reset all modems")
            out = self.save_py_on_host_and_run_pow_shell(content).replace("\x00", "") #, pipe_fliename="/out.log").replace("\x00", "")
        except Exception as e:
            mylogger.debug("reset_modems,Exception={}".format(e))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())

        mylogger.debug("reset_modems,out={}".format(out))

    def _reboot_ues_by_at(self):
        content = """JHNDb21Qb3J0TnVtYmVyID0gR2V0LVdtaU9iamVjdCBXaW4zMl9Qb3RzTW9kZW0gfCBgDQoJV2hlcmUtT2JqZWN0IHskXy
        5EZXZpY2VJRCAtbGlrZSAiVVNCXFZJRCoiIC1hbmQgJF8uU3RhdHVzIC1saWtlICJPSyJ9IHwgYA0KCWZvcmVhY2ggeyRfLkF0dGFjaGVkV
        G99DQoNCmZvcmVhY2ggKCRlbGVtZW50IGluICRzQ29tUG9ydE51bWJlcikgew0KCSRsaW5lID0gIiINCgl3cml0ZS1ob3N0ICRlbGVtZW50
        ICAifCIgDQoJJHBvcnQgPSBuZXctT2JqZWN0IFN5c3RlbS5JTy5Qb3J0cy5TZXJpYWxQb3J0ICRlbGVtZW50LDExNTIwMCAsTm9uZSw4LG9
        uZQ0KCSRwb3J0LlJlYWRUaW1lb3V0ID0gNTAwMDsNCgkkcG9ydC5Xcml0ZVRpbWVvdXQgPSAxMDAwOw0KCSRwb3J0Lk9wZW4oKTsNCgkkcG
        9ydC5Xcml0ZUxpbmUoICJBVCtDRlVOPTEsMWByIiApOw0KCSRjb250aW51ZSA9IDE7DQoJIHdoaWxlKCRjb250aW51ZSAtbHQgMTAwKQ0KI
        CAgICAgICB7CQlUcnkgew0KCQkJCQkkbGluZSArPSAkcG9ydC5SZWFkTGluZSgpOw0KCQkJCX0gY2F0Y2ggIFtzeXN0ZW0uZXhjZXB0aW9u
        XSB7DQoJCQkJfQ0KCQkJCQ0KICAgICAgICAgICAgICAgICRjb250aW51ZSArPSAxOw0KICAgICAgICAgICAgICAgIGlmICggLW5vdCAoKCR
        saW5lKS5Db250YWlucygiT0siKSAtb3IgKCRsaW5lKS5Db250YWlucygiRVJST1IiKSkgKQ0KICAgICAgICAgICAgICAgIHsNCiAgICAgICA
        gICAgICAgICAgICAgICAgICRvdXQgKz0gJGxpbmUNCiAgICAgICAgICAgICAgICB9IGVsc2Ugew0KICAgICAgICAgICAgICAgICAgICAgICA
        gJGNvbnRpbnVlID0gMTAxOw0KICAgICAgICAgICAgICAgIH0NCiAgICAgICAgfQ0KICAgICAgICB3cml0ZS1ob3N0ICgkZWxlbWVudCArICI
        gLSAiICsgJG91dCkNCgkNCgkkcG9ydC5DbG9zZSgpDQp9DQo="""
        out = ""
        try:
            out = self.save_py_on_host_and_run_pow_shell(content).replace("\x00", "")
        except Exception as e:
            mylogger.debug("_reboot_ues_by_at,Exception={}".format(e))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())

        mylogger.debug(out)
        mylogger.info("All UEs restarted , wait 60s")
        time.sleep(60)

    def _recover_modem(self, ue):
        cmd = '{} -s {} shell su -c "svc usb setFunction diag,acm,adb"'.format(self._adb_path,
                                                                                ue.adb_sn)
        mylogger.info("Enable USB modem for Ue-{}".format(ue.adb_sn))
        self._run_command(cmd)
        self.reset_modems()
        self._get_modems_imei()

    def run_at_command(self, adb_sn, commands=None, cnt=1):
        if commands is None:
            commands = []
        ue = self._get_ue__from_store_by_adb_sn(adb_sn)

        content = """cGFyYW0oW1N0cmluZ10gJGNvbU5vID0gIiIsIA0KICAgICAgW1N0cmluZ1tdXSAkY29tbWFuZCApDQogICAgICANCg0KICAg
        IA0KJHBvcnQgPSBuZXctT2JqZWN0IFN5c3RlbS5JTy5Qb3J0cy5TZXJpYWxQb3J0ICRjb21Obyw5NjAwICxOb25lLDgsb25lDQokcG9ydC5SZ
        WFkVGltZW91dCA9IDEwMDAwOw0KJHBvcnQuV3JpdGVUaW1lb3V0ID0gMjAwMDsNCnRyeSB7DQoJJHBvcnQuT3BlbigpDQoNCglmb3JlYWNoIC
        gkZWxlbWVudCBpbiAkY29tbWFuZCkgew0KCQkkc0RlY29kZWRTdHJpbmc9W1N5c3RlbS5UZXh0LkVuY29kaW5nXTo6VVRGOC5HZXRTdHJpbmc
        oW1N5c3RlbS5Db252ZXJ0XTo6RnJvbUJhc2U2NFN0cmluZygkZWxlbWVudCkpDQoJCXRyeSB7DQogICAgICAgICAgICAgU3RhcnQtU2xlZXAg
        LXMgMQ0KICAgICAgICAgICAgICRwb3J0LlJlYWRFeGlzdGluZygpOw0KICAgICAgICB9IGNhdGNoIFtFeGNlcHRpb25dIHsgZWNobyAkXy5Fe
        GNlcHRpb24uR2V0VHlwZSgpLkZ1bGxOYW1lLCAkXy5FeGNlcHRpb24uTWVzc2FnZSB9DQoJCQ0KCQkkcG9ydC5Xcml0ZUxpbmUoICRzRGVjb2
        RlZFN0cmluZyArICJgciIgKTsNCgkJJGxpbmUgPSAiIg0KCQkkcmVzdWx0ID0gIiINCgkJJG91dCA9ICAiIg0KCQkkY29udGludWUgPSAxOw0
        KCQkJIHdoaWxlKCRjb250aW51ZSAtbHQgMTAwKQ0KCQkJCXsJCQ0KCQkJCQkJJGxpbmUgPSAkcG9ydC5SZWFkTGluZSgpOw0KCQkJCQkJJGNv
        bnRpbnVlICs9IDE7DQoJCQkJCQlpZiAoICAoJGxpbmUpLkNvbnRhaW5zKCJPSyIpIC1vciAoJGxpbmUpLkNvbnRhaW5zKCJFUlJPUiIpKQ0KC
        QkJCQkJewkkcmVzdWx0ID0gJGxpbmUNCgkJCQkJCQkNCgkJCQkJCQkkY29udGludWUgPSAxMDE7DQoJCQkJCQl9CWVsc2Ugew0KCQkJCQkJCS
        RvdXQgKz0gJGxpbmUNCgkJCQkJCX0NCgkJCQkJCSRvdXQgPSAkb3V0LlJlcGxhY2UoJHNEZWNvZGVkU3RyaW5nLCIiKQ0KCQkJCQkJJG91dCA
        9ICRvdXQuUmVwbGFjZSgiYHIiLCIsIikNCgkJCQkJCSRvdXQgPSAkb3V0LlJlcGxhY2UoImAwIiwiIikNCgkJCQl9DQoJCQkJd3JpdGUtaG9z
        dCAoICRzRGVjb2RlZFN0cmluZyArICJ8IiArICRvdXQgKyAgInwiICsgJHJlc3VsdCApDQoJCSAgICAgICAgICAgICAgICANCgkJDQoJfSANC
        gkkcG9ydC5DbG9zZSgpDQoNCn0NCiAgICBjYXRjaCBbRXhjZXB0aW9uXQ0Kew0KICAgZWNobyAgJF8gfCBPdXQtU3RyaW5nDQogICBlY2hvIC
        RfLkV4Y2VwdGlvbnxmb3JtYXQtbGlzdCAtZm9yY2UNCn0NCg=="""

        if not ue.com_port:
            if cnt == 1:
                mylogger.warning("UE {} : modem not found !!! Recheck".format(ue.adb_sn))
                self._recover_modem(ue)
                if ue.com_port:
                    return self.run_at_command(ue.adb_sn, commands, 0)
            else:
                ret_val= "Error UE {} :modem not found !!! Please enable usb modem in UE settings".format(ue.adb_sn)
                mylogger.error(ret_val)
                return ret_val

        out = ""
        try:
            out = self.save_py_on_host_and_run_pow_shell(content, ue.com_port, commands).replace("\x00", "")
        except Exception as e:
            mylogger.debug("run_at_command,Exception={}".format(e))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())

        if not isinstance(out, list):
            out = out.split("AT+")

        mylogger.debug("run_at_command,out={}".format(out))

        if "xception" in "".join(out):
            result = "Exception , Error command not run"
            for a in "".join(out).split("\n"):
                if "FullyQualifiedErrorId" in a:
                    result = a + ",Error"

            out=[{"command":",".join([base64.b64decode(i) for i in commands])}, {"out":""} ,{"result": result}]
            return out

        out = list({"command": x.split("|")[0].replace("\n", "").replace("\r", ""),
                    "out": x.split("|")[-2].replace("\n", "").replace("\r", ""),
                    "result": x.split("|").pop().replace("\n", "").replace("\r", "")}
                   for x in out if "|" in x)

        return out

    def get_ue_cellid(self, adb_sn, cnt=1):

        ue = self._get_ue__from_store_by_adb_sn(adb_sn)
        content = """cGFyYW0oW1N0cmluZ10gJGNvbU5vID0gIiIsIA0KICAgICAgW1N0cmluZ1tdXSAkY29tbWFuZCkNCiAgICAgIA0KDQogI
        CAgDQokcG9ydCA9IG5ldy1PYmplY3QgU3lzdGVtLklPLlBvcnRzLlNlcmlhbFBvcnQgJGNvbU5vLDk2MDAgLE5vbmUsOCxvbmUNCiRwb3J
        0LlJlYWRUaW1lb3V0ID0gNTAwMDsNCiRwb3J0LldyaXRlVGltZW91dCA9IDIwMDA7DQp0cnkgew0KCSRwb3J0Lk9wZW4oKQ0KDQoJZm9yZ
        WFjaCAoJGVsZW1lbnQgaW4gJGNvbW1hbmQpIHsNCgkJJHNEZWNvZGVkU3RyaW5nPVtTeXN0ZW0uVGV4dC5FbmNvZGluZ106OlVURjguR2V
        0U3RyaW5nKFtTeXN0ZW0uQ29udmVydF06OkZyb21CYXNlNjRTdHJpbmcoJGVsZW1lbnQpKQ0KCQl0cnkgew0KICAgICAgICAgICAgICAgI
        CAgICBTdGFydC1TbGVlcCAtcyAxDQogICAgICAgICAgICAgICAgICAgICRwb3J0LlJlYWRFeGlzdGluZygpOw0KICAgICAgICAgICAgICA
        gIH0gY2F0Y2ggW0V4Y2VwdGlvbl0geyBlY2hvICRfLkV4Y2VwdGlvbi5HZXRUeXBlKCkuRnVsbE5hbWUsICRfLkV4Y2VwdGlvbi5NZXNzY
        WdlIH0NCiAgICAgICAgICAgICAgICAkcG9ydC5Xcml0ZUxpbmUoICRzRGVjb2RlZFN0cmluZyArICJgciIgKTsNCgkJJGxpbmUgPSAiIg0
        KCQkkb3V0ID0gIiINCgkJJGNvbnRpbnVlID0gMTsNCgkJCSB3aGlsZSgkY29udGludWUgLWx0IDExKQ0KCQkJCXsJCQ0KCQkJCQkJJGxpb
        mUgPSAkcG9ydC5SZWFkTGluZSgpOw0KCQkJCQkJDQoJCQkJCQkkY29udGludWUgKz0gMTsNCgkJCQkJCWlmICggLW5vdCAoJGxpbmUpLkN
        vbnRhaW5zKCJPSyIpICkNCgkJCQkJCXsNCgkJCQkJCQkgaWYgKCAtbm90ICgkb3V0KS5Db250YWlucygkbGluZSkpIHsNCgkJCQkJCQkJJ
        G91dCArPSAkbGluZQ0KCQkJCQkJCX0NCgkJCQkJCX0gZWxzZSB7DQoJCQkJCQkJCSRjb250aW51ZSA9IDExOw0KCQkJCQkJfQ0KCQkJCQk
        JJG91dCA9ICRvdXQuUmVwbGFjZSgkc0RlY29kZWRTdHJpbmcsIiIpDQoJCQkJCQkkb3V0ID0gJG91dC5SZXBsYWNlKCJgciIsIiIpDQoJC
        QkJCQkkb3V0ID0gJG91dC5SZXBsYWNlKCJgMCIsIiIpDQoJCQkJfQ0KCQkJCXdyaXRlLWhvc3QgKCRjb21ObyArICIgLSAiICsgJG91dCk
        NCgkJICAgICAgICAgICAgICAgIA0KCQkNCgl9IA0KCSRwb3J0LkNsb3NlKCkNCg0KfQ0KICAgIGNhdGNoIFtFeGNlcHRpb25dDQp7DQogI
        CBlY2hvICAkXyB8IE91dC1TdHJpbmcNCiAgIGVjaG8gJF8uRXhjZXB0aW9ufGZvcm1hdC1saXN0IC1mb3JjZQ0KfQ0K"""

        enable_info_cmd = base64.b64encode("AT+CREG=2")
        cell_info_cmd = base64.b64encode("AT+CREG?")
        commands = [enable_info_cmd, cell_info_cmd]
        if not ue.com_port:
            if cnt == 1:
                mylogger.error("UE {} :modem not found !!! Recheck".format(ue.adb_sn))
                self._get_modems_imei()
                self.get_ue_cellid(adb_sn, 0)
            else:
                return "UE {} :modem not found !!! Please enable usb modem in UE settings".format(ue.adb_sn)

        out = ""
        try:
            out = self.save_py_on_host_and_run_pow_shell(content, ue.com_port, commands).replace("\x00", "")
        except Exception as e:
            mylogger.debug("get_ue_cellid,Exception={}".format(e))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())

        cell_id_1 = cell_id_2 = ", neighbours {} !!!" \
            .format(self._get_neighbours_cells(ue.adb_sn))
        ue.cell_id = "Not registered{}".format(cell_id_1)
        mylogger.debug(out)
        for line in out.split("\n"):
            match = re.findall(r'\d+,\d+', line)
            match1 = re.findall(r'\d+,\d+,\"[0-9a-fA-F]+\",\"[0-9a-fA-F]+\",\d+', line)
            #match1 = re.findall(r'\d+,\d+,\"\d+\",\"[0-9a-fA-F]+\",\d+', line)
            mylogger.debug("get_ue_cellid,{}:line={},out.match1={}".format(ue.adb_sn,
                                                                    line,
                                                                    match1))
            if match and not match1:
                response = match[0].split(",")
                reg_state = response[1]
                try:
                    reg_state = int(reg_state)
                except ValueError as ex:
                    reg_state = 0
                    mylogger.debug("get_ue_cellid,{}-ValueError :{}".format(ue.adb_sn, ex))
                if reg_state != 1 and reg_state != 5:
                    mylogger.warning(
                        "Ue {} :Not registered, not currently searching for a new operator to register to"
                            .format(ue.adb_sn))

                    ue.cell_id = "Ue {} :Not registered {}".format(ue.adb_sn, cell_id_1)

            elif match1:
                response = match1[0].split(",")
                mylogger.debug("get_ue_cellid,{},out.response={},len={}".format(ue.adb_sn,
                                                                                response,
                                                                                len(response)))
                #['2,1,"193","9D9A"']=[tryb,reg_state,LAC,CELLID,rat]

                if len(response) == 5:
                    reg_state = response[1]
                    lac = response[2].replace('"', "")
                    cellid_hex=response[3].replace('"', "")
                    rat=response[4]
                    mylogger.debug(
                        ue.adb_sn + ",reg_state={}"
                                    ",LAC={}"
                                    ",CELLID={}"
                                    ",rat={}".format(reg_state
                                                     ,lac
                                                     ,cellid_hex
                                                     ,rat))

                    try:
                        reg_state = int(reg_state)
                        rat = int(rat)
                        cell_id_1 = int(cellid_hex, 16)
                        cell_id_2 = int(cellid_hex[2:], 16)

                    except ValueError as ex:
                        reg_state = 0
                        mylogger.debug("get_ue_cellid,{}-ValueError :{}".format(ue.adb_sn, ex))

                    if reg_state == 1 or reg_state == 5:

                        if rat == 2:
                            mylogger.debug("{}-cellId={}".format(ue.adb_sn, cell_id_2))
                            ue.cell_id = str(cell_id_2)
                        else:
                            mylogger.debug("{}-cellId={}".format(ue.adb_sn, cell_id_1))
                            ue.cell_id = str(cell_id_1)
                        mylogger.debug("UE {}-Registered in home , or roaming network ,cell={}"
                                       .format(ue.adb_sn, ue.cell_id))

        return ue.cell_id

    def _get_neighbours_cells(self, adb_sn):
        try:
            response = self.run_at_command(adb_sn, [base64.b64encode("AT$QCRSRQ?")])[0]
            result = response.get("result")
        except IndexError as ex:
            result = None

        if not result or "no network" in result:
            return result

        out = response.get("out")
        match = re.findall(r'\d+,\d+,\"[-+]?\d+\.\d+\"', out)
        out_list = []
        if match:
            for m in match:
                msplitted= m.split(",")
                if msplitted and len(msplitted)==3:
                    cellid=msplitted[0]
                    earfcn=msplitted[1]
                    rsrq=msplitted[2]
                    out_list.append("CellID={},EARFCN={},RSRQ={}".format(cellid, earfcn, rsrq))
            return out_list
        return response.get("out")

    def _get_modems_imei(self):
        content = """JHNDb21Qb3J0TnVtYmVyID0gR2V0LVdtaU9iamVjdCBXaW4zMl9Qb3RzTW9kZW0gfCBgDQoJV2hlcmUtT2JqZWN0IHsk
        Xy5EZXZpY2VJRCAtbGlrZSAiVVNCXFZJRCoiIC1hbmQgJF8uU3RhdHVzIC1saWtlICJPSyJ9IHwgYA0KCWZvcmVhY2ggeyRfLkF0dGFja
        GVkVG99DQoNCmZvcmVhY2ggKCRlbGVtZW50IGluICRzQ29tUG9ydE51bWJlcikgew0KCSRsaW5lID0gIiINCgkkb3V0ID0gIiINCgkkcG
        9ydCA9IG5ldy1PYmplY3QgU3lzdGVtLklPLlBvcnRzLlNlcmlhbFBvcnQgJGVsZW1lbnQsOTYwMCxOb25lLDgsb25lDQoJJHBvcnQuUmV
        hZFRpbWVvdXQgPSA1MDAwOw0KCSRwb3J0LldyaXRlVGltZW91dCA9IDIwMDA7DQoJVHJ5IHsNCgkJJHBvcnQuT3BlbigpOw0KCQlUcnkg
        ew0KCQkJJHBvcnQuUmVhZEV4aXN0aW5nKCk7DQoJCX0gY2F0Y2ggIFtzeXN0ZW0uZXhjZXB0aW9uXSB7fQ0KCQkNCgkJJHBvcnQuV3Jpd
        GVMaW5lKCAiQVQrR1NOYHIiICk7DQoJCSRjb250aW51ZSA9IDE7DQoJCSB3aGlsZSgkY29udGludWUgLWx0IDExKQ0KCQkJewkJDQoJCQ
        kJCSRsaW5lICs9ICRwb3J0LlJlYWRMaW5lKCk7DQoJCQkJCSRjb250aW51ZSArPSAxOw0KCQkJCQlpZiAoIC1ub3QgKCgkbGluZSkuQ29
        udGFpbnMoIk9LIikgLW9yICgkbGluZSkuQ29udGFpbnMoIkVSUk9SIikgKSApDQoJCQkJCXsNCgkJCQkJCQkkb3V0ICs9ICRsaW5lDQoJ
        CQkJCX0gZWxzZSB7DQoJCQkJCQkJJGNvbnRpbnVlID0gMTE7DQoJCQkJCX0NCgkJCQkJJG91dCA9ICRvdXQuUmVwbGFjZSgiQVQrR1NOI
        iwiIikNCgkJCQkJJG91dCA9ICRvdXQuUmVwbGFjZSgiYHIiLCIiKQ0KCQkJCQkkb3V0ID0gJG91dC5SZXBsYWNlKCJgMCIsIiIpDQoJCQ
        l9DQoJCQl3cml0ZS1ob3N0ICgkZWxlbWVudCArICIgLSAiICsgJG91dCkNCgkJDQoJCSRwb3J0LkNsb3NlKCkNCgl9DQoJIGNhdGNoIFt
        FeGNlcHRpb25dDQoJew0KCSAgIGVjaG8gICRfIHwgT3V0LVN0cmluZw0KCSAgIGVjaG8gJF8uRXhjZXB0aW9ufGZvcm1hdC1saXN0IC1m
        b3JjZQ0KCX0NCn0="""
        coms = ""
        try:
            coms = str(self.save_py_on_host_and_run_pow_shell(content)).replace("AT+GSN\r", "").replace("\x00", "")
        except Exception as e:
            mylogger.debug("_get_modems_imei,Exception={}".format(e))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())

        mylogger.debug(coms)
        time.sleep(5)

        for li in coms.split("\n"):
            mylogger.debug("_get_modems_imei,line=\n'{}'".format(li))
            a = li.split("-")
            if len(a) == 2:
                q = [m for m in re.findall(r'\d+', a[1])]
                imei = "".join(q)
                myue = next((x for x in self._myUes if imei in x.imei), None)
                q = [m for m in re.findall(r'COM\d+', a[0])]
                com_port = "".join(q)
                if myue:
                    mylogger.debug("_get_modems_imei,\n\tadb_sn={}\n\tcom_port={}\n\timei={}".format(myue.adb_sn,
                                                                                                     com_port,
                                                                                                     myue.imei))
                    myue.com_port = com_port
                else:
                    mylogger.debug("_get_modems_imei,Additional com modem found: imei:{}={}".format(imei, q))

        all_ues = map(self._ue_info, self._myUes)
        mylogger.debug("_get_modems_imei,all ues={}".format(all_ues))

    def save_py_on_host_and_run_pow_shell(self, content, comNo=None, commands=None, pipe_fliename=None):
        if commands is None:
            commands = []
        self._ssh_client.close()
        self._ssh_client.set_missing_host_key_policy(AutoAddPolicy())
        self._ssh_client.connect(self._ip, username=self._username, password=self._mypasswd, timeout=10, look_for_keys=False)
        mylogger.debug("save_py_on_host_and_run_pow_shell,open_sftp")
        sftp = self._ssh_client.open_sftp()
        mylogger.debug("save_py_on_host_and_run_pow_shell,settimeout")
        sftp.sock.settimeout(10.0)
        mylogger.debug("save_py_on_host_and_run_pow_shell,open")
        f = sftp.open("/tmp/a.ps1", 'wb')
        mylogger.debug("save_py_on_host_and_run_pow_shell,write")
        content = base64.b64decode(content)
        mylogger.debug("save_py_on_host_and_run_pow_shell,content")
        f.write(content)
        mylogger.debug("save_py_on_host_and_run_pow_shell,close")
        f.close()
        sftp.close()

        self._ssh_client.close()
        win_tmp_path, stderr = self._run_command("cygpath -w /tmp")
        ret, stderr = self._run_command("pwd")

        if not isinstance(ret, list):
            ret = [ret]

        mylogger.debug("".join(ret))
        cmd = "cmd /c powershell -executionpolicy unrestricted -command "
        if comNo:
            cmd += "".join(win_tmp_path).rstrip() + "/a.ps1 " + comNo + " "
            cmd += ",".join(commands)
        else:
            cmd += "".join(win_tmp_path).rstrip() + "/a.ps1 "

        if pipe_fliename:
            cmd += ">" + "" + pipe_fliename
        cmd = cmd.replace("\\", "/")
        mylogger.debug("save_py_on_host_and_run_pow_shell,{}".format(cmd))

        '''ret, stderr = self._run_command(cmd, timeout=60)
        if pipe_fliename:
            ret, stderr = self._run_command("cat " + "".join(win_tmp_path).rstrip() + pipe_fliename)
        '''
        ret = self._run_command2(cmd, duration=60)
        if pipe_fliename:
            #cat /cygdrive/c/cygwin64/tmp/out.log
            cmd = "cmd /c type {}".format("".join(win_tmp_path).rstrip() + pipe_fliename)
            cmd = cmd.replace("\\", "/")
            mylogger.debug("save_py_on_host_and_run_pow_shell,cmd={}".format(cmd))
            ret = self._run_command2("cmd \c {}".format(cmd))

        if not isinstance(ret, list):
            ret = [ret]
        if "Exception" in "".join(ret):
            mylogger.debug("save_py_on_host_and_run_pow_shell,\n\tscript={}\n\tException={}"
                           .format(base64.b64decode(content), ret))
        return "".join(ret)

    def save_py_on_host_and_run_py(self):
        content = """aW1wb3J0IHJlcXVlc3RzCmltcG9ydCBqc29uCmltcG9ydCBvcwppbXBvcnQgc3lzCmltcG9ydCB
        0cmFjZWJhY2sKCmRlZiBvY3Jfc3BhY2VfZmlsZShmaWxlbmFtZSwgb3ZlcmxheT1GYWxzZSwgYXBpX2tleT0nND
        g2ODhhMDE0Zjg4OTU3JywgbGFuZ3VhZ2U9J2VuZycpOgogICAgcGF5bG9hZCA9IHsnaXNPdmVybGF5UmVxdWlyZ
        WQnOiBvdmVybGF5LAogICAgICAgICAgICAgICAnYXBpa2V5JzogYXBpX2tleSwKICAgICAgICAgICAgICAgJ2x
        hbmd1YWdlJzogbGFuZ3VhZ2UsCiAgICAgICAgICAgICAgIH0KICAgIHdpdGggb3BlbihmaWxlbmFtZSwgJ3JiJy
        kgYXMgZjoKICAgICAgICByID0gcmVxdWVzdHMucG9zdCgnaHR0cHM6Ly9hcGkub2NyLnNwYWNlL3BhcnNlL2ltY
        WdlJywKICAgICAgICAgICAgICAgICAgICAgICAgICBmaWxlcz17ZmlsZW5hbWU6IGZ9LAogICAgICAgICAgICAgI
        CAgICAgICAgICAgIGRhdGE9cGF5bG9hZCwKICAgICAgICAgICAgICAgICAgICAgICAgICApCiAgICByZXR1cm4gc
        i5qc29uKCkKCnRlc3RfZmlsZSA9IG9jcl9zcGFjZV9maWxlKGZpbGVuYW1lPSdjOlxcdG1wXFxzY3JlZW4ucG5nJ
        ywgbGFuZ3VhZ2U9J2VuZycsYXBpX2tleT1zeXMuYXJndlsxXSkKaWYgIm1heGltdW0iIGluIHRlc3RfZmlsZToKC
        XByaW50ICgiRXhjZXB0aW9uTWF4VXNlZCIpCmVsc2U6Cgl0cnk6CgkJcHJpbnQgKHRlc3RfZmlsZVsiUGFyc2VkU
        mVzdWx0cyJdWzBdWyJQYXJzZWRUZXh0Il0uZW5jb2RlKCd1dGYtOCcpKQoJZXhjZXB0OgoJCXByaW50ICh0ZXN0X
        2ZpbGUpCgkJcHJpbnQoc3lzLmV4Y190eXBlKSAgICAgICAgICAgCgkJcHJpbnQodHJhY2ViYWNrLmZvcm1hdF9leG
        MoKSkg"""

        self._ssh_client.set_missing_host_key_policy(AutoAddPolicy())
        self._ssh_client.connect(self._ip, username=self._username, password=self._mypasswd, look_for_keys=False)
        sftp = self._ssh_client.open_sftp()
        sftp.sock.settimeout(10)

        f = sftp.open("/tmp/a.py", 'wb')
        f.write(base64.b64decode(content))
        f.close()
        sftp.close()
        self._ssh_client.close()
        win_tmp_path = self._run_command2("cygpath -w /tmp")
        cmd = "cmd /c python " + win_tmp_path.rstrip() + "/a.py 48688a014f88957"
        cmd = cmd.replace("\\", "/")
        ret = self._run_command2(cmd)
        if "ExceptionMaxUsed" in ret:
            cmd = "cmd /c python " + win_tmp_path.rstrip() + "/a.py helloworld"
            cmd = cmd.replace("\\", "/")
            ret = self._run_command2(cmd)
        return ret

    def _get_logcat_msg(self, ue):
        self._exec_command("")

    def _bandMenu_set(self, ue, sim_nr, rat, band):
        """Set selected band by adb
            """

        try:
            selected_phone = getattr(UePx, 'sam_' + ue.model_fixed + '_bsel_px')
        except AttributeError:
            raise UemExtPhoneException("Selected phone {} is not supported by library".format(ue.model_fixed))
            return

        if rat + "_" + band in selected_phone:
            band_px = selected_phone[rat + "_" + band]
        else:
            if str(sim_nr) + "_" + rat + "_" + band in selected_phone:
                band_px = selected_phone[str(sim_nr) + "_" + rat + "_" + band]
            else:
                mylogger.error("Selected " + rat + " band " + band + " for UE " + ue.model + " does not exist")
                return

        self._openBandMenu(ue)
        scrtext = self.get_screencap_text(ue)
        if "BAND SELECTION" in scrtext:
            mylogger.info("BAND SELECTION-OK")
        else:
            mylogger.debug("_bandMenu_set," + scrtext)

        self._check_act_window(ue)
        self._select_sim(ue, sim_nr)
        self._check_act_window(ue)

        scrtext = self.get_screencap_text(ue)
        if "clear all bands" in scrtext.lower():
            mylogger.console("Clear all bands found")
        else:
            mylogger.debug("_bandMenu_set," + scrtext)

        cmd = self._adb_path + ' -s ' + ue.adb_sn + ' shell input tap ' + selected_phone[str(sim_nr) + "_clear"]
        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("_bandMenu_set," + cmd + "\n_clear---" + " ".join(stdout) + "\n***\n" + str(stderr) + "---\n\n")

        time.sleep(1)
        scrtext = self.get_screencap_text(ue)
        if "(*)" not in scrtext:
            mylogger.info("CLEAR-OK")
        else:
            mylogger.debug("_bandMenu_set," + scrtext)

        # open rat menu
        if rat in selected_phone:
            cmd = self._adb_path + ' -s ' + ue.adb_sn + ' shell input tap ' + selected_phone[rat]
        elif str(sim_nr) + "_" + rat in UePx.sam_SM_J250M_bsel_px:
            cmd = self._adb_path + ' -s ' + ue.adb_sn + ' shell input tap ' + selected_phone[str(sim_nr) + "_" + rat]

        self._check_act_window(ue)

        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug(
            "_bandMenu_set," + cmd + "\n" + rat + "---" + " ".join(stdout) + "\n***\n" + str(stderr) + "---\n\n")

        scrtext = self.get_screencap_text(ue)
        if "] " + rat in scrtext.upper():
            mylogger.info(rat + " BAND-OK")
        else:
            mylogger.debug("_bandMenu_set," + scrtext)

        self._check_act_window(ue)

        cmd = self._adb_path + ' -s ' + ue.adb_sn + ' shell input tap ' + band_px
        stdout, stderr = self.start_process_by_ssh(cmd, 3)

        mylogger.debug("_bandMenu_set," + cmd + "\n---" + " ".join(stdout) + "\n***\n" + str(stderr) + "---\n\n")

        scrtext = self.get_screencap_text(ue)
        if rat + ":" in scrtext.upper():
            mylogger.info(rat + " BAND-OK")
            mylogger.info(re.findall(rat + ": \d", scrtext))
        else:
            mylogger.debug("_bandMenu_set," + scrtext)

        self._check_act_window(ue)
        cmd = self._adb_path + ' -s ' + ue.adb_sn + ' shell input tap ' + selected_phone["more"]
        stdout, stderr = self.start_process_by_ssh(cmd, 3)

        mylogger.debug("_bandMenu_set," + cmd + "\nmore---" + " ".join(stdout) + "\n***\n" + str(stderr) + "---\n\n")

        scrtext = self.get_screencap_text(ue).lower()
        if "select" in scrtext and "back" in scrtext:
            mylogger.info("MORE-OK")
        else:
            mylogger.debug("_bandMenu_set," + "more:\n" + scrtext)

        self._check_act_window(ue)
        cmd = self._adb_path + ' -s ' + ue.adb_sn + ' shell input tap ' + selected_phone["back"]
        stdout, stderr = self.start_process_by_ssh(cmd, 3)

        mylogger.debug("_bandMenu_set," + cmd + "\nback---" + " ".join(stdout) + "\n***\n" + str(stderr) + "---\n\n")

        scrtext = self.get_screencap_text(ue).upper()

        if rat + ":" in scrtext:
            mylogger.info("BACK-OK")
        else:
            mylogger.debug("_bandMenu_set," + "back:\n" + scrtext)

        self._check_act_window(ue)

        cmd = self._adb_path + ' -s ' + ue.adb_sn + ' shell input tap ' + selected_phone[str(sim_nr) + "_apply"]
        stdout, stderr = self.start_process_by_ssh(cmd, 3)

        mylogger.debug("_bandMenu_set," + cmd + "\n_apply---" + " ".join(stdout) + "\n***\n" + str(stderr) + "---\n\n")

        scrtext = self.get_screencap_text(ue).lower()

        if "apply" in scrtext and "done" in scrtext:
            mylogger.info("APPLY-OK")
        else:
            mylogger.debug("_bandMenu_set," + "apply:\n" + scrtext)

        self.toogleAirplane(ue.adb_sn)

    def _check_act_window(self, ue):
        cmd = self._adb_path + ' -s ' + \
              ue.adb_sn + " shell dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'"

        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("_check_act_window," + cmd + "\n---" + " ".join(stdout) + "\n***\n" + str(stderr) + "---\n\n")
        if "com.sec.android.RilServiceModeApp" not in " ".join(stdout):
            raise UemExtRilServiceException("com.sec.android.RilServiceModeApp not in the main activity")

    def _clickback(self, ue):
        # send back key
        cmd = self._adb_path + ' -s ' + ue.adb_sn + ' shell input keyevent 4'
        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("_clickback," + cmd + "\n---" + " ".join(stdout) + "\n***\n" + str(stderr) + "---\n\n")

    def ue_data_toggle(self, adb_sn):
        self._data_transfer(adb_sn, "disable")
        time.sleep(2)
        self._data_transfer(adb_sn, "enable")
        time.sleep(5)

    def data_transfer_mode_by_alias(self, ue_alias, option):
        myue = self._get_ue__from_store_by_alias(ue_alias)
        if "disable" in option or "enable" in option:
            self._data_transfer(myue.adb_sn, option)
        else:
            raise ParameterError("Wrong option for data transfer mode")

    def data_transfer_mode(self, adb_sn, option):
        if "disable" in option or "enable" in option:
            self._data_transfer(adb_sn, option)
        else:
            raise ParameterError("Wrong option for data transfer mode")

    def _data_transfer(self, adb_sn, action):
        cmd = "{} -s {} shell {}svc data {}{}".format(self._adb_path,
                                                      adb_sn,
                                                      self._su_str,
                                                      action.lower(),
                                                      self._su_str_end)

        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("_data_transfer,cmd={}\nstdout={}\nstderr={}\n".format(cmd, stdout, stderr))
    #svc data

    def _get_airplane_status(self, adb_sn):

        cmd = "{} -s {} shell {}settings get global airplane_mode_on{}".format(self._adb_path, adb_sn, self._su_str, self._su_str_end)
        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("_get_airplane_status,cmd={}\nstdout={}\nstderr={}\n".format(cmd, stdout, stderr))
        match = re.match(r"\d+", " ".join(stdout))

        if match:
            if 0 == int(match.group(0)):
                return "OFF"
            elif 1 == int(match.group(0)):
                return "ON"

        else:
            return "Not Known"

    def show_ue_table(self, adb_sn):
        myue = self._get_ue__from_store_by_adb_sn(adb_sn)
        mylogger.debug("show_ue_table,adb_sn={},myue={}".format(adb_sn, myue))

        ip = self._get_ue_ip(myue)
        if not ip:
            ip = 'Not Assigned'

        data = {'Adb sn': adb_sn,
                'Android version': myue.build_version.replace("\r", "").replace("u", ""),
                'IMEI': myue.imei,
                'Network type': self._get_string_service_state(myue),
                'IP': ip,
                'Model': myue.model_fixed,
                'Airplane settings': self._get_airplane_status(adb_sn),
                'SignalStrength': str(self._get_signal_stength(adb_sn)) + " dBm",
                'Battery level': self.get_battery_state(adb_sn, 'level'),
                'Battery temperature': self.get_battery_state(adb_sn, 'temperature') + " Celc.",
                'Battery health': self.get_battery_state(adb_sn, 'health'),
                "Cell_Id": self.get_ue_cellid(myue.adb_sn),
                "Com port": myue.com_port
                }
        for key, value in data.items():
            mylogger.info('{:<20} | {:<10}'.format(key, value))
        mylogger.info("\n")

        mylogger.info("\n")

    def get_battery_state(self, adb_sn, grep):
        #level,temperature,status,health,voltage,AC powered,USB powered
        b_level = "level" in grep
        b_temp = "temperature" in grep
        b_health = "health" in grep

        stdout = []
        cmd =  '{} -s {} shell dumpsys battery | grep {}'.format(self._adb_path, adb_sn, grep)
        try:
            stdout, stderr = self.start_process_by_ssh(cmd, 3)
            if stdout:
                level = re.findall("\d+",''.join(stdout))
                int_level = int(level[0] if level else 101)
                cmd = '{} -s {} shell dumpsys battery | grep {}'.format(self._adb_path, adb_sn, "status")
                stdout1, stderr = self.start_process_by_ssh(cmd, 3)
                status = re.findall("\d+", ''.join(stdout1))
                int_status = int(status[0] if status else 101)
                try:
                    str_status = ["Unknown", "Charging", "Discharging", "Not Charging", "Full"][int_status - 1]
                except IndexError:
                    str_status = None

                if int_level < 10 and b_level:
                    if int_status != 101:

                        if str_status:
                            mylogger.warning("Ue {} Low battery level :{}% ,Ue-{}".format(adb_sn, int_level,str_status))
                        else:
                            mylogger.warning("Ue {} Low battery level :{}% ".format(adb_sn, int_level))
                    else:
                        mylogger.warning("Ue {} Low battery level :{}%".format(adb_sn,int_level))

                if int_level == 101:
                    return ''.join(stdout)
                else:
                    if b_temp:
                        return str(float(int_level /10))
                    elif b_health:
                        health = re.findall("\d+", ''.join(stdout))
                        int_health = int(health[0] if health else 101)
                        if int_health != 101:
                            return ["UNKNOWN","GOOD","OVERHEAT","DEAD",
                         "OVER_VOLTAGE","UNSPECIFIED_FAILURE","COLD"][int_health-1]
                        else:
                            ''.join(stdout)
                    else:
                        return "{}, {}".format(int_level,str_status)
            return ''.join(stdout)

        except Exception as e:
            mylogger.debug("get_battery_state,Exception={}".format(e))
            mylogger.debug(sys.exc_type)
            mylogger.debug(traceback.format_exc())
            return ''.join(stdout)

    def toogleAirplane(self, adb_sn):
        myue = self._get_ue__from_store_by_adb_sn(adb_sn)
        mylogger.info("{}- Toogle Airplane Mode".format(myue.adb_sn))
        self._clickback(myue)
        self.set_air_plane(myue.adb_sn, 1)
        time.sleep(1)
        self.set_air_plane(myue.adb_sn, 0)
        time.sleep(5)

    def reboot_ue(self, ue):

        cmd = '{} -s {} reboot'.format(self._adb_path, ue.adb_sn)
        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("reboot_ue,{} :\n\tcmd={}\n\tstdout={}\n\tstderr={}\n".format(ue.adb_sn, cmd, stdout, stderr))
        time_tick = 21
        while time_tick > 0:
            if self._chk_ue_in_adb_devices(ue.ue_alias, ue.adb_sn, False):
                return
            else:
                time.sleep(2)
                time_tick -= 1

    def reboot_ue_by_sn(self, adb_sn):
        myue = self._get_ue__from_store_by_adb_sn(adb_sn)
        cmd = '{} -s {} reboot'.format(self._adb_path, myue.adb_sn)
        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("reboot_ue,cmd={}\nstdout={}\nstderr={}\n".format(cmd, stdout, stderr))
        time_tick = 21
        while time_tick > 0:
            if self._chk_ue_in_adb_devices(myue.ue_alias, myue.adb_sn, False):
                return
            else:
                time.sleep(2)
                time_tick -= 1

    def set_air_plane_by_alias(self, ue_alias, on_off):
        myue = self._get_ue__from_store_by_alias(ue_alias)
        if "OFF" in on_off:
            if not self.set_air_plane(myue.adb_sn, 1):
                mylogger.warning("UE-{} data transfer mode not changed.".format(myue.adb_sn))

        elif "ON" in on_off:
            if not self.set_air_plane(myue.adb_sn, 0):
                mylogger.warning("UE-{} data transfer mode not changed.".format(myue.adb_sn))
        else:
            raise ParameterError("Wrong option for data transfer mode")

    def set_air_plane(self, adb_sn, on_off):

        cmd = "{} -s {} shell {}settings put global airplane_mode_on {}{}".format(self._adb_path,
                                                                                  adb_sn,
                                                                                  self._su_str,
                                                                                  on_off,
                                                                                  self._su_str_end)
        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("setAirPlane,cmd={}\nstdout={}\nstderr={}".format(cmd, stdout, stderr))
        cmd = "{} -s {} shell {}am broadcast -a android.intent.action.AIRPLANE_MODE{}".format(self._adb_path,
                                                                                             adb_sn,
                                                                                             self._su_str,
                                                                                             self._su_str_end)

        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("setAirPlane,cmd={}\nstdout={}\nstderr={}".format(cmd, stdout, stderr))

        if "result=0" in stdout:
            mylogger.info("Airplane mode: {}".format(on_off))
            return True
        return False

    def _select_sim(self, ue, simNr):
        try:
            selected_phone = getattr(UePx, 'sam_' + ue.model_fixed + '_bsel_px')
        except AttributeError as a:
            mylogger.debug("_select_sim,selected phone in not supported\n\nAttributeError={}".format(a.message))
            return

        scrtext = self.get_screencap_text(ue)
        if "BAND SELECTION SIM" in scrtext:
            mylogger.info("BAND SELECTION SIM-OK")

        # select sim
        cmd = self._adb_path + ' -s ' + ue.adb_sn + ' shell input tap ' + selected_phone["SIM" + str(simNr)]
        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("_select_sim," + cmd + "\n---" + " ".join(stdout) + "\n***\n" + str(stderr) + "---\n\n")

        scrtext = self.get_screencap_text(ue)
        if "selected band element" in scrtext.lower() and "sim " + str(simNr) in scrtext.lower():
            mylogger.info("BAND SELECTION - SIM " + str(simNr) + "-OK")

        time.sleep(1)

    def get_all_ues(self):
        stdout, _ = self._run_command("{} devices".format(self._adb_path))
        mylogger.debug("get_all_ues,{}".format(stdout))
        aList = []
        for a in stdout:
            mylogger.debug("get_all_ues,{}".format(a))
            device = re.findall(r'[0-9a-fA-F]+\t',a)
            mylogger.debug("get_all_ues,{}".format(device))
            if device:
                b = device[0].split("\t")
                aList.append(b[0])
        return aList

    def _recover_offline_ues(self):
        stdout, _ = self._run_command("{} reconnect offline".format(self._adb_path))
        mylogger.debug("_recover_offline_ues,{}".format(stdout))

    def _chk_ue_in_adb_devices(self, ue_alias, ue_adb_sn, raise_err=True, cnt=2):
        stdout, _ = self._run_command("{} devices".format(self._adb_path))
        mylogger.debug("_chk_ue_in_adb_devices," + "\tUe-" + ue_alias + "," + ue_adb_sn + "stdout=" + "".join(stdout))

        stdout, _ = self._run_command("{} devices | grep {}".format(self._adb_path, ue_adb_sn))
        mylogger.debug("_chk_ue_in_adb_devices," + "\tUe-" + ue_alias + "," + ue_adb_sn + "stdout=" + "".join(stdout))

        if "device" in "".join(stdout):
            mylogger.info("\tUe-{},{},found in adb".format(ue_alias, ue_adb_sn))
            return True

        elif "offline" in "".join(stdout) and raise_err:
            if cnt == 2:
                cnt -= 1
                self._recover_offline_ues()
                return self._chk_ue_in_adb_devices(ue_alias, ue_adb_sn, raise_err, cnt=cnt)
            elif cnt == 1:
                cnt -= 1
                mylogger.error(
                    "Ue-{},{} not found in adb, Actual state: offline, Reboot UEs!!!".format(ue_alias, ue_adb_sn))
                self._restart_adb_server()
                self._reboot_ues_by_at()
                return self._chk_ue_in_adb_devices(ue_alias, ue_adb_sn, raise_err, cnt=cnt)
            else:
                raise UeNotFound(
                    "Ue-" + ue_alias + "," + ue_adb_sn +
                    " not found in adb, Actual state: offline, Please reboot UE and check connection !!!")

        elif not "".join(stdout) and raise_err:
            if cnt == 1:
                mylogger.error(
                    "Ue-" + ue_alias + "," + ue_adb_sn + " not found in adb, Actual state: not known, Reboot UEs!!!")
                self._restart_adb_server()
                self._reboot_ues_by_at()
                return self._chk_ue_in_adb_devices(ue_alias, ue_adb_sn, raise_err, cnt=0)
            else:
                raise UeNotFound(
                "Ue-" + ue_alias + "," + ue_adb_sn + " not found in adb, please check connection !!! empty")

        else:
            if raise_err:
                raise UeNotFound(
                    "Ue-" + ue_alias + "," + ue_adb_sn + " not found in adb, please check connection !!! \n" + "".join(
                        stdout))

        return False

    def _phoneVer(self, adb_sn):
        """Get phone Product Model by adb
            ret : string s_model
            """
        cmd = self._adb_path + ' -s ' + adb_sn + ' shell getprop ro.product.model'

        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("_phoneVer," + cmd + "\n---" + str(stdout) + "\n***\n" + str(stderr) + "---\n\n")

        mylogger.info("\t" + adb_sn + "-Product model = " + " ".join(stdout))

        if stdout.__len__() == 0:
            raise UemExtPhoneVerEmpty("Phone product code empty")

        return stdout[0].rstrip()

    def _screen_is_locked(self, ue):
        cmd = self._adb_path + ' -s ' + ue.adb_sn + ' shell dumpsys window'
        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("_screen_is_locked," + stdout)
        for a in stdout:
            if "mShowingLockscreen" in a:
                return bool(re.search("mShowingLockscreen=true", a))

        return True

    def _screen_is_off(self, ue):
        cmd = self._adb_path + ' -s ' + ue.adb_sn + ' shell dumpsys window'
        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("_screen_is_off," + stdout)
        for a in stdout:
            if "mAwake" in a:
                return bool(re.search("mAwake=false", a))

        return True

    def _unlockPhone(self, ue):
        """Unlock phone by adb
            """
        if self._screen_is_off(ue):
            mylogger.debug("_unlockPhone," + "unlock phone ")
            cmd = self._adb_path + " -s " + ue.adb_sn + ' shell input keyevent 26'
            stdout, stderr = self.start_process_by_ssh(cmd, 3)
            mylogger.debug("_unlockPhone," + cmd + "\n---" + str(stdout) + "\n***\n" + str(stderr) + "---\n\n")

            time.sleep(1)

        if self._screen_is_locked(ue):
            cmd = self._adb_path + " -s " + ue.adb_sn + ' shell input touchscreen swipe 335 940 335 180'
            stdout, stderr = self.start_process_by_ssh(cmd, 3)
            mylogger.debug("_unlockPhone," + cmd + "\n---" + str(stdout) + "\n***\n" + str(stderr) + "---\n\n")

        return not self._screen_is_locked(ue) and not self._screen_is_off(ue)

    def _openBandMenu(self, ue):
        """Open select band menu by adb
            """
        i = 0
        is_ready = self._unlockPhone(ue)
        while not is_ready and i != 3:
            i += 1
            is_ready = self._unlockPhone(ue)

        cmd = "{} -s {} shell {}am force-stop com.sec.android.RilServiceModeApp{}".format(self._adb_path,
                                                                                          ue.adb_sn,
                                                                                          self._su_str,
                                                                                          self._su_str_end)
        # s = self._myUe.run_adb_shell(cmd)
        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("_openBandMenu," + cmd + "\n---" + " ".join(stdout) + "\n***\n" + str(stderr) + "---\n\n")
        time.sleep(1)
        self._unlockPhone(ue)
        cmd = self._adb_path + " -s " + ue.adb_sn + \
              ' shell su -c am start -a android.intent.action.MAIN -n com.sec.android.RilServiceModeApp' \
              '/com.sec.android.RilServiceModeApp.ServiceModeApp -e keyString 2263 ' \
              '--activity-clear-when-task-reset --activity-clear-task'

        # s = self._myUe.run_adb_shell(cmd)
        stdout, stderr = self.start_process_by_ssh(cmd, 3)
        mylogger.debug("_openBandMenu," + cmd + "\n---" + " ".join(stdout) + "\n***\n" + str(stderr) + "---\n\n")

        time.sleep(1)

    def set_band_by_at(self, selected_band=None, adb_sn=None):
        if selected_band is None:
            selected_band = []
        supported_bands = [i for i in dir(BANDS) if not callable(i) and "__module__" not in i and not "__doc__" in i]
        myue = self._get_ue__from_store_by_adb_sn(adb_sn)

        if self._get_string_service_state(myue) == NetType.LTE:

            self.run_at_command(adb_sn, [base64.b64encode("AT^SYSCONFIG=13,0,1,3")])

            if self._get_string_service_state(myue) == NetType.LTE:
                raise UemExtPhoneException(
                    "Selected band {} could not be set when Ue is connected to LTE ".format(selected_band))

        command = 'AT$QCBANDPREF=1,"'
        expected = ""
        try:
            for b in selected_band:
                band = getattr(BANDS, b)
                command += str(band) + ','

        except AttributeError:
            raise UemExtPhoneException("UE {} - Selected band {} is not supported by library\n Supported bands:\n {}"
                                       .format(adb_sn, selected_band, supported_bands))
        command = command[:-1] + '"'

        mylogger.debug("set_band_by_at," + command)
        out = self.run_at_command(myue.adb_sn, [base64.b64encode(command)])[0]
        result = out.get("result")

        if "ok" not in result.lower():
            mylogger.error("UE {} - Selected band {} not set ,AT error {}, out {}".
                                       format(adb_sn, selected_band, out.get("result"), out.get("out")))
            return
            raise UemExtPhoneException(
                "UE {} - Selected band {} not set ,AT error {}, out {}"
                "".format(adb_sn, selected_band, out.get("result"), out.get("out")))
        else:
            mylogger.info("UE {} - Band successfully changed to {}".format(adb_sn, selected_band))

    def _get_ue__from_store_by_adb_sn(self, adb_sn):
        myue = next((x for x in self._myUes if x.adb_sn == adb_sn), None)
        if not myue:
            all_ues = map(self._ue_info, self._myUes)
            raise UeNotFound(
                "UE with sn {} not found, please setup UE !!!\n\tCommisioned devices = {}".format(adb_sn, all_ues))
        return myue


    def _get_ue__from_store_by_alias(self, ue_alias):
        myue = next((x for x in self._myUes if x.ue_alias == ue_alias), None)
        if not myue:
            all_ues = map(self._ue_info, self._myUes)
            raise UeNotFound(
                "Alias not found :{},please setup UE !!!\n\tCommisioned devices = {}".format(ue_alias, all_ues))
        return myue

if __name__ == "__main__":
    while True:


        test_params = {
                        'alias': "daniel test",
                        'ip': "10.44.131.156",#,,181,,181,155,154,182
                        'port': 9091,
                        'uname': 'sranwro8',
                        'domain': 'NOKLAB',
                        'passwd': 'wro8pass'
                    }

        IV8_res1 = SimpleCallInterface(**test_params)
        iperfclass = IperfClass("10.44.44.167", "syslab", "system")
                    #print(IV8_res1.get_bts_cells("lte"))
                    #print(IV8_res1.get_bts_cells("gsm"))
                    #print(IV8_res1.get_bts_cells("wcdma"))



        IV8_res1.setup_pc(iperfclass)

                    #IV8_res1._run_ssh_command("adb devices")



                    #IV8_res1.check_ssh()

                    #IV8_res1.reboot_ue_pc()

        IV8_res1.setup_all_ues()
        print(IV8_res1.get_all_ues_cellid())
        for ue_adb in IV8_res1.get_all_ues():
            #IV8_res1.setup_ue( ue_adb, ue_adb, "daniel test")
            print("-----test for ue : {} started".format(ue_adb))
            try:
                #IV8_res1.reboot_ue_by_sn(ue_adb)
                #IV8_res1.reboot_ue_by_sn(ue_adb)
                IV8_res1.show_ue_table(ue_adb)
            except Exception as e:
                print(str(e))
                print(sys.exc_type)
                print(traceback.format_exc())
                print("Error:{}".format(e))
            try:

                IV8_res1.make_voice_call(ue_adb, "0666002", 10)
            except Exception as e:
                #raise e
                print("Error:{}".format(e))
            try:
                IV8_res1.make_ps_call(ue_adb,10)
            except Exception as e:
                print(str(e))
                print(sys.exc_type)
                print(traceback.format_exc())
                print("Error:{}".format(e))
            print("-----test for ue : {} finished".format(ue_adb))

        continue

        for ue_adb in IV8_res1.get_all_ues():
            #IV8_res1.setup_ue(ue_adb,ue_adb,"")
            print(IV8_res1.run_at_command(ue_adb, [base64.b64encode("AT+CGATT=0")]))
            IV8_res1.show_ue_table(ue_adb)
            print(IV8_res1.run_at_command(ue_adb, [base64.b64encode("AT+CGATT=1")]))
            IV8_res1.show_ue_table(ue_adb)
        exit(0)
        #IV8_res1.make_voice_call("50d8ce07", "0666002", 10)
        #exit(0)
        '''try:
            IV8_res1.make_voice_call_for_rat("GSM")
            IV8_res1.make_ps_call_for_rat("GSM")
            IV8_res1.make_voice_call_for_rat("WCDMA")
            IV8_res1.make_ps_call_for_rat("WCDMA")
            IV8_res1.make_ps_call_for_rat("LTE")
            IV8_res1.teardown()
        except Exception as e:         
            print("Error:{}".format(e))
        '''
        for ue_adb in IV8_res1.get_all_ues():
            #IV8_res1.setup_ue( ue_adb, ue_adb, "daniel test")
            print("-----test for ue : {} started".format(ue_adb))
            try:
                IV8_res1.reboot_ue_by_sn(ue_adb)
                IV8_res1.show_ue_table(ue_adb)
            except Exception as e:
                print("Error:{}".format(e))
            try:

                IV8_res1.make_voice_call(ue_adb, "0666002", 10)
            except Exception as e:
                print("Error:{}".format(e))
            try:
                IV8_res1.make_ps_call(ue_adb,10)
            except Exception as e:
                print("Error:{}".format(e))
            print("-----test for ue : {} finished".format(ue_adb))



        continue

        IV8_res1.setup_iperf_server("10.44.44.167", "syslab", "system")
        IV8_res1.setup_ues([{"ue_alias": "adf8b824", "ue_adb_sn": "adf8b824"},
                                {"ue_alias": "ae0fb898", "ue_adb_sn": "ae0fb898"},
                                {"ue_alias": "de73a8d2", "ue_adb_sn": "de73a8d2"},
                                {"ue_alias": "1b0acee4", "ue_adb_sn": "1b0acee4"}])  # ,
            # {"ue_alias": "95794f37", "ue_adb_sn": "95794f37"}])
        supported_bands = [i for i in dir(BANDS) if not callable(i) and "__module__" not in i and not "__doc__" in i]

        print(IV8_res1.get_all_ues_cellid())
        get_sig_stength_cmd = base64.b64encode("AT+CSQ")
        enable_info_cmd = base64.b64encode("AT+CREG=2")
        cell_info_cmd = base64.b64encode("AT+CREG?")
        cell_neighbor = base64.b64encode("AT$QCRSRQ?")
        cell_neighbor2 = base64.b64encode("AT+VZWRSRP?")
        cell_neighbor3 = base64.b64encode("AT$QCRSRQ?")
        prefBand = base64.b64encode("AT$QCBANDPREF?")
        sysmode = base64.b64encode("AT$QCSYSMODE?")
        setmodegsm = base64.b64encode("AT$QCNSP=1,0,1")
        setmodewcdma = base64.b64encode("AT$QCNSP=2,0,2")
        setmodelte = base64.b64encode("AT$QCNSP=6,0,3")
        apn = base64.b64encode("AT$QCAPNE?")
        supportedbands = base64.b64encode("AT$QCBANDPREF=?")

        commands = [supportedbands,
                        cell_info_cmd, enable_info_cmd,
                        cell_neighbor, cell_neighbor2,
                        cell_neighbor3, prefBand, sysmode,
                        setmodegsm, cell_info_cmd,
                        setmodewcdma, cell_info_cmd,
                        setmodelte, cell_info_cmd]
        IV8_res1.show_ue_table("adf8b824")
        print(IV8_res1.run_at_command("adf8b824", [get_sig_stength_cmd]))
        print(IV8_res1.run_at_command("ae0fb898", [get_sig_stength_cmd]))
        print(IV8_res1.run_at_command("de73a8d2", [get_sig_stength_cmd]))
        print(IV8_res1.run_at_command("1b0acee4", [get_sig_stength_cmd]))

        '''print(IV8_res1.run_at_command("adf8b824", commands))
            print(IV8_res1.run_at_command("ae0fb898", commands))
            print(IV8_res1.run_at_command("de73a8d2", commands))
            
        
            IV8_res1.show_ue_table("adf8b824")
            IV8_res1.show_ue_table("ae0fb898")
            IV8_res1.show_ue_table("de73a8d2")
            IV8_res1.show_ue_table("1b0acee4")
        
        
            IV8_res1.set_band_by_at(["Any"], "adf8b824")
            print(IV8_res1.get_all_ues_cellid())
            IV8_res1.show_ue_table("adf8b824")
            IV8_res1.show_ue_table("ae0fb898")
            
            
            IV8_res1.make_voice_call("adf8b824", "0666002", 10)
            #IV8_res1.make_voice_call("ae0fb898", "0666002", 10)
            IV8_res1.make_voice_call("de73a8d2", "0666002", 10)
            #IV8_res1.make_voice_call("1b0acee4", "0666002", 10)


            IV8_res1.show_ue_table("1b0acee4")

            IV8_res1.get_all_ues_cellid()
            # " adf8b824, ae0fb898, de73a8d2, 1b0acee4"

            IV8_res1.make_ps_call("adf8b824","10")
            IV8_res1.make_ps_call("ae0fb898","10",cnt=3,bandwidth="240",dl_max="2000000000",dl_min="9000000",ul_max="1200000000",ul_min="6000000")
            IV8_res1.make_ps_call("de73a8d2", "10", cnt=3, bandwidth="240", dl_max="2000000000", dl_min="30000",
                                  ul_max="1200000000", ul_min="10000")

            IV8_res1.iperf_installer.install_iperf("adf8b824")
            IV8_res1.iperf_installer.install_iperf("ae0fb898")
            IV8_res1.iperf_installer.install_iperf("de73a8d2")
            IV8_res1.iperf_installer.install_iperf("1b0acee4")

            # " adf8b824, ae0fb898, de73a8d2, 1b0acee4"


            IV8_res1.set_band("adf8b824",2,"WCDMA","B1")      '''
        IV8_res1.teardown()

