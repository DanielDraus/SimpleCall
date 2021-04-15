*** Settings ***
Library        Collections
Library        DateTime
Library        hran_IV8
Library        ute_async
Library        hran_bsc
Resource       /home/ute/btsauto/hran_ta/resources/hran_frame_sbts.robot
#Resource       /home/ute/btsauto/hran_ta/resources/hran_uem.robot
Test Setup     Perform setup
Test Teardown  Perform teardown


*** Variables ***
${DATA_TRANSFER_DURATION}     45s
${ASYNC_WAIT_DURATION}        90.0
${WAIT_FOR_DT_TO_BE_VISIBLE}  30s
${CALL_DURATION}  15
${BANDWIDTH}      10M
${MIN_TPUT}       1000
${MAX_TPUT}       1000000000
${FTP_LABEL}      FTP_SERVER
${GSM_NUMBER}     0666002
${WCDMA_NUMBER}   0666006

&{ignored_alarm1}       faultId=61524  severity=Major
&{ignored_alarm2}       faultId=61652  severity=Major
&{ignored_alarm3}       faultId=61649  severity=Major
&{ignored_alarm4}       number=7114  severity=Critical
@{ignored}    ${ignored_alarm1}  ${ignored_alarm2}  ${ignored_alarm3}  ${ignored_alarm4}

*** Test Cases ***
Run_all_scenarios_for_datatransfers
    ${bsc_cids} =    Get GSM cell IDs after connecting to BSC
    Prepare UEs  ${gsm_ues}    ${bsc_cids}    GSM
    :FOR  ${ue_serial}  IN  @{gsm_ues}
    \  Run keyword and continue on failure  Execute all voice calls    ${ue_serial}  ${CALL_DURATION}  ${GSM_NUMBER}
    \  Run keyword and continue on failure  Execute all datatransfers  ${ue_serial}

    ${wcdma_cids} =  Get WCDMA cells IDs
    Prepare UEs  ${wcdma_ues}  ${wcdma_cids}  WCDMA
    :FOR  ${ue_serial}  IN  @{wcdma_ues}
    \  Run keyword and continue on failure  Execute all voice calls    ${ue_serial}  ${CALL_DURATION}  ${WCDMA_NUMBER}
    \  Run keyword and continue on failure  Execute all datatransfers  ${ue_serial}

    ${lnbts_id} =    Get LTE LNBTS ID
    Prepare UEs  ${lte_ues}    ${lnbts_id}    LTE
    :FOR  ${ue_serial}  IN  @{lte_ues}
    \  Run keyword and continue on failure  Execute all datatransfers  ${ue_serial}


*** Keywords ***
Setup FTP
    ${ftp} =  Get Variable Value  &{${FTP_LABEL}}
    Should Not Be Equal  ${FTP_LABEL}  ${None}
    ...  Config for ${FTP_LABEL} doesn't exist. Did you add ${FTP_LABEL}=${FTP_LABEL} to env_config_1.yaml?
    ...  values=False
    Register FTP    FTP   ${ftp['ip']}  ${ftp['user']}  ${ftp['password']}

Setup UE PC
    Register UE PC  UEPC  ${uepc['ip']}  ${uepc['pyro_port']}  ${uepc['username']}  ${uepc['password']}
    Recover UE PC   UEPC

Get GSM cell IDs after connecting to BSC
    Bsc Connection  host=${BSC['ip']}
    Bsc Login  username=${BSC['user']}  password=${BSC['password']}
    ${bcfs} =  Query Infomodel  get list //GNBCF_A-1
    ${bcf_id} =  Evaluate  next((bcf['bcfId'] for bcf in ${bcfs}))
    ${bsc_cids} =  Get Gsm Cells Ids  ${bcf_id}
    [Return]  ${bsc_cids}

Get LTE LNBTS ID
    ${bts} =  Get Parameters For All  BTS
    ${lnbts_id} =  Evaluate  [next(b['btsId'] for b in ${bts})]
    [Return]  ${lnbts_id}

