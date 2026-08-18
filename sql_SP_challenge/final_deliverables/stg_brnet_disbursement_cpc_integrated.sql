%sql
-- ============================================================================
--  lakehouse_uat.stg_brnet.disb_test
--  Integration pass: +3 attributes from the GLOSMemberTracker report SP
--    BRNet Stage / BRNet Status / CurrentStatus
--
--  PREVIOUS REVISION integrated +3 PTP attributes from the DPD / collections
--  report SP (#LoanDtls):
--    Number of times PTP date has been entered
--    PTP date
--    PTP Reason
--
--  THIS REVISION integrates +1 attribute from the GLOSMemberTracker report SP:
--    Accrued interest
--
--  ── ACCRUED INTEREST NOTES (this revision) ─────────────────────────────────
--  SP final SELECT:
--    ROUND(ISNULL(IntDue,0) + ISNULL(BrokenperiodInterest,0), 2) AS [Accrued interest]
--
--  Five ordered SP stages, each a separate UPDATE that the next depends on:
--    STAGE 0  DeathDate            ← t_ClientDemiseDetail (joined on ClientID ONLY)
--    STAGE 1  IntDue / BefInstallmentDate / NexInstallmentDate /
--             InstallmentStDate    ← t_LoanInstallment aggregate per
--                                    (branch, account, series); Bef/Nex pivot on
--                                    ISNULL(DeathDate, @ToDate)
--    STAGE 2  Interest             ← InterestDue of the installment whose
--                                    InstallmentDueDate = NexInstallmentDate
--    STAGE 3  DailyAccredAmt       ← Interest / day-span (death branch uses
--                                    DisbursedDate → InstallmentStDate)
--    STAGE 4  BrokenperiodInterest ← DailyAccredAmt × (days + 1), then a separate
--                                    UPDATE clamping negatives to 0
--
--  Implemented as CTEs 54-59; fills the pre-existing CAST(NULL) AccruedInterest
--  placeholder in the final SELECT. cte_li (CTE 4) is NOT reusable here — it
--  collapses to one row per account, so it cannot back an aggregate.
--
--  *** @ToDate ANCHOR *** hardcoded DATE '2026-07-07' to match the existing
--    cte_loantrx_agg literal. Keep the two in sync (or lift both to a param).
--  *** DATEDIFF ARG ORDER *** T-SQL DATEDIFF(DD, start, end) inverts to Spark
--    datediff(end, start). Reversed throughout CTEs 57-59.
--  *** CONFIRM COLUMN *** InstallmentNo assumed as the per-installment key in
--    cte_li_dedup (CTE 55).
--
--  ── PTP INTEGRATION NOTES (previous revision) ──────────────────────────────
--  The DPD SP computes these in FOUR ordered stages; later UPDATEs overwrite
--  earlier ones ONLY where they match, so the precedence is load-bearing.
--
--    STAGE 0  MaxCollDate (a THRESHOLD, not an output)
--      = MAX(TrxDate) WHERE CollectedAmount>0, per (Branch,Account,Client);
--        falls back to MAX(TrxDate) WHERE CollectedAmount=0 only when the
--        first is NULL.  → cte_ptp_maxcoll
--
--    STAGE 1  (client-grain, the FALLBACK; SP's first PTP UPDATE)
--      COUNT(1)/MAX(PTPDate) over t_TrxGroupPostingDet correlated to each
--      loan's own MaxCollDate, grouped by ClientID.
--      *** SP BUG, deliberately NOT reproduced *** — the SP joins every trx
--      against every loan row for the client, then groups by ClientID, so a
--      single transaction is counted once per qualifying loan the client
--      holds (double-count on multi-loan clients). We instead evaluate the
--      threshold per (Branch,Account,Client), which is the grain the report
--      actually renders on. See cte_ptp_client.
--
--    STAGE 2a PTP date (loan-grain, OVERWRITES stage 1)
--      MAX(PTPDate) restricted to the loan's LATEST TrxDate and the highest
--      TrxBatchID on that date.  → cte_ptp_date
--
--    STAGE 2b PTP count (loan-grain, OVERWRITES stage 1, DIFFERENT batch rule
--      from 2a) — dedupe to one row PER DISTINCT PTPDate (highest batch per
--      date) at/after MaxCollDate, then COUNT those dates.  → cte_ptp_count
--
--    STAGE 3  null-outs, in order: count = NULL when the final PTP date is
--      NULL; then count = NULL when it is exactly 0. Applied at the SELECT.
--
--    PTP Reason — joined on ClientID + PTPDate ONLY (no branch/account: an SP
--      quirk), ArrearReasonID → DelinquencyReasonID fallback through the
--      DelinquencyReasonID user-code lookup.  → cte_ptp_reason + cte_delinq_desc
--
--  GRAIN: all three are LOAN-grain and join into the (a) LOAN-grain family
--    alongside cte_offline_ft / cte_dsign / cte_netoff — keyed on
--    tl.OurBranchID + tl.AccountID + client, matching the SP's own join.
--    A multi-loan client can legitimately show a different count per loan.
--
--  *** CONFIRM SOURCE: t_TrxGroupPostingDet ***  All PTP CTEs read
--    stg_brnet.t_TrxGroupPostingDet_inc_full. Confirm it is landed. The DPD SP
--    reads columns TrxBranchID / AccountID / ClientID / TrxDate / TrxBatchID /
--    PTPDate / CollectedAmount / ArrearReasonID / DelinquencyReasonID.
-- ============================================================================

create or replace table lakehouse_uat.stg_brnet.disb_test_test
as
WITH

        -- CTE 1: driving t_Loan dedup
        cte_loan AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, AccountID, LoanSeries
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_Loan_inc_full where ApplicationID is not null
            ) t WHERE t.rn = 1
        ),

        -- CTE 1b: first-source account
        cte_loan_src AS (
            SELECT
                tl.*,
                COALESCE(s.src_branch,  tl.OurBranchID) AS eff_branch,
                COALESCE(s.src_account, tl.AccountID)   AS eff_account,
                COALESCE(s.src_series,  tl.LoanSeries)  AS eff_series
            FROM cte_loan tl
            LEFT JOIN LATERAL (
                SELECT OurBranchID AS src_branch,
                       AccountID   AS src_account,
                       LoanSeries  AS src_series
                FROM stg_brnet.f_GetFirstSourceAccount(
                         tl.OurBranchID, tl.AccountID, tl.LoanSeries, tl.LoanTransferDate)
                
            ) s ON TRUE
        ),

        -- CTE 1c: source (pre-transfer) t_Loan ApplicationID backtrack
        cte_source_loan AS (
            SELECT OurBranchID, AccountID, LoanSeries, ApplicationID
            FROM (
                SELECT OurBranchID, AccountID, LoanSeries, ApplicationID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, AccountID, LoanSeries
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_Loan_inc_full
                WHERE ApplicationID    IS NOT NULL
                  AND LoanTransferDate IS NULL
            ) t WHERE t.rn = 1
        ),

        -- CTE 2: t_accountcustomer dedup
        cte_acccust AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, AccountID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_accountcustomer_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 3: t_LoanMonthEndAccrual dedup
        cte_lmea AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, AccountID
                        ORDER BY ProcessDate DESC
                    ) AS rn
                FROM stg_brnet.t_LoanMonthEndAccrual_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 4: t_LoanInstallment dedup
        -- NOTE: one row per ACCOUNT — cannot back the Accrued-interest aggregate.
        --   See cte_li_dedup (CTE 55) for the per-installment grain.
        cte_li AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, AccountID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_LoanInstallment_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 5a: t_LoanTrx one row per Account+Branch
        cte_loantrx_dedup AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY AccountID, OurBranchID
                        ORDER BY TrxDate DESC, TrxBatchID DESC
                    ) AS rn2
                FROM (
                    SELECT *,
                        ROW_NUMBER() OVER (
                            PARTITION BY AccountID, OurBranchID, TrxDate, TrxBatchID
                            ORDER BY TrxDate DESC
                        ) AS rn
                    FROM stg_brnet.t_LoanTrx_inc_full
                ) t WHERE t.rn = 1
            ) t2 WHERE t2.rn2 = 1
        ),

        -- CTE 5b: t_LoanTrx aggregated
        cte_loantrx_agg AS (
            SELECT
                OurBranchID,
                AccountID,
                COALESCE(SUM(CASE
                    WHEN InstComponentTypeID IN ('INT_PAID', 'INT_PPAID')
                    THEN Amount ELSE 0 END), 0)                         AS AdditionalInterest,
                COALESCE(SUM(CASE
                    WHEN InstComponentTypeID IN ('ADVINST_RCD')
                    THEN Amount ELSE 0 END), 0)                         AS Advance,
                COALESCE(SUM(CASE
                    WHEN TrxDate BETWEEN DATE_TRUNC('month', DATE '2026-07-07')
                                     AND LAST_DAY(DATE '2026-07-07')
                     AND InstComponentTypeID IN ('INT_PPAID', 'INT_PAID')
                    THEN Amount ELSE 0 END), 0)                         AS BilledIntAmtForTheMonth,
                COALESCE(SUM(CASE
                    WHEN TrxDate            <= LAST_DAY(DATE '2026-07-07')
                     AND InstComponentTypeID IN ('INT_PPAID', 'INT_PAID')
                    THEN Amount ELSE 0 END), 0)                         AS BilledIntAmtTillDate,
                COALESCE(SUM(CASE
                    WHEN InstComponentTypeID = 'EXCESS_PAID'
                    THEN Amount ELSE 0 END), 0)                         AS ExcessAmount
            FROM stg_brnet.t_LoanTrx_inc_full
            GROUP BY OurBranchID, AccountID
        ),

        -- CTE 6: t_ClientBankTransaction dedup
        -- FIX #1: source switched from t_ to cv_ClientBankTransaction and the
        --   pick made deterministic toward the completed disbursement
        --   fund-transfer row. Now also drives FundTransferMode/Status/StatusTime.
        cte_cbt AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, LoanAccountID, LoanSeries
                        ORDER BY
                            CASE WHEN BatchID IS NOT NULL
                                  AND FundTransferModeID IS NOT NULL THEN 0 ELSE 1 END,
                            CASE WHEN TrxStatusID = 'COM' THEN 0 ELSE 1 END,
                            COALESCE(TrxStatusOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_ClientBankTransaction_inc_full   -- FIX: was t_ClientBankTransaction_inc_full
                WHERE RecordStatusID = 'A'
            ) t WHERE t.rn = 1
        ),

        -- CTE 6b: ExcessAmount override (SP excess update also reads cv_).
        cte_excess_cbt AS (
            SELECT OurBranchID, LoanAccountID, LoanSeries, TrxAmount
            FROM (
                SELECT
                    cbt.OurBranchID,
                    cbt.LoanAccountID,
                    cbt.LoanSeries,
                    cbt.TrxAmount,
                    ROW_NUMBER() OVER (
                        PARTITION BY cbt.OurBranchID, cbt.LoanAccountID, cbt.LoanSeries
                        ORDER BY cbt.CreatedOn DESC
                    ) AS rn
                FROM stg_brnet.cv_ClientBankTransaction_inc_full cbt   -- FIX: was t_ClientBankTransaction_inc_full
                WHERE cbt.RecordStatusID = 'A'
                  AND EXISTS (
                      SELECT 1
                      FROM stg_brnet.t_LoanRefundBalance_inc_full lrb
                      WHERE lrb.OurBranchID  = cbt.OurBranchID
                        AND lrb.AccountID    = cbt.LoanAccountID
                        AND lrb.LoanSeries   = cbt.LoanSeries
                        AND lrb.TrxBatchID   = cbt.TrxBatchID
                        AND lrb.TrxDate      = cbt.TrxDate
                        AND lrb.ExcessTypeID = 'R'
                  )
            ) t WHERE t.rn = 1
        ),

        -- CTE 7: t_RBLBankTrxExtractLog NEFTTransaction
        cte_rbl AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY TrxRefID
                        ORDER BY RequestOn DESC
                    ) AS rn
                FROM stg_brnet.t_RBLBankTrxExtractLog_inc_full
                WHERE RequestTypeID = 'NEFTTransaction'
            ) t WHERE t.rn = 1
        ),

        -- CTE 8: t_CashRemittance dedup
        cte_cashr AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, TrxDate, TrxBatchID
                        ORDER BY CreatedOn DESC
                    ) AS rn
                FROM stg_brnet.t_CashRemittance_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 9: t_WFLoanApplication dedup
        -- THIS PASS: CBEnquiryRefNo, WFAdvStageID, WFAppStatusID (SELECT *) now
        --   consumed for VerificationDate + BRNet Stage/Status. Fan-out risk on
        --   (branch, ApplicationID) carrying multiple ClientIDs now hits those too.
        cte_wfla AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationID, ClientID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_WFLoanApplication_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 10: t_LoanLossProvision dedup
        cte_llp AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, AccountID
                        ORDER BY TrxDate DESC
                    ) AS rn
                FROM stg_brnet.t_LoanLossProvision_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 11: t_client dedup
        -- FIX #2 (filter-after-dedup): ClientTypeID='E' moved INSIDE the window.
        cte_cli AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ClientID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_client_inc_full
                WHERE ClientTypeID = 'E'          -- FIX: moved from outer WHERE
            ) t WHERE t.rn = 1
        ),

        -- CTE 12: t_glosclient
        -- FIX #3 (part A): re-grained to BRNETApplicationID + BRNETClientID.
        -- THIS PASS: GLOSPActivityStatusID added — the CurrentStatus seed.
        cte_tglc AS (
            SELECT OurBranchID, BRNETApplicationID, BRNETClientID, ApplicationFileNo, MemberID,
                   GLOSPActivityStatusID
            FROM (
                SELECT OurBranchID, BRNETApplicationID, BRNETClientID, ApplicationFileNo, MemberID,
                       GLOSPActivityStatusID,   -- ADDED: CurrentStatus seed (SP GLOW base insert)
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, BRNETApplicationID, BRNETClientID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_glosclient_inc_full   --name update form t to cv
            ) t WHERE t.rn = 1
        ),

        -- CTE 13: t_GLOSActivityLog — CPV2 / COMP / 30APR (CrossVerifyDoneBy)
        -- FIX #3 (part B): filter moved INSIDE the window. One of THREE reads of
        --   this table (see cte_gal_grt 'GRTC', cte_gal_current unfiltered).
        cte_gal AS (
            SELECT OurBranchID, ApplicationFileNo, OfficerID
            FROM (
                SELECT OurBranchID, ApplicationFileNo, OfficerID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY COALESCE(StatusOn, StartOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSActivityLog_inc_full  --name updated from cv to t
                WHERE GLOSProcessActivityID = 'CPV2'     -- FIX: moved from outer WHERE
                  AND ActivityStatusID      = 'COMP'
                  AND GLOSProcessStageID    = '30APR'
            ) t WHERE t.rn = 1
        ),

        -- CTE 14: BM hop
        cte_ao_bm AS (
            SELECT ReportingBranchID, OfficerID, ReportingOfficerID
            FROM (
                SELECT ReportingBranchID, OfficerID, ReportingOfficerID,
                    ROW_NUMBER() OVER (
                        PARTITION BY ReportingBranchID, OfficerID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_AccountOfficer_inc_full
                WHERE OfficerTypeID IN ('BM', 'BMS')
                  AND Status = 'A'
            ) t WHERE t.rn = 1
        ),

        -- CTE 15: ASM hop
        cte_ao_asm AS (
            SELECT OfficerID
            FROM (
                SELECT OfficerID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OfficerID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_AccountOfficer_inc_full
                WHERE OfficerTypeID IN ('ASM', 'ARM')
                  AND Status = 'A'
            ) t WHERE t.rn = 1
        ),

        -- CTE 16: generic officer-name resolver (f_GetOfficerName — no type/status filter)
        cte_officer_name AS (
            SELECT OfficerID, Name
            FROM (
                SELECT OfficerID, Name,
                    ROW_NUMBER() OVER (
                        PARTITION BY OfficerID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_AccountOfficer_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 17: CrossVerify officer-name resolver — Status='A' (FIX #3 part C)
        cte_cv_officer_name AS (
            SELECT OfficerID, Name
            FROM (
                SELECT OfficerID, Name,
                    ROW_NUMBER() OVER (
                        PARTITION BY OfficerID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_AccountOfficer_inc_full
                WHERE Status = 'A'
            ) t WHERE t.rn = 1
        ),

        -- CTE 18: t_GroupMember → GroupID (SubGroupID) + CenterID
        -- SP GroupMemberHistory fallback is dead code; deliberately NOT reproduced.
        cte_groupmember AS (
            SELECT OurBranchID, ClientID, GroupID, SubGroupID
            FROM (
                SELECT OurBranchID, ClientID, GroupID, SubGroupID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ClientID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_GroupMember_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 19: CV_GLOSGRTDetail → GRT Date/By/Start/End/GPS at MAX(GRTRefNo)
        cte_grt AS (
            SELECT OurBranchID, ApplicationFileNo, GRTDoneDate, GRTDoneBy,
                   StartTime, EndTime, GPSCoordinate
            FROM (
                SELECT OurBranchID, ApplicationFileNo, GRTDoneDate, GRTDoneBy,
                       StartTime, EndTime, GPSCoordinate,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY GRTRefNo DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSGRTDetail_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 20: cv_GlosClientLoan → Loan Cycle
        -- FIX (determinism): ORDER BY LoanCycleNo DESC (was partition keys only).
        cte_gclloan AS (
            SELECT OurBranchID, ApplicationFileNo, MemberID, LoanCycleNo
            FROM (
                SELECT OurBranchID, ApplicationFileNo, MemberID, LoanCycleNo,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                        ORDER BY LoanCycleNo DESC   -- FIX: was ApplicationFileNo, MemberID DESC (both partition keys)
                    ) AS rn
                FROM stg_brnet.cv_GlosClientLoan_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 21: t_SystemBranchSetting → StateID
        cte_branchsetting AS (
            SELECT OurBranchID, StateID
            FROM (
                SELECT OurBranchID, StateID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_SystemBranchSetting_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 22: t_BankUserCode → StateName  (CASE CHECK: literal 'STATEID')
        cte_state_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (
                        PARTITION BY SubCodeID
                        ORDER BY COALESCE(CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_BankUserCode_inc_full
                WHERE ID = 'STATEID'
            ) t WHERE t.rn = 1
        ),

        -- CTE 23: t_ClientMultipleAddress → VillageID (step 1)
        cte_cli_addr AS (
            SELECT ClientID, PlaceID
            FROM (
                SELECT ClientID, PlaceID,
                    ROW_NUMBER() OVER (
                        PARTITION BY ClientID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_ClientMultipleAddress_inc_full
                WHERE IsMailingAddress = True
            ) t WHERE t.rn = 1
        ),

        -- CTE 24: t_Group → VillageID (step 2) + GroupName (via CenterID)
        cte_group AS (
            SELECT OurBranchID, GroupID, VillageID, GroupName AS Name
            FROM (
                SELECT OurBranchID, GroupID, VillageID, GroupName,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, GroupID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_Group_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 25: cv_GlosApplication → VillageID (steps 3,4) + OriginationWorkflowID
        cte_glosapp AS (
            SELECT OurBranchID, ApplicationFileNo, PlaceID, VillageID, GLOSProcessTypeID
            FROM (
                SELECT OurBranchID, ApplicationFileNo, PlaceID, VillageID, GLOSProcessTypeID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GlosApplication_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 26: cv_GLOSActivityLog — 'GRTC' → GRT Status/Started/Ended (TAT).
        -- NO ActivityStatusID/StageID predicate (SP filters on activity ID alone).
        cte_gal_grt AS (
            SELECT OurBranchID, ApplicationFileNo, ActivityStatusID, StartOn, StatusOn
            FROM (
                SELECT OurBranchID, ApplicationFileNo, ActivityStatusID, StartOn, StatusOn,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY COALESCE(StatusOn, StartOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSActivityLog_inc_full
                WHERE GLOSProcessActivityID = 'GRTC'
            ) t WHERE t.rn = 1
        ),

        -- CTE 27: t_SystemCodeDetail → ActivityStatusID description
        -- FAN-OUT FIX: ROW_NUMBER restored (config grained by language).
        -- Consumed TWICE: `gstat` (GRTStatus) and `cstat` (CurrentStatus).
        cte_activity_status_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (
                        PARTITION BY SubCodeID
                        ORDER BY SubCodeID
                    ) AS rn
                FROM stg_brnet.t_SystemCodeDetail_inc_full
                WHERE ID = 'ActivityStatusID'
                --  AND LanguageID = 'en'   -- add if the column exists
            ) t WHERE t.rn = 1
        ),

        -- CTE 28: t_SystemCodeDetail → TACStatusID description (Fund Transfer Status)
        cte_tac_status_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (
                        PARTITION BY SubCodeID
                        ORDER BY SubCodeID
                    ) AS rn
                FROM stg_brnet.t_SystemCodeDetail_inc_full
                WHERE ID = 'TACStatusID'
            ) t WHERE t.rn = 1
        ),

        -- CTE 29: cv_ClientBankTransaction → offline-transfer marker (existence-only)
        cte_offline_ft AS (
            SELECT DISTINCT OurBranchID, LoanAccountID, LoanSeries
            FROM stg_brnet.cv_ClientBankTransaction_inc_full
            WHERE OffLineBatchID IS NOT NULL
        ),

        -- CTE 30: t_RBLBankTrxExtractLog — ResponseStatus → UTRNo (step 1, XML)
        cte_utr_rbl AS (
            SELECT TrxRefID, txn_utr
            FROM (
                SELECT
                    TrxRefID,
                    xpath_string(ResponseXML, '/StatusCheck_response/data/txn_utr') AS txn_utr,
                    ROW_NUMBER() OVER (
                        PARTITION BY TrxRefID
                        ORDER BY RequestOn DESC
                    ) AS rn
                FROM stg_brnet.t_RBLBankTrxExtractLog_inc_full
                WHERE RequestTypeID = 'ResponseStatus'
                  AND ResponseXML IS NOT NULL
            ) t WHERE t.rn = 1
        ),

        -- CTE 31: cv_ClientBankTransaction → UTRNo (step 2 fallback)
        -- NOTE key: branch + CLIENT + account, NO LoanSeries (SP quirk).
        cte_cbt_utr AS (
            SELECT OurBranchID, ClientID, LoanAccountID, UTRNo
            FROM (
                SELECT OurBranchID, ClientID, LoanAccountID, UTRNo,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ClientID, LoanAccountID
                        ORDER BY COALESCE(TrxStatusOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_ClientBankTransaction_inc_full
                WHERE RecordStatusID = 'A'
                  AND TrxStatusID    = 'COM'
            ) t WHERE t.rn = 1
        ),

        -- CTE 32: v_CBStaggingData → Verification date
        cte_cbstag AS (
            SELECT CBEnquiryRefNo, EnquiryStatusOn
            FROM (
                SELECT CBEnquiryRefNo, EnquiryStatusOn,
                    ROW_NUMBER() OVER (
                        PARTITION BY CBEnquiryRefNo
                        ORDER BY COALESCE(CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.v_CBStaggingData_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 33: cv_GLOSSendBackChkLstData → Create Flag (MIN is dup-safe)
        cte_sendback AS (
            SELECT
                OurBranchID,
                ApplicationFileNo,
                MemberID,
                MIN(CreatedOn) AS ReworkStartedOn
            FROM stg_brnet.cv_GLOSSendBackChkLstData_inc_full
            WHERE COALESCE(CAST(IsNotOK AS INT), 0) = 1
              AND ActivityID = 'CPCV'
            GROUP BY OurBranchID, ApplicationFileNo, MemberID
        ),

        -- CTE 34: t_ChargeDue (+ t_Charge, t_ChargeClass) → GST + Stamp Duty
        -- FIX: IsChargeIncludeTax lives on t_ChargeClass (chc), carried through.
        -- ReversedDate verified on cd. *** CONFIRM KEY *** (branch,app,charge,class).
        cte_chargedue_agg AS (
            SELECT
                cd.OurBranchID,
                cd.ApplicationID,
                SUM(CASE WHEN ch.ChargeClassID = 'PF'
                         THEN COALESCE(cd.TaxAmount, 0) ELSE 0 END)              AS ProcessFeeTax,
                SUM(CASE WHEN ch.ChargeClassID = 'SC' AND cd.ChargeID = 'STAMPDUTY'
                         THEN CASE WHEN COALESCE(CAST(chc.IsChargeIncludeTax AS INT), 0) = 1   -- FIX: was cd.IsChargeIncludeTax
                                   THEN COALESCE(cd.ChargeAmount, 0) - COALESCE(cd.TaxAmount, 0)
                                   ELSE COALESCE(cd.ChargeAmount, 0)
                              END
                         ELSE 0 END)                                             AS StampFee
            FROM (
                SELECT * FROM (
                    SELECT *,
                        ROW_NUMBER() OVER (
                            PARTITION BY OurBranchID, ApplicationID, ChargeID, ClassID
                            ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                        ) AS rn
                    FROM stg_brnet.t_ChargeDue_inc_full
                ) d WHERE d.rn = 1
            ) cd
            left JOIN (
                SELECT * FROM (
                    SELECT ChargeID, ChargeClassID,
                        ROW_NUMBER() OVER (
                            PARTITION BY ChargeID
                            ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                        ) AS rn
                    FROM stg_brnet.t_Charge_inc_full
                ) c WHERE c.rn = 1
            ) ch
                ON ch.ChargeID = cd.ChargeID
            left JOIN (
                SELECT * FROM (
                    SELECT ChargeID, ClassID, IsChargeIncludeTax,   -- FIX: carry the flag (lives on t_ChargeClass)
                        ROW_NUMBER() OVER (
                            PARTITION BY ChargeID, ClassID
                            ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                        ) AS rn
                    FROM stg_brnet.t_ChargeClass_inc_full
                    WHERE CurrencyID = 'INR'
                ) cc WHERE cc.rn = 1
            ) chc
                ON  chc.ChargeID = cd.ChargeID
                AND chc.ClassID  = cd.ClassID
            WHERE cd.ReversedDate IS NULL                       -- verified on cd
              AND COALESCE(cd.ExemptedBy, '') <> 'SYS'
            GROUP BY cd.OurBranchID, cd.ApplicationID
        ),

        -- CTE 35: CV_GLOSMemberRuleLog — VOTVER/VOTVEC → ID verification (base)
        cte_idverify AS (
            SELECT OurBranchID, ApplicationFileNo, MemberID, GLOSRuleStatusID, Remarks
            FROM (
                SELECT OurBranchID, ApplicationFileNo, MemberID, GLOSRuleStatusID, Remarks,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                        ORDER BY GLOSProcessStageID DESC,
                                 COALESCE(StatusOn) DESC   -- added tiebreaker
                    ) AS rn
                FROM stg_brnet.cv_GLOSMemberRuleLog_inc_full
                WHERE RuleID IN ('VOTVER', 'VOTVEC')
            ) t WHERE t.rn = 1
        ),

        -- CTE 36: CV_GLOSMemberRuleLog — override markers
        cte_idverify_ovr AS (
            SELECT
                OurBranchID,
                ApplicationFileNo,
                MemberID,
                MAX(CASE WHEN COALESCE(CAST(IsMandatory  AS INT), 0) = 1
                          AND COALESCE(CAST(IsOverridden AS INT), 0) = 1
                         THEN 1 ELSE 0 END) AS HasMandatoryOverridden,
                MAX(CASE WHEN COALESCE(CAST(IsMandatory  AS INT), 0) = 1
                          AND COALESCE(CAST(IsOverridden AS INT), 0) = 0
                         THEN 1 ELSE 0 END) AS HasMandatoryNotOverridden
            FROM stg_brnet.cv_GLOSMemberRuleLog_inc_full
            WHERE RuleID IN ('VOTVER', 'VOTVEC')
            GROUP BY OurBranchID, ApplicationFileNo, MemberID
        ),

        -- CTE 37: t_GroupMemberSchemeTransfer → Is Center Transferred
        -- *** OUTSTANDING FAN-OUT: ROW_NUMBER commented out, no DISTINCT ***
        cte_scheme_transfer AS (
            SELECT OurBranchID, LoanAccountID, LoanSeries, NewBranchID
            FROM (
                SELECT OurBranchID, LoanAccountID, LoanSeries, NewBranchID
                FROM stg_brnet.t_GroupMemberSchemeTransfer_inc_full
            ) t
        ),

        -- CTE 38: t_WFDSignWorkflowLog → Is DG Signed
        -- DEVIATION: COUNT(DISTINCT DSignStageID) (SP uses COUNT(1)).
        cte_dsign AS (
            SELECT
                OurBranchID,
                AccountID,
                LoanSeries,
                COUNT(DISTINCT DSignStageID) AS SignCount   -- DEVIATION: SP uses COUNT(1)
            FROM stg_brnet.t_WFDSignWorkflowLog_inc_full
            WHERE DSignStageStatusID = 'P'
            GROUP BY OurBranchID, AccountID, LoanSeries
        ),

        -- CTE 39: t_NACHExtractionDet → Is Enach Done (ILOS-scoped source)
        cte_nach_enach AS (
            SELECT
                OurBranchID,
                ApplicationFileNo,
                MemberID,
                MAX(CASE WHEN StatusID = 'COM' AND UMRNNo IS NOT NULL
                         THEN 1 ELSE 0 END) AS IsEnachDone
            FROM stg_brnet.t_NACHExtractionDet_inc_full
            WHERE SourceTypeID = 'ILOS'      -- *** ILOS-ONLY: reads 'NO' on GLOW rows ***
            GROUP BY OurBranchID, ApplicationFileNo, MemberID
        ),

        -- CTE 40: t_LoanNetOff → Is Net Off / Net Off Amount
        -- *** CONFIRM KEY *** dedup grain (branch, account, series[, ref]).
        cte_netoff AS (
            SELECT
                OurBranchID,
                AccountID,
                LoanSeries,
                SUM(COALESCE(TotalNetOffAmount, 0)) AS NetOffAmt
            FROM (
                SELECT * FROM (
                    SELECT *,
                        ROW_NUMBER() OVER (
                            PARTITION BY OurBranchID, AccountID, LoanSeries
                            ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                        ) AS rn
                    FROM stg_brnet.t_LoanNetOff_inc_full
                ) d WHERE d.rn = 1
            ) n
            GROUP BY OurBranchID, AccountID, LoanSeries
        ),

        -- CTE 41: t_EStampDataExtraction → IsEstampComp (existence-only)
        cte_estamp AS (
            SELECT DISTINCT OurBranchID, ApplicationID
            FROM stg_brnet.t_EStampDataExtraction_inc_full
            WHERE RecordStatusID = 'A'
              AND StatusID       = 'COM'
        ),

        -- CTE 42: t_userfielddata → KLIAvailable  (CASE CHECK: 'KLIAvailable')
        cte_userfield_kli AS (
            SELECT OurBranchID, RelevantID, FieldValue
            FROM (
                SELECT OurBranchID, RelevantID, FieldValue,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, RelevantID
                        ORDER BY COALESCE(CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_userfielddata_inc_full
                WHERE FieldName    = 'KLIAvailable'
                  AND ModuleTypeID = 'L'
            ) t WHERE t.rn = 1
        ),

        -- CTE 43: cv_GLOSClientRelation → No of Relations / DigiLocker Sourced
        -- *** CONFIRM KEY *** (branch, file, member, RelationRefNo).
        cte_glosrelation AS (
            SELECT
                OurBranchID,
                ApplicationFileNo,
                MemberID,
                COUNT(1)                                                    AS NoOfRelations,
                SUM(CASE WHEN COALESCE(CAST(IsDKYC AS INT), 0) = 1
                         THEN 1 ELSE 0 END)                                 AS NoOfDigiLockerSourced
            FROM (
                SELECT * FROM (
                    SELECT *,
                        ROW_NUMBER() OVER (
                            PARTITION BY OurBranchID, ApplicationFileNo, MemberID, RelationRefNo
                            ORDER BY OurBranchID, ApplicationFileNo, MemberID DESC
                        ) AS rn
                    FROM stg_brnet.cv_GLOSClientRelation_inc_full
                ) d WHERE d.rn = 1
            ) r
            GROUP BY OurBranchID, ApplicationFileNo, MemberID
        ),

        -- CTE 44: t_GLOSProcessType → Origination Workflow (description)
        cte_processtype AS (
            SELECT GLOSProcessTypeID, Description
            FROM (
                SELECT GLOSProcessTypeID, Description,
                    ROW_NUMBER() OVER (
                        PARTITION BY GLOSProcessTypeID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_GLOSProcessType_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 45: cv_GLOSActivityLog — LATEST activity → CurrentStatus (3rd read).
        -- Keyed on branch + ApplicationFileNo only (NO MemberID — SP grain).
        cte_gal_current AS (
            SELECT OurBranchID, ApplicationFileNo, ActivityStatusID
            FROM (
                SELECT OurBranchID, ApplicationFileNo, ActivityStatusID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY GLOSProcessStageID DESC,
                                 ActivityOrderNo    DESC,
                                 COALESCE(StatusOn, StartOn) DESC   -- added tiebreaker
                    ) AS rn
                FROM stg_brnet.cv_GLOSActivityLog_inc_full
                WHERE ActivityStatusID IS NOT NULL   -- inside the window, per SP
            ) t WHERE t.rn = 1
        ),

        -- CTE 46: t_SystemCodeDetail → WFAdvStageID description (BRNet Stage)
        cte_wfadvstage_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (
                        PARTITION BY SubCodeID
                        ORDER BY SubCodeID
                    ) AS rn
                FROM stg_brnet.t_SystemCodeDetail_inc_full
                WHERE ID = 'WFAdvStageID'
            ) t WHERE t.rn = 1
        ),

        -- CTE 47: t_SystemCodeDetail → WFAppStatusID description (BRNet Status)
        -- *** ASYMMETRY: WFAdvStageID vs WFAppStatusID — Adv vs App, not a typo ***
        cte_wfappstatus_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (
                        PARTITION BY SubCodeID
                        ORDER BY SubCodeID
                    ) AS rn
                FROM stg_brnet.t_SystemCodeDetail_inc_full
                WHERE ID = 'WFAppStatusID'
            ) t WHERE t.rn = 1
        ),

        -- ####################################################################
        -- ####     NEW CTEs 48-53  —  PTP block (DPD / collections SP)     ####
        -- ####  Number of times PTP date has been entered | PTP date       ####
        -- ####  | PTP Reason                                               ####
        -- ####                                                             ####
        -- ####  Source: stg_brnet.t_TrxGroupPostingDet_inc_full            ####
        -- ####    *** CONFIRM SOURCE *** confirm this table + columns are   ####
        -- ####    landed: TrxBranchID, AccountID, ClientID, TrxDate,        ####
        -- ####    TrxBatchID, PTPDate, CollectedAmount, ArrearReasonID,     ####
        -- ####    DelinquencyReasonID.                                      ####
        -- ####  Grain: (TrxBranchID, AccountID, ClientID) — the SP's own    ####
        -- ####    PTP key. Joins into the (a) LOAN-grain family at the      ####
        -- ####    SELECT (tl.OurBranchID + tl.AccountID + client).          ####
        -- ####################################################################

        -- ================================================================
        -- CTE 48: MaxCollDate — a THRESHOLD, not an output.
        -- SP stage 0: MAX(TrxDate) WHERE CollectedAmount>0 per key; falls back
        --   to MAX(TrxDate) WHERE CollectedAmount=0 only when the first is NULL.
        --   Both computed in one pass and COALESCEd in that precedence order.
        -- Every PTP CTE below is gated on TrxDate >= this date.
        -- ================================================================
        cte_ptp_maxcoll AS (
            SELECT TrxBranchID, AccountID, ClientID,
                   COALESCE(MaxCollPos, MaxCollZero) AS MaxCollDate
            FROM (
                SELECT TrxBranchID, AccountID, ClientID,
                       MAX(CASE WHEN COALESCE(CollectedAmount, 0) > 0 THEN TrxDate END) AS MaxCollPos,
                       MAX(CASE WHEN COALESCE(CollectedAmount, 0) = 0 THEN TrxDate END) AS MaxCollZero
                FROM stg_brnet.t_TrxGroupPostingDet_inc_full
                GROUP BY TrxBranchID, AccountID, ClientID
            ) t
        ),

        -- ================================================================
        -- CTE 49: PTP fallback (SP stage 1) — loose COUNT / MAX(PTPDate) at
        --   (branch, account, client), gated on TrxDate >= MaxCollDate and
        --   CollectedAmount >= 0.
        --
        -- *** SP BUG NOT REPRODUCED ***  The SP's stage-1 UPDATE cross-joins
        --   every transaction against every loan row for the client and groups
        --   by ClientID, double-counting a transaction once per qualifying loan
        --   a multi-loan client holds. Evaluated here at (branch, account,
        --   client) — the grain the report actually renders on — so a shared
        --   transaction is not multiplied across the client's loans.
        --
        -- Supersession: this is the FALLBACK only. cte_ptp_date (50) and
        --   cte_ptp_count (51) OVERWRITE it wherever they match (SP stages 2a/2b
        --   run after stage 1); the SELECT COALESCEs primary over fallback.
        --   NOTE the count semantics differ between the two by design — stage 1
        --   counts raw rows, stage 2b counts distinct PTP dates (see CTE 51).
        -- ================================================================
        cte_ptp_client AS (
            SELECT p.TrxBranchID, p.AccountID, p.ClientID,
                   COUNT(1)       AS PTPCountFallback,
                   MAX(p.PTPDate) AS PTPDateFallback
            FROM stg_brnet.t_TrxGroupPostingDet_inc_full p
            JOIN cte_ptp_maxcoll m
              ON  m.TrxBranchID = p.TrxBranchID
              AND m.AccountID   = p.AccountID
              AND m.ClientID    = p.ClientID
            WHERE p.TrxDate >= m.MaxCollDate
              AND COALESCE(p.CollectedAmount, 0) >= 0
            GROUP BY p.TrxBranchID, p.AccountID, p.ClientID
        ),

        -- ================================================================
        -- CTE 50: PTP date (SP stage 2a) — MAX(PTPDate) restricted to the
        --   loan's LATEST TrxDate (>= MaxCollDate), and the HIGHEST TrxBatchID
        --   on that date. Three layers: attach max_trxdate → filter to it →
        --   attach max_batch on that date → filter to it → MAX(PTPDate).
        -- ================================================================
        cte_ptp_date AS (
            SELECT TrxBranchID, AccountID, ClientID, MAX(PTPDate) AS PTPDate
            FROM (
                SELECT TrxBranchID, AccountID, ClientID, PTPDate, TrxBatchID,
                       MAX(TrxBatchID) OVER (
                           PARTITION BY TrxBranchID, AccountID, ClientID
                       ) AS max_batch
                FROM (
                    SELECT p.TrxBranchID, p.AccountID, p.ClientID, p.PTPDate,
                           p.TrxDate, p.TrxBatchID,
                           MAX(p.TrxDate) OVER (
                               PARTITION BY p.TrxBranchID, p.AccountID, p.ClientID
                           ) AS max_trxdate
                    FROM stg_brnet.t_TrxGroupPostingDet_inc_full p
                    JOIN cte_ptp_maxcoll m
                      ON  m.TrxBranchID = p.TrxBranchID
                      AND m.AccountID   = p.AccountID
                      AND m.ClientID    = p.ClientID
                    WHERE p.TrxDate >= m.MaxCollDate
                ) a
                WHERE a.TrxDate = a.max_trxdate
            ) b
            WHERE b.TrxBatchID = b.max_batch
            GROUP BY TrxBranchID, AccountID, ClientID
        ),

        -- ================================================================
        -- CTE 51: PTP count (SP stage 2b) — a DIFFERENT batch rule from 2a.
        --   Dedupe to ONE row PER DISTINCT PTPDate (its latest TrxDate, then
        --   highest TrxBatchID), gated on TrxDate >= MaxCollDate and
        --   CollectedAmount >= 0, then COUNT those dates.
        --   => count of DISTINCT qualifying PTP dates, not of raw rows.
        -- ================================================================
        cte_ptp_count AS (
            SELECT x.TrxBranchID, x.AccountID, x.ClientID, COUNT(1) AS PTPCount
            FROM (
                SELECT p.TrxBranchID, p.AccountID, p.ClientID, p.PTPDate,
                       ROW_NUMBER() OVER (
                           PARTITION BY p.TrxBranchID, p.AccountID, p.ClientID, p.PTPDate
                           ORDER BY p.TrxDate DESC, p.TrxBatchID DESC
                       ) AS rn
                FROM stg_brnet.t_TrxGroupPostingDet_inc_full p
                JOIN cte_ptp_maxcoll m
                  ON  m.TrxBranchID = p.TrxBranchID
                  AND m.AccountID   = p.AccountID
                  AND m.ClientID    = p.ClientID
                WHERE p.TrxDate >= m.MaxCollDate
                  AND COALESCE(p.CollectedAmount, 0) >= 0
                  AND p.PTPDate IS NOT NULL
            ) x
            WHERE x.rn = 1
            GROUP BY x.TrxBranchID, x.AccountID, x.ClientID
        ),

        -- ================================================================
        -- CTE 52: PTP Reason source — per (ClientID, PTPDate), the reason codes.
        -- SP joins reason on ClientID + PTPDate ONLY (no branch/account — a
        --   genuine SP quirk; a client on two loans sharing a PTPDate resolves
        --   the same reason on both). Deduped to one row per (ClientID, PTPDate)
        --   deterministically (latest TrxDate, then batch) — the SP's UPDATE
        --   picked arbitrarily on ties.
        -- Carries BOTH ArrearReasonID and DelinquencyReasonID; the SELECT
        --   resolves ISNULL(desc(Arrear), desc(Delinquency)) through CTE 53.
        -- ================================================================
        cte_ptp_reason AS (
            SELECT ClientID, PTPDate, ArrearReasonID, DelinquencyReasonID
            FROM (
                SELECT ClientID, PTPDate, ArrearReasonID, DelinquencyReasonID,
                       ROW_NUMBER() OVER (
                           PARTITION BY ClientID, PTPDate
                           ORDER BY TrxDate DESC, TrxBatchID DESC
                       ) AS rn
                FROM stg_brnet.t_TrxGroupPostingDet_inc_full
                WHERE PTPDate IS NOT NULL
            ) t WHERE t.rn = 1
        ),

        -- ================================================================
        -- CTE 53: DelinquencyReasonID description (fn_GetUserCodeDesc family).
        -- SP: dbo.fn_GetUserCodeDesc('DelinquencyReasonID', <code>) — user-code
        --   family, resolved here from t_BankUserCode (same table as StateName,
        --   CTE 22). *** CONFIRM SOURCE *** if DelinquencyReasonID is a SYSTEM
        --   code in your lake, point this at t_SystemCodeDetail instead.
        -- Both ArrearReasonID and DelinquencyReasonID resolve through this SAME
        --   code family, matching the SP.
        -- ================================================================
        cte_delinq_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (
                        PARTITION BY SubCodeID
                        ORDER BY COALESCE(CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_BankUserCode_inc_full
                WHERE ID = 'DelinquencyReasonID'
                --  AND BankID = '<BANK_ID>'
            ) t WHERE t.rn = 1
        ),

        -- ####################################################################
        -- ####   NEW CTEs 54-59  —  Accrued interest  (GLOSMemberTracker SP)
        -- ####   Fills the existing CAST(NULL) AccruedInterest placeholder.
        -- ####
        -- ####   SP final SELECT:
        -- ####     ROUND(ISNULL(IntDue,0) + ISNULL(BrokenperiodInterest,0), 2)
        -- ####
        -- ####   Chain (SP UPDATE order — later steps depend on earlier):
        -- ####     0  DeathDate            ← t_ClientDemiseDetail (ClientID only)
        -- ####     1  IntDue / Bef / Nex / InstallmentStDate  ← t_LoanInstallment agg
        -- ####     2  Interest             ← installment AT NexInstallmentDate
        -- ####     3  DailyAccredAmt       ← Interest / day-span
        -- ####     4  BrokenperiodInterest ← DailyAccredAmt × (days+1), clamped >= 0
        -- ####
        -- ####   *** @ToDate ANCHOR *** hardcoded DATE '2026-07-07' to match the
        -- ####     existing cte_loantrx_agg literal. Keep the two in sync (or
        -- ####     lift both into one parameter).
        -- ####
        -- ####   *** DATEDIFF ARG ORDER *** T-SQL DATEDIFF(DD, start, end)
        -- ####     inverts to Spark datediff(end, start). Reversed below.
        -- ####
        -- ####   Keyed on tl.OurBranchID/AccountID/LoanSeries (CURRENT branch),
        -- ####     matching the SP's installment join — deliberately NOT eff_*,
        -- ####     unlike lmea / lt_agg / llp in this query.
        -- ####################################################################

        -- ================================================================
        -- CTE 54: DeathDate per client.
        -- SP joins t_ClientDemiseDetail on ClientID ALONE, so relation-level
        --   demise rows (RelationID / RelationRefNo) also match and the UPDATE
        --   picked arbitrarily. MIN() is dup-safe and deterministic, and the
        --   earliest date is the conservative choice for the
        --   DeathDate < InstallmentStDate branch below.
        --   To restrict to the borrower's OWN demise, add a RelationID IS NULL
        --   predicate — that is a semantic change from the SP.
        -- ================================================================
        cte_demise AS (
            SELECT ClientID, MIN(DeathDate) AS DeathDate
            FROM stg_brnet.t_ClientDemiseDetail_inc_full
            WHERE DeathDate IS NOT NULL
            GROUP BY ClientID
        ),

        -- ================================================================
        -- CTE 55: t_LoanInstallment deduped to ONE ROW PER INSTALLMENT.
        --   cte_li (CTE 4) collapses to one row per ACCOUNT and cannot be used
        --   for an aggregate. *** CONFIRM KEY *** InstallmentNo assumed as the
        --   per-installment identifier; if absent, partition on
        --   InstallmentDueDate instead (loses genuine same-date installments).
        -- ================================================================
        cte_li_dedup AS (
            SELECT OurBranchID, AccountID, LoanSeries, InstallmentNo,
                   InstallmentDueDate, InterestDue
            FROM (
                SELECT OurBranchID, AccountID, LoanSeries, InstallmentNo,
                       InstallmentDueDate, InterestDue,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, AccountID, LoanSeries, InstallmentNo
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_LoanInstallment_inc_full
            ) t WHERE t.rn = 1
        ),

        -- ================================================================
        -- CTE 56: loan → ClientID, so the installment aggregate can reach
        --   DeathDate. Mirrors the final SELECT's
        --   COALESCE(acccust.ClientID, acccust_src.ClientID).
        -- ================================================================
        cte_loan_client AS (
            SELECT tl.OurBranchID, tl.AccountID, tl.LoanSeries,
                   COALESCE(ac.ClientID, ac_src.ClientID) AS ClientID
            FROM cte_loan_src tl
            LEFT JOIN cte_acccust ac
                   ON ac.OurBranchID     = tl.OurBranchID
                  AND ac.AccountID       = tl.AccountID
            LEFT JOIN cte_acccust ac_src
                   ON ac_src.OurBranchID = tl.eff_branch
                  AND ac_src.AccountID   = tl.eff_account
        ),

        -- ================================================================
        -- CTE 57: installment aggregate (SP's LoanInstallment derived table).
        --   left JOIN to cte_loan_client reproduces the SP's left JOIN #Details
        --   — restricts to driving loans instead of aggregating the whole table.
        --   Bef/Nex pivot on ISNULL(DeathDate, @ToDate), per the SP.
        -- ================================================================
        cte_li_agg AS (
            SELECT
                li.OurBranchID,
                li.AccountID,
                li.LoanSeries,
                SUM(CASE WHEN li.InstallmentDueDate <= DATE '2026-07-07'
                         THEN COALESCE(li.InterestDue, 0) ELSE 0 END)   AS IntDue,
                MAX(CASE WHEN li.InstallmentDueDate <= COALESCE(dm.DeathDate, DATE '2026-07-07')
                         THEN li.InstallmentDueDate END)                AS BefInstallmentDate,
                MIN(CASE WHEN li.InstallmentDueDate >  COALESCE(dm.DeathDate, DATE '2026-07-07')
                         THEN li.InstallmentDueDate END)                AS NexInstallmentDate,
                MIN(li.InstallmentDueDate)                              AS InstallmentStDate
            FROM cte_li_dedup li
            left JOIN cte_loan_client lc
                   ON lc.OurBranchID = li.OurBranchID
                  AND lc.AccountID   = li.AccountID
                  AND lc.LoanSeries  = li.LoanSeries
            LEFT JOIN cte_demise dm
                   ON dm.ClientID    = lc.ClientID
            GROUP BY li.OurBranchID, li.AccountID, li.LoanSeries
        ),

        -- ================================================================
        -- CTE 58: Interest = InterestDue of the installment AT NexInstallmentDate.
        --   SP's left-JOIN UPDATE could match several rows on duplicate due
        --   dates and picked arbitrarily; MAX() is dup-safe.
        -- ================================================================
        cte_li_next_int AS (
            SELECT a.OurBranchID, a.AccountID, a.LoanSeries,
                   MAX(li.InterestDue) AS Interest
            FROM cte_li_agg a
            left JOIN cte_li_dedup li
                   ON li.OurBranchID        = a.OurBranchID
                  AND li.AccountID          = a.AccountID
                  AND li.LoanSeries         = a.LoanSeries
                  AND li.InstallmentDueDate = a.NexInstallmentDate
            GROUP BY a.OurBranchID, a.AccountID, a.LoanSeries
        ),

        -- ================================================================
        -- CTE 59: DailyAccredAmt → BrokenperiodInterest → Accrued interest.
        --   GREATEST(COALESCE(bpi,0), 0) reproduces BOTH SP steps at once: the
        --   "SET BrokenperiodInterest = 0 WHERE < 0" UPDATE and the outer
        --   ISNULL(...,0) in the final SELECT.
        --   NULLIF added to the DEATH branch too — the SP omits it there and
        --   would divide by zero when DisbursedDate = InstallmentStDate.
        -- ================================================================
        cte_accrued AS (
            SELECT
                x.OurBranchID,
                x.AccountID,
                x.LoanSeries,
                CAST(ROUND(
                    COALESCE(x.IntDue, 0)
                  + GREATEST(COALESCE(
                        CASE
                            WHEN x.DeathDate < x.InstallmentStDate
                                THEN x.DailyAccredAmt
                                     * (datediff(x.DeathDate, x.DisbursedDate) + 1)
                            WHEN x.BefInstallmentDate < DATE '2026-07-07'
                                THEN x.DailyAccredAmt
                                     * (datediff(DATE '2026-07-07', x.BefInstallmentDate) + 1)
                            ELSE 0
                        END, 0), 0)
                , 2) AS DECIMAL(19,4))                                  AS AccruedInterest
            FROM (
                SELECT
                    a.OurBranchID,
                    a.AccountID,
                    a.LoanSeries,
                    a.IntDue,
                    a.BefInstallmentDate,
                    a.NexInstallmentDate,
                    a.InstallmentStDate,
                    dm.DeathDate,
                    tl.FirstDisbursementDate                            AS DisbursedDate,
                    CASE
                        WHEN dm.DeathDate < a.InstallmentStDate
                            THEN COALESCE(ni.Interest, 0)
                                 / NULLIF(datediff(a.InstallmentStDate, tl.FirstDisbursementDate), 0)
                        ELSE COALESCE(ni.Interest, 0)
                             / NULLIF(datediff(a.NexInstallmentDate, a.BefInstallmentDate), 0)
                    END                                                 AS DailyAccredAmt
                FROM cte_li_agg a
                left JOIN cte_loan_src tl
                       ON tl.OurBranchID = a.OurBranchID
                      AND tl.AccountID   = a.AccountID
                      AND tl.LoanSeries  = a.LoanSeries
                LEFT JOIN cte_loan_client lc
                       ON lc.OurBranchID = a.OurBranchID
                      AND lc.AccountID   = a.AccountID
                      AND lc.LoanSeries  = a.LoanSeries
                LEFT JOIN cte_demise dm
                       ON dm.ClientID    = lc.ClientID
                LEFT JOIN cte_li_next_int ni
                       ON ni.OurBranchID = a.OurBranchID
                      AND ni.AccountID   = a.AccountID
                      AND ni.LoanSeries  = a.LoanSeries
            ) x
        )

        -- ================================================================
        -- CTE 64: Online Fund Transfer Log — Initiation (Stage 'FI')
        -- ================================================================
        cte_oftl_init AS (
            SELECT * FROM (
                SELECT
                    OurBranchID,
                    TrxRowID,
                    PassedBy AS PaymentInitiatedBy,
                    PassedOn AS PaymentInitiatedOn,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, TrxRowID
                        ORDER BY COALESCE(PassedOn, ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_OnLineFundTransferLog_inc_full
                WHERE FTStageID = 'FI'
            ) t WHERE t.rn = 1
        ),

        -- ================================================================
        -- CTE 65: Online Fund Transfer Log — Approval (Stage 'FA')
        -- ================================================================
        cte_oftl_app AS (
            SELECT * FROM (
                SELECT
                    OurBranchID,
                    TrxRowID,
                    PassedBy AS PaymentApprovedBy,
                    PassedOn AS PaymentApprovedOn,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, TrxRowID
                        ORDER BY COALESCE(PassedOn, ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_OnLineFundTransferLog_inc_full
                WHERE FTStageID = 'FA'
            ) t WHERE t.rn = 1
        ),

        -- ================================================================
        -- CTE 66: WFLoanBooking — Loan Booked By & On
        -- ================================================================
        cte_wfloanbooking AS (
            SELECT * FROM (
                SELECT
                    OurBranchID,
                    ApplicationID,
                    CreatedBy AS LoanBookedBy,
                    BookedDate AS LoanBookedOn,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationID
                        ORDER BY COALESCE(BookedDate, ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_WFLoanBooking_inc_full
            ) t WHERE t.rn = 1
        ),

        -- ================================================================
        -- CTE 67: Benecheck / BACV Historical Remarks (ordered by SerialID)
        -- ================================================================
        cte_benecheck_all_remarks AS (
            SELECT
                OurBranchID,
                ApplicationFileNo,
                MemberID,
                concat_ws(',', collect_list(trim(PreviousBACVRemarks))) AS PreviousBenecheckRemarks
            FROM (
                SELECT
                    OurBranchID,
                    ApplicationFileNo,
                    MemberID,
                    PreviousBACVRemarks
                FROM stg_brnet.t_GLOSClientBankAccount_inc_full
                WHERE AccountTypeID = 'SB'
                  AND PreviousBACVRemarks IS NOT NULL
                  AND trim(PreviousBACVRemarks) <> ''
                ORDER BY OurBranchID, ApplicationFileNo, MemberID, SerialID
            )
            GROUP BY OurBranchID, ApplicationFileNo, MemberID
        ),

        -- ================================================================
        -- CTE 68: GLOSClientBankAccount — Latest ModifiedBy & Status
        -- ================================================================
        cte_client_bank_acc_latest AS (
            SELECT * FROM (
                SELECT
                    OurBranchID,
                    ApplicationFileNo,
                    MemberID,
                    ModifiedBy,
                    ModifiedOn,
                    BACVRemarks,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                        ORDER BY SerialID DESC, COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSClientBankAccount_inc_full
                WHERE AccountTypeID = 'SB'
            ) t WHERE t.rn = 1
        ),

        -- ================================================================
        -- CTE 69: CPC Query & Sendback Date Aggregation (Activity 'CPCV')
        -- ================================================================
        cte_cpc_query_max_dates AS (
            SELECT
                OurBranchID,
                ApplicationFileNo,
                MemberID,
                MIN(CreatedOn) AS MinCreatedOn,
                MAX(CreatedOn) AS MaxCreatedOn,
                MAX(ActionOn)  AS MaxActionOn,
                COUNT(DISTINCT SendBackRefNo) AS SendbackCount
            FROM stg_brnet.cv_GLOSSendBackChkLstData_inc_full
            WHERE ActivityID = 'CPCV'
            GROUP BY OurBranchID, ApplicationFileNo, MemberID
        ),

        -- ================================================================
        -- CTE 70: CPC Queries, Remarks & Aggregations
        -- ================================================================
        cte_cpc_queries_agg AS (
            SELECT
                sb.OurBranchID,
                sb.ApplicationFileNo,
                sb.MemberID,
                COUNT(CASE WHEN COALESCE(sb.IsNotOK, 0) = 1 THEN 1 END) AS QueryRaisedCount,
                array_join(array_sort(collect_set(CASE WHEN COALESCE(sb.IsNotOK, 0) = 1 THEN cl.Description END)), '|') AS Queries,
                array_join(array_sort(collect_set(CASE WHEN COALESCE(sb.IsNotOK, 0) = 1 AND sb.CreatedOn = md.MaxCreatedOn THEN cl.Description END)), '|') AS LiveQueries,
                array_join(collect_list(CASE WHEN COALESCE(sb.IsNotOK, 0) = 1 AND sb.CreatedOn = md.MaxCreatedOn THEN sb.CheckListRemarks END), '|') AS LiveRemarks,
                array_join(array_sort(collect_set(CASE WHEN COALESCE(sb.IsNotOK, 0) = 1 AND sb.CreatedOn < md.MaxCreatedOn THEN cl.Description END)), '|') AS PreviousQueries,
                array_join(array_sort(collect_set(CASE WHEN COALESCE(sb.IsNotOK, 0) = 1 AND sb.CreatedOn < md.MaxCreatedOn THEN sb.ResolvedRemarks END)), '|') AS PreviousRemarks,
                date_format(md.MaxCreatedOn, 'dd/MM/yyyy hh:mm a') AS LastCPCQueryRaisedOn,
                date_format(md.MaxActionOn, 'dd/MM/yyyy hh:mm a')  AS LastCPCQueryRespondedOn
            FROM stg_brnet.cv_GLOSSendBackChkLstData_inc_full sb
            INNER JOIN stg_brnet.t_GLOSCheckList_inc_full cl
                    ON cl.CheckListID = sb.CheckListID
            INNER JOIN cte_cpc_query_max_dates md
                    ON md.OurBranchID        = sb.OurBranchID
                   AND md.ApplicationFileNo  = sb.ApplicationFileNo
                   AND md.MemberID           = sb.MemberID
            WHERE sb.ActivityID = 'CPCV'
            GROUP BY sb.OurBranchID, sb.ApplicationFileNo, sb.MemberID, md.MaxCreatedOn, md.MaxActionOn
        ),

        -- ================================================================
        -- CTE 71: CPC Done By Officer Resolver (Activity 'CPCV')
        -- ================================================================
        cte_cpc_done_by AS (
            SELECT * FROM (
                SELECT
                    OurBranchID,
                    ApplicationFileNo,
                    OfficerID AS CPCDoneBy,
                    StartOn   AS CPCStartedOn,
                    CASE WHEN ActivityStatusID = 'COMP' THEN StatusOn ELSE NULL END AS CPCCompletedOn,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY COALESCE(EndOn, StartOn, ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSActivityLog_inc_full
                WHERE ActivityID = 'CPCV'
            ) t WHERE t.rn = 1
        ),

        -- ================================================================
        -- CTE 73: Member Created Date Resolver (Activity 'MDEN' / 'MEMC')
        -- ================================================================
        cte_member_created_date AS (
            SELECT * FROM (
                SELECT
                    OurBranchID,
                    ApplicationFileNo,
                    StartOn AS MemberCreatedDate,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY COALESCE(StartOn, ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSActivityLog_inc_full
                WHERE GLOSProcessActivityID IN ('MDEN', 'MEMC')
                  AND ActivityStatusID IS NOT NULL
            ) t WHERE t.rn = 1
        ),

        -- ================================================================
        -- CTE 72: Loan Officer Mobile Resolver
        -- ================================================================
        cte_lo_mobile AS (
            SELECT * FROM (
                SELECT
                    ao.OfficerID,
                    cli.Mobile AS LOMobile,
                    ROW_NUMBER() OVER (
                        PARTITION BY ao.OfficerID
                        ORDER BY COALESCE(cli.ModifiedOn, cli.CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_AccountOfficer_inc_full ao
                INNER JOIN stg_brnet.t_client_inc_full cli
                        ON cli.ClientID = ao.ClientID
                WHERE cli.ClientTypeID = 'E'
            ) t WHERE t.rn = 1
        )

-- FINAL SELECT
        -- ================================================================
        SELECT
            'BRNET'                                                                         AS SourceSystemName,

            tl.HKC_ETLMasterExecutionId,
            tl.HKC_ETLDetailExecutionId,
            tl.HKC_EDWSourceSystemID,
            tl.DQStatus                                                                     AS DQStatus,
            tl.DQId                                                                         AS DQId,

            tl.OurBranchID,
            tl.AccountID,
            -- Loan Series — raw passthrough (the loan's OWN series), NOT eff_series.
            --   Kept OUT of the SHA1 payload (grain, not a mutable value).
            tl.LoanSeries                                                                   AS LoanSeries,
            tl.CreditOfficerID                                                              AS CurrentloanofficerID,
            cli.Name                                                                        AS CurrnetLoanofficerName,

            COALESCE(acccust.ClientID, acccust_src.ClientID)                                AS ClientID,

            CASE tl.LoanStatusID
                WHEN 'P' THEN 'Paid Off'
                WHEN 'I' THEN 'Insurance Paid Off'
                WHEN 'R' THEN 'Rescheduled'
                WHEN 'N' THEN 'NPA'
                WHEN 'M' THEN 'Transffered'
                WHEN 'O' THEN 'Net-Off'
                WHEN 'L' THEN 'Loan Settled'
                WHEN 'Z' THEN 'WriteOff Settled'
                WHEN 'W' THEN 'Write Off'
                WHEN 'F' THEN 'Fully Paid'
                WHEN 'T' THEN 'Refinanced'
                WHEN 'S' THEN 'Sanctioned Loan'
                WHEN 'X' THEN 'Cancelled'
                WHEN 'A' THEN 'Active Loan'
                WHEN 'C' THEN 'Charge Off'
                ELSE tl.LoanStatusID
            END                                                                             AS AccountCloseType,

            COALESCE(lmea.AccrualAmount, lmea_src.AccrualAmount)                            AS TotalAccruedAmount,

            -- ════════════════════════════════════════════════════════════════
            -- Accrued interest  (was CAST(NULL AS DECIMAL(19,4)) placeholder)
            --   SP: ROUND(ISNULL(IntDue,0) + ISNULL(BrokenperiodInterest,0), 2)
            --   Computed in cte_accrued (CTE 59); see the CTE 54-59 header block
            --   for the five SP stages and the @ToDate / DATEDIFF caveats.
            --   COALESCE to 0 (not NULL): the SP's double ISNULL means a loan with
            --   no installment rows renders 0.00, never NULL. Drop the COALESCE if
            --   you would rather distinguish "no schedule" from "nothing accrued".
            -- ════════════════════════════════════════════════════════════════
            CAST(COALESCE(acr.AccruedInterest, 0) AS DECIMAL(19,4))                         AS AccruedInterest,

            lt_agg.AdditionalInterest,
            lt_agg.Advance,
            CAST(NULL AS DECIMAL(19,4))                                                     AS AdvanceCollected,
            CAST(NULL AS DECIMAL(19,4))                                                     AS AdvanceCollected1,
            lt_agg.BilledIntAmtForTheMonth,
            lt_agg.BilledIntAmtTillDate,

            COALESCE(excess_cbt.TrxAmount, lt_agg.ExcessAmount)                             AS ExcessAmount,

            cbt.BatchID                                                                     AS BatchID,
            rbl.RequestOn                                                                   AS BatchIDApprovalTime,

            tcashr.receiverofficerid                                                        AS CashRemittanceAcceptedby,
            tcashr.TrxBatchID                                                               AS CashRemittanceBatchID,
            CONCAT(
                COALESCE(DATE_FORMAT(tcashr.TrxDate,   'dd MMM yyyy'), ''),
                ' ',
                COALESCE(DATE_FORMAT(tcashr.CreatedOn, 'HH:mm:ss'),    '')
            )                                                                               AS CashRemittanceDateAndTimeStamp,

            -- BRNet Stage / BRNet Status — resolved through t_SystemCodeDetail;
            --   COALESCE(desc, raw) = SP ILOS behaviour (unresolved code survives).
            --   ID asymmetry: WFAdvStageID (stage) vs WFAppStatusID (status).
            COALESCE(wfstg.Description, wfla.WFAdvStageID)                                   AS BRNetStage,
            COALESCE(wfsts.Description, wfla.WFAppStatusID)                                  AS BRNetStatus,

            -- CurrentStatus — activity-log latest FIRST, glosclient seed as
            --   fallback (SP overwrites seed from log via left-JOIN UPDATE).
            --   Raw code retained on unresolved description.
            COALESCE(
                cstat.Description,
                galcur.ActivityStatusID,
                cvgl.GLOSPActivityStatusID
            )                                                                               AS CurrentStatus,

            -- CrossVerifyDoneBy — ID-Name (no spaces), ISNULL(name,id) fallback.
            CASE
    WHEN gal.OfficerID IS NULL THEN NULL
    WHEN cvname.Name IS NULL OR cvname.Name = '' THEN CAST(gal.OfficerID AS STRING)
    ELSE CONCAT(CAST(gal.OfficerID AS STRING), '-', cvname.Name)
END as CrossVerifyDoneBy,


            CONCAT(CAST(tl.disbursedby AS STRING),   ' - ', bm_name.Name)                   AS DisbursedByBM,
            CONCAT(CAST(ao_asm.OfficerID AS STRING), ' - ', asm_name.Name)                  AS DisbursedByASM,

            COALESCE(llp.ProvisionAmount, llp_src.ProvisionAmount)                          AS FinalProvAmt,

            -- GroupID = t_GroupMember.SubGroupID (GLOW semantics).
            gm.SubGroupID                                                                   AS GroupID,

            -- GroupName = t_Group.GroupName keyed on CenterID (SubGroupID: 0%
            --   match; CenterID: 100%). GroupID/GroupName describe different
            --   entities in adjacent columns — see CTE 24.
            grp.Name                                                                        AS GroupName,

            -- GRT block (cv_GLOSGRTDetail at MAX(GRTRefNo))
            grt.GRTDoneBy                                                                   AS GRTByEmpID,
            grtname.Name                                                                    AS GRTByName,
            DATE_FORMAT(
            FROM_UTC_TIMESTAMP(grt.GRTDoneDate, 'Asia/Kolkata'),
            'dd MMM yyyy'
        ) AS GRTDate,
            CAST(grt.StartTime AS STRING)                                                   AS GRTStartTime,
            CAST(grt.EndTime   AS STRING)                                                   AS GRTEndTime,

            -- GRT Latitude / Longitude — split GPSCoordinate on first comma.
            CASE WHEN INSTR(grt.GPSCoordinate, ',') > 0
                 THEN TRIM(SUBSTRING(grt.GPSCoordinate, 1, INSTR(grt.GPSCoordinate, ',') - 1))
            END                                                                             AS GRTLatitude,
            CASE WHEN INSTR(grt.GPSCoordinate, ',') > 0
                 THEN TRIM(SUBSTRING(grt.GPSCoordinate, INSTR(grt.GPSCoordinate, ',') + 1))
            END                                                                             AS GRTLongitude,

            -- GRT activity-log block (cv_GLOSActivityLog 'GRTC' via cte_gal_grt)
            COALESCE(gstat.Description, grtlog.ActivityStatusID)                            AS GRTStatus,
            grtlog.StartOn                                                                  AS GRTStartedOn,
            grtlog.StatusOn                                                                 AS GRTEndedOn,

            -- GRT TAT Hrs — SQL Server DATEDIFF(mi) truncates INPUTS to minute.
            CAST(CEIL(
                (unix_timestamp(date_trunc('MINUTE', grtlog.StatusOn))
               - unix_timestamp(date_trunc('MINUTE', grtlog.StartOn))) / 3600.0
            ) AS DECIMAL(19,2))                                                             AS GRTTATHrs,

            -- GRT TAT Days — Hrs/24 rounded to 2 dp (DECIMAL, not truncated).
            CAST(ROUND(CEIL(
                (unix_timestamp(date_trunc('MINUTE', grtlog.StatusOn))
               - unix_timestamp(date_trunc('MINUTE', grtlog.StartOn))) / 3600.0
            ) / 24, 2) AS DECIMAL(19,2))                                                    AS GRTTATDays,

            -- Loan Cycle: (LoanCycleNo + 1), default 1, then -1 when > 1.
            CASE
                WHEN COALESCE(CAST(gcl.LoanCycleNo AS INT) + 1, 1) > 1
                    THEN COALESCE(CAST(gcl.LoanCycleNo AS INT) + 1, 1) - 1
                ELSE COALESCE(CAST(gcl.LoanCycleNo AS INT) + 1, 1)
            END                                                                             AS LoanCycle,

            sbs.StateID                                                                     AS StateID,
            st.Description                                                                  AS StateName,

            -- VillageID: mailing PlaceID → t_Group.VillageID → app PlaceID → app VillageID
            COALESCE(cma.PlaceID, grp.VillageID, gapp.PlaceID, gapp.VillageID)               AS VillageID,

            -- Create Flag: FTR when no CPCV send-back, else FTNR (never NULL).
            CASE WHEN sbk.ReworkStartedOn IS NULL THEN 'FTR' ELSE 'FTNR' END                AS CreateFlag,

            -- Fund Transfer Mode: ISNULL(FundTransferModeID, 'IMPS') (never NULL).
            COALESCE(cbt.FundTransferModeID, 'IMPS')                                        AS FundTransferMode,

            -- Fund Transfer Status: offline branch overwrites online desc; the
            --   COM/REJ/INT map is nested inside the offline branch.
            CASE
                WHEN oft.LoanAccountID IS NOT NULL
                    THEN CASE tl.OfflineFTStatusID
                             WHEN 'COM' THEN 'Offline Transaction completed'
                             WHEN 'REJ' THEN 'Offline Transaction Rejected'
                             WHEN 'INT' THEN 'Offline Transaction Initiated'
                             ELSE tl.OfflineFTStatusID
                         END
                ELSE tacd.Description
            END                                                                             AS FundTransferStatus,

            -- Fund Transfer Status Time Stamp (same offline/online switch)
            DATE_FORMAT(
                    FROM_UTC_TIMESTAMP(
                        CASE
                            WHEN oft.LoanAccountID IS NOT NULL THEN tl.OfflineFTStatusOn
                            ELSE cbt.TrxStatusOn
                        END,
                        'Asia/Kolkata'
                    ),
                    'dd MMM yyyy HH:mm:ss'
                ) AS FundTransferStatusTimeStamp,

            -- GST details (Taxamount) — SUM TaxAmount over PF-class charges.
            CAST(COALESCE(chg.ProcessFeeTax, 0) AS DECIMAL(19,4))                           AS GSTDetails,

            -- Stamp Duty Fee — ILOS-only in SP, computed for all rows here.
            CAST(COALESCE(chg.StampFee, 0) AS DECIMAL(19,4))                                AS StampDutyFee,

            -- ID verification status — 4 ordered SP steps (order matters).
            --   Step 2 is a HARDCODED 5-account PASS patch — confirm before promoting.
            CASE
                WHEN tl.AccountID IN ('204816300174','200916300893','204116300437',
                                      '106616300914','107416301018')
                    THEN 'PASS'
                WHEN idvo.HasMandatoryOverridden = 1
                 AND idv.Remarks          IS NOT NULL
                 AND idv.GLOSRuleStatusID IS NOT NULL
                 AND idv.GLOSRuleStatusID <> 'PASS'
                    THEN 'OVERRIDDEN'
                WHEN idvo.HasMandatoryNotOverridden = 1
                 AND idv.GLOSRuleStatusID = 'NOTC'
                    THEN 'OVERRIDDEN'
                ELSE idv.GLOSRuleStatusID
            END                                                                             AS IDVerificationStatus,

            -- ID override reason — moves in lockstep with the status above.
            CASE
                WHEN tl.AccountID IN ('204816300174','200916300893','204116300437',
                                      '106616300914','107416301018')
                    THEN idv.Remarks
                WHEN idvo.HasMandatoryOverridden = 1
                 AND idv.Remarks          IS NOT NULL
                 AND idv.GLOSRuleStatusID IS NOT NULL
                 AND idv.GLOSRuleStatusID <> 'PASS'
                    THEN 'Source System Unavailable'
                WHEN idvo.HasMandatoryNotOverridden = 1
                 AND idv.GLOSRuleStatusID = 'NOTC'
                    THEN 'Source System Unavailable'
                ELSE idv.Remarks
            END                                                                             AS IDOverrideReason,

            -- Is Center Transferred (never NULL)
            CASE WHEN sxfer.NewBranchID IS NOT NULL THEN 'YES' ELSE 'NO' END                AS IsCenterTransferred,

            -- Is DG Signed — three-valued (NULL = no signature activity).
            CASE WHEN dsg.SignCount >= 8      THEN 'Yes'
                 WHEN dsg.SignCount IS NOT NULL THEN 'No'
            END                                                                             AS IsDGSigned,

            -- Is Enach Done (ILOS-scoped source; 'NO' on GLOW rows)
            CASE WHEN COALESCE(nach.IsEnachDone, 0) = 1 THEN 'YES' ELSE 'NO' END            AS IsEnachDone,

            -- Is Net Off / Net Off Amount (both non-NULL; SP mixed-case 'Yes'/'No')
            CASE WHEN COALESCE(nof.NetOffAmt, 0) > 0 THEN 'Yes' ELSE 'No' END               AS IsNetOff,
            CAST(COALESCE(nof.NetOffAmt, 0) AS DECIMAL(19,4))                               AS NetOffAmount,

            -- IsEstampComp — evaluated for all rows here (SP GLOW = constant 'NO').
            CASE WHEN est.ApplicationID IS NOT NULL THEN 'YES' ELSE 'NO' END                AS IsEstampComp,

            -- KLIAvailable — raw user-field passthrough.
            ufkli.FieldValue                                                                AS KLIAvailable,

            -- No of Relations / DigiLocker Sourced (COALESCE to 0, not NULL)
            CAST(COALESCE(gclrel.NoOfRelations, 0) AS INT)                                  AS NoOfRelations,
            CAST(COALESCE(gclrel.NoOfDigiLockerSourced, 0) AS INT)                          AS NoOfDigiLockerSourced,

            -- Origination Workflow — ID '-' Description; NULL unless both resolve.
            CASE WHEN gapp.GLOSProcessTypeID IS NOT NULL AND gpt.Description IS NOT NULL
                 THEN CONCAT(CAST(gapp.GLOSProcessTypeID AS STRING), '-', gpt.Description)
            END                                                                             AS OriginationWorkflow,

            -- UTRNo — XML step 1, then cv_CBT fallback (fires on '' and 'null' too).
            CASE WHEN utrx.txn_utr IS NULL OR utrx.txn_utr = '' OR utrx.txn_utr = 'null'
                 THEN cbtu.UTRNo
                 ELSE utrx.txn_utr
            END                                                                             AS UTRNo,

            -- Verification date
            DATE_FORMAT(
                from_UTC_TIMESTAMP
                (cbst.EnquiryStatusOn , 'Asia/Kolkata'), 'dd-MMM-yy')                                AS VerificationDate,

            -- ================================================================
            -- PTP block (DPD SP) — loan-grain, COALESCE(primary, fallback).
            -- ================================================================

            -- PTP date — stage 2a (latest date + highest batch) wins; the
            --   stage-1 client fallback fills gaps.
            COALESCE(ptpd.PTPDate, ptpc.PTPDateFallback)                                    AS PTPDate,

            -- Number of times PTP date has been entered — stage 2b (count of
            --   DISTINCT qualifying PTP dates) over the stage-1 fallback, then
            --   the SP's two null-outs IN ORDER: NULL when the resolved PTP date
            --   is NULL; then NULL when the count is exactly 0.
            CASE
                WHEN COALESCE(ptpd.PTPDate, ptpc.PTPDateFallback) IS NULL THEN NULL
                WHEN COALESCE(ptpcnt.PTPCount, ptpc.PTPCountFallback, 0) = 0 THEN NULL
                ELSE COALESCE(ptpcnt.PTPCount, ptpc.PTPCountFallback)
            END                                                                             AS NoOfTimesPTPDateEntered,

            -- PTP Reason — ISNULL(desc(ArrearReasonID), desc(DelinquencyReasonID)),
            --   both via the DelinquencyReasonID user-code family (CTE 53). The
            --   reason row is matched on ClientID + resolved PTP date (SP quirk:
            --   no branch/account in that join — see the ptpr join).
            COALESCE(darr.Description, ddel.Description)                                     AS PTPReason,

            
            -- ════════════════════════════════════════════════════════════════
            -- 38 ATTRIBUTES FROM TCL CPC DETAILS REPORT
            -- ════════════════════════════════════════════════════════════════
            CAST(cbt.NetDisbursementAmount AS DECIMAL(18,2))                                AS PaymentAmount,

            CASE
                WHEN tl.FirstDisbursementDate IS NOT NULL AND cbt.TrxStatusID NOT IN ('COM', 'ERR') THEN 'In-Pending'
                WHEN tl.FirstDisbursementDate IS NOT NULL AND cbt.TrxStatusID = 'COM' THEN 'Success'
                WHEN tl.FirstDisbursementDate IS NOT NULL AND cbt.TrxStatusID = 'ERR' THEN 'Error'
                ELSE NULL
            END                                                                             AS PaymentStatus,

            cbt.TrxStatusOn                                                                 AS PaymentStatusOn,
            oftl_init.PaymentInitiatedBy                                                    AS PaymentInitiatedBy,
            oftl_init.PaymentInitiatedOn                                                    AS PaymentInitiatedOn,
            oftl_app.PaymentApprovedBy                                                      AS PaymentApprovedBy,
            oftl_app.PaymentApprovedOn                                                      AS PaymentApprovedOn,

            CAST(cbt.Score AS DOUBLE)                                                       AS NameMatchScore,
            TRIM(regexp_replace(cbt.ErrorMsg, r'[\t\r\n\"]+', ' '))                     AS HDFCRemarks,

            wflb.LoanBookedBy                                                               AS LoanBookedBy,
            wflb.LoanBookedOn                                                               AS LoanBookedON,
            tl.disbursedby                                                                  AS LoanDisbursedBy,
            tl.FirstDisbursementDate                                                        AS LoanDisbursedOn,

            COALESCE(gcl.LoanSchemeID, wfla.LoanSchemeID)                                   AS LoanScheme,
            lo_mob.LOMobile                                                                 AS LOMobile,

            COALESCE(cpc_off.Name, cpc_db.CPCDoneBy)                                        AS OwnerName,
            cpc_db.CPCDoneBy                                                                AS CPCDoneBy,
            cpc_db.CPCCompletedOn                                                           AS CPCCompletedOn,

            CASE
                WHEN COALESCE(qa.QueryRaisedCount, 0) = 0 AND (qa.PreviousQueries IS NULL OR TRIM(qa.PreviousQueries) = '') THEN 'FTR'
                ELSE 'NFTR'
            END                                                                             AS CPCFTRFlag,

            gcba.ModifiedBy                                                                 AS ModifiedBy,
            gcba.ModifiedOn                                                                 AS Modifiedon,
            bar.PreviousBenecheckRemarks                                                    AS PreviousBenecheckRemarks,

            CASE
                WHEN bar.PreviousBenecheckRemarks IS NULL OR TRIM(bar.PreviousBenecheckRemarks) = '' THEN 0
                ELSE size(split(bar.PreviousBenecheckRemarks, ','))
            END                                                                             AS BenecheckSendbackCount,

            COALESCE(qmd.SendbackCount, 0)                                                  AS SendbackCount,
            COALESCE(qa.QueryRaisedCount, 0)                                                AS QueryRaisedCount,
            date_format(qmd.MinCreatedOn, 'dd/MM/yyyy hh:mm a')                             AS QueryRaisedOn,
            qa.Queries                                                                      AS Queries,
            qa.LiveQueries                                                                  AS LiveQueries,
            qa.LiveRemarks                                                                  AS LiveRemarks,
            date_format(qmd.MaxCreatedOn, 'dd/MM/yyyy hh:mm a')                             AS LiveCPCQueryRaisedOn,
            date_format(qmd.MaxActionOn, 'dd/MM/yyyy hh:mm a')                              AS LiveCPCQueryRespondedOn,
            qa.PreviousQueries                                                              AS PreviousQueries,
            qa.PreviousRemarks                                                              AS PreviousRemarks,
            qa.LastCPCQueryRaisedOn                                                         AS LastCPCQueryRaisedOn,
            qa.LastCPCQueryRespondedOn                                                      AS LastCPCQueryRespondedOn,

            CASE
                WHEN COALESCE(qa.QueryRaisedCount, 0) = 0 AND (qa.PreviousQueries IS NULL OR TRIM(qa.PreviousQueries) = '') THEN 'No'
                ELSE 'Yes'
            END                                                                             AS IsQueryRaised,

            CASE
                WHEN COALESCE(qa.QueryRaisedCount, 0) = 0 AND (qa.PreviousQueries IS NULL OR TRIM(qa.PreviousQueries) = '') THEN 'No'
                ELSE 'Yes'
            END                                                                             AS QueryRaised,

            CASE
                WHEN COALESCE(qa.QueryRaisedCount, 0) = 0 AND (qa.PreviousQueries IS NULL OR TRIM(qa.PreviousQueries) = '')
                     AND COALESCE(galcur.ActivityStatusID, cvgl.GLOSPActivityStatusID, '') <> 'PEND' THEN 'Completed'
                WHEN qa.LastCPCQueryRespondedOn IS NOT NULL THEN 'Query Responded'
                WHEN qa.LastCPCQueryRaisedOn IS NOT NULL THEN 'Query Raised'
                ELSE CASE COALESCE(galcur.ActivityStatusID, cvgl.GLOSPActivityStatusID)
                         WHEN 'PEND' THEN 'Pending'
                         WHEN 'COMP' THEN 'Completed'
                         WHEN 'REJT' THEN 'Rejected'
                         ELSE COALESCE(cstat.Description, 'Not Started')
                     END
            END                                                                             AS MemberCPCStatus,

            date_format(mcd.MemberCreatedDate, 'dd-MMM-yyyy')                               AS MemberCreatedDate,

-- SHA1 hash — append-only. New attributes appended at the END so
            --   previously hashed column positions do not shift. The hash flips
            --   for every row on the first run after any append (expected).
            -- Accrued interest appended as the FINAL segment this revision.
            CAST(sha1(CONCAT(
                COALESCE(CAST(tl.OurBranchID AS STRING), ''), '|',
                COALESCE(CAST(tl.AccountID AS STRING), ''), '|',
                COALESCE(CAST(COALESCE(acccust.ClientID, acccust_src.ClientID) AS STRING), ''), '|',
                COALESCE(CAST(
                    CASE tl.LoanStatusID
                        WHEN 'P' THEN 'Paid Off'
                        WHEN 'I' THEN 'Insurance Paid Off'
                        WHEN 'R' THEN 'Rescheduled'
                        WHEN 'N' THEN 'NPA'
                        WHEN 'M' THEN 'Transffered'
                        WHEN 'O' THEN 'Net-Off'
                        WHEN 'L' THEN 'Loan Settled'
                        WHEN 'Z' THEN 'WriteOff Settled'
                        WHEN 'W' THEN 'Write Off'
                        WHEN 'F' THEN 'Fully Paid'
                        WHEN 'T' THEN 'Refinanced'
                        WHEN 'S' THEN 'Sanctioned Loan'
                        WHEN 'X' THEN 'Cancelled'
                        WHEN 'A' THEN 'Active Loan'
                        WHEN 'C' THEN 'Charge Off'
                        ELSE tl.LoanStatusID
                    END AS STRING), ''), '|',
                COALESCE(CAST(COALESCE(lmea.AccrualAmount, lmea_src.AccrualAmount) AS STRING), ''), '|',
                COALESCE(CAST(lt_agg.AdditionalInterest AS STRING), ''), '|',
                COALESCE(CAST(lt_agg.Advance AS STRING), ''), '|',
                COALESCE(CAST(lt_agg.BilledIntAmtForTheMonth AS STRING), ''), '|',
                COALESCE(CAST(lt_agg.BilledIntAmtTillDate AS STRING), ''), '|',
                COALESCE(CAST(COALESCE(excess_cbt.TrxAmount, lt_agg.ExcessAmount) AS STRING), ''), '|',
                COALESCE(CAST(cbt.BatchID AS STRING), ''), '|',
                COALESCE(CAST(rbl.RequestOn AS STRING), ''), '|',
                COALESCE(CAST(tcashr.receiverofficerid AS STRING), ''), '|',
                COALESCE(CAST(tcashr.TrxBatchID AS STRING), ''), '|',
                COALESCE(CAST(CONCAT(
                    COALESCE(DATE_FORMAT(tcashr.TrxDate,   'dd MMM yyyy'), ''),
                    ' ',
                    COALESCE(DATE_FORMAT(tcashr.CreatedOn, 'HH:mm:ss'),    '')
                ) AS STRING), ''), '|',
                COALESCE(CAST(wfla.WFAdvStageID AS STRING), ''), '|',
                COALESCE(CAST(wfla.WFAppStatusID AS STRING), ''), '|',
                COALESCE(CONCAT(CAST(tl.disbursedby AS STRING),   ' - ', bm_name.Name), ''), '|',
                COALESCE(CONCAT(CAST(ao_asm.OfficerID AS STRING), ' - ', asm_name.Name), ''), '|',
                COALESCE(CAST(COALESCE(llp.ProvisionAmount, llp_src.ProvisionAmount) AS STRING), ''), '|',
                -- ---- appended: group / GRT / cycle / state / village ----
                COALESCE(CAST(gm.SubGroupID AS STRING), ''), '|',
                COALESCE(CAST(grp.Name AS STRING), ''), '|',
                COALESCE(CAST(grt.GRTDoneBy AS STRING), ''), '|',
                COALESCE(CAST(grtname.Name AS STRING), ''), '|',
                COALESCE(DATE_FORMAT(grt.GRTDoneDate, 'dd MMM yyyy'), ''), '|',
                COALESCE(CAST(grt.StartTime AS STRING), ''), '|',
                COALESCE(CAST(grt.EndTime AS STRING), ''), '|',
                COALESCE(CAST(
                    CASE
                        WHEN COALESCE(CAST(gcl.LoanCycleNo AS INT) + 1, 1) > 1
                            THEN COALESCE(CAST(gcl.LoanCycleNo AS INT) + 1, 1) - 1
                        ELSE COALESCE(CAST(gcl.LoanCycleNo AS INT) + 1, 1)
                    END AS STRING), ''), '|',
                COALESCE(CAST(sbs.StateID AS STRING), ''), '|',
                COALESCE(CAST(st.Description AS STRING), ''), '|',
                COALESCE(CAST(COALESCE(cma.PlaceID, grp.VillageID, gapp.PlaceID, gapp.VillageID) AS STRING), ''), '|',
                -- ---- appended: GRT GPS ----
                COALESCE(CASE WHEN INSTR(grt.GPSCoordinate, ',') > 0
                              THEN TRIM(SUBSTRING(grt.GPSCoordinate, 1, INSTR(grt.GPSCoordinate, ',') - 1))
                         END, ''), '|',
                COALESCE(CASE WHEN INSTR(grt.GPSCoordinate, ',') > 0
                              THEN TRIM(SUBSTRING(grt.GPSCoordinate, INSTR(grt.GPSCoordinate, ',') + 1))
                         END, ''), '|',
                -- ---- appended: GRT activity-log block ----
                COALESCE(CAST(COALESCE(gstat.Description, grtlog.ActivityStatusID) AS STRING), ''), '|',
                COALESCE(CAST(grtlog.StartOn AS STRING), ''), '|',
                COALESCE(CAST(grtlog.StatusOn AS STRING), ''), '|',
                COALESCE(CAST(CAST(CEIL(
                    (unix_timestamp(date_trunc('MINUTE', grtlog.StatusOn))
                   - unix_timestamp(date_trunc('MINUTE', grtlog.StartOn))) / 3600.0
                ) AS DECIMAL(19,2)) AS STRING), ''), '|',
                COALESCE(CAST(CAST(ROUND(CEIL(
                    (unix_timestamp(date_trunc('MINUTE', grtlog.StatusOn))
                   - unix_timestamp(date_trunc('MINUTE', grtlog.StartOn))) / 3600.0
                ) / 24, 2) AS DECIMAL(19,2)) AS STRING), ''), '|',
                -- ---- appended: 20-attribute pass ----
                CASE WHEN sbk.ReworkStartedOn IS NULL THEN 'FTR' ELSE 'FTNR' END, '|',
                COALESCE(cbt.FundTransferModeID, 'IMPS'), '|',
                COALESCE(CAST(
                    CASE
                        WHEN oft.LoanAccountID IS NOT NULL
                            THEN CASE tl.OfflineFTStatusID
                                     WHEN 'COM' THEN 'Offline Transaction completed'
                                     WHEN 'REJ' THEN 'Offline Transaction Rejected'
                                     WHEN 'INT' THEN 'Offline Transaction Initiated'
                                     ELSE tl.OfflineFTStatusID
                                 END
                        ELSE tacd.Description
                    END AS STRING), ''), '|',
                COALESCE(DATE_FORMAT(
                    CASE WHEN oft.LoanAccountID IS NOT NULL THEN tl.OfflineFTStatusOn
                         ELSE cbt.TrxStatusOn END,
                    'dd MMM yyyy HH:mm:ss'), ''), '|',
                CAST(CAST(COALESCE(chg.ProcessFeeTax, 0) AS DECIMAL(19,4)) AS STRING), '|',
                CAST(CAST(COALESCE(chg.StampFee, 0) AS DECIMAL(19,4)) AS STRING), '|',
                COALESCE(CAST(
                    CASE
                        WHEN tl.AccountID IN ('204816300174','200916300893','204116300437',
                                              '106616300914','107416301018')
                            THEN 'PASS'
                        WHEN idvo.HasMandatoryOverridden = 1
                         AND idv.Remarks          IS NOT NULL
                         AND idv.GLOSRuleStatusID IS NOT NULL
                         AND idv.GLOSRuleStatusID <> 'PASS'
                            THEN 'OVERRIDDEN'
                        WHEN idvo.HasMandatoryNotOverridden = 1
                         AND idv.GLOSRuleStatusID = 'NOTC'
                            THEN 'OVERRIDDEN'
                        ELSE idv.GLOSRuleStatusID
                    END AS STRING), ''), '|',
                COALESCE(CAST(
                    CASE
                        WHEN tl.AccountID IN ('204816300174','200916300893','204116300437',
                                              '106616300914','107416301018')
                            THEN idv.Remarks
                        WHEN idvo.HasMandatoryOverridden = 1
                         AND idv.Remarks          IS NOT NULL
                         AND idv.GLOSRuleStatusID IS NOT NULL
                         AND idv.GLOSRuleStatusID <> 'PASS'
                            THEN 'Source System Unavailable'
                        WHEN idvo.HasMandatoryNotOverridden = 1
                         AND idv.GLOSRuleStatusID = 'NOTC'
                            THEN 'Source System Unavailable'
                        ELSE idv.Remarks
                    END AS STRING), ''), '|',
                CASE WHEN sxfer.NewBranchID IS NOT NULL THEN 'YES' ELSE 'NO' END, '|',
                COALESCE(CASE WHEN dsg.SignCount >= 8        THEN 'Yes'
                              WHEN dsg.SignCount IS NOT NULL THEN 'No'
                         END, ''), '|',
                CASE WHEN COALESCE(nach.IsEnachDone, 0) = 1 THEN 'YES' ELSE 'NO' END, '|',
                CASE WHEN COALESCE(nof.NetOffAmt, 0) > 0 THEN 'Yes' ELSE 'No' END, '|',
                CAST(CAST(COALESCE(nof.NetOffAmt, 0) AS DECIMAL(19,4)) AS STRING), '|',
                CASE WHEN est.ApplicationID IS NOT NULL THEN 'YES' ELSE 'NO' END, '|',
                COALESCE(CAST(ufkli.FieldValue AS STRING), ''), '|',
                CAST(CAST(COALESCE(gclrel.NoOfRelations, 0) AS INT) AS STRING), '|',
                CAST(CAST(COALESCE(gclrel.NoOfDigiLockerSourced, 0) AS INT) AS STRING), '|',
                COALESCE(CASE WHEN gapp.GLOSProcessTypeID IS NOT NULL AND gpt.Description IS NOT NULL
                              THEN CONCAT(CAST(gapp.GLOSProcessTypeID AS STRING), '-', gpt.Description)
                         END, ''), '|',
                COALESCE(CAST(
                    CASE WHEN utrx.txn_utr IS NULL OR utrx.txn_utr = '' OR utrx.txn_utr = 'null'
                         THEN cbtu.UTRNo
                         ELSE utrx.txn_utr
                    END AS STRING), ''), '|',
                COALESCE(DATE_FORMAT(cbst.EnquiryStatusOn, 'dd MMM yyyy'), ''), '|',
                -- ---- appended: BRNet Stage / Status / CurrentStatus ----
                COALESCE(CAST(COALESCE(wfstg.Description, wfla.WFAdvStageID) AS STRING), ''), '|',
                COALESCE(CAST(COALESCE(wfsts.Description, wfla.WFAppStatusID) AS STRING), ''), '|',
                COALESCE(CAST(COALESCE(cstat.Description,
                                       galcur.ActivityStatusID,
                                       cvgl.GLOSPActivityStatusID) AS STRING), ''), '|',
                -- ---- appended: PTP block (previous revision) ----
                COALESCE(CAST(COALESCE(ptpd.PTPDate, ptpc.PTPDateFallback) AS STRING), ''), '|',
                COALESCE(CAST(
                    CASE
                        WHEN COALESCE(ptpd.PTPDate, ptpc.PTPDateFallback) IS NULL THEN NULL
                        WHEN COALESCE(ptpcnt.PTPCount, ptpc.PTPCountFallback, 0) = 0 THEN NULL
                        ELSE COALESCE(ptpcnt.PTPCount, ptpc.PTPCountFallback)
                    END AS STRING), ''), '|',
                COALESCE(CAST(COALESCE(darr.Description, ddel.Description) AS STRING), ''), '|',
                -- ---- appended: Accrued interest (this revision) ----
                CAST(CAST(COALESCE(acr.AccruedInterest, 0) AS DECIMAL(19,4)) AS STRING)
            
                -- 38 CPC Attributes in SHA1 Hash
                COALESCE(CAST(cbt.NetDisbursementAmount AS STRING), ''), '|', -- 1. Payment Amount (PaymentAmount)
                COALESCE(CAST(
                    CASE
                        WHEN tl.FirstDisbursementDate IS NOT NULL AND cbt.TrxStatusID NOT IN ('COM', 'ERR') THEN 'In-Pending'
                        WHEN tl.FirstDisbursementDate IS NOT NULL AND cbt.TrxStatusID = 'COM' THEN 'Success'
                        WHEN tl.FirstDisbursementDate IS NOT NULL AND cbt.TrxStatusID = 'ERR' THEN 'Error'
                        ELSE NULL
                    END AS STRING), ''), '|', -- 2. Payment Status (PaymentStatus)
                COALESCE(CAST(cbt.TrxStatusOn AS STRING), ''), '|', -- 3. Payment Status On (PaymentStatusOn)
                COALESCE(CAST(oftl_init.PaymentInitiatedBy AS STRING), ''), '|', -- 4. Payment Initiated by (PaymentInitiatedBy)
                COALESCE(CAST(oftl_init.PaymentInitiatedOn AS STRING), ''), '|', -- 5. Payment Initiated On (PaymentInitiatedOn)
                COALESCE(CAST(oftl_app.PaymentApprovedBy AS STRING), ''), '|', -- 6. Payment Approved By (PaymentApprovedBy)
                COALESCE(CAST(oftl_app.PaymentApprovedOn AS STRING), ''), '|', -- 7. Payment Approved On (PaymentApprovedOn)
                COALESCE(CAST(cbt.Score AS STRING), ''), '|', -- 8. Name Match Score (NameMatchScore)
                COALESCE(CAST(TRIM(regexp_replace(cbt.ErrorMsg, r'[\t\r\n\"]+', ' ')) AS STRING), ''), '|', -- 9. HDFC Remarks (HDFCRemarks)
                COALESCE(CAST(wflb.LoanBookedBy AS STRING), ''), '|', -- 10. Loan Booked By (LoanBookedBy)
                COALESCE(CAST(wflb.LoanBookedOn AS STRING), ''), '|', -- 11. Loan Booked ON (LoanBookedON)
                COALESCE(CAST(tl.disbursedby AS STRING), ''), '|', -- 12. Loan Disbursed By (LoanDisbursedBy)
                COALESCE(CAST(tl.FirstDisbursementDate AS STRING), ''), '|', -- 13. Loan Disbursed On (LoanDisbursedOn)
                COALESCE(CAST(COALESCE(gcl.LoanSchemeID, wfla.LoanSchemeID) AS STRING), ''), '|', -- 14. Loan Scheme (LoanScheme)
                COALESCE(CAST(lo_mob.LOMobile AS STRING), ''), '|', -- 15. LO Mobile (LOMobile)
                COALESCE(CAST(COALESCE(cpc_off.Name, cpc_db.CPCDoneBy) AS STRING), ''), '|', -- 16. Owner Name (OwnerName)
                COALESCE(CAST(cpc_db.CPCDoneBy AS STRING), ''), '|', -- 17. CPC Done By (CPCDoneBy)
                COALESCE(CAST(cpc_db.CPCCompletedOn AS STRING), ''), '|', -- 18. CPC Completed On (CPCCompletedOn)
                COALESCE(CAST(
                    CASE
                        WHEN COALESCE(qa.QueryRaisedCount, 0) = 0 AND (qa.PreviousQueries IS NULL OR TRIM(qa.PreviousQueries) = '') THEN 'FTR'
                        ELSE 'NFTR'
                    END AS STRING), ''), '|', -- 19. CPC FTR Flag (CPCFTRFlag)
                COALESCE(CAST(gcba.ModifiedBy AS STRING), ''), '|', -- 20. ModifiedBy (ModifiedBy)
                COALESCE(CAST(gcba.ModifiedOn AS STRING), ''), '|', -- 21. Modifiedon (Modifiedon)
                COALESCE(CAST(bar.PreviousBenecheckRemarks AS STRING), ''), '|', -- 22. PreviousBenecheckRemarks (PreviousBenecheckRemarks)
                COALESCE(CAST(
                    CASE
                        WHEN bar.PreviousBenecheckRemarks IS NULL OR TRIM(bar.PreviousBenecheckRemarks) = '' THEN 0
                        ELSE size(split(bar.PreviousBenecheckRemarks, ','))
                    END AS STRING), ''), '|', -- 23. BenecheckSendbackCount (BenecheckSendbackCount)
                COALESCE(CAST(COALESCE(qmd.SendbackCount, 0) AS STRING), ''), '|', -- 24. Sendback Count (SendbackCount)
                COALESCE(CAST(COALESCE(qa.QueryRaisedCount, 0) AS STRING), ''), '|', -- 25. Query Raised Count (QueryRaisedCount)
                COALESCE(CAST(date_format(qmd.MinCreatedOn, 'dd/MM/yyyy hh:mm a') AS STRING), ''), '|', -- 26. Query Raised On (QueryRaisedOn)
                COALESCE(CAST(qa.Queries AS STRING), ''), '|', -- 27. Queries (Queries)
                COALESCE(CAST(qa.LiveQueries AS STRING), ''), '|', -- 28. Live Queries (LiveQueries)
                COALESCE(CAST(qa.LiveRemarks AS STRING), ''), '|', -- 29. Live Remarks (LiveRemarks)
                COALESCE(CAST(date_format(qmd.MaxCreatedOn, 'dd/MM/yyyy hh:mm a') AS STRING), ''), '|', -- 30. Live CPC Query Raised On (LiveCPCQueryRaisedOn)
                COALESCE(CAST(date_format(qmd.MaxActionOn, 'dd/MM/yyyy hh:mm a') AS STRING), ''), '|', -- 31. Live CPC Query Responded On (LiveCPCQueryRespondedOn)
                COALESCE(CAST(qa.PreviousQueries AS STRING), ''), '|', -- 32. Previous Queries (PreviousQueries)
                COALESCE(CAST(qa.PreviousRemarks AS STRING), ''), '|', -- 33. Previous Remarks (PreviousRemarks)
                COALESCE(CAST(qa.LastCPCQueryRaisedOn AS STRING), ''), '|', -- 34. Last CPC Query Raised On (LastCPCQueryRaisedOn)
                COALESCE(CAST(qa.LastCPCQueryRespondedOn AS STRING), ''), '|', -- 35. Last CPC Query Responded On (LastCPCQueryRespondedOn)
                COALESCE(CAST(
                    CASE
                        WHEN COALESCE(qa.QueryRaisedCount, 0) = 0 AND (qa.PreviousQueries IS NULL OR TRIM(qa.PreviousQueries) = '') THEN 'No'
                        ELSE 'Yes'
                    END AS STRING), ''), '|', -- 36. Is Query Raised & Query Raised (IsQueryRaised, QueryRaised)
                COALESCE(CAST(
                    CASE
                        WHEN COALESCE(qa.QueryRaisedCount, 0) = 0 AND (qa.PreviousQueries IS NULL OR TRIM(qa.PreviousQueries) = '')
                             AND COALESCE(galcur.ActivityStatusID, cvgl.GLOSPActivityStatusID, '') <> 'PEND' THEN 'Completed'
                        WHEN qa.LastCPCQueryRespondedOn IS NOT NULL THEN 'Query Responded'
                        WHEN qa.LastCPCQueryRaisedOn IS NOT NULL THEN 'Query Raised'
                        ELSE CASE COALESCE(galcur.ActivityStatusID, cvgl.GLOSPActivityStatusID)
                                 WHEN 'PEND' THEN 'Pending'
                                 WHEN 'COMP' THEN 'Completed'
                                 WHEN 'REJT' THEN 'Rejected'
                                 ELSE COALESCE(cstat.Description, 'Not Started')
                             END
                    END AS STRING), ''), '|', -- 37. Member CPC Status (MemberCPCStatus)
                COALESCE(CAST(date_format(mcd.MemberCreatedDate, 'dd-MMM-yyyy') AS STRING), ''), '|' -- 38. Member Created Date (MemberCreatedDate)
)) AS BINARY)                                                                   AS HASHBYTESSHA1

        FROM      cte_loan_src         tl

        LEFT JOIN cte_acccust          acccust      ON tl.AccountID        = acccust.AccountID
                                                   AND tl.OurBranchID       = acccust.OurBranchID
        LEFT JOIN cte_acccust          acccust_src  ON tl.eff_account      = acccust_src.AccountID
                                                   AND tl.eff_branch        = acccust_src.OurBranchID
        LEFT JOIN cte_source_loan      srcloan      ON tl.eff_branch       = srcloan.OurBranchID
                                                   AND tl.eff_account       = srcloan.AccountID
                                                   AND tl.eff_series        = srcloan.LoanSeries
        LEFT JOIN cte_lmea             lmea         ON tl.AccountID        = lmea.AccountID
                                                   AND tl.OurBranchID       = lmea.OurBranchID
        LEFT JOIN cte_lmea             lmea_src     ON tl.eff_account      = lmea_src.AccountID
                                                   AND tl.eff_branch        = lmea_src.OurBranchID
        LEFT JOIN cte_li               li           ON tl.AccountID        = li.AccountID
                                                   AND tl.OurBranchID       = li.OurBranchID
        LEFT JOIN cte_loantrx_dedup    lt_dedup     ON tl.eff_account      = lt_dedup.AccountID
                                                   AND tl.eff_branch        = lt_dedup.OurBranchID
        LEFT JOIN cte_loantrx_agg      lt_agg       ON tl.eff_account      = lt_agg.AccountID
                                                   AND tl.eff_branch        = lt_agg.OurBranchID
        LEFT JOIN cte_cbt              cbt          ON tl.OurBranchID      = cbt.OurBranchID
                                                   AND tl.AccountID         = cbt.LoanAccountID
                                                   AND tl.LoanSeries        = cbt.LoanSeries
        LEFT JOIN cte_excess_cbt       excess_cbt   ON tl.OurBranchID      = excess_cbt.OurBranchID
                                                   AND tl.AccountID         = excess_cbt.LoanAccountID
                                                   AND tl.LoanSeries        = excess_cbt.LoanSeries
        LEFT JOIN cte_rbl              rbl          ON cbt.TrxRowID        = rbl.TrxRefID
        LEFT JOIN cte_cashr            tcashr       ON lt_dedup.TrxBatchID = tcashr.TrxBatchID
                                                   AND lt_dedup.TrxDate     = tcashr.TrxDate
                                                   AND lt_dedup.OurBranchID = tcashr.OurBranchID
        -- NOTE: BRNetStage, BRNetStatus and VerificationDate all hang off this
        --   join. Fan-out risk: cte_wfla deduped at (branch, ApplicationID,
        --   ClientID) but joined on branch + ApplicationID only. Check before
        --   promoting; if an ApplicationID carries multiple ClientIDs, add:
        --     AND wfla.ClientID = COALESCE(acccust.ClientID, acccust_src.ClientID)
        LEFT JOIN cte_wfla             wfla         ON tl.eff_branch       = wfla.OurBranchID
                                                   AND COALESCE(tl.ApplicationID, srcloan.ApplicationID) = wfla.ApplicationID
        LEFT JOIN cte_llp              llp          ON tl.AccountID        = llp.AccountID
                                                   AND tl.OurBranchID       = llp.OurBranchID
        LEFT JOIN cte_llp              llp_src      ON tl.eff_account      = llp_src.AccountID
                                                   AND tl.eff_branch        = llp_src.OurBranchID
        LEFT JOIN cte_cli              cli          ON acccust.OurBranchID  = cli.OurBranchID
                                                   AND acccust.ClientID      = cli.ClientID

        -- FIX #3: glosclient re-keyed to BRNETApplicationID + BRNETClientID.
        -- THIS PASS: also supplies GLOSPActivityStatusID (CurrentStatus seed).
        LEFT JOIN cte_tglc             cvgl         ON cvgl.OurBranchID        = tl.eff_branch
                                                   AND cvgl.BRNETApplicationID  = COALESCE(tl.ApplicationID, srcloan.ApplicationID)
                                                   AND cvgl.BRNETClientID       = COALESCE(acccust.ClientID, acccust_src.ClientID)

        LEFT JOIN cte_gal              gal          ON cvgl.OurBranchID        = gal.OurBranchID
                                                   AND cvgl.ApplicationFileNo   = gal.ApplicationFileNo
        LEFT JOIN cte_cv_officer_name  cvname       ON cvname.OfficerID          = gal.OfficerID

        LEFT JOIN cte_ao_bm            ao_bm        ON ao_bm.ReportingBranchID = tl.OurBranchID
                                                   AND ao_bm.OfficerID          = tl.disbursedby
        LEFT JOIN cte_ao_asm           ao_asm       ON ao_asm.OfficerID          = ao_bm.ReportingOfficerID
        LEFT JOIN cte_officer_name     bm_name      ON bm_name.OfficerID         = tl.disbursedby
        LEFT JOIN cte_officer_name     asm_name     ON asm_name.OfficerID        = ao_asm.OfficerID

        -- GroupID + CenterID (t_GroupMember on tl.OurBranchID + client)
        -- LEFT JOIN cte_groupmember      gm           ON gm.OurBranchID            = tl.OurBranchID
        --                                            AND gm.ClientID                = COALESCE(acccust.ClientID, acccust_src.ClientID)

        left join cte_groupmember         gm    on      --ON gm.OurBranchID            = cli.OurBranchID      -- changed for testing
                                                     gm.ClientID                = acccust.clientID

        -- GRT block — keyed tl.OurBranchID + cvgl.ApplicationFileNo.
        LEFT JOIN cte_grt              grt          ON grt.OurBranchID           = tl.OurBranchID
                                                   AND grt.ApplicationFileNo      = cvgl.ApplicationFileNo
        LEFT JOIN cte_officer_name     grtname      ON grtname.OfficerID         = grt.GRTDoneBy

        -- GRT activity-log block (Status / Started On / TAT) — same branch key.
        LEFT JOIN cte_gal_grt              grtlog   ON grtlog.OurBranchID        = tl.OurBranchID
                                                   AND grtlog.ApplicationFileNo   = cvgl.ApplicationFileNo
        LEFT JOIN cte_activity_status_desc gstat    ON gstat.SubCodeID           = grtlog.ActivityStatusID

        -- Loan Cycle (eff_branch)
        LEFT JOIN cte_gclloan          gcl          ON gcl.OurBranchID           = tl.eff_branch
                                                   AND gcl.ApplicationFileNo      = cvgl.ApplicationFileNo
                                                   AND gcl.MemberID               = cvgl.MemberID

        -- StateID / StateName
        LEFT JOIN cte_branchsetting    sbs          ON sbs.OurBranchID           = tl.OurBranchID
        LEFT JOIN cte_state_desc       st           ON st.SubCodeID              = sbs.StateID

        -- BRNet Stage / Status descriptions (bank-level config, (ID,SubCodeID)).
        LEFT JOIN cte_wfadvstage_desc    wfstg      ON wfstg.SubCodeID           = wfla.WFAdvStageID
        LEFT JOIN cte_wfappstatus_desc   wfsts      ON wfsts.SubCodeID           = wfla.WFAppStatusID

        -- CurrentStatus (branch + ApplicationFileNo, NO MemberID — SP grain).
        LEFT JOIN cte_gal_current        galcur     ON galcur.OurBranchID        = tl.OurBranchID
                                                   AND galcur.ApplicationFileNo   = cvgl.ApplicationFileNo
        LEFT JOIN cte_activity_status_desc cstat    ON cstat.SubCodeID           =
                                                        COALESCE(galcur.ActivityStatusID,
                                                                 cvgl.GLOSPActivityStatusID)

        -- (a) LOAN grain
        LEFT JOIN cte_offline_ft       oft          ON oft.OurBranchID           = tl.OurBranchID
                                                   AND oft.LoanAccountID          = tl.AccountID
                                                   AND oft.LoanSeries             = tl.LoanSeries
        LEFT JOIN cte_scheme_transfer  sxfer        ON sxfer.OurBranchID         = tl.OurBranchID
                                                   AND sxfer.LoanAccountID        = tl.AccountID
                                                   AND sxfer.LoanSeries           = tl.LoanSeries
        LEFT JOIN cte_dsign            dsg          ON dsg.OurBranchID           = tl.OurBranchID
                                                   AND dsg.AccountID              = tl.AccountID
                                                   AND dsg.LoanSeries             = tl.LoanSeries
        LEFT JOIN cte_netoff           nof          ON nof.OurBranchID           = tl.OurBranchID
                                                   AND nof.AccountID              = tl.AccountID
                                                   AND nof.LoanSeries             = tl.LoanSeries
        LEFT JOIN cte_userfield_kli    ufkli        ON ufkli.OurBranchID         = tl.OurBranchID
                                                   AND ufkli.RelevantID           = CONCAT(CAST(tl.AccountID AS STRING), '-',
                                                                                           CAST(tl.LoanSeries AS STRING))

        -- Accrued interest (loan grain — CURRENT branch keys, per the SP).
        --   NOTE the asymmetry with lmea / lt_agg / llp above, which read from
        --   eff_branch/eff_account: for a transferred loan TotalAccruedAmount
        --   comes from the ORIGIN while AccruedInterest comes from the CURRENT
        --   branch. Switch to eff_* here if BRNet leaves the schedule at origin.
        LEFT JOIN cte_accrued          acr          ON acr.OurBranchID           = tl.OurBranchID
                                                   AND acr.AccountID              = tl.AccountID
                                                   AND acr.LoanSeries             = tl.LoanSeries

        -- (b) APPLICATION grain — at eff_branch
        LEFT JOIN cte_chargedue_agg    chg          ON chg.OurBranchID           = tl.eff_branch
                                                   AND chg.ApplicationID          = COALESCE(tl.ApplicationID, srcloan.ApplicationID)
        LEFT JOIN cte_estamp           est          ON est.OurBranchID           = tl.eff_branch
                                                   AND est.ApplicationID          = COALESCE(tl.ApplicationID, srcloan.ApplicationID)

        -- (c) GLOS FILE grain — all via cvgl
        LEFT JOIN cte_sendback         sbk          ON sbk.OurBranchID           = tl.OurBranchID
                                                   AND sbk.ApplicationFileNo      = cvgl.ApplicationFileNo
                                                   AND sbk.MemberID               = cvgl.MemberID
        LEFT JOIN cte_idverify         idv          ON idv.OurBranchID           = tl.OurBranchID
                                                   AND idv.ApplicationFileNo      = cvgl.ApplicationFileNo
                                                   AND idv.MemberID               = cvgl.MemberID
        LEFT JOIN cte_idverify_ovr     idvo         ON idvo.OurBranchID          = tl.OurBranchID
                                                   AND idvo.ApplicationFileNo     = cvgl.ApplicationFileNo
                                                   AND idvo.MemberID              = cvgl.MemberID
        LEFT JOIN cte_nach_enach       nach         ON nach.OurBranchID          = tl.OurBranchID
                                                   AND nach.ApplicationFileNo     = cvgl.ApplicationFileNo
                                                   AND nach.MemberID              = cvgl.MemberID
        LEFT JOIN cte_glosrelation     gclrel       ON gclrel.OurBranchID        = tl.OurBranchID
                                                   AND gclrel.ApplicationFileNo   = cvgl.ApplicationFileNo
                                                   AND gclrel.MemberID            = cvgl.MemberID

        -- VillageID chain (grp dual-purpose: VillageID step 2 + GroupName)
        LEFT JOIN cte_cli_addr         cma          ON cma.ClientID              = COALESCE(acccust.ClientID, acccust_src.ClientID)
        LEFT JOIN cte_group            grp          ON grp.OurBranchID           = tl.OurBranchID
                                                   AND grp.GroupID                = COALESCE(gm.GroupID, wfla.GroupID)


        LEFT JOIN cte_glosapp          gapp         ON gapp.OurBranchID          = tl.eff_branch
                                                   AND gapp.ApplicationFileNo     = cvgl.ApplicationFileNo

        LEFT JOIN cte_processtype      gpt          ON gpt.GLOSProcessTypeID     = gapp.GLOSProcessTypeID

        LEFT JOIN cte_tac_status_desc  tacd         ON tacd.SubCodeID            = cbt.TrxStatusID

        LEFT JOIN cte_utr_rbl          utrx         ON utrx.TrxRefID             = cbt.TrxRowID
        LEFT JOIN cte_cbt_utr          cbtu         ON cbtu.OurBranchID          = tl.OurBranchID
                                                   AND cbtu.ClientID              = COALESCE(acccust.ClientID, acccust_src.ClientID)
                                                   AND cbtu.LoanAccountID         = tl.AccountID

        LEFT JOIN cte_cbstag           cbst         ON cbst.CBEnquiryRefNo       = wfla.CBEnquiryRefNo

        -- ################################################################
        -- ####          PTP block joins (previous revision)            ####
        -- ####  (a) LOAN grain — keyed tl.OurBranchID + tl.AccountID +   ####
        -- ####  client, matching the DPD SP's (TrxBranchID, AccountID,   ####
        -- ####  ClientID). NO LoanSeries — PTP is account/client level.  ####
        -- ################################################################
        LEFT JOIN cte_ptp_date         ptpd         ON ptpd.TrxBranchID          = tl.OurBranchID
                                                   AND ptpd.AccountID             = tl.AccountID
                                                   AND ptpd.ClientID              = COALESCE(acccust.ClientID, acccust_src.ClientID)
        LEFT JOIN cte_ptp_count        ptpcnt       ON ptpcnt.TrxBranchID        = tl.OurBranchID
                                                   AND ptpcnt.AccountID           = tl.AccountID
                                                   AND ptpcnt.ClientID            = COALESCE(acccust.ClientID, acccust_src.ClientID)
        LEFT JOIN cte_ptp_client       ptpc         ON ptpc.TrxBranchID          = tl.OurBranchID
                                                   AND ptpc.AccountID             = tl.AccountID
                                                   AND ptpc.ClientID              = COALESCE(acccust.ClientID, acccust_src.ClientID)
        -- PTP Reason — SP quirk: joined on ClientID + resolved PTP date ONLY
        --   (no branch/account). The date is the FINAL COALESCE(ptpd, fallback).
        LEFT JOIN cte_ptp_reason       ptpr         ON ptpr.ClientID             = COALESCE(acccust.ClientID, acccust_src.ClientID)
                                                   AND ptpr.PTPDate               = COALESCE(ptpd.PTPDate, ptpc.PTPDateFallback)
        LEFT JOIN cte_delinq_desc      darr         ON darr.SubCodeID            = ptpr.ArrearReasonID
        LEFT JOIN cte_delinq_desc      ddel         ON ddel.SubCodeID            = ptpr.DelinquencyReasonID
        -- ################################################################
        -- ####          30 P0 CPC Attributes Joins                     ####
        -- ################################################################
        LEFT JOIN cte_oftl_init        oftl_init    ON oftl_init.OurBranchID     = cbt.OurBranchID
                                                   AND oftl_init.TrxRowID         = cbt.TrxRowID
        LEFT JOIN cte_oftl_app         oftl_app     ON oftl_app.OurBranchID      = cbt.OurBranchID
                                                   AND oftl_app.TrxRowID         = cbt.TrxRowID
        LEFT JOIN cte_wfloanbooking    wflb         ON wflb.OurBranchID          = tl.eff_branch
                                                   AND wflb.ApplicationID        = COALESCE(tl.ApplicationID, srcloan.ApplicationID)
        LEFT JOIN cte_benecheck_all_remarks bar     ON bar.OurBranchID           = cvgl.OurBranchID
                                                   AND bar.ApplicationFileNo     = cvgl.ApplicationFileNo
                                                   AND bar.MemberID              = cvgl.MemberID
        LEFT JOIN cte_client_bank_acc_latest gcba   ON gcba.OurBranchID          = cvgl.OurBranchID
                                                   AND gcba.ApplicationFileNo    = cvgl.ApplicationFileNo
                                                   AND gcba.MemberID             = cvgl.MemberID
        LEFT JOIN cte_cpc_query_max_dates qmd       ON qmd.OurBranchID           = cvgl.OurBranchID
                                                   AND qmd.ApplicationFileNo     = cvgl.ApplicationFileNo
                                                   AND qmd.MemberID              = cvgl.MemberID
        LEFT JOIN cte_cpc_queries_agg  qa           ON qa.OurBranchID            = cvgl.OurBranchID
                                                   AND qa.ApplicationFileNo      = cvgl.ApplicationFileNo
                                                   AND qa.MemberID               = cvgl.MemberID
        LEFT JOIN cte_cpc_done_by      cpc_db       ON cpc_db.OurBranchID        = cvgl.OurBranchID
                                                   AND cpc_db.ApplicationFileNo  = cvgl.ApplicationFileNo
        LEFT JOIN cte_officer_name     cpc_off      ON cpc_off.OfficerID         = cpc_db.CPCDoneBy
        LEFT JOIN cte_lo_mobile        lo_mob       ON lo_mob.OfficerID          = tl.CreditOfficerID
        LEFT JOIN cte_member_created_date mcd       ON mcd.OurBranchID           = cvgl.OurBranchID
                                                   AND mcd.ApplicationFileNo     = cvgl.ApplicationFileNo
