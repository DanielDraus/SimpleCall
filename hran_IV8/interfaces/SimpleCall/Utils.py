# -*- coding: utf-8 -*-
"""
:copyright: Nokia Networks
:author: Daniel Draus
:contact: daniel.draus@nokia.com
"""

from SimpleCallInterface import *
import threading
import time
from paramiko import client
from paramiko import SSHClient
from ExceptionsClass import *
import sys
import traceback
#import ute_admin_infomodel

import logging

try:
    import ute_admin
except:
    class ute_admin(object):
        class ute_admin(object):
            def setup_admin(self,
                            address,
                            port,
                            username,
                            password,
                            use_ssl,
                            alias):
                pass
            def get_cell_list(self):
                pass

            class store(object):
                def get(self,_alias):
                    pass



class Ue(object):
    def __init__(self,ue_alias,adb_sn):
        self.ue_alias = ue_alias
        self.adb_sn = adb_sn
        self.sn = ""
        self.model = ""
        self.model_fixed = ""
        self.ip = ""
        self.imei = ""
        self.build_version = ""
        self.no_of_sim_slots = ""
        self.com_port = ""
        self.cell_id = ""
        self.ssh_client = SSHClient()
        self.iperf_path = ""
        self.rat = ""


class BANDS(object):
    GSM_DCS_1800 = 8
    GSM_EGSM_900 = 9
    GSM_PGSM_900 = 10
    GSM_850 = 24
    GSM_PCS_1900 = 26
    WCDMA_I_IMT_2000 = 27
    WCDMA_II_PCS_1900 = 28
    WCDMA_IV_1700 = 30
    WCDMA_V_850 = 31
    WCDMA_VIII_900 = 34
    Any = 46


class NetType(object):
    UNKNOWN = 0
    GSM = 1
    UMTS = 2
    LTE = 3


class IperfClass(object):
    def __init__(self, iperf_ip, iperf_uname,iperf_passwd):
        self.pc_host_ip = iperf_ip
        self.username = iperf_uname
        self.password = iperf_passwd


class UePx(object):
    sam_SM_J510FN_bsel_px = {"model": "SM-J510FN",
                      "LTE" : "400 410",
                       "LTE_B1" : "120 250",
                       "LTE_B3" : "120 300",
                       "LTE_B8" : "120 450",
                       "WCDMA" 	: "250 290",
                       "WCDMA_B8" 	: "250 410",
                       "WCDMA_B2" : "250 570",
                       "WCDMA_B1" : "250 630",
                       "GSM" 	: "250 240",
                       "GSM_900" : "250 300",
                       "clear" 	: "400 460",
                       "apply" 	: "400 569",
                       "more" 	: "654 104",
                       "back" 	: "440 210"
                       }
    sam_GT_I950_bsel_px = { "model"	: "GT-I950",
                       "LTE" 	: "400 505",
                       "LTE_B1" : "120 260",
                       "LTE_B3" : "120 345",
                       "LTE_B8" : "120 590",
                       "WCDMA" 	: "250 345",
                       "WCDMA_B8" 	: "250 345",
                       "GSM" 	: "250 425",
                       "GSM_900" : "250 345",
                       }
    sam_SM_J250M_bsel_px = { "model"	: "SM-J250M",
                       "SIM1"   : "120 170",
                       "SIM2"   : "120 215",
                       "2_LTE" 	: "120 300",
                       "2_LTE_B1" : "120 165",
                       "2_LTE_B2" : "120 205",
                       "2_LTE_B3" : "120 250",
                       "2_LTE_B4" : "120 300",
                       "2_LTE_B5" : "120 335",
                       "2_LTE_B7" : "120 380",
                       "2_LTE_B8" : "120 425",
                       "2_LTE_ALL" : "120 465",
                       "2_LTE_NEXT" : "120 510",
                       "2_LTE_B12" : "120 165",
                       "2_LTE_B13" : "120 205",
                       "2_LTE_B17" : "120 250",
                       "2_LTE_B28" : "120 300",
                       "2_LTE_B66" : "120 335",
                       "WCDMA" 	: "250 217",
                       "WCDMA_B1" : "250 465",
                       "WCDMA_B2" : "250 425",
                       "WCDMA_B4" : "250 340",
                       "WCDMA_B5" : "250 165",
                       "WCDMA_B8" 	: "250 300",
                       "GSM" 	: "146 172",
                       "GSM_850" : "125 165",
                       "GSM_900" : "125 210",
                       "GSM_1800" : "125 250",
                       "GSM_1900" : "125 300",
                       "1_clear" 	: "120 260",
                       "2_clear" 	: "120 342",
                       "1_apply" 	: "120 342",
                       "2_apply" 	: "120 425",
                       "more" 	: "490 73",
                       "back" 	: "328 146"
                       }

