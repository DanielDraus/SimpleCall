*** Settings ***
Library  simple_call

*** Test Cases ***
Make Voice Call for all connected UEs
    [Tags]    DEBUG
    Provided precondition
    simple_call.Set active pc  UEPC
    simple_call.Make voice call for rat  WCDMA
    simple_call.Make voice call for rat  GSM

    simple_call.Set active pc  UEPC2

    simple_call.Make voice call for rat  WCDMA
    simple_call.Make voice call for rat  GSM

*** Keywords ***
Provided precondition
    ${lte_calls}=  simple_call.get bts cells  lte
    ${wcdma_calls}=  simple_call.get bts cells  wcdma
    ${gsm_calls}=  simple_call.get bts cells  gsm
    log to console  ${lte_calls}
    log to console  ${wcdma_calls}
    log to console  ${gsm_calls}

    simple_call.Register UE PC  UEPC  10.44.131.182
    simple_call.Register Ftp  FTP
    simple_call.Setup all ues
    simple_call.Register UE PC  UEPC2  10.44.131.181
    simple_call.Register Ftp  FTP
    simple_call.Setup all ues
