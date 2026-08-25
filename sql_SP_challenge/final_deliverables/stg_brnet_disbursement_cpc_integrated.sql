--=============================================================================
--  lakehouse_uat.stg_brnet.testing_t
--  TCL CPC Details Report -- FULL REBUILD (79 business columns)
--
--  This is a from-scratch rebuild of the CPC report pipeline. The previous
--  revision of this file had accreted CTEs from several UNRELATED report
--  integrations that happened to share this same scratch table (GRT/TAT,
--  PTP + Accrued Interest from the DPD/collections SP, GST/Stamp Duty, KLI,
--  DigiLocker, NACH/Enach, e-Stamp, Net-Off, D-Sign, ID-verification via
--  VOTVER/VOTVEC). NONE of those ever fed the CPC report's final SELECT --
--  they were dead weight. This rebuild removes all of it and keeps only
--  what the 79-column TCL CPC Details Report actually needs, then adds the
--  ~35 columns that were previously missing.
--
--  SCOPE (confirmed with report owner):
--    * GLOW only. The legacy SP's ILOS path (raw t_iLOS* tables) is a
--      completely separate source system with no _inc_full tables landed
--      in this lakehouse yet -- deferred to a future pass.
--    * Grain stays LOAN-driven: (OurBranchID, AccountID, LoanSeries,
--      ClientID), same as the previous revision (driven from cte_loan /
--      t_Loan_inc_full). Applications that have not yet reached loan
--      booking are out of scope, same limitation as before.
--
--  SOURCE: r_TCL_CPCDtls (TCL CPC Details Report).sql -- legacy T-SQL SP,
--    ~125 sequential UPDATE passes over a #CPCDetail temp table. Every CTE
--    below cites the SP section it reproduces.
--
--  *** UNCONFIRMED TABLES -- VERIFY BEFORE RUNNING ***
--  The following 7 source tables are referenced here for the first time in
--  this pipeline (no existing CTE anywhere established their _inc_full
--  name) -- the names below follow this pipeline's existing convention
--  (preserve source casing, add `_inc_full`) but are GUESSES, not confirmed
--  landings. Run the pre-flight cell in the notebook first.
--    1. stg_brnet.t_BCMaintenance_inc_full
--    2. stg_brnet.t_SystemBranchRegion_inc_full
--    3. stg_brnet.t_TCL_ZoneRegionMap_inc_full
--    4. stg_brnet.t_BranchUserCode_inc_full
--    5. stg_brnet.t_Place_inc_full
--    6. stg_brnet.t_villagesurveydet_inc_full
--    7. stg_brnet.t_LOSLoanApprovalDetail_inc_full
--    8. stg_brnet.cv_GLOSClientAddress_inc_full
--  Also ASSUMED: t_SystemBranchSetting_inc_full carries BranchName,
--    BCCodeID and GPSCoordinate columns (only StateID was read from it
--    before); cv_ClientBankTransaction_inc_full carries a BeneficiaryName,
--    IMPSBatchID and AccountID (bank-account, distinct from LoanAccountID)
--    column; cv_GLOSClientBankAccount_inc_full carries AccountID/IFSCCode.
--  *** LoanScheme is left as the raw LoanSchemeID (not resolved to a name)
--    -- same as the previous revision. The legacy SP resolves it via a
--    dedicated f_GetLoanSchemeName(BankID, SchemeID) function, not the
--    generic user-code lookup this pipeline uses elsewhere, and no scheme/
--    product master table has been identified in this lakehouse yet.
-- ============================================================================

DROP TABLE IF EXISTS lakehouse_uat.stg_brnet.testing_t;

