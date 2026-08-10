#!/bin/ksh
################################################################################################
#
#  Change History
#
#  ChangeDate                   Version         Author                                  Description
#  20230215                       1.0         Monisha Thangam M               CHG0074101-FEASIBLE_SALES_Load table status Check
##################################################################################################################

## Set DS profile

. /local/data1/edw/profile/set_ebi_ds_env

SERVER_NAM=`hostname`
echo server name: $SERVER_NAM
BTEQ_LOG="${LOG_DIR}/feasible_sales_load_dep_check.log"

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

SEL *  FROM DS_APP_CNTRL.EDW_LOAD_QUEUE_V WHERE LOAD_NAM IN ('FEASIBLE_SALES');

.IF ACTIVITYCOUNT <> 0  THEN .EXIT 40

SEL *  FROM DS_APP_CNTRL.EDW_LOAD_HST_V WHERE LOAD_EVT_ID ='POST-POST'
AND LOAD_NAM IN ('FEASIBLE_SALES')
AND CAST(EVT_END_DTTM AS DATE) = CURRENT_DATE;

.IF ACTIVITYCOUNT <> 0  THEN .EXIT 80

SELECT SUM(CNT1) AS CNT2 FROM
(
SEL COUNT(*) AS CNT1 FROM DS_APP_CNTRL.EDW_LOAD_HST_V WHERE LOAD_EVT_ID ='POST-POST' AND EVT_STATUS_CD='COMPLETED'
AND LOAD_NAM IN ('TD_FX_A','TD_FX_C','TD_FX_E','TD_FX_H','TD_FX_D','TD_FX_G',
'TD_FFP_SCP_OUT_A','TD_FFP_SCP_OUT_C','TD_FFP_SCP_OUT_E','TD_FFP_SCP_OUT_H',
'TD_FFP_SCP_OUT_D','TD_FFP_SCP_OUT_G','TD_SHP_SCP_OUT_A','TD_SHP_SCP_OUT_C','TD_SHP_SCP_OUT_D','TD_SHP_SCP_OUT_E','TD_SHP_SCP_OUT_G',
'TD_SHP_SCP_OUT_H','SALES_BLEND','ORDERBOOK_SNAPSHOT_DAILY')
AND CAST(EVT_END_DTTM AS DATE)  IN ( CURRENT_DATE,CURRENT_DATE-1)
GROUP BY LOAD_NAM
) A HAVING CNT2 =20;

.IF ACTIVITYCOUNT = 0  THEN .EXIT 8


.QUIT;
EOFBTEQ

nExitStatus=$?
if [[ $nExitStatus -eq 0 ]]
then

echo ".trig file has been created to initiate FEASIBLE_SALES Load"
touch /local/data1/edw/trigger/FEASIBLE_SALES.trig

fi
exit 0;

