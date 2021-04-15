import json
from collections import OrderedDict
import datetime
import os
import time
import re
import argparse
import base64

class MyJsonGenerator(object):
    content = """eyAgDQogICAiMkdfUlJNX19BTVJfb3Zlcl9HU01fIjp7ICANCiAgICAgICJyZXBvcnRlZF9uYW1lIjoiMkdfUlJNX19BTVJ
    fb3Zlcl9HU00iLA0KICAgICAgInRlc3QiOiIyR19SUk1fX0FNUl9vdmVyX0dTTSIsDQogICAgICAidGltZW91dCI6MTQ0MDAsDQogICAgICA
    icnVucyI6MSwNCiAgICAgICJmaWxlbmFtZSI6Ii9ob21lL3V0ZS9idHNhdXRvL0NBTEwvMkdfUlJNX19BTVJfb3Zlcl9HU00ucm9ib3QiDQo
    gICB9LA0KICAgIjJHX1JSTV9fR1NNX2RhdGFfdHJhbnNmZXJfIjp7ICANCiAgICAgICJyZXBvcnRlZF9uYW1lIjoiMkdfUlJNX19HU01fZGF
    0YV90cmFuc2ZlciIsDQogICAgICAidGVzdCI6IjJHX1JSTV9fR1NNX2RhdGFfdHJhbnNmZXIiLA0KICAgICAgInRpbWVvdXQiOjE0NDAwLA0
    KICAgICAgInJ1bnMiOjEsDQogICAgICAiZmlsZW5hbWUiOiIvaG9tZS91dGUvYnRzYXV0by9DQUxMLzJHX1JSTV9fR1NNX2RhdGFfdHJhbnN
    mZXIucm9ib3QiLA0KICAgICAgInBhcmFtZXRlcnMiOnsgIA0KICAgICAgICAgImRsX21pbiI6IjEyMDAwMCINCiAgICAgIH0NCiAgIH0sDQog
    ICAiM0dfUlJNX19BTVJfb3Zlcl9XQ0RNQV8iOnsgIA0KICAgICAgInJlcG9ydGVkX25hbWUiOiIzR19SUk1fX0FNUl9vdmVyX1dDRE1BIiwN
    CiAgICAgICJ0ZXN0IjoiM0dfUlJNX19BTVJfb3Zlcl9XQ0RNQSIsDQogICAgICAidGltZW91dCI6MTQ0MDAsDQogICAgICAicnVucyI6MSwNC
    iAgICAgICJmaWxlbmFtZSI6Ii9ob21lL3V0ZS9idHNhdXRvL0NBTEwvM0dfUlJNX19BTVJfb3Zlcl9XQ0RNQS5yb2JvdCINCiAgIH0sDQogIC
    AiM0dfUlJNX19IU1BBX2RhdGFfdHJhbnNmZXJfIjp7ICANCiAgICAgICJyZXBvcnRlZF9uYW1lIjoiM0dfUlJNX19IU1BBX2RhdGFfdHJhbn
    NmZXIiLA0KICAgICAgInRlc3QiOiIzR19SUk1fX0hTUEFfZGF0YV90cmFuc2ZlciIsDQogICAgICAidGltZW91dCI6MTQ0MDAsDQogICAgICA
    icnVucyI6MSwNCiAgICAgICJmaWxlbmFtZSI6Ii9ob21lL3V0ZS9idHNhdXRvL0NBTEwvM0dfUlJNX19IU1BBX2RhdGFfdHJhbnNmZXIucm9i
    b3QiLA0KICAgICAgInBhcmFtZXRlcnMiOnsgIA0KICAgICAgICAgImRsX21heCI6IjIwMDAwMDAwIiwNCiAgICAgICAgICJURVNUX1RJTUVPV
    VQiOiIyMCIsDQogICAgICAgICAiZGxfbWluIjoiMzAwMDAwMCIsDQogICAgICAgICAidWxfbWluIjoiMTUwMDAwMCINCiAgICAgIH0NCiAgIH
    0sDQogICAiNEdfUlJNX19MVEVfZGF0YV90cmFuc2Zlcl8iOnsgIA0KICAgICAgInJlcG9ydGVkX25hbWUiOiI0R19SUk1fX0xURV9kYXRhX3R
    yYW5zZmVyIiwNCiAgICAgICJ0ZXN0IjoiNEdfUlJNX19MVEVfZGF0YV90cmFuc2ZlciIsDQogICAgICAidGltZW91dCI6MTQ0MDAsDQogICAg
    ICAicnVucyI6MSwNCiAgICAgICJmaWxlbmFtZSI6Ii9ob21lL3V0ZS9idHNhdXRvL0NBTEwvNEdfUlJNX19MVEVfZGF0YV90cmFuc2Zlci5yb
    2JvdCIsDQogICAgICAicGFyYW1ldGVycyI6eyAgDQogICAgICAgICAiYmFuZHdpZHRoIjoiMTUwTSIsDQogICAgICAgICAiZGxfbWF4IjoiMT
    UwMDAwMDAwIiwNCiAgICAgICAgICJ1bF9tYXgiOiI3NTAwMDAwMCIsDQogICAgICAgICAiVEVTVF9USU1FT1VUIjoiMjAiDQogICAgICB9DQo
    gICB9DQp9"""
    dev_info = {"*": "*************",
                "**Developed by": "Daniel Draus",
                "***": "*************"}

    x = json.loads(base64.b64decode(content))

    def __init__(self, **kwargs):

        for key, value in self.dev_info.items():
            print('{:<20} | {:<10}'.format(key, value))

        for key, value in kwargs.items():
            print('{:<20} | {:<10}'.format(key, value))

        self.input_folder =  kwargs.get("input")
        self.output_file =  kwargs.get("output")
        self.auto = kwargs.get("auto")
        self.no_call = kwargs.get("no_call")
        self.call_json = kwargs.get("call_json")
        if self.call_json:
            self.check_file(self.call_json)
            json_data = open(self.call_json).read()
            self.x = json.loads(json_data)
        self.tc_json = kwargs.get("tc_json")
        self.exclude = kwargs.get("regex_exclude")
        self.include = kwargs.get("regex_include")
        if self.exclude and self.include:
            print("\nPlease use only one regex_include or regex_exclude option!!!\n")
            exit(0)

    def main(self):
        if not self.tc_json:
            self.prepare_json_from_falied_tc()
        else:
            self.prepare_json_from_json()

    def check_file(self, filepath):
        try:
            return open(filepath).closed
        except:
            print("File {} do not exist!!!".format(filepath))
            exit(0)

    def prepare_json_from_json(self):
        new_tc = OrderedDict()
        self.check_file(self.tc_json)
        json_data = open(self.tc_json).read()
        json_data = json.loads(json_data, object_pairs_hook=OrderedDict)
        cnt = 0
        cnt1 = 0
        cnt2 = 0
        for key_name in json_data.keys():
            cnt2 += 1
            item = json_data.get(key_name)
            try:
                reported_name = item.get("reported_name")
            except:
                reported_name = None

            if self.exclude:
                x = re.findall(self.exclude, reported_name)
            else:
                x = None

            if self.include:
                y = re.findall(self.include, reported_name)
            else:
                y = None

            test = item.get("test")
            no_add = self.check_if_not_call_test(test)

            if not x and not no_add:

                if y:
                    cnt += 1
                    new_tc.update({str(cnt) + "_" + key_name: item})
                    print("{}.Add TC:{}".format(cnt, key_name))
                else:
                    print("Not Included TC, skipping:{}".format(key_name))

            elif no_add:
                cnt1 += 1
                #print("Call TC, skipping:{}".format(key_name))
            elif x:
                cnt1 += 1
                #print("Excluded TC, skipping:{}".format(key_name))

        with open(self.tc_json + '_new.json', 'w') as outfile:
            json.dump(new_tc, outfile, indent=6, separators=(',', ': '))
        if cnt>0:
            self.generate_new_test_suite_json(self.tc_json + '_new.json')
            print("\nAll TC = {}, Skipped TC = {}, Saved TC = {}".format(cnt2, cnt1, cnt))
        else:
            print("\nNo TC found, All TC = {}, Skipped TC = {}".format(cnt2, cnt1))

        #with open(self.output_file, 'w') as outfile:
        #    json.dump(new_tc, outfile, indent=6, separators=(',', ': '))



    def prepare_json_from_falied_tc(self):
        if self.auto:
            self._generate_json_for_failed(os.path.join(self._find_last_modified(), "result.json"))
        else:
            self._generate_json_for_failed(os.path.join(self.input_folder, "result.json"))

    def check_if_not_call_test(self, test):
        for key_name in self.x.keys():
            item = self.x.get(key_name)
            if test in item.get("test"):
                return True
        return False

    def _find_last_modified(self):
        src_folder = self.input_folder
        relevant_folders = []
        last = ""
        lst_mod = datetime.datetime(1990, 1, 1)
        for name in os.listdir(src_folder):
            full_name = os.path.join(src_folder, name)
            if os.path.isdir(full_name):
                modifiedDate = datetime.datetime.fromtimestamp(os.path.getmtime(full_name))
                if os.path.exists(os.path.join(full_name, "result.json")):
                    if modifiedDate > lst_mod:
                        lst_mod = modifiedDate
                        last = name

        print("Last modified folder : {}\n".format(os.path.join(src_folder, last)))
        return os.path.join(src_folder, last)

    def _generate_json_for_failed(self, filename):
        tests_failed = OrderedDict()
        self.check_file(filename)
        json_data = open(filename).read()
        m = json.loads(json_data)
        cnt = 0
        cnt1 = 0
        for key_name in m.keys():
            item = m.get(key_name)
            try:
                verdict = item.get("verdict").lower()
                verdict_passed = "passed" in verdict
                verdict_failed = "failed" in verdict
            except AttributeError:
                verdict = None
                verdict_failed = True
                verdict_passed = False

            if verdict_passed:
                cnt1 += 1
                print("Found passed TC no.{}:{}".format(cnt1,item.get("reported_name")))

            if verdict_failed:
                if verdict:
                    print("Found failed TC no.{}:{}".format(cnt1, item.get("reported_name")))
                else:
                    print("Found NoRun TC no.{}:{}".format(cnt1, item.get("reported_name")))

                if not self.check_if_not_call_test(item.get("test")):
                    cnt += 1
                    tests_failed.update({str(cnt) + "_" + key_name: item})
                else:
                    print("Call TC, skipping")

        with open(filename + '_failed.json', 'w') as outfile:
            json.dump(tests_failed, outfile, indent=6, separators=(',', ': '))
        if cnt>0:
            self.generate_new_test_suite_json(filename + '_failed.json')
        else:
            print("\nNo failed TC found, 'passed' TC = {}".format(cnt1))

    def generate_new_test_suite_json(self, filename):
        json_data=open(filename).read()
        m = json.loads(json_data)

        allsites_ordered = OrderedDict()
        cnt = 0

        for key_name in m.keys():
            if self.no_call:
                for key_name2 in self.x.keys():
                    cnt += 1
                    item = self.x.get(key_name2)
                    allsites_ordered.update({str(cnt) + "_" + key_name2: item})
            cnt += 1
            item = m.get(key_name)
            allsites_ordered.update({str(cnt) + "_" + key_name: item})

        if self.no_call:
            for key_name2 in self.x.keys():
                cnt += 1
                item = self.x.get(key_name2)
                allsites_ordered.update({str(cnt) + "_" + key_name2: item})

        with open(self.output_file, 'w') as outfile:
            json.dump(allsites_ordered,outfile, indent=6, separators=(',', ': '))

        print ("NewTestSet generated under :\n\t{}".format(self.output_file))

