Logs :

Supported Samsung rooted phones:

"model"               : "SM-J510FN"
"model"               : "GT-I950"
"model"               : "SM-J250M"

Ue Pc – operationg system : Windows

Req.

1.Superuser on UE.

2.UE USB connection mode set to modem,adb

3.UE connected to UE PC

4.Cygwin SSH installed on Ue Pc

5.PowerShell on Ue Pc

6.samba-common-bin on VM or host PC

7.Python 2.7


Instalation :

pip install -U git+https://github.com/DanielDraus/SimpleCall.git@master --no-deps

Python usage1:

    test_params = {
                        'alias': "daniel test",
                        'ip': "10.44.131.181",
                        'port': 9091,
                        'uname': 'username',
                        'domain': 'SomeDomain',
                        'passwd': 'password'
                    }

    s_call_instance = SimpleCallInterface(**test_params)

    iperfclass = IperfClass("10.44.44.167", "syslab", "system")

    s_call_instance.setup_pc(iperfclass)

    try:
        s_call_instance.check_ssh()
    except:
        s_call_instance.reboot_ue_pc()

        s_call_instance.setup_all_ues()
        s_call_instance.make_voice_call_for_rat("GSM")
        s_call_instance.make_ps_call_for_rat("GSM")
        s_call_instance.make_voice_call_for_rat("WCDMA")
        s_call_instance.make_ps_call_for_rat("WCDMA")
        s_call_instance.make_ps_call_for_rat("LTE")
        s_call_instance.teardown()


Python usage2:


    from simple_call.interfaces.SimpleCall.SimpleCallInterface import SimpleCallInterface
    from simple_call.interfaces.SimpleCall.Utils import IperfClass, BANDS
    import base64

    #define SimpleCallInterface parameters
    test_params = {
        'alias': "daniel test",
        'ip': "10.44.131.181",
        'port': 9091,
        'uname': 'username',
        'domain': 'DOMAIN',
        'passwd': 'password'
    }

    #create SimpleCall instance
    s_call_instance = SimpleCallInterface(**test_params)
    #create IperfClass instance
    iperfclass = IperfClass("10.44.44.167", "syslab", "system")

    #setup UE_PC
    s_call_instance.setup_pc(iperfclass)

    #Check if sshd service is running on UE_PC
    s_call_instance.check_ssh()

    #Reboot UE_PC
    s_call_instance.reboot_ue_pc()

    #setup Iperf Server
    s_call_instance.setup_iperf_server("10.44.44.167", "syslab", "system")

    #setup UEs
    s_call_instance.setup_ues([{"ue_alias": "0279cef6", "ue_adb_sn": "0279cef6"},
                        {"ue_alias": "de73a8d2", "ue_adb_sn": "de73a8d2"},
                        {"ue_alias": "ae0fb898", "ue_adb_sn": "ae0fb898"},
                        {"ue_alias": "adf8b824", "ue_adb_sn": "adf8b824"},
                        {"ue_alias": "1b0acee4", "ue_adb_sn": "1b0acee4"}])

    #Get supported band by library
    supported_bands = [i for i in dir(BANDS) if not callable(i) and not "__module__" in i and not "__doc__" in i]

    #Run single AT Commnad on UE
    print(s_call_instance.run_at_command("ae0fb898", [base64.b64encode("AT$QCBANDPREF=?")]))

    #Test all supported bands change on UE:
    for a in supported_bands:
        s_call_instance.set_band_by_at([a],"ae0fb898")

    #Change UE band example:
    s_call_instance.set_band_by_at(["Any"], "ae0fb898")

    #Print all UEs cell id
    print(s_call_instance.get_all_ues_cellid())

    #Change UE band example:
    s_call_instance.set_band_by_at(["GSM_EGSM_900"], "0279cef6")

    #Toogle AirPlane mode on UE:
    s_call_instance.toogleAirplane("0279cef6")


    #Create Commands List
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

    #Run and print AT Commands List on UE
    print(s_call_instance.run_at_command("0279cef6", commands))

    '''Show UE table:
    'Android version','IMEI','Network type','IP','Model',Airplane settings'
    'SignalStrength','Battery level','Battery temperature','Battery health'
    'Cell_Id','Com port'
    '''
    s_call_instance.show_ue_table("0279cef6")

    #Make AMR call with number
    s_call_instance.make_voice_call("0279cef6", "0666002", 10)

    #Make Data call with default arguments
    s_call_instance.make_ps_call("0279cef6","10")

    #Make Data call with arguments
    s_call_instance.make_ps_call("0279cef6","10",cnt=3,bandwidth="240",dl_max="20000000",dl_min="9000000",ul_max="12000000",ul_min="6000000")

    #install iperf on UE under /system/bin
    s_call_instance.iperf_installer.install_iperf("0279cef6")

    #Set band for UE by Service Menu
    s_call_instance.set_band("DD",2,"WCDMA","B1")