Prepare UEs
    [Arguments]  ${ue_serials}  ${cell_ids}  ${rat}
    : FOR  ${ue_serial}  IN  @{ue_serials}
    \  Prepare single UE  ${ue_serial}  ${cell_ids}  ${rat}

Prepare single UE
    [Arguments]  ${ue_serial}  ${cell_ids}  ${rat}
    Register UE  ${ue_serial}  ${ue_serial}  UEPC
    Recover UE   ${ue_serial}  UEPC
    Data transfer mode  ${ue_serial}  disable
    Ensure that UE is connected to proper cell  ${ue_serial}  ${cell_ids}  ${rat}
    Data transfer mode  ${ue_serial}  enable
    Sleep  10s  Wait for UE establishment
    Show UE table  ${ue_serial}

Execute all voice calls
    [Arguments]  ${ue_serial}  ${call_duration}  ${number}
    Run keyword and continue on failure  Start voice call and wait for it to finish  ${ue_serial}  ${call_duration}  ${number}
    Run keyword and continue on failure  Start voice call and interrupt it           ${ue_serial}  ${call_duration}  ${number}

Start voice call and log its status
    [Arguments]  ${call_alias}  ${ue_serial}  ${number}
    Start voice call  ${call_alias}  ${ue_serial}  ${number}
    Sleep  2s
    ${call_ongoing} =  Call status  ${call_alias}
    Run keyword unless  ${call_ongoing}  Log  Call ${call_alias} did not start  level=WARN  console=True

Start voice call and wait for it to finish
    [Arguments]  ${ue_serial}  ${call_duration}  ${number}
    ${call_alias} =  Set variable  ${ue_serial}_await_finish
    Start voice call and log its status  ${call_alias}  ${ue_serial}  ${number}
    Await voice call finish  ${call_alias}  ${call_duration}

Start voice call and interrupt it
    [Arguments]  ${ue_serial}  ${call_duration}  ${number}
    ${call_alias} =  Set variable  ${ue_serial}_interrupted_call
    Start voice call and log its status  ${call_alias}  ${ue_serial}   ${number}
    ${sleep_duration} =  Subtract time from time  ${call_duration}  2s
    Sleep  ${sleep_duration}
    End voice call  ${call_alias}

Execute all datatransfers
    [Arguments]  ${ue_serial}
    Execute datatransfers for given protocol  ${ue_serial}  TCP
    Execute datatransfers for given protocol  ${ue_serial}  UDP