if __name__ == "__main__":
    # construct the argument parser and parse the arguments
    ap = argparse.ArgumentParser()
    ap.add_argument("-a", "--auto", required=False,
    	help="enable search for last modified log folder in INPUT", default=True,
        action='store_false')

    ap.add_argument("-i", "--input", required=False,
    	help="path to logs folder Ex. : '/home/ute/btsauto/AutoTest/'",default="/home/ute/btsauto/AutoTest/")

    ap.add_argument("-o", "--output", required=True,
    	help="path to output json fileEx. : '/home/ute/btsauto/run_failed.json'")

    ap.add_argument("-noc", "--no_call", required=False,
                    help="flag for adding call tests before and after each failed TC\n"
                         "if defined then Calls TC will be not added",
                    action='store_false')
    ap.add_argument("-cj", "--call_json", required=False, default=None,
                    help="path to call TC json file Ex. : '/home/ute/btsauto/call.json'")

    ap.add_argument("-j", "--tc_json", required=False, default=None,
                    help="path to TC json file Ex. : '/home/ute/btsauto/sbts18_cr1.json'")

    ap.add_argument("-ex", "--regex_exclude", required=False, default=None,
                    help="Exclude reported_name TC regex Ex."
                         ":'cell_lock_unlock|reset_from_BSC'")

    ap.add_argument("-inc", "--regex_include", required=False, default=None,
                    help="Include only reported_name TC regex Ex."
                         ":'cell_lock_unlock|reset_from_BSC'")

    args = ["-o",
            "/home/ute/btsauto/test.json",
            "-i",
            "/home/ute/btsauto/AutoTest/automated_19-03-07_04-23-14/",
            "-a",
            "-cj",
            "/home/ute/btsauto/call_sbts18.json"]

    args = ["-j",
            "/home/ute/btsauto/sbts18_cr1.json",
            "-ex",
            "cell_lock_unlock|reset_from_BSC"
            ]

    args = vars(ap.parse_args())
    jsg = MyJsonGenerator(**args)
    jsg.main()

