# -*- coding: utf-8 -*-
"""
:author: Daniel Draus
:contact: danieldraus1@interia.pl
"""
import re
from ute_common_store.store import Store
from ute_common_store.exception import NameIsProtected,AliasError

from contextlib import contextmanager
try:
    from robot.api import logger
    from robot.libraries.BuiltIn import BuiltIn
except ImportError:
    import logging
    logger = logging.getLogger("SimpleCall")

    class BuiltIn(object):
        def log(self, s, console):
            pass

        def fail(self, s):
            pass

        def run_keyword(self, s):
            pass

        def get_variable_value(self, s):
            pass


from interfaces import SimpleCall
from .interfaces.SimpleCall.Utils import IperfClass
from .interfaces.SimpleCall.Utils import BTS


class simple_call(object):

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    simple_call_instance = SimpleCall()
    _iperfclass = IperfClass("", "", "")
    _active_pc = None

    def __init__(self):
        self.store = Store()

    def register_ue_pc(self, uepc_alias="default",
                       uepc_host="",
                       pyro_port=9091,
                       uepc_username="username",
                       uepc_password="password",
                       uepc_domain="DOMAIN",
                       robot=True):

        self.simple_call_instance = SimpleCall(alias=uepc_alias,
                                            ip=uepc_host,
                                            port=pyro_port,
                                            domain=uepc_domain,
                                            uname=uepc_username,
                                            passwd=uepc_password,
                                            robot=robot)

        self.simple_call_instance.setup_pc(self._iperfclass)
        simple_call = self.simple_call_instance
        try:
            self.store.add(simple_call, uepc_alias)
            self._active_pc = self.store.get(uepc_alias)
        except NameIsProtected:

            raise NameIsProtected(
                "Alias ({}) exists. Please remove it to reuse.".format(uepc_alias))

    def recover_ue_pc(self, uepc_alias="default"):
        self._active_pc.check_ssh(True)
        self._active_pc.reset_modems()

    def setup_ues(self, *ue_list):
        self._active_pc.setup_ues(ue_list)

    def register_ue(self, ue_alias, ue_serial, uepc_alias):
        self._active_pc.setup_ue(ue_alias, ue_serial, uepc_alias)

    def register_ftp(self, ftp_alias="myFtp",
                     pc_host_ip="10.44.44.167",
                     username="syslab",
                     password="system"):

        self._iperfclass = IperfClass(pc_host_ip, username, password)
        if self._active_pc:
            self._active_pc.setup_iperf_server(self._iperfclass.pc_host_ip,
                                                  self._iperfclass.username,
                                                  self._iperfclass.password)
        else:
            self.simple_call_instance.setup_iperf_server(self._iperfclass.pc_host_ip,
                                                  self._iperfclass.username,
                                                  self._iperfclass.password)

    def set_band_pref(self, ue_alias, sim_no, rat, band):
        self._active_pc.set_band(ue_alias, sim_no, rat, band)

    def make_ps_call(self,ue_serial,
                     duration=10,
                     protocol="udp",
                     bandwidth="240",
                     dl_max="200000000",
                     dl_min="14",
                     ul_max="120000000",
                     ul_min="9"):

        self._active_pc.make_ps_call(ue_serial=ue_serial,
                                     duration=duration,
                                     protocol=protocol,
                                     bandwidth=bandwidth,
                                     dl_max=dl_max,
                                     dl_min=dl_min,
                                     ul_max=ul_max,
                                     ul_min=ul_min,
                                     cnt=3)

    def make_ps_call_for_rat(self, rat,
                             duration=10,
                             protocol="udp",
                             bandwidth="240",
                             dl_max="200000000",
                             dl_min="14",
                             ul_max="120000000",
                             ul_min="9"):

        self._active_pc.make_ps_call_for_rat(rat,
                                                    duration,
                                                    protocol,
                                                    bandwidth,
                                                    dl_max,
                                                    dl_min,
                                                    ul_max,
                                                    ul_min,
                                                    3)

    def make_voice_call(self, ue_serial, number, duration):
        self._active_pc.make_voice_call(ue_serial, number, duration)

    def make_voice_call_for_rat(self, rat, number="0666002", duration=10):
        self._active_pc.make_voice_call_for_rat(rat,number,duration)

    def data_transfer_mode(self, ue_serial, option):
        self._active_pc.data_transfer_mode(ue_serial,option)

    def ensure_that_ue_is_connected_to_proper_cell(self, ue_serial, lnbts_id, rat,retries=3):
        cid = self._active_pc.get_ue_cellid(ue_serial).strip()

        try:
            cid = int(cid)
        except ValueError:
            pass

        if not isinstance(cid, "".__class__):
            if 'WCDMA' in rat:
                cid = cid & 0xFFFF
            elif 'LTE' in rat:
                cid = cid >> 8
        cid = str(cid)

        lnbts_id_fixed = list(str(x[0]) for x in lnbts_id if isinstance(x, list))

        if lnbts_id_fixed:
            lnbts_id = lnbts_id_fixed
        else:
            lnbts_id = str(lnbts_id)

        if 'LTE' in rat:
            BuiltIn().log("Checking if UE {} is connected to proper cell,"
                          "UE BTS no '{}' ,SBTS no: {}".format(ue_serial, cid, lnbts_id), console=True)
        else:
            BuiltIn().log("Checking if UE {} is connected to proper cell,"
                          " Current cell id: '{}' ,SBTS cells: {}".format(ue_serial, cid, lnbts_id), console=True)

        if cid not in lnbts_id:
            if retries > 0:
                retries -= 1
                BuiltIn().fail("UE not locked to SBTS cells\n")
                self._active_pc.toogleAirplane(ue_serial)
                self.ensure_that_ue_is_connected_to_proper_cell(ue_serial, lnbts_id, rat, retries)
            else:
                BuiltIn().fail(
                    "UE {} not locked to SBTS cells: {}. Current cell id: {}".format(ue_serial, lnbts_id, cid))

    def get_cell_id_in_specific_rat(self, ue_serial, rat):
        cid = self._active_pc.get_ue_cellid(ue_serial).strip()

        try:
            cid = int(cid)
        except ValueError:
            pass

        if isinstance(cid, "".__class__):
            return -1
        else:
            if 'WCDMA' in rat:
                cid = cid & 0xFFFF
            elif 'LTE' in rat:
                cid = cid >> 8
            return cid

    def recover_ue_pc(self, uepc_alias):
        pass

    def recover_ue(self, ue_serial, uepc_alias):
        pass

    def show_ue_table(self, ue_serial):
        self._active_pc.show_ue_table(ue_serial)

    def recover_ues_services(self, ue_aliases):
        for ue in ue_aliases:
            self._active_pc.set_air_plane_by_alias(ue, "OFF")
            self._active_pc.data_transfer_mode_by_alias(ue, "enable")

    @staticmethod
    def get_wcdma_cells_ids():
        cells_cid = []
        cells_obj = BuiltIn().run_keyword("Get Ids For All","WNCEL")
        for cell in cells_obj:
            match = re.findall("\d+$", cell)
            if match:
               cells_cid.append(match)
        return cells_cid


    def qt_custom_test_teardown(self,env_errors_alowed):

        BuiltIn().log("SimpleCall teardown- close all apps, amr calls, connections.",console=True)

        self._active_pc.teardown()

        if BuiltIn().get_variable_value("${TEST_STATUS}") == "PASS" or env_errors_alowed:
            BuiltIn().run_keyword("Common Test Teardown")
        else:
            collect_snapshot = "failed_verdict"
            BuiltIn().run_keyword("Common Test Teardown", collect_snapshot)

    def run_at_command(self, ue_serial, *commands):
        return self._active_pc.run_at_command(ue_serial, commands)

    def setup_all_ues(self):
        self._active_pc.setup_all_ues()

    def get_bts_cells(self, rat):
        self.bts = BTS()
        return self.bts.get_bts_cells_info(rat)

    def set_active_pc(self, uepc_alias):
        if self.store.has_alias(uepc_alias):
            self._active_pc = self.store.get(uepc_alias)
        else:
            raise AliasError(
                "Alias ({}) do not exists. Please setup PC to reuse.".format(uepc_alias))

    def teardown_pc(self, uepc_alias):
        if self.store.has_alias(uepc_alias):
            self._active_pc = self.store.remove(uepc_alias)
        else:
            raise AliasError(
                "Alias ({}) do not exists. Please setup PC to reuse.".format(uepc_alias))