Execute datatransfers for given protocol
    [Arguments]  ${ue_serial}  ${protocol}
    ${bandwidth} =  Set variable if  '${protocol}' == 'TCP'  ${None}  ${BANDWIDTH}

    Run keyword and continue on failure  Run keywords
    ...  Create datatransfer  ${protocol}_${ue_serial}_sync_DL   downlink  ${ue_serial}  FTP  ${DATA_TRANSFER_DURATION}  ${protocol}  bandwidth=${bandwidth}
    ...  AND  Execute synchronous datatransfer  ${protocol}_${ue_serial}_sync_DL

    Run keyword and continue on failure  Run keywords
    ...  Create datatransfer  ${protocol}_${ue_serial}_sync_UL   uplink    ${ue_serial}  FTP  ${DATA_TRANSFER_DURATION}  ${protocol}  bandwidth=${bandwidth}
    ...  AND  Execute synchronous datatransfer  ${protocol}_${ue_serial}_sync_UL

    Run keyword and continue on failure  Run keywords
    ...  Create datatransfer  ${protocol}_${ue_serial}_sync_multistream_DL   downlink  ${ue_serial}  FTP  ${DATA_TRANSFER_DURATION}  ${protocol}  bandwidth=${bandwidth}  streams=5
    ...  AND  Execute synchronous datatransfer  ${protocol}_${ue_serial}_sync_multistream_DL

    Run keyword and continue on failure  Run keywords
    ...  Create datatransfer  ${protocol}_${ue_serial}_sync_multistream_UL   uplink    ${ue_serial}  FTP  ${DATA_TRANSFER_DURATION}  ${protocol}  bandwidth=${bandwidth}  streams=5
    ...  AND  Execute synchronous datatransfer  ${protocol}_${ue_serial}_sync_multistream_UL

    Run keyword and continue on failure  Run keywords
    ...  Create datatransfer  ${protocol}_${ue_serial}_async_DL  downlink  ${ue_serial}  FTP  ${DATA_TRANSFER_DURATION}  ${protocol}  bandwidth=${bandwidth}
    ...  AND  Execute asynchronous datatransfer and wait for result  ${protocol}_${ue_serial}_async_DL

    Run keyword and continue on failure  Run keywords
    ...  Create datatransfer  ${protocol}_${ue_serial}_async_UL  uplink    ${ue_serial}  FTP  ${DATA_TRANSFER_DURATION}  ${protocol}  bandwidth=${bandwidth}
    ...  AND  Execute asynchronous datatransfer and wait for result  ${protocol}_${ue_serial}_async_UL

    Run keyword and continue on failure  Run keywords
    ...  Create datatransfer  ${protocol}_${ue_serial}_async_interrupted_DL  downlink  ${ue_serial}  FTP  ${DATA_TRANSFER_DURATION}  ${protocol}  bandwidth=${bandwidth}
    ...  AND  Execute asynchronous datatransfer and interrupt it during execution  ${protocol}_${ue_serial}_async_interrupted_DL

    Run keyword and continue on failure  Run keywords
    ...  Create datatransfer  ${protocol}_${ue_serial}_async_interrupted_UL  uplink    ${ue_serial}  FTP  ${DATA_TRANSFER_DURATION}  ${protocol}  bandwidth=${bandwidth}
    ...  AND  Execute asynchronous datatransfer and interrupt it during execution  ${protocol}_${ue_serial}_async_interrupted_UL

    [Teardown]  Clear all datatransfers

Execute synchronous datatransfer
    [Arguments]  ${data_transfer_alias}
    Start datatransfer  ${data_transfer_alias}
    Verify average throughput  ${data_transfer_alias}  ${MIN_TPUT}  ${MAX_TPUT}

Execute asynchronous datatransfer and wait for result
    [Arguments]  ${data_transfer_alias}
    ${async_alias} =  Set variable  async_${data_transfer_alias}
    Start async  hran_uem  Start datatransfer  ${data_transfer_alias}  alias=${async_alias}
    Wait for async result  ${ASYNC_WAIT_DURATION}  alias=${async_alias}
    Stop async  ${ASYNC_WAIT_DURATION}  alias=${async_alias}
    Verify average throughput  ${data_transfer_alias}  ${MIN_TPUT}  ${MAX_TPUT}

Execute asynchronous datatransfer and interrupt it during execution
    [Arguments]  ${data_transfer_alias}
    ${async_alias} =  Set variable  async_${data_transfer_alias}
    Start async  hran_uem  Start datatransfer  ${data_transfer_alias}  alias=${async_alias}
    Sleep  ${WAIT_FOR_DT_TO_BE_VISIBLE}  Testers wait until data transfer is visible on BTS before they terminate the transfer.
    Stop datatransfer  ${data_transfer_alias}
    Wait for async result  ${ASYNC_WAIT_DURATION}  alias=${async_alias}
    Stop async  ${ASYNC_WAIT_DURATION}  alias=${async_alias}
    Verify average throughput  ${data_transfer_alias}  ${MIN_TPUT}  ${MAX_TPUT}

Perform setup
    Common Test Setup  ignored_alarms=@{ignored}
    Setup FTP
    Setup UE PC

Perform teardown
    Run keyword and ignore error  hran_bsc.Close All Connections
    Common Test Teardown  collect_snapshot=never