class SSH_CLS(object):
    client = None

    def __init__(self, address, username1, password1,adb_sn,logger):
        self.adb_sn = adb_sn
        self.logger = logger
        self.logger.info(adb_sn + "-Connecting to server :" + str(address))
        self.client = client.SSHClient()
        self.client.set_missing_host_key_policy(client.AutoAddPolicy())
        try:
            self.client.connect(address, username=username1, password=password1)
        except:
            raise UemExtSshNotAvaliable("SSH not avaliable, Please check connection to :" + address)

        if (self.client):
            self.logger.info(adb_sn + "-Connected to server. :-)\n")

    def sendCommand(self, command, timeout=None):
        self.logger.debug("{}-sendCommand={}".format(self.adb_sn, command))
        if self.client:
            try:
                stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
                while not stdout.channel.exit_status_ready():
                    # Print data when available

                    if stdout.channel.recv_ready():
                        alldata = stdout.channel.recv(1024)
                        prevdata = b"1"
                        while prevdata:
                            prevdata = stdout.channel.recv(1024)
                            alldata += prevdata
                            self.logger.debug(self.adb_sn + "-prevdata=" + prevdata + "\n")
                        return alldata
            except socket.timeout as e:
                self.logger.debug(str(e))
                self.logger.debug(sys.exc_type)
                self.logger.debug(traceback.format_exc())

        else:
            self.logger.debug(self.adb_sn + "-sendCommand_end")
            raise UemExtSshConnectionBroken("Connection not opened.")


class ThM(object):
    """ThM (ThreadManager)
    Handles very simple thread operations:
        Creating single-shot threads -> ThM.run(...)
        Creating 'looping per interval' threads -> ThM.run(...) with loop set to True
        Stopping looping threads based on name -> ThM.stop_loop(...)
        Joining all threads into the calling thread ThM.joinall()
        Removing stopped threads from 'running_threads' - > ThM.free_dead()


    The class has been designed for very simple operations, mainly
    for programs that need "workers" that mindlessly loop over a function.

    NOTE: Locks,Events,Semaphores etc. have not been taken into consideration
    and may cause unexpected behaviour if used!
     """
    running_threads = []

    @classmethod
    def run(cls, targetfunc, thname, loop, interval, arglist):
        """Statrs a new thread and appends it to the running_threads list
        along with the specified values.
        Loop and interval needs to be specified even if you dont
        want it to loop over. This is to avoid lot of keyword arguments
        and possible confusion.
        Example of starting a looping thread:
            ThM.run(function,"MyThreadName",True,0.5,[1,2,"StringArguemnt"])

        To stop it, use:
            ThM.stop_loop("MyThreadName")
        Note, a stopped thread cannot be started again!

        Example of a single-shot thread:
            ThM.run(function,"ThreadName",False,0.5,[1,2,"StringArgument"])
            """

        th = threading.Thread(target=cls._thread_runner_, args=(targetfunc, thname, interval, arglist))
        th.setDaemon(True)
        cls.running_threads.append([th, thname, loop])
        th.start()

    @classmethod
    def free_dead(cls):
        """Removes all threads that return FALSE on isAlive() from the running_threads list """
        for th in cls.running_threads[:]:
            if not th[0].isAlive():
                cls.running_threads.remove(th)

    @classmethod
    def stop_loop(cls, threadname):
        """Stops a looping function that was started with ThM.run(...)"""
        for i, thlis in enumerate(cls.running_threads):
            if thlis[1] == threadname:
                cls.running_threads[i][2] = False
                break

    @classmethod
    def joinall(cls):
        """Joins all the threads together into the calling thread."""
        for th in cls.running_threads[:]:
            while th[0].isAlive():
                time.sleep(0.1)
            th[0].join()
        #   print "Thread:",th[1],"joined","isalive:",th[0].isAlive() --- Debug stuff

    @classmethod
    def get_all_params(cls):
        """Returns parameters from the running_threads list for external manipulation"""
        for thli in cls.running_threads:
            yield (thli[0], thli[1], thli[2])

    # This method is only intended for threads started with ThM !
    @classmethod
    def _thread_runner_(cls, targetfunc, thname, interval, arglist):
        """Internal function handling the running and looping of the threads
        Note: threading.Event() has not been taken into consideration and neither the
        other thread managing objects (semaphores, locks, etc.)"""
        indx = 0
        for thread in cls.running_threads[:]:
            if thname == thread[1]:
                break
            indx += 1
        targetfunc(*arglist)
        while cls.running_threads[indx][2]:
            targetfunc(*arglist)
            if interval != 0:
                time.sleep(interval)


