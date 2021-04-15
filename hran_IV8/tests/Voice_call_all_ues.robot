*** Settings ***
Library  hran_IV8

*** Test Cases ***
Make Voice Call for all connected UEs
    [Tags]    DEBUG
    Provided precondition
    hran_IV8.Set active pc  UEPC
    hran_IV8.Make voice call for rat  WCDMA
    hran_IV8.Make voice call for rat  GSM

    hran_IV8.Set active pc  UEPC2

    hran_IV8.Make voice call for rat  WCDMA
    hran_IV8.Make voice call for rat  GSM

*** Keywords ***
Provided precondition
    ${lte_calls}=  hran_IV8.get bts cells  lte
    ${wcdma_calls}=  hran_IV8.get bts cells  wcdma
    ${gsm_calls}=  hran_IV8.get bts cells  gsm
    log to console  ${lte_calls}
    log to console  ${wcdma_calls}
    log to console  ${gsm_calls}

    hran_IV8.Register UE PC  UEPC  10.44.131.182
    hran_IV8.Register Ftp  FTP
    hran_IV8.Setup all ues
    hran_IV8.Register UE PC  UEPC2  10.44.131.181
    hran_IV8.Register Ftp  FTP
    hran_IV8.Setup all ues