Robot Framework usage:

AMR CALL:


    *** Settings ***
    library  simple_call

    *** Test Cases ***
    Make Voice Call for all connected UEs
        [Tags]    DEBUG
        Provided precondition
        simple_call.Make voice call for rat  WCDMA
        simple_call.Make voice call for rat  GSM

    *** Keywords ***
    Provided precondition
        simple_call.Register UE PC  UEPC
        simple_call.Register Ftp  FTP
        simple_call.Setup all ues


DATA CALL:


    *** Settings ***
    library  simple_call

    *** Test Cases ***
    Make Data Call for all connected UEs
        [Tags]    DEBUG
        Provided precondition
        simple_call.Make PS call for rat  LTE
        simple_call.Make PS call for rat  WCDMA
        simple_call.Make PS call for rat  GSM

    *** Keywords ***
    Provided precondition
        simple_call.Register UE PC  UEPC
        simple_call.Register Ftp  FTP
        simple_call.Setup all ues


Warning: CryptographyDeprecationWarning: · Issue #1386:
    This has been fixed in Paramiko already:
    https://github.com/paramiko/paramiko/issues/1369
    https://github.com/paramiko/paramiko/pull/1379
    Bug the fix was not released yet.

    Meanwhile, you can workaround it by downgrading cryptography:

    pip install cryptography==2.4.2

after all:
pip install cryptography==2.4.2
DEPRECATION: Python 2.7 will reach the end of its life on January 1st, 2020. Please upgrade your Python as Python 2.7 won't be maintained after that date. A future version of pip will drop support for Python 2.7.
Looking in indexes: https://pypi.dynamic.nsn-net.net/panda/pypi
Collecting cryptography==2.4.2
  Downloading https://pypi.dynamic.nsn-net.net/root/pypi/+f/af1/2dfc9874ac27e/cryptography-2.4.2-cp27-cp27mu-manylinux1_x86_64.whl (2.1MB)
    100% |\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588| 2.1MB 56.5MB/s
Requirement already satisfied: asn1crypto>=0.21.0 in /opt/ute/python/lib/python2.7/site-packages (from cryptography==2.4.2) (0.24.0)
Requirement already satisfied: enum34; python_version < "3" in /opt/ute/python/lib/python2.7/site-packages (from cryptography==2.4.2) (1.1.6)
Requirement already satisfied: six>=1.4.1 in /opt/ute/python/lib/python2.7/site-packages (from cryptography==2.4.2) (1.10.0)
Requirement already satisfied: cffi!=1.11.3,>=1.7 in /opt/ute/python/lib/python2.7/site-packages (from cryptography==2.4.2) (1.12.2)
Requirement already satisfied: idna>=2.1 in /opt/ute/python/lib/python2.7/site-packages (from cryptography==2.4.2) (2.8)
Requirement already satisfied: ipaddress; python_version < "3" in /opt/ute/python/lib/python2.7/site-packages (from cryptography==2.4.2) (1.0.22)
Requirement already satisfied: pycparser in /opt/ute/python/lib/python2.7/site-packages (from cffi!=1.11.3,>=1.7->cryptography==2.4.2) (2.19)
ute-syslog 2.5.0 has requirement mock<2.0.0,>=1.0.1, but you'll have mock 2.0.0 which is incompatible.
ute-syslog 2.5.0 has requirement paramiko<2.0.0,>=1.10.1, but you'll have paramiko 2.4.2 which is incompatible.
Installing collected packages: cryptography
  Found existing installation: cryptography 2.6.1
    Uninstalling cryptography-2.6.1:
      Successfully uninstalled cryptography-2.6.1
Successfully installed cryptography-2.4.2

