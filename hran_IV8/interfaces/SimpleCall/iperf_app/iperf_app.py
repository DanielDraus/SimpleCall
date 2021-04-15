# -*- coding: utf-8 -*-
"""
:copyright: Nokia Networks
:author: Daniel Draus
:contact: daniel.draus@nokia.com
"""

from paramiko import SSHClient, AutoAddPolicy, SSHException
import socket
import traceback
import sys
import re
import os


class IperfInstaller(object):
    def __init__(self, ip, uname, passwd, logger):
        self._ssh_client = SSHClient()
        self._ssh_client.__myname__ = "IperfInstaller_Main"
        self._ip = ip
        self._username = uname
        self._mypasswd = passwd
        self._mylogger = logger

    @staticmethod
    def _get_my_path():
        return os.path.dirname(sys.argv[0])

    def _run_cmd(self, command, timeout=10):
        stdout = ""
        stderr = 0
        try:
            if not isinstance(self._ssh_client, SSHClient):
                self._ssh_client = SSHClient()

            if not self._ssh_client.get_transport() or not self._ssh_client.get_transport().is_active():
                raise socket.error("Transport not active")

        except socket.error as e:
            self._mylogger.debug("_run_cmd,{} -Exception:{}"
                                 .format(command, str(e)))
            self._ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            self._ssh_client.connect(self._ip,
                                     username=self._username,
                                     password=self._mypasswd,
                                     timeout=10)  # , allow_agent=False)
        try:

            stdin, stdout, stderr = self._ssh_client.exec_command(
                                                command,
                                                timeout=int(timeout))
            stdout = stdout.readlines()

        except SSHException as e:
            self._mylogger.debug("_run_cmd,{} -timeout:{}"
                                 .format(command, str(e)))
        except Exception as e:
            self._mylogger.debug("start_process_by_ssh,{} -Exception:{}"
                                 .format(command, str(e)))
            self._mylogger.debug(sys.exc_type)
            self._mylogger.debug(traceback.format_exc())

        return stdout, stderr

    def copy_app_to_pc(self, app_name):
        self._ssh_client.set_missing_host_key_policy(AutoAddPolicy())
        self._ssh_client.connect(self._ip, username=self._username, password=self._mypasswd)
        sftp = self._ssh_client.open_sftp()
        f = sftp.open("/tmp/" + app_name, 'wb')
        f.write(open(self._get_my_path() + "/iperf_app/" + app_name).read())
        f.close()
        sftp.close()
        self._ssh_client.close()
        win_tmp_path, stderr = self._run_cmd("cygpath -w /tmp")
        ret, stderr = self._run_cmd("pwd")
        self._mylogger.debug("".join(ret))

        return ("".join(win_tmp_path).rstrip() + "\\" + app_name).replace("\\", "/")

    def _sdcard_file_exist(self, usbID, file_path):

        cmd = "adb -s " + usbID + " shell " + chr(34) +\
              "set echo off && test -f '" + file_path +\
              "' && echo 'File exists'" + chr(34)

        stdout, stderr = self._run_cmd(cmd)
        self._mylogger.debug("cmd=" + cmd + "," + "".join(stdout) + "," + str(stderr))
        return 'File exists' in "".join(stdout)

    def _getBuildVersion(self, usbID):
        """Get android ver by adb
               ret : sting stdout
            """
        cmd = "adb -s " + usbID + " shell getprop ro.build.version.release"
        stdout, _ = self._run_cmd(cmd)
        self._mylogger.debug(stdout)
        return re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\b", "".join(stdout))

    def install_iperf(self, usbID):

        self._mylogger.info("Install iperf started usbid =" + usbID)
        try:
            buid_ver = int("".join(self._getBuildVersion(usbID)))
        except ValueError:
            buid_ver = 0

        if buid_ver > 699:
            filename = "iperfUEAndroid7.py"
        else:
            filename = "iperfUEAndroid4-6.py"

        # kill iperf app
        cmd = "adb -s " + usbID + ' shell am force-stop com.magicandroidapps.iperf'
        stdout, stderr = self._run_cmd(cmd)
        self._mylogger.debug("cmd=" + cmd + "," + "".join(stdout) + "," + str(stderr))

        cmd = "adb -s " + usbID + ' shell pkill iperf'
        stdout, stderr = self._run_cmd(cmd)
        self._mylogger.debug("cmd=" + cmd + "," + "".join(stdout)+ "," + str(stderr))

        file_path = self.copy_app_to_pc(filename)

        cmd = 'adb -s ' + usbID + ' push ' + file_path + ' /sdcard/iperf'
        stdout, stderr = self._run_cmd(cmd)
        self._mylogger.debug("cmd=" + cmd + "," + "".join(stdout)+ "," + str(stderr))

        if self._sdcard_file_exist(usbID,  "/sdcard/iperf"):
            cmd = 'adb -s ' + usbID + ' uninstall com.magicandroidapps.iperf'
            stdout, stderr = self._run_cmd(cmd)
            self._mylogger.debug("cmd=" + cmd + "," + "".join(stdout) + "," + str(stderr))

            cmd = 'adb -s ' + usbID + ' shell su -c "mount -o rw,remount /system"'
            stdout, stderr = self._run_cmd(cmd)
            self._mylogger.debug("cmd=" + cmd + "," + "".join(stdout)+ "," + str(stderr))

            cmd = 'adb -s ' + usbID + ' shell su -c "rm /system/bin/iperf"'
            stdout, stderr = self._run_cmd(cmd)
            self._mylogger.debug("cmd=" + cmd + "," + "".join(stdout)+ "," + str(stderr))

            cmd = 'adb -s ' + usbID + ' shell su -c "cp /sdcard/iperf /system/bin/"'
            stdout, stderr = self._run_cmd(cmd)
            self._mylogger.debug("cmd=" + cmd + "," + "".join(stdout)+ "," + str(stderr))

            cmd = 'adb -s ' + usbID + ' shell su -c "chmod 777 /system/bin/iperf"'
            stdout, stderr = self._run_cmd(cmd)
            self._mylogger.debug("cmd=" + cmd + "," + "".join(stdout)+ "," + str(stderr))

            cmd = 'adb -s ' + usbID + ' shell iperf'
            stdout, stderr = self._run_cmd(cmd)
            self._mylogger.debug("cmd=" + cmd + "," + "".join(stdout)+ "," + str(stderr))
            if "iperf --help" in "".join(stdout):
                self._mylogger.info("Install iperf succeded usbid =" + usbID)
                return

        self._mylogger.error("Iperf not installed usbid =" + usbID)

if __name__ == "__main__":
    test_params = {
        'ip': "10.44.131.181",
        'uname': 'sranwro8',
        'passwd': 'wro8pass'
    }
    import logging

    mylogger = logging.getLogger("SimpleCall")
    mylogger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    ch.setLevel(logging.INFO)
    fh = logging.FileHandler('/tmp/SimpleCall.log')
    fh.setFormatter(formatter)
    fh.setLevel(logging.DEBUG)
    mylogger.addHandler(ch)
    mylogger.addHandler(fh)

    test_params = {'ip': "10.44.131.181",
                    'uname': 'sranwro8',
                    'passwd': 'wro8pass',
                    'logger' : mylogger
                    }

    IperfInstaller = IperfInstaller(**test_params)
    if IperfInstaller.install_iperf("0279cef6"):
        mylogger.info("Iperf installed in /system/bin ")
    else:
        mylogger.info("Iperf Not installed")
