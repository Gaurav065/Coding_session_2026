#!/bin/ksh
################################################################################################
#
#  Change History
#
#  ChangeDate                   Version         Author                                  Description
#  20230323                       1.0         KARTHIKEYAN S               CHG0084862-FEASIBLE_SALES Load FOR BEEXE
##################################################################################################################

## Set DS profile

. /local/data1/edw/profile/set_ebi_ds_env

SERVER_NAM=`hostname`
echo server name: $SERVER_NAM
BTEQ_LOG="${LOG_DIR}/feasible_sales_be_load_dep_check.log"

if [ -f $BTEQ_LOG ]
then
rm $BTEQ_LOG
fi

bteq << EOFBTEQ > ${BTEQ_LOG} 2>&1

.RUN FILE /local/data1/edw/bin/edwp_generic_etl.logon;
.SET TITLE OFF;
.SET TITLEDASHES OFF;
.SET ECHOREQ OFF;
.SET RECORDMODE OFF;

SEL *  FROM DS_APP_CNTRL.EDW_LOAD_QUEUE_V WHERE LOAD_NAM IN ('FEASIBLE_SALES_BE');

.IF ACTIVITYCOUNT <> 0  THEN .EXIT 40

SEL *  FROM DS_APP_CNTRL.EDW_LOAD_HST_V WHERE LOAD_EVT_ID ='POST-POST' AND EVT_STATUS_CD='COMPLETED' 
AND LOAD_NAM IN ('FEASIBLE_SALES_BE')
AND CAST(EVT_END_DTTM AS DATE) = CURRENT_DATE;

.IF ACTIVITYCOUNT <> 0  THEN .EXIT 80

SELECT SUM(CNT1) AS CNT2 FROM
(
SEL COUNT(*) AS CNT1 FROM DS_APP_CNTRL.EDW_LOAD_HST_V WHERE LOAD_EVT_ID ='POST-POST' AND EVT_STATUS_CD='COMPLETED'
AND LOAD_NAM IN ('TD_FX_J'
,'TD_FFP_SCP_OUT_J'
,'TD_SHP_SCP_OUT_J'
,'SALES_BLEND'
,'ORDERBOOK_SNAPSHOT_DAILY')
AND CAST(EVT_END_DTTM AS DATE)=CURRENT_DATE
GROUP BY LOAD_NAM
) A HAVING CNT2 =5;

.IF ACTIVITYCOUNT = 0  THEN .EXIT 8


.QUIT;
EOFBTEQ

nExitStatus=$?
if [[ $nExitStatus -eq 0 ]]
then

echo ".trig file has been created to initiate FEASIBLE_SALES_BE Load"
touch /local/data1/edw/trigger/FEASIBLE_SALES_BE.trig

fi
exit 0;
