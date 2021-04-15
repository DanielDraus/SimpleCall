*** Settings ***
Library   simple_call

*** Test Cases ***
Make Data Call for all connected UEs
    [Tags]    DEBUG
    Provided precondition
    simple_call.Make PS call for rat  LTE
    simple_call.Make PS call for rat  WCDMA
    simple_call.Make PS call for rat  GSM

*** Keywords ***
Provided precondition
    simple_call.Register UE PC  UEPC  10.44.131.182
    simple_call.Register Ftp  FTP
    simple_call.Setup all ues
