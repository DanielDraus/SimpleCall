*** Settings ***
Library   hran_IV8

*** Test Cases ***
Make Data Call for all connected UEs
    [Tags]    DEBUG
    Provided precondition
    hran_IV8.Make PS call for rat  LTE
    hran_IV8.Make PS call for rat  WCDMA
    hran_IV8.Make PS call for rat  GSM

*** Keywords ***
Provided precondition
    hran_IV8.Register UE PC  UEPC  10.44.131.182
    hran_IV8.Register Ftp  FTP
    hran_IV8.Setup all ues
