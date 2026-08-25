-- ============================================================================
--  lakehouse_uat.stg_brnet.testing_membertracker_t
--  TCL GLOW Memberwise Tracker (r_TCL_GLOSMemberTracker) -- Pipeline attributes
--
--  SOURCE: r_TCL_GLOSMemberTracker(TCLGLOWMemberwise Tracker) (3).sql
--    -- legacy T-SQL SP building a #MemberTracker temp table, grained on
--    (OurBranchID, ApplicationFileNo, MemberID). Every CTE below cites the
--    exact line range it reproduces.
--
--  SCOPE: GLOW only (same decision as the CPC pipeline). The SP's ILOS path
--    (t_iLOS*/t_ILOS* tables) is a separate source system, deferred.
--
--  GRAIN: (OurBranchID, AccountID, ClientID) -- per the requested key list.
--    This SP's NATIVE grain has no AccountID for most rows (it tracks
--    applications before/without a booked loan); to get a stable, non-null
--    AccountID key we drive from t_Loan the same way the CPC pipeline does.
--    This is consistent with the SP's OWN framing: every one of the
--    requested attributes carries "(Pipeline)" in its name, and the SP
--    itself does `DELETE FROM #MemberTracker WHERE FirstDisbursementDate
--    IS NOT NULL` (line 2528-2529) -- i.e. this report is specifically
--    about BOOKED-BUT-NOT-YET-DISBURSED loans ("the pipeline"). We
--    reproduce that filter directly: cte_loan requires
--    FirstDisbursementDate IS NULL.
--
--  *** UNCONFIRMED TABLES -- VERIFY BEFORE RUNNING ***
--  These 3 tables are not referenced anywhere in the existing CPC pipeline,
--  so their _inc_full names are a best-effort guess following this
--  lakehouse's established convention (preserve source casing + _inc_full):
--    1. stg_brnet.t_gloscrossselldetail_inc_full   (IsApplicant Optin cols)
--    2. stg_brnet.t_GLOSCrossSellMember_inc_full   (IsCoApplicant Optin col)
--    3. stg_brnet.t_ILOSActivityLog_inc_full       (Personal Discussion /
--       Recommendation Ended On -- see note below: this table's own
--       ILOSFileNO key is ILOS-format, and our rows are GLOW-sourced, so
--       this join may find no matches against real data even once the
--       table itself is confirmed to exist -- two separate things to verify)
--  Everything else used here (cv_glosclient_inc_full, cv_GlosApplication_
--  inc_full, cv_GLOSClientRelation_inc_full, t_Loan_inc_full,
--  t_accountcustomer_inc_full) is already confirmed working in the CPC
--  pipeline. v_CBStaggingRuleLog_inc_full is unconfirmed by itself, but
--  follows the exact same naming pattern as the already-confirmed sibling
--  table v_CBStaggingData_inc_full (same "v_CBStagging*" family).
--
--  *** ATTRIBUTES WITH NO LIVE GLOW SOURCE IN THE DEPLOYED SP ***
--  Confirmed by reading the SP directly (not assumed):
--    - IncomeCheckPass: only ever SET in the ILOS branch (t_ILOSAppRuleLog,
--      RuleID IN ('ILINCK','OHRICC')). No GLOW-side UPDATE exists anywhere
--      in this SP. The final SELECT's ISNULL(IncomeCheckPass,'No') makes
--      this a constant 'No' for every GLOW row.
--    - LAFStartedOn / LAFEndedOn: the GLOW output reads these from
--      LAFSupervisionStartedOn/LAFSupervisionEndedOn (v_GLOSActivitylog,
--      GLOSProcessActivityID='DDES'), and that populating UPDATE is
--      commented out in the deployed SP (lines 1238-1257, wrapped in
--      /* ... */). Per the report owner's explicit instruction, REACTIVATED
--      here (see cte_laf_supervision) rather than left NULL -- this is a
--      deliberate deviation from the SP as currently deployed, reproducing
--      its disabled-but-intended logic instead.
--    - PersonalDiscussionEndedOn / RecommendationEndedOn: these columns
--      don't exist in the GLOW final SELECT at all (lines 2535-2600) --
--      only in the ILOS final SELECT (lines 2801-2806), sourced from
--      t_ILOSActivityLog (ProcessActivityID = 'PEDI' / 'RECM'
--      respectively -- ILOS's individual-lending workflow steps). The GLOW
--      SELECT has "Cross Verification Started/Ended On" (GLOSProcessActivityID
--      = 'CPV2') in that exact position instead -- GLOW is a GROUP-lending
--      workflow (GRT/CGT/CPCV/cross-verification) with no per-applicant
--      "personal discussion" or "recommendation" step. Re-searched the full
--      2,940-line SP (case-insensitive, all spellings) for any GLOW-side
--      GLOSProcessActivityID or comment referencing either concept -- found
--      none. Per the report owner's explicit instruction, WIRED UP anyway
--      (see cte_ilos_activity_stage) using the SP's own t_ILOSActivityLog
--      logic verbatim, joined on ApplicationFileNo = ILOSFileNO -- flagged
--      as likely to find no matches against GLOW-sourced rows in practice
--      (different file-numbering systems), but implemented as requested
--      rather than left NULL.
-- ============================================================================

DROP TABLE IF EXISTS lakehouse_uat.stg_brnet.testing_membertracker_t;

CREATE TABLE lakehouse_uat.stg_brnet.testing_membertracker_t
USING DELTA
AS
WITH

        -- CTE 1: driving t_Loan dedup, collapsed to one row per (OurBranchID,
        --   AccountID) -- the requested grain has no LoanSeries key, so we
        --   pick the latest series deterministically.
        --   FirstDisbursementDate IS NULL reproduces the SP's own
        --   `DELETE FROM #MemberTracker WHERE FirstDisbursementDate IS NOT
        --   NULL` (line 2528-2529) -- this report is pipeline-only.
        cte_loan AS (
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, AccountID
                        ORDER BY LoanSeries DESC, COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_Loan_inc_full
                WHERE ApplicationID IS NOT NULL
                  AND FirstDisbursementDate IS NULL
            ) t WHERE t.rn = 1
        ),

        -- CTE 2: t_accountcustomer dedup -> resolves ClientID for the loan
        --   (identical pattern to the CPC pipeline's cte_acccust).
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

        -- CTE 3: cv_glosclient -> ApplicationFileNo, MemberID, MemberName,
        --   IsExistingClient, CBEnquiryRefNo, BR.Net Client ID components.
        --   FIX applied (same as the CPC pipeline's cte_tglc): the SP's own
        --   join from t_Loan to CV_GLOSClient (SP lines 308-310 /
        --   557-565: "ON #MemberTracker.OurBranchID = t_Loan.OurBranchID
        --   AND #MemberTracker.BRNETApplicationID = t_Loan.ApplicationID")
        --   has NO ClientID predicate -- dedup grain is (OurBranchID,
        --   BRNETApplicationID) only, tie-broken MemberID ASC (primary
        --   applicant) since our grain collapses each application to one
        --   representative row.
        --   *** ASSUMPTION: CBEnquiryRefNo is carried on cv_glosclient_inc_
        --   full. The SP's seed INSERT (line 315/398) references it
        --   unqualified against a CV_GLOSClient/CV_GLOSApplication join, so
        --   it lives on exactly one of the two source views -- if this
        --   column isn't present here, source it from cv_GlosApplication_
        --   inc_full instead. ***
        cte_glosclient AS (
            SELECT OurBranchID, BRNETApplicationID, ApplicationFileNo, MemberID,
                   Name AS MemberName, IsExistingClient, CBEnquiryRefNo
            FROM (
                SELECT OurBranchID, BRNETApplicationID, ApplicationFileNo, MemberID,
                       Name, IsExistingClient, CBEnquiryRefNo,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, BRNETApplicationID
                        ORDER BY MemberID ASC, COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_glosclient_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 3b: LAF Supervision (LAFStartedOn/LAFEndedOn), REACTIVATED per
        --   the report owner's instruction. The SP's own populating UPDATE
        --   (lines 1238-1246) is commented out in the deployed procedure --
        --   reproduced here from that commented-out block verbatim:
        --     SET LAFSupervisionStartedOn = v_GLOSActivitylog.StartOn
        --        ,LAFSupervisionEndedOn   = CASE WHEN ActivityStatusID <> 'INPR'
        --                                        THEN StatusOn ELSE NULL END
        --     FROM v_GLOSActivitylog
        --     WHERE GLOSProcessActivityID = 'DDES' --LAF - Supervision
        --   "v_GLOSActivitylog" here is the same activity-log view already
        --   confirmed as cv_GLOSActivityLog_inc_full in the CPC pipeline.
        --   The SP's UPDATE has no dedup, so on multiple matching activity
        --   rows SQL Server would apply one nondeterministically; deduped
        --   here to the latest row by StatusOn/StartOn for determinism.
        cte_laf_supervision AS (
            SELECT OurBranchID, ApplicationFileNo, LAFStartedOn, LAFEndedOn
            FROM (
                SELECT OurBranchID, ApplicationFileNo,
                       StartOn AS LAFStartedOn,
                       CASE WHEN ActivityStatusID <> 'INPR' THEN StatusOn ELSE NULL END AS LAFEndedOn,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo
                        ORDER BY COALESCE(StatusOn, StartOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSActivityLog_inc_full
                WHERE GLOSProcessActivityID = 'DDES'
            ) t WHERE t.rn = 1
        ),

        -- CTE 3c: t_ILOSActivityLog -> Personal Discussion / Recommendation
        --   Ended On, per SP lines 2017-2042 (implemented verbatim on
        --   direct instruction). *** UNCONFIRMED TABLE (see header) ***
        --   NOTE: the SP joins on `#MemberTracker.ApplicationFileNo =
        --   t_ILOSActivityLog.ILOSFileNO` -- ILOSFileNO is the ILOS
        --   schema's own file identifier. For our GLOW-sourced rows,
        --   ApplicationFileNo holds a GLOS-format file number, so this
        --   join will typically find no match unless the same file-number
        --   space is shared in this lakehouse's data -- verify against
        --   real values rather than assuming either way.
        --   Output is STRING (not a date), matching the temp table's own
        --   NVARCHAR(50) declaration: either a formatted timestamp (SP's
        --   CONVERT(nvarchar, StatusOn, 120), style 120 = 'yyyy-MM-dd
        --   HH:mm:ss') when the stage is COMP, or the literal 'Not Started'
        --   when PEND/blank -- exactly reproducing the SP's CASE WHEN.
        --   No dedup exists in the SP's own UPDATE (plain INNER JOIN, so
        --   SQL Server would apply one matching row nondeterministically
        --   on a fan-out); deduped here to the latest StatusOn/StartOn per
        --   stage for determinism.
        cte_ilos_activity_stage AS (
            SELECT ILOSFileNO,
                MAX(CASE WHEN ProcessActivityID = 'PEDI' THEN
                        CASE WHEN ActivityStatusID = 'COMP' THEN date_format(StatusOn, 'yyyy-MM-dd HH:mm:ss')
                             WHEN COALESCE(ActivityStatusID, '') IN ('', 'PEND') THEN 'Not Started'
                        END
                    END) AS PersonalDiscussionEndedOn,
                MAX(CASE WHEN ProcessActivityID = 'RECM' THEN
                        CASE WHEN ActivityStatusID = 'COMP' THEN date_format(StatusOn, 'yyyy-MM-dd HH:mm:ss')
                             WHEN COALESCE(ActivityStatusID, '') IN ('', 'PEND') THEN 'Not Started'
                        END
                    END) AS RecommendationEndedOn
            FROM (
                SELECT ILOSFileNO, ProcessActivityID, ActivityStatusID, StatusOn
                FROM (
                    SELECT ILOSFileNO, ProcessActivityID, ActivityStatusID, StatusOn,
                        ROW_NUMBER() OVER (
                            PARTITION BY ILOSFileNO, ProcessActivityID
                            ORDER BY COALESCE(StatusOn, StartOn) DESC
                        ) AS rn
                    FROM stg_brnet.t_ILOSActivityLog_inc_full
                    WHERE ProcessActivityID IN ('PEDI', 'RECM')
                ) d WHERE d.rn = 1
            ) dedup
            GROUP BY ILOSFileNO
        ),

        -- CTE 4: t_gloscrossselldetail -> IsApplicant Optin for Health
        --   Service / HospiIns. SP lines 930-937:
        --     SET IsApplicantOptinforHospiIns = CASE WHEN IsHospiCash=1 THEN 'Yes' ELSE 'No' END
        --        ,IsApplicantOptinforHealthIns = CASE WHEN IsHealthIns=1  THEN 'Yes' ELSE 'No' END
        --     FROM t_gloscrossselldetail
        --     ON OurBranchID + ApplicationFileNo + MemberID
        --   *** UNCONFIRMED TABLE (see header) ***
        cte_crosssell_applicant AS (
            SELECT OurBranchID, ApplicationFileNo, MemberID,
                   CASE WHEN IsHealthIns  = 1 THEN 'Yes' ELSE 'No' END AS IsApplicantOptinforHealthIns,
                   CASE WHEN IsHospiCash = 1 THEN 'Yes' ELSE 'No' END AS IsApplicantOptinforHospiIns
            FROM (
                SELECT OurBranchID, ApplicationFileNo, MemberID, IsHealthIns, IsHospiCash,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.t_gloscrossselldetail_inc_full
            ) t WHERE t.rn = 1
        ),

        -- CTE 5: CV_GLOSClientRelation -> RelationRefNo of the co-applicant
        --   (RelationRoleID = 'C'). SP lines 873-881. Needed as the join key
        --   for the co-applicant cross-sell flag below.
        cte_coapplicant_relation AS (
            SELECT OurBranchID, ApplicationFileNo, MemberID, RelationRefNo
            FROM (
                SELECT OurBranchID, ApplicationFileNo, MemberID, RelationRefNo,
                    ROW_NUMBER() OVER (
                        PARTITION BY OurBranchID, ApplicationFileNo, MemberID
                        ORDER BY COALESCE(ModifiedOn, CreatedOn) DESC
                    ) AS rn
                FROM stg_brnet.cv_GLOSClientRelation_inc_full
                WHERE RelationRoleID = 'C'
            ) t WHERE t.rn = 1
        ),

        -- CTE 6: t_GLOSCrossSellMember -> IsCoApplicant Optin for HospiIns.
        --   SP lines 949-957: existence-only flag ('Yes' if a matching row
        --   exists, else 'No' via the later NULL-backfill at lines 974-977),
        --   keyed OurBranchID + ApplicationFileNo + MemberID + RelationRefNo,
        --   filtered CrossSellTypeID LIKE '%Hospi%'.
        --   *** UNCONFIRMED TABLE (see header) ***
        cte_crosssell_coapplicant_hospi AS (
            SELECT DISTINCT OurBranchID, ApplicationFileNo, MemberID, RelationRefNo
            FROM stg_brnet.t_GLOSCrossSellMember_inc_full
            WHERE CrossSellTypeID LIKE '%Hospi%'
        ),

        -- CTE 7: v_CBStaggingRuleLog -> Rejected Reason(Rule Failed).
        --   SP lines 628-637: pipe-joined "RuleID-Remarks" for every FAILED
        --   rule (IsPassed=0) tied to the member's CBEnquiryRefNo.
        --   Table follows the same naming family as the already-confirmed
        --   v_CBStaggingData_inc_full.
        cte_rejected_reason AS (
            SELECT
                CBEnquiryRefNo,
                array_join(collect_list(CONCAT(RuleID, '-', Remarks)), ',') AS RejectedReasonRuleFailed
            FROM stg_brnet.v_CBStaggingRuleLog_inc_full
            WHERE COALESCE(CAST(IsPassed AS INT), 0) = 0
            GROUP BY CBEnquiryRefNo
        )

-- ============================================================================
-- FINAL SELECT
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
    acccust.ClientID                                                                AS ClientID,

    -- ════════════════════════════════════════════════════════════════
    -- 10 BUSINESS ATTRIBUTES -- TCL GLOW MEMBERWISE TRACKER (PIPELINE)
    -- ════════════════════════════════════════════════════════════════

    -- Always 'No' for GLOW -- see header note (ILOS-only source logic).
    'No'                                                                            AS IncomeCheckPass,

    COALESCE(cca.IsApplicantOptinforHealthIns, 'No')                                AS IsApplicantOptinforHealthIns,
    COALESCE(cca.IsApplicantOptinforHospiIns, 'No')                                 AS IsApplicantOptinforHospiIns,
    CASE WHEN cch.OurBranchID IS NOT NULL THEN 'Yes' ELSE 'No' END                  AS IsCoApplicantOptinforHospiIns,

    CASE WHEN cvgl.IsExistingClient = 0 THEN 'Fresh' ELSE 'Existing' END            AS IsExistingMember,

    -- Reactivated from the SP's commented-out block -- see cte_laf_supervision.
    laf.LAFStartedOn                                                                AS LAFStartedOn,
    laf.LAFEndedOn                                                                  AS LAFEndedOn,

    -- Wired to t_ILOSActivityLog per direct instruction -- see
    -- cte_ilos_activity_stage's header comment for the ILOSFileNO /
    -- ApplicationFileNo join-key caveat.
    ilos_stage.PersonalDiscussionEndedOn                                            AS PersonalDiscussionEndedOn,
    ilos_stage.RecommendationEndedOn                                                AS RecommendationEndedOn,

    rr.RejectedReasonRuleFailed                                                     AS RejectedReasonRuleFailed,

    -- ════════════════════════════════════════════════════════════════
    -- SHA1 CDC HASH -- covers all mutable business attributes above.
    -- Grain keys (OurBranchID/AccountID/ClientID) excluded.
    -- ════════════════════════════════════════════════════════════════
    CAST(sha1(CONCAT_WS('|',
        'No',
        COALESCE(CAST(COALESCE(cca.IsApplicantOptinforHealthIns, 'No') AS STRING), ''),
        COALESCE(CAST(COALESCE(cca.IsApplicantOptinforHospiIns, 'No') AS STRING), ''),
        COALESCE(CAST(CASE WHEN cch.OurBranchID IS NOT NULL THEN 'Yes' ELSE 'No' END AS STRING), ''),
        COALESCE(CAST(CASE WHEN cvgl.IsExistingClient = 0 THEN 'Fresh' ELSE 'Existing' END AS STRING), ''),
        COALESCE(CAST(rr.RejectedReasonRuleFailed AS STRING), ''),
        COALESCE(CAST(laf.LAFStartedOn AS STRING), ''),
        COALESCE(CAST(laf.LAFEndedOn AS STRING), ''),
        COALESCE(CAST(ilos_stage.PersonalDiscussionEndedOn AS STRING), ''),
        COALESCE(CAST(ilos_stage.RecommendationEndedOn AS STRING), '')
    )) AS BINARY)                                                                   AS HASHBYTESSHA1

FROM      cte_loan             tl

LEFT JOIN cte_acccust          acccust      ON tl.OurBranchID          = acccust.OurBranchID
                                           AND tl.AccountID              = acccust.AccountID

-- FIX (per SP lines 308-310 / 557-565): t_Loan -> CV_GLOSClient joins ONLY
--   on (OurBranchID, BrnetApplicationID = ApplicationID) -- current branch,
--   no ClientID predicate. See cte_glosclient's header comment.
LEFT JOIN cte_glosclient       cvgl         ON cvgl.OurBranchID          = tl.OurBranchID
                                           AND cvgl.BRNETApplicationID    = tl.ApplicationID

LEFT JOIN cte_crosssell_applicant cca       ON cca.OurBranchID           = cvgl.OurBranchID
                                           AND cca.ApplicationFileNo      = cvgl.ApplicationFileNo
                                           AND cca.MemberID               = cvgl.MemberID

LEFT JOIN cte_coapplicant_relation coapp    ON coapp.OurBranchID         = cvgl.OurBranchID
                                           AND coapp.ApplicationFileNo     = cvgl.ApplicationFileNo
                                           AND coapp.MemberID              = cvgl.MemberID

LEFT JOIN cte_crosssell_coapplicant_hospi cch ON cch.OurBranchID         = cvgl.OurBranchID
                                           AND cch.ApplicationFileNo       = cvgl.ApplicationFileNo
                                           AND cch.MemberID                = cvgl.MemberID
                                           AND cch.RelationRefNo           = coapp.RelationRefNo

LEFT JOIN cte_rejected_reason  rr           ON rr.CBEnquiryRefNo         = cvgl.CBEnquiryRefNo

LEFT JOIN cte_laf_supervision  laf          ON laf.OurBranchID           = cvgl.OurBranchID
                                           AND laf.ApplicationFileNo       = cvgl.ApplicationFileNo

-- SP's own join shape (ApplicationFileNo = ILOSFileNO) -- see
-- cte_ilos_activity_stage's header comment for the caveat this implies
-- for GLOW-sourced ApplicationFileNo values.
LEFT JOIN cte_ilos_activity_stage ilos_stage ON ilos_stage.ILOSFileNO      = cvgl.ApplicationFileNo