CREATE TABLE lakehouse_uat.stg_brnet.testing_t
USING DELTA
AS
WITH

        -- ====================================================================
        -- DRIVING LOAN + basic dedup helpers (unchanged from previous revision)
        -- ====================================================================

        -- CTE 1: driving t_Loan dedup
        cte_loan AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, AccountID, LoanSeries
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_Loan_inc_full WHERE ApplicationID IS NOT NULL
            ) t WHERE t.rn = 1
        ),

        -- CTE 2: first-source account (handles branch-transferred loans)
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

        -- CTE 3: t_accountcustomer dedup -> resolves ClientID for the loan
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

        -- ====================================================================
        -- BANK TRANSACTION / PAYMENT (unchanged from previous revision)
        -- SP Sec."Payment Amount / Payment Status / UTR NO", Sec."Name Match Score",
        --   Sec."BeneficiaryName", Sec."HDFC Remarks", Sec."BatchID"
        -- ====================================================================
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
                FROM stg_brnet.cv_ClientBankTransaction_inc_full
                WHERE RecordStatusID = 'A'
            ) t WHERE t.rn = 1
        ),

        -- CTE: t_RBLBankTrxExtractLog -- XML -> UTRNo (step 1)
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

        -- CTE: cv_ClientBankTransaction -> UTRNo (step 2 fallback)
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

        -- CTE: Online Fund Transfer Log -- Initiation (Stage 'FI')
        cte_oftl_init AS (
            SELECT * FROM (
                SELECT
                    OurBranchID, TrxRowID,
                    PassedBy AS PaymentInitiatedBy,
                    PassedOn AS PaymentInitiatedOn,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, TrxRowID
                        ORDER BY COALESCE(PassedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_OnLineFundTransferLog_inc_full
                WHERE FTStageID = 'FI'
            ) t WHERE t.rn = 1
        ),

        -- CTE: Online Fund Transfer Log -- Approval (Stage 'FA')
        cte_oftl_app AS (
            SELECT * FROM (
                SELECT
                    OurBranchID, TrxRowID,
                    PassedBy AS PaymentApprovedBy,
                    PassedOn AS PaymentApprovedOn,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, TrxRowID
                        ORDER BY COALESCE(PassedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_OnLineFundTransferLog_inc_full
                WHERE FTStageID = 'FA'
            ) t WHERE t.rn = 1
        ),

        -- CTE: WFLoanBooking -- Loan Booked By & On
        cte_wfloanbooking AS (
            SELECT * FROM (
                SELECT
                    OurBranchID, ApplicationID,
                    CreatedBy  AS LoanBookedBy,
                    BookedDate AS LoanBookedOn,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationID
                        ORDER BY COALESCE(BookedDate, ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_WFLoanBooking_inc_full
            ) t WHERE t.rn = 1
        ),

        -- ====================================================================
        -- t_WFLoanApplication -- Center/Group (once submitted), stage/status IDs
        -- SP Sec."Center ID / Center Name / Group ID / Group Name" (post-WF),
        --   Sec."Application Current Stage" (WFAdvStageID), Sec."CPC Status" area
        -- ====================================================================
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

        -- CTE: t_GroupMember -> GroupID (SubGroupID) + CenterID, pre-WF fallback
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

        -- CTE: t_Group -> VillageID + GroupName ("Center Name" once GroupID resolved)
        -- SP naming note: the report's "Center ID"/"Center Name" is the
        --   workflow-level GroupID, and "Group ID"/"Group Name" is the
        --   SubGroupID -- legacy GLOS terminology carried into the report.
        cte_group AS (
            SELECT OurBranchID, GroupID, VillageID, GroupName
            FROM (
                SELECT OurBranchID, GroupID, VillageID, GroupName,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, GroupID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_Group_inc_full
            ) t WHERE t.rn = 1
        ),

        -- ====================================================================
        -- cv_glosclient -- Member ID/Name/MobileNo, Application Number, seed
        --   CurrentStatus (GLOSPActivityStatusID)
        -- SP Sec."Application Number", Sec."Member ID / Member Name",
        --   Sec."Applicant Mobile" (GLOW seed)
        -- ====================================================================
        -- FIX (per legacy SP lines 308-310): the SP's own join from t_Loan to
        --   CV_GLOSClient is ON (OurBranchID, BrnetApplicationID = ApplicationID)
        --   ONLY — there is NO ClientID predicate. The SP's own "ClientID"
        --   report column is a SEPARATE, independently-derived field
        --   (ISNULL(ExistingClientID, BRNetClientID), line 230) — it is not
        --   used to join CV_GLOSClient to t_Loan, and is NOT the same ID
        --   space as t_accountcustomer.ClientID (our grain's ClientID).
        --   Dedup grain dropped from (OurBranchID, BRNETApplicationID,
        --   BRNETClientID) to (OurBranchID, BRNETApplicationID) — matching
        --   the SP exactly — picking MemberID ASC (the primary applicant)
        --   as the representative row per application, since our approved
        --   loan-driven grain collapses each application to one output row
        --   (every sample row observed so far has MemberID = 1).
        cte_tglc AS (
            SELECT OurBranchID, BRNETApplicationID, ApplicationFileNo,
                   MemberID, Name AS MemberName, MobileNo AS ApplicantMobile,
                   GLOSPActivityStatusID
            FROM (
                SELECT OurBranchID, BRNETApplicationID, ApplicationFileNo,
                       MemberID, Name, MobileNo, GLOSPActivityStatusID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, BRNETApplicationID
                        ORDER BY MemberID ASC, COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_glosclient_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE: cv_GlosApplication -> VillageID + OfficerID (SP's LOName = this
        --   OfficerID) -- feeds LOMobile, LOName, Area Name.
        cte_glosapp AS (
            SELECT OurBranchID, ApplicationFileNo, VillageID, OfficerID
            FROM (
                SELECT OurBranchID, ApplicationFileNo, VillageID, OfficerID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GlosApplication_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE: cv_GlosClientLoan -> Loan Scheme ID (raw, see header note)
        cte_gclloan AS (
            SELECT OurBranchID, ApplicationFileNo, MemberID, LoanSchemeID
            FROM (
                SELECT OurBranchID, ApplicationFileNo, MemberID, LoanSchemeID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                        ORDER BY LoanCycleNo DESC
                    ) AS rn
                FROM stg_brnet.cv_GlosClientLoan_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE: generic officer-name resolver (f_GetOfficerName equivalent) --
        --   reused for LOName, Owner Name, CPC Done By, Branch Manager.
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

        -- CTE: Loan Officer Mobile Resolver (SP line ~1156):
        --   #CPCDetail.LOName = t_GLOSApplication.OfficerID
        --   INNER JOIN t_AccountOfficer ON OfficerID = LOName
        --   INNER JOIN t_Client ON ClientID = t_AccountOfficer.ClientID -> Mobile
        -- (Kept as LEFT JOIN / no ClientTypeID filter -- see previous revision's
        --  notes; SP uses INNER + no filter, this is deliberately more robust.)
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
                LEFT JOIN stg_brnet.t_client_inc_full cli
                       ON cli.ClientID = ao.ClientID
            ) t WHERE t.rn = 1
        ),

        -- CTE: t_AccountOfficer -> Branch Manager name.
        -- SP Sec."Branch Manager": ReportingBranchID = branch, OfficerTypeID='BM',
        --   ResignedDate IS NULL.
        cte_branch_manager AS (
            SELECT ReportingBranchID, Name AS BranchManagerName
            FROM (
                SELECT ReportingBranchID, Name,
                    ROW_NUMBER() OVER (
                        PARTITION BY ReportingBranchID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_AccountOfficer_inc_full
                WHERE OfficerTypeID = 'BM'
                  AND ResignedDate IS NULL
            ) t WHERE t.rn = 1
        ),

        -- ====================================================================
        -- BRANCH / BC / REGION / ZONE hierarchy
        -- SP Sec."BC ID / BC Name", Sec."RegionID / Zone / RegionName",
        --   Sec."Branch ID / Branch Name"
        -- ====================================================================

        -- CTE: t_SystemBranchSetting -- extended vs. previous revision to also
        --   carry BranchName, BCCodeID, GPSCoordinate (branch GPS for the
        --   village-distance calc). *** ASSUMED columns -- verify. ***
        cte_branchsetting AS (
            SELECT OurBranchID, BranchName, BCCodeID, GPSCoordinate
            FROM (
                SELECT OurBranchID, BranchName, BCCodeID, GPSCoordinate,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_SystemBranchSetting_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE: t_BCMaintenance -> BC Name.  *** UNCONFIRMED TABLE ***
        cte_bc_desc AS (
            SELECT BCCodeID, BCDescription
            FROM (
                SELECT BCCodeID, BCDescription,
                    ROW_NUMBER() OVER (
                        PARTITION BY BCCodeID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_BCMaintenance_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE: t_SystemBranchRegion -> RegionID per branch. *** UNCONFIRMED TABLE ***
        cte_branch_region AS (
            SELECT OurBranchID, RegionID
            FROM (
                SELECT OurBranchID, RegionID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_SystemBranchRegion_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE: t_TCL_ZoneRegionMap -> ZoneID per RegionID. *** UNCONFIRMED TABLE ***
        cte_zone_map AS (
            SELECT RegionID, ZoneID
            FROM (
                SELECT RegionID, ZoneID,
                    ROW_NUMBER() OVER (
                        PARTITION BY RegionID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_TCL_ZoneRegionMap_inc_full
                WHERE Status = 1
            ) t WHERE t.rn = 1
        ),

        -- CTE: t_BankUserCode -> Zone description ('BankZoneID')
        cte_zone_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (
                        PARTITION BY SubCodeID
                        ORDER BY COALESCE(CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_BankUserCode_inc_full
                WHERE ID = 'BankZoneID'
            ) t WHERE t.rn = 1
        ),

        -- CTE: t_BankUserCode -> Region description ('BankRegionID')
        -- SP note: this is a DIFFERENT lookup family than Zone's
        --   t_TCL_ZoneRegionMap -- two independent mechanisms for two
        --   conceptually similar fields, per the SP.
        cte_region_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (
                        PARTITION BY SubCodeID
                        ORDER BY COALESCE(CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_BankUserCode_inc_full
                WHERE ID = 'BankRegionID'
            ) t WHERE t.rn = 1
        ),

        -- ====================================================================
        -- CPC STATUS / ACTIVITY LOG cascades
        -- SP Sec."CPC Status", Sec."Application Current Stage" (+Status),
        --   Sec."Owner Name", Sec."CPC Done By / Started On / Completed On"
        -- ====================================================================

        -- CTE: latest CPCV/CSOV activity per (branch,file) -> base CPC Status
        -- + carries GLOSProcessActivityID for the "Application Current Stage"
        -- activity-description fallback (SP orders GLOSProcessStageID DESC,
        -- ActivityOrderNo DESC -- same ordering used here).
        cte_gal_current AS (
            SELECT OurBranchID, ApplicationFileNo, ActivityStatusID, GLOSProcessActivityID
            FROM (
                SELECT OurBranchID, ApplicationFileNo, ActivityStatusID, GLOSProcessActivityID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY GLOSProcessStageID DESC,
                                 ActivityOrderNo    DESC,
                                 COALESCE(StatusOn, StartOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSActivityLog_inc_full
                WHERE ActivityStatusID IS NOT NULL
            ) t WHERE t.rn = 1
        ),

        cte_activity_status_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (PARTITION BY SubCodeID ORDER BY SubCodeID) AS rn
                FROM stg_brnet.t_SystemCodeDetail_inc_full
                WHERE ID = 'ActivityStatusID'
            ) t WHERE t.rn = 1
        ),

        -- CTE: t_SystemCodeDetail -> GLOSProcessActivityID description (activity
        --   name, e.g. "CPC Verification") -- feeds Application Current Stage.
        cte_activity_id_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (PARTITION BY SubCodeID ORDER BY SubCodeID) AS rn
                FROM stg_brnet.t_SystemCodeDetail_inc_full
                WHERE ID = 'GLOSProcessActivityID'
            ) t WHERE t.rn = 1
        ),

        cte_wfadvstage_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (PARTITION BY SubCodeID ORDER BY SubCodeID) AS rn
                FROM stg_brnet.t_SystemCodeDetail_inc_full
                WHERE ID = 'WFAdvStageID'
            ) t WHERE t.rn = 1
        ),

        cte_wfappstatus_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (PARTITION BY SubCodeID ORDER BY SubCodeID) AS rn
                FROM stg_brnet.t_SystemCodeDetail_inc_full
                WHERE ID = 'WFAppStatusID'
            ) t WHERE t.rn = 1
        ),

        cte_tac_status_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (PARTITION BY SubCodeID ORDER BY SubCodeID) AS rn
                FROM stg_brnet.t_SystemCodeDetail_inc_full
                WHERE ID = 'TACStatusID'
            ) t WHERE t.rn = 1
        ),

        -- CTE: base CPC Status from CPCV/CSOV activity (SP's 3-way cascade,
        --   collapsed to CPCV-else-CSOV since both use the same PEND/INPR/COMP
        --   -> Pending/In-Progress/Completed mapping).
        cte_cpc_status_base AS (
            SELECT OurBranchID, ApplicationFileNo,
                   COALESCE(cpcv.ActivityStatusID, csov.ActivityStatusID) AS RawStatus
            FROM (
                SELECT DISTINCT OurBranchID, ApplicationFileNo FROM stg_brnet.cv_GLOSActivityLog_inc_full
            ) keys
            LEFT JOIN (
                SELECT OurBranchID, ApplicationFileNo, ActivityStatusID
                FROM (
                    SELECT OurBranchID, ApplicationFileNo, ActivityStatusID,
                        ROW_NUMBER() OVER (
                            PARTITION BY OurBranchID, ApplicationFileNo
                            ORDER BY COALESCE(StatusOn, StartOn) DESC
                        ) AS rn
                    FROM stg_brnet.cv_GLOSActivityLog_inc_full
                    WHERE GLOSProcessActivityID = 'CPCV'
                ) t WHERE t.rn = 1
            ) cpcv ON cpcv.OurBranchID = keys.OurBranchID AND cpcv.ApplicationFileNo = keys.ApplicationFileNo
            LEFT JOIN (
                SELECT OurBranchID, ApplicationFileNo, ActivityStatusID
                FROM (
                    SELECT OurBranchID, ApplicationFileNo, ActivityStatusID,
                        ROW_NUMBER() OVER (
                            PARTITION BY OurBranchID, ApplicationFileNo
                            ORDER BY COALESCE(StatusOn, StartOn) DESC
                        ) AS rn
                    FROM stg_brnet.cv_GLOSActivityLog_inc_full
                    WHERE GLOSProcessActivityID = 'CSOV'
                ) t WHERE t.rn = 1
            ) csov ON csov.OurBranchID = keys.OurBranchID AND csov.ApplicationFileNo = keys.ApplicationFileNo
        ),

        -- CTE: latest send-back row's own status code (SNT/SUB), for the
        --   "Query Raised"/"Query Responded" CPC-Status override.
        cte_sendback_latest_status AS (
            SELECT OurBranchID, ApplicationFileNo, MemberID, SendBackStatusID
            FROM (
                SELECT OurBranchID, ApplicationFileNo, MemberID, SendBackStatusID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                        ORDER BY CreatedOn DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSSendBackChkLstData_inc_full
                WHERE ActivityID = 'CPCV'
            ) t WHERE t.rn = 1
        ),

        -- ====================================================================
        -- BENE CHECK (bank-account verification) -- SP Sec."Bene Check Status",
        --   Sec."Bene check Done By/On"
        -- ====================================================================
        cte_benecheck_status AS (
            SELECT
                keys.OurBranchID, keys.ApplicationFileNo, keys.MemberID,
                COALESCE(primary_.StatusCase, fallback.StatusCase) AS BeneCheckStatus,
                COALESCE(primary_.DoneBy,     fallback.DoneBy)     AS BeneCheckDoneBy,
                COALESCE(primary_.DoneOn,     fallback.DoneOn)     AS BeneCheckDoneOn
            FROM (
                SELECT DISTINCT OurBranchID, ApplicationFileNo, MemberID
                FROM stg_brnet.cv_GLOSMemberRuleLog_inc_full
                WHERE RuleID IN ('BENCHK', 'BENVAL')
            ) keys
            LEFT JOIN (
                SELECT OurBranchID, ApplicationFileNo, MemberID,
                    CASE WHEN GLOSRuleStatusID = 'FAIL' AND Remarks LIKE '%Name Mismatch%' AND COALESCE(CAST(IsOverridden AS INT),0) = 1 THEN 'Name Mismatch Overridden'
                         WHEN GLOSRuleStatusID = 'FAIL' AND Remarks LIKE '%Name Mismatch%' THEN 'Name Mismatch'
                         WHEN GLOSRuleStatusID = 'FAIL' THEN 'Failure'
                         WHEN GLOSRuleStatusID = 'PASS' THEN 'Success'
                         WHEN COALESCE(CAST(IsOverridden AS INT),0) = 1 THEN 'Beneficiary Check Rule is Overridden'
                    END AS StatusCase,
                    COALESCE(OverriddenBy, PassedBy) AS DoneBy,
                    StatusOn AS DoneOn
                FROM (
                    SELECT *,
                        ROW_NUMBER() OVER (
                            PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                            ORDER BY COALESCE(StatusOn) DESC
                        ) AS rn
                    FROM stg_brnet.cv_GLOSMemberRuleLog_inc_full
                    WHERE RuleID = 'BENVAL'
                      AND GLOSProcessActivityID IN ('BACV', 'DAEN')
                      AND GLOSProcessStageID = '20APP'
                ) t WHERE t.rn = 1
            ) primary_ ON primary_.OurBranchID = keys.OurBranchID
                      AND primary_.ApplicationFileNo = keys.ApplicationFileNo
                      AND primary_.MemberID = keys.MemberID
            LEFT JOIN (
                SELECT OurBranchID, ApplicationFileNo, MemberID,
                    CASE WHEN GLOSRuleStatusID = 'FAIL' AND Remarks LIKE '%Name Mismatch%' AND COALESCE(CAST(IsOverridden AS INT),0) = 1 THEN 'Name Mismatch Overridden'
                         WHEN GLOSRuleStatusID = 'FAIL' AND Remarks LIKE '%Name Mismatch%' THEN 'Name Mismatch'
                         WHEN GLOSRuleStatusID = 'FAIL' THEN 'Failure'
                         WHEN GLOSRuleStatusID = 'PASS' THEN 'Success'
                         WHEN COALESCE(CAST(IsOverridden AS INT),0) = 1 THEN 'Beneficiary Check Rule is Overridden'
                    END AS StatusCase,
                    COALESCE(OverriddenBy, PassedBy) AS DoneBy,
                    StatusOn AS DoneOn
                FROM (
                    SELECT *,
                        ROW_NUMBER() OVER (
                            PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                            ORDER BY COALESCE(StatusOn) DESC
                        ) AS rn
                    FROM stg_brnet.cv_GLOSMemberRuleLog_inc_full
                    WHERE RuleID = 'BENCHK'
                      AND GLOSProcessActivityID = 'BACV'
                      AND GLOSProcessStageID <> '20APP'
                ) t WHERE t.rn = 1
            ) fallback ON fallback.OurBranchID = keys.OurBranchID
                      AND fallback.ApplicationFileNo = keys.ApplicationFileNo
                      AND fallback.MemberID = keys.MemberID
        ),

        -- CTE: Beneficary Member bucket. SP Sec."Beneficary Member bucket":
        --   BACV activity PEND->'LO', INPR->'CPC'; overridden to 'Completed'
        --   at SELECT time when Bene Check Status = 'Success' (applied below).
        cte_bene_bucket AS (
            SELECT OurBranchID, ApplicationFileNo,
                   CASE WHEN ActivityStatusID = 'PEND' THEN 'LO'
                        WHEN ActivityStatusID = 'INPR' THEN 'CPC'
                   END AS FileBucket
            FROM (
                SELECT OurBranchID, ApplicationFileNo, ActivityStatusID,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY COALESCE(StatusOn, StartOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSActivityLog_inc_full
                WHERE GLOSProcessActivityID = 'BACV'
            ) t WHERE t.rn = 1
        ),

        -- ====================================================================
        -- BANK ACCOUNT ON FILE + Beni check remarks / CDC audit fields
        -- SP Sec."Bank Account No", Sec."IFSCCode", Sec."Beni check Rejection Remarks",
        --   Sec."ModifiedBy/Modifiedon", Sec."BenecheckSendbackCount",
        --   Sec."PreviousBenecheckRemarks"
        -- Extended vs. previous revision to also carry AccountID/IFSCCode.
        -- *** ASSUMED columns on cv_GLOSClientBankAccount_inc_full -- verify.***
        -- ====================================================================
        cte_client_bank_acc_latest AS (
            SELECT * FROM (
                SELECT
                    OurBranchID, ApplicationFileNo, MemberID,
                    AccountID, IFSCCode, ModifiedBy, ModifiedOn, BACVRemarks,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                        ORDER BY SerialID DESC, COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSClientBankAccount_inc_full
                WHERE AccountTypeID = 'SB'
            ) t WHERE t.rn = 1
        ),

        cte_benecheck_all_remarks AS (
            SELECT
                OurBranchID, ApplicationFileNo, MemberID,
                concat_ws(',', collect_list(trim(PreviousBACVRemarks))) AS PreviousBenecheckRemarks
            FROM (
                SELECT OurBranchID, ApplicationFileNo, MemberID, PreviousBACVRemarks
                FROM stg_brnet.t_GLOSClientBankAccount_inc_full
                WHERE AccountTypeID = 'SB'
                  AND PreviousBACVRemarks IS NOT NULL
                  AND trim(PreviousBACVRemarks) <> ''
                ORDER BY OurBranchID, ApplicationFileNo, MemberID, SerialID
            )
            GROUP BY OurBranchID, ApplicationFileNo, MemberID
        ),

        -- ====================================================================
        -- QUERIES / SENDBACK -- SP Sec."Queries", Sec."Live/Previous Queries",
        --   Sec."Query Raised Count", Sec."Sendback Count", Sec."Member CPC Status"
        -- ====================================================================
        cte_cpc_query_max_dates AS (
            SELECT
                OurBranchID, ApplicationFileNo, MemberID,
                MIN(CreatedOn) AS MinCreatedOn,
                MAX(CreatedOn) AS MaxCreatedOn,
                MAX(ActionOn)  AS MaxActionOn,
                COUNT(DISTINCT SendBackRefNo) AS SendbackCount
            FROM stg_brnet.cv_GLOSSendBackChkLstData_inc_full
            WHERE ActivityID = 'CPCV'
            GROUP BY OurBranchID, ApplicationFileNo, MemberID
        ),

        cte_cpc_queries_agg AS (
            SELECT
                sb.OurBranchID, sb.ApplicationFileNo, sb.MemberID,
                COUNT(CASE WHEN COALESCE(sb.IsNotOK, false) = true THEN 1 END) AS QueryRaisedCount,
                array_join(array_sort(collect_set(CASE WHEN COALESCE(sb.IsNotOK, false) = true THEN cl.Description END)), '|') AS Queries,
                array_join(array_sort(collect_set(CASE WHEN COALESCE(sb.IsNotOK, false) = true AND sb.CreatedOn = md.MaxCreatedOn THEN cl.Description END)), '|') AS LiveQueries,
                array_join(collect_list(CASE WHEN COALESCE(sb.IsNotOK, false) = true AND sb.CreatedOn = md.MaxCreatedOn THEN sb.CheckListRemarks END), '|') AS LiveRemarks,
                array_join(array_sort(collect_set(CASE WHEN COALESCE(sb.IsNotOK, false) = true AND sb.CreatedOn < md.MaxCreatedOn THEN cl.Description END)), '|') AS PreviousQueries,
                array_join(array_sort(collect_set(CASE WHEN COALESCE(sb.IsNotOK, false) = true AND sb.CreatedOn < md.MaxCreatedOn THEN sb.ResolvedRemarks END)), '|') AS PreviousRemarks,
                date_format(md.MaxCreatedOn, 'dd/MM/yyyy hh:mm a') AS LastCPCQueryRaisedOn,
                date_format(md.MaxActionOn, 'dd/MM/yyyy hh:mm a')  AS LastCPCQueryRespondedOn
            FROM stg_brnet.cv_GLOSSendBackChkLstData_inc_full sb
            INNER JOIN stg_brnet.t_GLOSCheckList_inc_full cl
                    ON cl.CheckListID = sb.CheckListID
            INNER JOIN cte_cpc_query_max_dates md
                    ON md.OurBranchID = sb.OurBranchID
                   AND md.ApplicationFileNo = sb.ApplicationFileNo
                   AND md.MemberID = sb.MemberID
            WHERE sb.ActivityID = 'CPCV'
            GROUP BY sb.OurBranchID, sb.ApplicationFileNo, sb.MemberID, md.MaxCreatedOn, md.MaxActionOn
        ),

        cte_cpc_done_by AS (
            SELECT * FROM (
                SELECT
                    OurBranchID, ApplicationFileNo,
                    OfficerID AS CPCDoneBy,
                    StartOn   AS CPCStartedOn,
                    CASE WHEN ActivityStatusID = 'COMP' THEN StatusOn ELSE NULL END AS CPCCompletedOn,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY COALESCE(StatusOn, StartOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSActivityLog_inc_full
                WHERE GLOSProcessActivityID = 'CPCV'
            ) t WHERE t.rn = 1
        ),

        cte_member_created_date AS (
            SELECT * FROM (
                SELECT
                    OurBranchID, ApplicationFileNo,
                    StartOn AS MemberCreatedDate,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY COALESCE(StatusOn, StartOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSActivityLog_inc_full
                WHERE GLOSProcessActivityID IN ('MDEN', 'MEMC')
                  AND ActivityStatusID IS NOT NULL
            ) t WHERE t.rn = 1
        ),

        -- ====================================================================
        -- VILLAGE / ADDRESS / DISTANCE
        -- SP Sec."VillageID / Village Name", Sec."District / Pincode / Area Name",
        --   Sec."Branch to Village Distance"
        -- ====================================================================

        -- CTE: t_BranchUserCode -> Village Name (primary). *** UNCONFIRMED TABLE ***
        cte_village_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (PARTITION BY SubCodeID ORDER BY SubCodeID) AS rn
                FROM stg_brnet.t_BranchUserCode_inc_full
                WHERE ID = 'VillageID'
            ) t WHERE t.rn = 1
        ),

        -- CTE: t_Place -> fallback Village Name / Area Name description.
        -- *** UNCONFIRMED TABLE ***
        cte_place_desc AS (
            SELECT PlaceID, Description
            FROM (
                SELECT PlaceID, Description,
                    ROW_NUMBER() OVER (
                        PARTITION BY PlaceID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_Place_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE: cv_GLOSClientAddress (mailing address) -> District/Pincode.
        -- *** UNCONFIRMED TABLE ***
        cte_mailing_address AS (
            SELECT * FROM (
                SELECT
                    OurBranchID, ApplicationFileNo, MemberID,
                    StateID, DistrictID, Pincode,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSClientAddress_inc_full
                WHERE IsMailingAddress = true
            ) t WHERE t.rn = 1
        ),

        -- CTE: t_BankUserCode -> District description ('DistrictID').
        -- SP resolves via f_GetDistrictName(StateID, DistrictID); this
        --   pipeline's established pattern resolves single-key user-codes
        --   only, so the StateID half of the SP's key is NOT applied here
        --   -- flag if district codes are not globally unique in your lake.
        cte_district_desc AS (
            SELECT SubCodeID, Description
            FROM (
                SELECT SubCodeID, Description,
                    ROW_NUMBER() OVER (PARTITION BY SubCodeID ORDER BY SubCodeID) AS rn
                FROM stg_brnet.t_BankUserCode_inc_full
                WHERE ID = 'DistrictID'
            ) t WHERE t.rn = 1
        ),

        -- CTE: t_villagesurveydet -> village lat/long, keyed SurveyNo = VillageID.
        -- *** UNCONFIRMED TABLE ***
        cte_village_geo AS (
            SELECT SurveyNo, latitude, longitude
            FROM (
                SELECT SurveyNo, latitude, longitude,
                    ROW_NUMBER() OVER (
                        PARTITION BY SurveyNo
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_villagesurveydet_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE: Applicant/Co-Applicant relations
        -- SP Sec."Co-Applicant Mobile no" (RelationRoleID='C'),
        --   Sec."No of dependents" (RelationRoleID='G')
        cte_coapplicant_mobile AS (
            SELECT OurBranchID, ApplicationFileNo, MemberID, Mobile AS CoApplicantMobile
            FROM (
                SELECT OurBranchID, ApplicationFileNo, MemberID, Mobile,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSClientRelation_inc_full
                WHERE RelationRoleID = 'C'
            ) t WHERE t.rn = 1
        ),

        cte_dependents AS (
            SELECT OurBranchID, ApplicationFileNo, MemberID, COUNT(1) AS NoOfDependents
            FROM stg_brnet.cv_GLOSClientRelation_inc_full
            WHERE RelationRoleID = 'G'
            GROUP BY OurBranchID, ApplicationFileNo, MemberID
        ),

        -- CTE: t_LOSLoanApprovalDetail -> CreditApprovedBy (GLOS path only --
        --   the ILOS path is a hard-coded bug in the legacy SP, not reproduced
        --   since ILOS is out of scope here anyway). *** UNCONFIRMED TABLE ***
        cte_credit_approved AS (
            SELECT OurBranchID, ApplicationFileNo, MemberID, StatusBy AS CreditApprovedBy
            FROM (
                SELECT OurBranchID, ApplicationFileNo, MemberID, StatusBy,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_LOSLoanApprovalDetail_inc_full
                WHERE SourceTypeID = 'GLOS'
            ) t WHERE t.rn = 1
        )

-- ============================================================================
-- FINAL SELECT -- 4 grain/metadata + 79 CPC report columns + CDC hash
-- ============================================================================
SELECT
    'BRNET'                                                                         AS SourceSystemName,

    tl.HKC_ETLMasterExecutionId,
    tl.HKC_ETLDetailExecutionId,
    tl.HKC_EDWSourceSystemID,
    tl.DQStatus                                                                     AS DQStatus,
    tl.DQId                                                                         AS DQId,

    tl.OurBranchID,
    tl.AccountID,
    tl.LoanSeries                                                                   AS LoanSeries,
    COALESCE(acccust.ClientID, acccust_src.ClientID)                                AS ClientID,

    -- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    -- 79 BUSINESS COLUMNS -- TCL CPC DETAILS REPORT
    -- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    sbs.BCCodeID                                                                    AS BCID,
    bcd.BCDescription                                                               AS BCName,
    br.RegionID                                                                     AS RegionID,
    zdesc.Description                                                               AS Zone,
    rdesc.Description                                                               AS RegionName,
    tl.OurBranchID                                                                  AS BranchID,
    sbs.BranchName                                                                  AS BranchName,
    COALESCE(gm.GroupID, wfla.GroupID)                                              AS CenterID,
    grp.GroupName                                                                   AS CenterName,
    COALESCE(gm.SubGroupID, wfla.SubGroupID)                                        AS GroupID,
    -- *** BEST EFFORT: no confirmed sub-group-name table identified; reusing
    --     the Center's GroupName until a dedicated sub-group name source is
    --     confirmed. Verify against sample data. ***
    grp.GroupName                                                                   AS GroupName,
    'GLOW'                                                                          AS ApplicationType,
    cvgl.ApplicationFileNo                                                          AS ApplicationNumber,
    cvgl.MemberID                                                                   AS MemberID,
    cvgl.MemberName                                                                 AS MemberName,
    COALESCE(gcl.LoanSchemeID, wfla.LoanSchemeID)                                   AS LoanScheme,
    tl.AccountID                                                                    AS LoanAccountID,
    tl.LoanAmount                                                                   AS LoanAmount,
    tl.RepaymentTerm                                                                AS Tenure,

    CASE
        WHEN sbk_status.SendBackStatusID = 'SNT' THEN 'Query Raised'
        WHEN sbk_status.SendBackStatusID = 'SUB' THEN 'Query Responded'
        WHEN cs.RawStatus = 'PEND' THEN 'Pending'
        WHEN cs.RawStatus = 'INPR' THEN 'In-Progress'
        WHEN cs.RawStatus = 'COMP' THEN 'Completed'
        WHEN bucket.FileBucket IS NOT NULL THEN 'Not Started'
        ELSE NULL
    END                                                                             AS CPCStatus,

    COALESCE(tacd.Description, wfstg.Description, actid.Description)               AS ApplicationCurrentStage,
    COALESCE(wfsts.Description, cstat.Description)                                  AS ApplicationCurrentStageStatus,

    COALESCE(cpc_off.Name, cpc_db.CPCDoneBy)                                        AS OwnerName,
    cpc_db.CPCDoneBy                                                                AS CPCDoneBy,
    cpc_db.CPCStartedOn                                                             AS CPCStartedOn,
    cpc_db.CPCCompletedOn                                                           AS CPCCompletedOn,

    CASE
        WHEN COALESCE(qa.QueryRaisedCount, 0) = 0 AND (qa.PreviousQueries IS NULL OR TRIM(qa.PreviousQueries) = '') THEN 'No'
        ELSE 'Yes'
    END                                                                             AS IsQueryRaised,
    date_format(qmd.MinCreatedOn, 'dd/MM/yyyy hh:mm a')                             AS QueryRaisedOn,
    qa.Queries                                                                      AS Queries,

    CASE WHEN cbt.AccountID = gcba.AccountID THEN bene.BeneCheckStatus ELSE NULL END AS BeneCheckStatus,
    CASE WHEN cbt.AccountID = gcba.AccountID THEN CAST(cbt.Score AS DOUBLE) ELSE NULL END AS NameMatchScore,
    CASE WHEN cbt.AccountID = gcba.AccountID THEN bene.BeneCheckDoneBy ELSE NULL END AS BeneCheckDoneBy,
    bene.BeneCheckDoneOn                                                            AS BeneCheckDoneOn,

    wflb.LoanBookedBy                                                               AS LoanBookedBy,
    wflb.LoanBookedOn                                                               AS LoanBookedON,
    tl.disbursedby                                                                  AS LoanDisbursedBy,
    tl.FirstDisbursementDate                                                        AS LoanDisbursedOn,

    CAST(cbt.NetDisbursementAmount AS DECIMAL(18,2))                                AS PaymentAmount,
    oftl_init.PaymentInitiatedBy                                                    AS PaymentInitiatedBy,
    oftl_init.PaymentInitiatedOn                                                    AS PaymentInitiatedOn,
    oftl_app.PaymentApprovedBy                                                      AS PaymentApprovedBy,
    oftl_app.PaymentApprovedOn                                                      AS PaymentApprovedOn,

    CASE
        WHEN tl.FirstDisbursementDate IS NOT NULL AND cbt.TrxStatusID NOT IN ('COM', 'ERR') THEN 'In-Pending'
        WHEN tl.FirstDisbursementDate IS NOT NULL AND cbt.TrxStatusID = 'COM' THEN 'Success'
        WHEN tl.FirstDisbursementDate IS NOT NULL AND cbt.TrxStatusID = 'ERR' THEN 'Error'
        ELSE NULL
    END                                                                             AS PaymentStatus,
    cbt.TrxStatusOn                                                                 AS PaymentStatusOn,

    COALESCE(utrx.txn_utr, cbtu.UTRNo)                                              AS UTRNo,
    CASE WHEN cbt.AccountID = gcba.AccountID
         THEN TRIM(regexp_replace(cbt.ErrorMsg, r'[\t\r\n\"]+', ' '))
         ELSE NULL END                                                              AS HDFCRemarks,
    COALESCE(qmd.SendbackCount, 0)                                                  AS SendbackCount,

    bm.BranchManagerName                                                            AS BranchManager,
    lo_name.Name                                                                    AS LOName,

    CASE WHEN bene.BeneCheckStatus = 'Success' THEN 'Completed' ELSE bucket.FileBucket END AS BeneficaryMemberBucket,
    CASE WHEN cbt.AccountID = gcba.AccountID THEN cbt.BeneficiaryName ELSE NULL END  AS BeneficiaryName,

    CONCAT('="', CAST(gcba.AccountID AS STRING), '"')                               AS BankAccountNo,
    gcba.IFSCCode                                                                   AS IFSCCode,
    cbt.IMPSBatchID                                                                  AS BatchID,

    grp.VillageID                                                                   AS VillageID,
    COALESCE(vdesc.Description, pdesc_village.Description)                         AS VillageName,

    COALESCE(qa.QueryRaisedCount, 0)                                                AS QueryRaisedCount,

    CASE
        WHEN COALESCE(qa.QueryRaisedCount, 0) = 0 AND (qa.PreviousQueries IS NULL OR TRIM(qa.PreviousQueries) = '')
             AND COALESCE(cs.RawStatus, cvgl.GLOSPActivityStatusID, '') <> 'PEND' THEN 'Completed'
        WHEN qa.LastCPCQueryRespondedOn IS NOT NULL THEN 'Query Responded'
        WHEN qa.LastCPCQueryRaisedOn IS NOT NULL THEN 'Query Raised'
        ELSE CASE COALESCE(cs.RawStatus, cvgl.GLOSPActivityStatusID)
                 WHEN 'PEND' THEN 'Pending'
                 WHEN 'COMP' THEN 'Completed'
                 WHEN 'REJT' THEN 'Rejected'
                 ELSE COALESCE(cstat.Description, 'Not Started')
             END
    END                                                                             AS MemberCPCStatus,

    qa.LastCPCQueryRaisedOn                                                         AS LastCPCQueryRaisedOn,
    qa.LastCPCQueryRespondedOn                                                       AS LastCPCQueryRespondedOn,
    qa.PreviousQueries                                                              AS PreviousQueries,
    qa.PreviousRemarks                                                              AS PreviousRemarks,
    date_format(qmd.MaxCreatedOn, 'dd/MM/yyyy hh:mm a')                             AS LiveCPCQueryRaisedOn,
    date_format(qmd.MaxActionOn, 'dd/MM/yyyy hh:mm a')                              AS LiveCPCQueryRespondedOn,
    qa.LiveQueries                                                                  AS LiveQueries,
    qa.LiveRemarks                                                                  AS LiveRemarks,

    lo_mob.LOMobile                                                                 AS LOMobile,
    cvgl.ApplicantMobile                                                            AS ApplicantMobile,
    coapp.CoApplicantMobile                                                         AS CoApplicantMobileNo,

    CASE WHEN sbs.GPSCoordinate IS NOT NULL AND vgeo.latitude IS NOT NULL THEN
        ROUND(
            6371 * 2 * asin(sqrt(
                pow(sin(radians(vgeo.latitude  - CAST(split(sbs.GPSCoordinate, ',')[0] AS DOUBLE)) / 2), 2) +
                cos(radians(CAST(split(sbs.GPSCoordinate, ',')[0] AS DOUBLE))) * cos(radians(vgeo.latitude)) *
                pow(sin(radians(vgeo.longitude - CAST(split(sbs.GPSCoordinate, ',')[1] AS DOUBLE)) / 2), 2)
            ))
        , 2)
    ELSE NULL END                                                                   AS BranchToVillageDistance,

    COALESCE(distd.Description, addr.DistrictID)                                    AS District,
    addr.Pincode                                                                    AS Pincode,
    pdesc_area.Description                                                         AS AreaName,

    CASE
        WHEN COALESCE(qa.QueryRaisedCount, 0) = 0 AND (qa.PreviousQueries IS NULL OR TRIM(qa.PreviousQueries) = '') THEN 'FTR'
        ELSE 'NFTR'
    END                                                                             AS CPCFTRFlag,
    CASE
        WHEN COALESCE(qa.QueryRaisedCount, 0) = 0 AND (qa.PreviousQueries IS NULL OR TRIM(qa.PreviousQueries) = '') THEN 'No'
        ELSE 'Yes'
    END                                                                             AS QueryRaised,

    COALESCE(dep.NoOfDependents, 0)                                                 AS NoOfDependents,
    date_format(mcd.MemberCreatedDate, 'dd-MMM-yyyy')                               AS MemberCreatedDate,
    credit.CreditApprovedBy                                                        AS CreditApprovedBy,

    RTRIM(LTRIM(regexp_replace(regexp_replace(COALESCE(gcba.BACVRemarks, ''), r'[\t\r\n\",-]+', ''), '  ', ' '))) AS BeniCheckRejectionRemarks,

    gcba.ModifiedBy                                                                 AS ModifiedBy,
    gcba.ModifiedOn                                                                 AS Modifiedon,

    CASE WHEN COALESCE(bar.PreviousBenecheckRemarks, '') = '' THEN 0
         ELSE size(split(bar.PreviousBenecheckRemarks, ',')) END                    AS BenecheckSendbackCount,
    bar.PreviousBenecheckRemarks                                                    AS PreviousBenecheckRemarks,

    -- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    -- SHA1 CDC HASH -- covers all mutable business columns above.
    -- Grain keys (OurBranchID/AccountID/ClientID/LoanSeries) and pure
    -- geography lookups (BC/Region/Zone/Branch names, which change only
    -- when master data changes, not per-application state) ARE still
    -- included below, matching the "define row identity, not its state"
    -- principle only for the 4 true grain keys.
    -- â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    CAST(sha1(CONCAT_WS('|',
        COALESCE(CAST(sbs.BCCodeID AS STRING), ''),
        COALESCE(CAST(bcd.BCDescription AS STRING), ''),
        COALESCE(CAST(br.RegionID AS STRING), ''),
        COALESCE(CAST(zdesc.Description AS STRING), ''),
        COALESCE(CAST(rdesc.Description AS STRING), ''),
        COALESCE(CAST(sbs.BranchName AS STRING), ''),
        COALESCE(CAST(COALESCE(gm.GroupID, wfla.GroupID) AS STRING), ''),
        COALESCE(CAST(grp.GroupName AS STRING), ''),
        COALESCE(CAST(COALESCE(gm.SubGroupID, wfla.SubGroupID) AS STRING), ''),
        COALESCE(CAST(cvgl.ApplicationFileNo AS STRING), ''),
        COALESCE(CAST(cvgl.MemberID AS STRING), ''),
        COALESCE(CAST(cvgl.MemberName AS STRING), ''),
        COALESCE(CAST(COALESCE(gcl.LoanSchemeID, wfla.LoanSchemeID) AS STRING), ''),
        COALESCE(CAST(tl.LoanAmount AS STRING), ''),
        COALESCE(CAST(tl.RepaymentTerm AS STRING), ''),
        COALESCE(CAST(
            CASE
                WHEN sbk_status.SendBackStatusID = 'SNT' THEN 'Query Raised'
                WHEN sbk_status.SendBackStatusID = 'SUB' THEN 'Query Responded'
                WHEN cs.RawStatus = 'PEND' THEN 'Pending'
                WHEN cs.RawStatus = 'INPR' THEN 'In-Progress'
                WHEN cs.RawStatus = 'COMP' THEN 'Completed'
                WHEN bucket.FileBucket IS NOT NULL THEN 'Not Started'
                ELSE NULL
            END AS STRING), ''),
        COALESCE(CAST(COALESCE(tacd.Description, wfstg.Description, actid.Description) AS STRING), ''),
        COALESCE(CAST(COALESCE(wfsts.Description, cstat.Description) AS STRING), ''),
        COALESCE(CAST(COALESCE(cpc_off.Name, cpc_db.CPCDoneBy) AS STRING), ''),
        COALESCE(CAST(cpc_db.CPCDoneBy AS STRING), ''),
        COALESCE(CAST(cpc_db.CPCStartedOn AS STRING), ''),
        COALESCE(CAST(cpc_db.CPCCompletedOn AS STRING), ''),
        COALESCE(date_format(qmd.MinCreatedOn, 'dd/MM/yyyy hh:mm a'), ''),
        COALESCE(CAST(qa.Queries AS STRING), ''),
        COALESCE(CAST(CASE WHEN cbt.AccountID = gcba.AccountID THEN bene.BeneCheckStatus ELSE NULL END AS STRING), ''),
        COALESCE(CAST(CASE WHEN cbt.AccountID = gcba.AccountID THEN CAST(cbt.Score AS DOUBLE) ELSE NULL END AS STRING), ''),
        COALESCE(CAST(CASE WHEN cbt.AccountID = gcba.AccountID THEN bene.BeneCheckDoneBy ELSE NULL END AS STRING), ''),
        COALESCE(CAST(bene.BeneCheckDoneOn AS STRING), ''),
        COALESCE(CAST(wflb.LoanBookedBy AS STRING), ''),
        COALESCE(CAST(wflb.LoanBookedOn AS STRING), ''),
        COALESCE(CAST(tl.disbursedby AS STRING), ''),
        COALESCE(CAST(tl.FirstDisbursementDate AS STRING), ''),
        COALESCE(CAST(CAST(cbt.NetDisbursementAmount AS DECIMAL(18,2)) AS STRING), ''),
        COALESCE(CAST(oftl_init.PaymentInitiatedBy AS STRING), ''),
        COALESCE(CAST(oftl_init.PaymentInitiatedOn AS STRING), ''),
        COALESCE(CAST(oftl_app.PaymentApprovedBy AS STRING), ''),
        COALESCE(CAST(oftl_app.PaymentApprovedOn AS STRING), ''),
        COALESCE(CAST(
            CASE
                WHEN tl.FirstDisbursementDate IS NOT NULL AND cbt.TrxStatusID NOT IN ('COM', 'ERR') THEN 'In-Pending'
                WHEN tl.FirstDisbursementDate IS NOT NULL AND cbt.TrxStatusID = 'COM' THEN 'Success'
                WHEN tl.FirstDisbursementDate IS NOT NULL AND cbt.TrxStatusID = 'ERR' THEN 'Error'
                ELSE NULL
            END AS STRING), ''),
        COALESCE(CAST(cbt.TrxStatusOn AS STRING), ''),
        COALESCE(CAST(COALESCE(utrx.txn_utr, cbtu.UTRNo) AS STRING), ''),
        COALESCE(CASE WHEN cbt.AccountID = gcba.AccountID THEN TRIM(regexp_replace(cbt.ErrorMsg, r'[\t\r\n\"]+', ' ')) ELSE NULL END, ''),
        COALESCE(CAST(COALESCE(qmd.SendbackCount, 0) AS STRING), ''),
        COALESCE(CAST(bm.BranchManagerName AS STRING), ''),
        COALESCE(CAST(lo_name.Name AS STRING), ''),
        COALESCE(CAST(CASE WHEN bene.BeneCheckStatus = 'Success' THEN 'Completed' ELSE bucket.FileBucket END AS STRING), ''),
        COALESCE(CAST(CASE WHEN cbt.AccountID = gcba.AccountID THEN cbt.BeneficiaryName ELSE NULL END AS STRING), ''),
        COALESCE(CAST(gcba.AccountID AS STRING), ''),
        COALESCE(CAST(gcba.IFSCCode AS STRING), ''),
        COALESCE(CAST(cbt.IMPSBatchID AS STRING), ''),
        COALESCE(CAST(grp.VillageID AS STRING), ''),
        COALESCE(CAST(COALESCE(vdesc.Description, pdesc_village.Description) AS STRING), ''),
        COALESCE(CAST(COALESCE(qa.QueryRaisedCount, 0) AS STRING), ''),
        COALESCE(CAST(qa.LastCPCQueryRaisedOn AS STRING), ''),
        COALESCE(CAST(qa.LastCPCQueryRespondedOn AS STRING), ''),
        COALESCE(CAST(qa.PreviousQueries AS STRING), ''),
        COALESCE(CAST(qa.PreviousRemarks AS STRING), ''),
        COALESCE(date_format(qmd.MaxCreatedOn, 'dd/MM/yyyy hh:mm a'), ''),
        COALESCE(date_format(qmd.MaxActionOn, 'dd/MM/yyyy hh:mm a'), ''),
        COALESCE(CAST(qa.LiveQueries AS STRING), ''),
        COALESCE(CAST(qa.LiveRemarks AS STRING), ''),
        COALESCE(CAST(lo_mob.LOMobile AS STRING), ''),
        COALESCE(CAST(cvgl.ApplicantMobile AS STRING), ''),
        COALESCE(CAST(coapp.CoApplicantMobile AS STRING), ''),
        COALESCE(CAST(COALESCE(distd.Description, addr.DistrictID) AS STRING), ''),
        COALESCE(CAST(addr.Pincode AS STRING), ''),
        COALESCE(CAST(pdesc_area.Description AS STRING), ''),
        COALESCE(CAST(COALESCE(dep.NoOfDependents, 0) AS STRING), ''),
        COALESCE(date_format(mcd.MemberCreatedDate, 'dd-MMM-yyyy'), ''),
        COALESCE(CAST(credit.CreditApprovedBy AS STRING), ''),
        COALESCE(RTRIM(LTRIM(regexp_replace(regexp_replace(COALESCE(gcba.BACVRemarks, ''), r'[\t\r\n\",-]+', ''), '  ', ' '))), ''),
        COALESCE(CAST(gcba.ModifiedBy AS STRING), ''),
        COALESCE(CAST(gcba.ModifiedOn AS STRING), ''),
        COALESCE(CAST(bar.PreviousBenecheckRemarks AS STRING), '')
    )) AS BINARY)                                                                   AS HASHBYTESSHA1

FROM      cte_loan_src         tl

LEFT JOIN cte_acccust          acccust      ON tl.AccountID        = acccust.AccountID
                                           AND tl.OurBranchID       = acccust.OurBranchID
LEFT JOIN cte_acccust          acccust_src  ON tl.eff_account      = acccust_src.AccountID
                                           AND tl.eff_branch        = acccust_src.OurBranchID

LEFT JOIN cte_cbt              cbt          ON tl.OurBranchID      = cbt.OurBranchID
                                           AND tl.AccountID         = cbt.LoanAccountID
                                           AND tl.LoanSeries        = cbt.LoanSeries
LEFT JOIN cte_utr_rbl          utrx         ON utrx.TrxRefID       = cbt.TrxRowID
LEFT JOIN cte_cbt_utr          cbtu         ON cbtu.OurBranchID    = tl.OurBranchID
                                           AND cbtu.ClientID        = COALESCE(acccust.ClientID, acccust_src.ClientID)
                                           AND cbtu.LoanAccountID   = tl.AccountID
LEFT JOIN cte_oftl_init        oftl_init    ON oftl_init.OurBranchID = cbt.OurBranchID
                                           AND oftl_init.TrxRowID     = cbt.TrxRowID
LEFT JOIN cte_oftl_app         oftl_app     ON oftl_app.OurBranchID  = cbt.OurBranchID
                                           AND oftl_app.TrxRowID      = cbt.TrxRowID
LEFT JOIN cte_tac_status_desc  tacd         ON tacd.SubCodeID        = cbt.TrxStatusID

-- FIX (per legacy SP lines 488-500 / 566-572): both WFLoanApplication and
--   WFLoanBooking are keyed by the SP on t_Loan's CURRENT branch/ApplicationID
--   (#CPCDetail.OurBranchID / .ApplicationID) — not the transfer-origin
--   eff_branch. Also tl.ApplicationID is never null here (cte_loan already
--   filters WHERE ApplicationID IS NOT NULL), so the srcloan.ApplicationID
--   fallback was dead code for this join and has been dropped.
LEFT JOIN cte_wfla             wfla         ON tl.OurBranchID      = wfla.OurBranchID
                                           AND tl.ApplicationID     = wfla.ApplicationID
LEFT JOIN cte_wfloanbooking    wflb         ON wflb.OurBranchID      = tl.OurBranchID
                                           AND wflb.ApplicationID     = tl.ApplicationID

-- FIX (per legacy SP lines 308-310): t_Loan -> CV_GLOSClient joins ONLY on
--   (OurBranchID, BrnetApplicationID = ApplicationID) — current branch, no
--   ClientID predicate (see cte_tglc's header comment for why the previous
--   revision's BRNETClientID = acccust.ClientID predicate was wrong).
LEFT JOIN cte_tglc             cvgl         ON cvgl.OurBranchID        = tl.OurBranchID
                                           AND cvgl.BRNETApplicationID  = tl.ApplicationID

LEFT JOIN cte_gclloan          gcl          ON gcl.OurBranchID         = cvgl.OurBranchID
                                           AND gcl.ApplicationFileNo    = cvgl.ApplicationFileNo
                                           AND gcl.MemberID             = cvgl.MemberID
LEFT JOIN cte_glosapp          gapp         ON gapp.OurBranchID        = cvgl.OurBranchID
                                           AND gapp.ApplicationFileNo   = cvgl.ApplicationFileNo
LEFT JOIN cte_officer_name     lo_name      ON lo_name.OfficerID       = gapp.OfficerID
LEFT JOIN cte_lo_mobile        lo_mob       ON lo_mob.OfficerID        = COALESCE(gapp.OfficerID, tl.CreditOfficerID)
LEFT JOIN cte_officer_name     cpc_off      ON cpc_off.OfficerID       = cpc_db.CPCDoneBy

LEFT JOIN cte_groupmember      gm           ON gm.ClientID             = acccust.ClientID
LEFT JOIN cte_group            grp          ON grp.OurBranchID         = tl.OurBranchID
                                           AND grp.GroupID              = COALESCE(gm.GroupID, wfla.GroupID)

-- BC / Region / Zone / Branch hierarchy
LEFT JOIN cte_branchsetting    sbs          ON sbs.OurBranchID         = tl.OurBranchID
LEFT JOIN cte_bc_desc          bcd          ON bcd.BCCodeID            = sbs.BCCodeID
LEFT JOIN cte_branch_region    br           ON br.OurBranchID          = tl.OurBranchID
LEFT JOIN cte_zone_map         zmap         ON zmap.RegionID           = br.RegionID
LEFT JOIN cte_zone_desc        zdesc        ON zdesc.SubCodeID         = zmap.ZoneID
LEFT JOIN cte_region_desc      rdesc        ON rdesc.SubCodeID         = br.RegionID
LEFT JOIN cte_branch_manager   bm           ON bm.ReportingBranchID    = tl.OurBranchID

-- CPC Status / Application Current Stage cascades
LEFT JOIN cte_cpc_status_base  cs           ON cs.OurBranchID          = cvgl.OurBranchID
                                           AND cs.ApplicationFileNo     = cvgl.ApplicationFileNo
LEFT JOIN cte_sendback_latest_status sbk_status ON sbk_status.OurBranchID = cvgl.OurBranchID
                                           AND sbk_status.ApplicationFileNo = cvgl.ApplicationFileNo
                                           AND sbk_status.MemberID       = cvgl.MemberID
LEFT JOIN cte_bene_bucket      bucket       ON bucket.OurBranchID      = cvgl.OurBranchID
                                           AND bucket.ApplicationFileNo  = cvgl.ApplicationFileNo
LEFT JOIN cte_gal_current      galcur       ON galcur.OurBranchID      = tl.OurBranchID
                                           AND galcur.ApplicationFileNo  = cvgl.ApplicationFileNo
LEFT JOIN cte_activity_id_desc actid        ON actid.SubCodeID          = galcur.GLOSProcessActivityID
LEFT JOIN cte_activity_status_desc cstat    ON cstat.SubCodeID          = COALESCE(galcur.ActivityStatusID, cvgl.GLOSPActivityStatusID)
LEFT JOIN cte_wfadvstage_desc  wfstg        ON wfstg.SubCodeID          = wfla.WFAdvStageID
LEFT JOIN cte_wfappstatus_desc wfsts        ON wfsts.SubCodeID          = wfla.WFAppStatusID

-- Bene Check
LEFT JOIN cte_benecheck_status bene         ON bene.OurBranchID        = cvgl.OurBranchID
                                           AND bene.ApplicationFileNo    = cvgl.ApplicationFileNo
                                           AND bene.MemberID             = cvgl.MemberID

-- Bank account on file / remarks / CDC audit
LEFT JOIN cte_client_bank_acc_latest gcba   ON gcba.OurBranchID        = cvgl.OurBranchID
                                           AND gcba.ApplicationFileNo    = cvgl.ApplicationFileNo
                                           AND gcba.MemberID             = cvgl.MemberID
LEFT JOIN cte_benecheck_all_remarks bar     ON bar.OurBranchID          = cvgl.OurBranchID
                                           AND bar.ApplicationFileNo      = cvgl.ApplicationFileNo
                                           AND bar.MemberID               = cvgl.MemberID

-- Queries / Sendback
LEFT JOIN cte_cpc_query_max_dates qmd       ON qmd.OurBranchID          = cvgl.OurBranchID
                                           AND qmd.ApplicationFileNo      = cvgl.ApplicationFileNo
                                           AND qmd.MemberID               = cvgl.MemberID
LEFT JOIN cte_cpc_queries_agg  qa           ON qa.OurBranchID           = cvgl.OurBranchID
                                           AND qa.ApplicationFileNo       = cvgl.ApplicationFileNo
                                           AND qa.MemberID                = cvgl.MemberID
LEFT JOIN cte_cpc_done_by      cpc_db       ON cpc_db.OurBranchID       = cvgl.OurBranchID
                                           AND cpc_db.ApplicationFileNo   = cvgl.ApplicationFileNo
LEFT JOIN cte_member_created_date mcd       ON mcd.OurBranchID          = cvgl.OurBranchID
                                           AND mcd.ApplicationFileNo      = cvgl.ApplicationFileNo

-- Village / address / distance
LEFT JOIN cte_village_desc     vdesc        ON vdesc.SubCodeID          = grp.VillageID
LEFT JOIN cte_place_desc       pdesc_village ON pdesc_village.PlaceID   = grp.VillageID
LEFT JOIN cte_place_desc       pdesc_area   ON pdesc_area.PlaceID       = gapp.VillageID
LEFT JOIN cte_village_geo      vgeo         ON vgeo.SurveyNo            = grp.VillageID
LEFT JOIN cte_mailing_address  addr         ON addr.OurBranchID         = cvgl.OurBranchID
                                           AND addr.ApplicationFileNo     = cvgl.ApplicationFileNo
                                           AND addr.MemberID              = cvgl.MemberID
LEFT JOIN cte_district_desc    distd        ON distd.SubCodeID          = addr.DistrictID
LEFT JOIN cte_coapplicant_mobile coapp      ON coapp.OurBranchID        = cvgl.OurBranchID
                                           AND coapp.ApplicationFileNo    = cvgl.ApplicationFileNo
                                           AND coapp.MemberID             = cvgl.MemberID
LEFT JOIN cte_dependents       dep          ON dep.OurBranchID          = cvgl.OurBranchID
                                           AND dep.ApplicationFileNo      = cvgl.ApplicationFileNo
                                           AND dep.MemberID               = cvgl.MemberID
LEFT JOIN cte_credit_approved  credit       ON credit.OurBranchID       = cvgl.OurBranchID
                                           AND credit.ApplicationFileNo   = cvgl.ApplicationFileNo
                                           AND credit.MemberID            = cvgl.MemberID