class BTS(object):

    _address = "192.168.255.1"
    _port = 3600
    _username = "Nemuadmin"
    _password = "nemuuser"
    _use_ssl = True
    _alias = "default"
    _mylogger = None

    def __init__(self,
                 address="192.168.255.1",
                 port=3600,
                 username="Nemuadmin",
                 password="nemuuser",
                 use_ssl=True,
                 alias="default",
                 mylogger = None):

        if mylogger:
            self._mylogger = mylogger
        else:
            self._mylogger = logging.getLogger("SimpleCall")

        self._address = address
        self._port = port
        self._username = username
        self._password = password
        self._use_ssl = use_ssl
        self._alias = alias

        self.admin = ute_admin.ute_admin()
        self.admin.setup_admin(address=self._address,
                                 port=self._port,
                                 username=self._username,
                                 password=self._password,
                                 use_ssl=self._use_ssl,
                                 alias=self._alias)
    #MPLANE_IP
    # noinspection PyNoneFunctionAssignment
    def _check_admin_setup(self):
        try:
            self.admin.store.get(self._alias)
            self._mylogger.debug("_check_admin_setup,store exist :alias={}".format(self._alias))

        except:
            self._mylogger.debug("_check_admin_setup,setup_admin:alias={}".format(self._alias))
            self.admin.setup_admin(address=self._address,
                                   port=self._port,
                                   username=self._username,
                                   password=self._password,
                                   use_ssl=self._use_ssl,
                                   alias=self._alias)

    def get_bts_cells_info(self, rat):
        rat = rat.lower()
        ret_list =[]
        self._check_admin_setup()
        try:


            list = self.admin.get_cell_list()
            self._mylogger.debug("_check_admin_setup,list:{}".format(list))
            list = list.get("cells").get(rat)
            for cell in list:
                if "wcdma" in rat:
                    re_dic = {"cellId" : cell.get("cellId"),
                              "downlinkFrequency": int(cell.get("downlinkFrequency"))/1000000,
                              "bandwidth": cell.get("downlinkChannelBandwidth"),
                              "band": None,
                              }
                    ret_list.append(re_dic)

                elif "lte" in rat:
                    re_dic = {"cellId" : cell.get("eutranCellId"),
                              "downlinkFrequency": cell.get("downlinkFrequency"),
                              "earfcnDownlink": cell.get("earfcnDownlink"),
                              "bandwidth": cell.get("downlinkChannelBandwith"),
                              "band": cell.get("bandNumber"),
                              "downlinkMimoMode": cell.get("downlinkMimoMode"),
                              }
                    ret_list.append(re_dic)

                elif "gsm" in rat:
                    re_dic = {"cellId" : cell.get("gsmSectorID"),
                              "downlinkFrequency": int(cell.get("trxInformation")[0]
                                                       .get("downlinkFrequencies")[0].get("low"))/1000000,
                              "bandwidth": None,
                              "band": cell.get("gsmBand"),
                              }
                    ret_list.append(re_dic)
                else:
                    raise UemExtPhoneException("Selected rat {} not found".format(rat))

        except Exception as ex:
            self._mylogger.debug("_check_admin_setup,Exception:{}".format(ex))

        finally:
            self.teardown()

        return ret_list

    def teardown(self):
        try:
            self.admin.teardown_admin()
        except Exception as ex:
            self._mylogger.debug("_check_admin_setup,Exception:{}".format(ex))


