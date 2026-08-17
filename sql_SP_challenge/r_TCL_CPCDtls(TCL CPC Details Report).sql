--/*
DECLARE @FromRegionID			NVARCHAR(25)	= NULL,
		@ToRegionID				NVARCHAR(25)	= NULL,
		@FromBranchID			BranchID		= NULL,
		@ToBranchID				BranchID		= NULL,
		@FromDate				SMALLDATETIME	= '01 JAN 2024',
		@ToDate					SMALLDATETIME	= '30 JAN 2024',
		@IsDisbAccounts			BIT				= 0,
		@IsCPCNotStarted		BIT				= 0,
		@ApplicationTypeID		NVARCHAR(25)    = 'GLOW',
		@OperatorID				NVARCHAR(25)	= 'CS',
		@LoginBranchID			NVARCHAR(6)		= '1000',
		@IsDataLakeJob			NVARCHAR(6)		= 0
--*/
BEGIN

	SET NOCOUNT ON

	DROP TABLE IF EXISTS #CPCDetail,#Branch

	DECLARE @BankID			NVARCHAR(6),
			@LanguageID		NVARCHAR(3),
			@WorkingDate	SMALLDATETIME, 
			@EodDate		DATETIME,
			@MaxEODDate		SMALLDATETIME
	
	SELECT @BankID = BankID FROM t_SystemBankSetting
	SELECT @LanguageID = dbo.f_GetDefaultLanguageID()

	CREATE TABLE #CPCDetail
    (
    OurBranchID                         NVARCHAR(6)
    ,ApplicationFileNo                  NVARCHAR(20)
    ,MemberID                           SMALLINT
    ,ApplicationID                      NVARCHAR(20)
    ,ClientID                           NVARCHAR(30)
    ,[BC ID]                            NVARCHAR(50)
    ,[BC Name]                          NVARCHAR(100)
    ,[Branch ID]                        NVARCHAR(6)
    ,[Branch Name]                      NVARCHAR(100)
    ,[Center ID]                        NVARCHAR(50)
    ,[Center Name]                      NVARCHAR(100)
    ,[Group ID]                         NVARCHAR(50)
    ,[Group Name]                       NVARCHAR(100)
    ,[Application Number]               NVARCHAR(50)
    ,[Member ID]                        SMALLINT
    ,[Member Name]                      NVARCHAR(100)
	,[Loan Scheme ID]					NVARCHAR(25)
    ,[Loan Scheme]                      NVARCHAR(50)
    ,[Loan Account ID]                  NVARCHAR(50)
    ,[Loan Amount]                      DECIMAL(18,0)
    ,[Tenure]                           INT
    ,[CPC Status]                       NVARCHAR(50)
    ,[Application Current Stage]        NVARCHAR(100)
    ,[Application current Stage Status] NVARCHAR(250)
    ,[Owner Name]                       NVARCHAR(100)
    ,[CPC Done By]                      NVARCHAR(100)
    ,[CPC Started On]                   DATETIME
    ,[CPC Completed On]                 DATETIME
    ,[Is Query Raised]                  NVARCHAR(50) DEFAULT 'NO'
    ,[Query Raised On]                  DATETIME
    ,[Queries]                          NVARCHAR(max)
    ,[Bene Check Status]                NVARCHAR(500)
    ,[Bene check Done By]               NVARCHAR(100)
    ,[Bene check Done On]               DATETIME
    ,[Loan Booked By]                   NVARCHAR(100)
    ,[Loan Booked ON]                   DATETIME
    ,[Loan Disbursed By]   NVARCHAR(100)
    ,[Loan Disbursed On]                DATETIME
    ,[Payment Amount]                   DECIMAL(18,2)
    ,[Payment Initiated by]             NVARCHAR(100)
    ,[Payment Initiated On]             DATETIME
    ,[Payment Approved By]              NVARCHAR(100)
    ,[Payment Approved On]              DATETIME
    ,[Payment Status]                   NVARCHAR(50)
    ,[Payment Status On]                DATETIME
    ,[UTR NO]                           NVARCHAR(50)
    ,SendBackStatusID					NVARCHAR(50)
    ,AccountID							NVARCHAR(30)
    ,LoanSeries							SMALLINT
	,TrxRowID                           BIGINT
	,TrxRefID							BIGINT
    ,[HDFC Remarks]						NVARCHAR(510)
    ,[Sendback Count]                   BIGINT
    ,BranchManager                      NVARCHAR(250)
    ,LOName                             NVARCHAR(250)
    ,[File bucket]                      NVARCHAR(250)
    ,IFSCCode                           NVARCHAR(50)
    ,BankAcNo                           NVARCHAR(100)
    ,BankName                           NVARCHAR(250)
    ,BankBranch                         NVARCHAR(250)
    ,AccountHoldername                  NVARCHAR(250)
    ,BeneficiaryName                    NVARCHAR(250)
    ,RegionID                           NVARCHAR(250)
    ,BatchID                            NVARCHAR(50)
    ,VillageID                          NVARCHAR(25)
    ,VillageName                        NVARCHAR(100)
    ,[Query Raised Count]               INT
    ,[Member CPC Status]                NVARCHAR(50)
    ,[Last CPC Query Raised On]         NVARCHAR(MAX)
    ,[Last CPC Query Responded On]      NVARCHAR(MAX)
    ,[Previous Queries]                 NVARCHAR(MAX)
    ,[Previous Remarks]                 NVARCHAR(MAX)
    ,[Live CPC Query Raised On]         NVARCHAR(MAX)
    ,[Live CPC Query Responded On]      NVARCHAR(MAX)
    ,[Live Queries]                     NVARCHAR(MAX)
    ,[Live Remarks]                     NVARCHAR(MAX)
    ,[LO Mobile]                        NVARCHAR(25)
    ,[Applicant Mobile]                 NVARCHAR(25)
    ,[Co-Applicant Mobile no]           NVARCHAR(25)
    ,[Branch to Village Distance]       NVARCHAR(MAX)
    ,[District]                         NVARCHAR(255)
    ,[Pincode]                          NVARCHAR(50)
    ,[Area Name]                        NVARCHAR(255)
    ,[CPC FTR Flag]                     NVARCHAR(25)
    ,MobileNo                           NVARCHAR(25)
    ,BranchGPSCoordinate                nvarchar(255)
    ,BranchLatitude                     nvarchar(255)
    ,BranchLangitude                    nvarchar(255)
    ,ClientAddressPlaceCOOrdinate       nvarchar(255)
    ,ClientAddressPlaceLatitude         nvarchar(255)
    ,ClientAddressPlaceLangitude        nvarchar(255)
    ,BranchGeoGraphy					GEOGRAPHY
    ,DifferenceinDistance				DECIMAL(18,2)
	,[Query Raised]						NVARCHAR(25)
	,PlaceID							NVARCHAR(25)
	,NameMatchScore						FLOAT
	,TransactionAccountID				NVARCHAR(50)
	,ReportingOfficerID					NVARCHAR(25)
	,CurrentBMID						NVARCHAR(25)
	,CurrentASMID						NVARCHAR(25)
	,CurrentASMName						NVARCHAR(255)
	,CurrentBMName						NVARCHAR(255)
	,NoOfDependents						INT
	,MemberCreatedDate					SMALLDATETIME
	,BACVRemarks						nvarchar(255)
	,CreditApprovedBy					NVARCHAR(150)
	,ModifiedBy							nvarchar(30)
	,Modifiedon							SMALLDATETIME
	,ApplicationType					NVARCHAR(50)
	,ApplicationSourceID				NVARCHAR(25)
	,OldBranchID						NVARCHAR(6)
	,OldAccountID 						NVARCHAR(20)
	,OldLoanseries						SMALLINT
	,BenecheckSendbackCount             INT
	,PreviousBenecheckRemarks           NVARCHAR(max)
	,ZoneID		                        NVARCHAR(10)
    ,Zone                               NVARCHAR(150)
    )
	

	CREATE TABLE #Branch
	(
	OurBranchID			NVARCHAR(6) 
	,RegionID			NVARCHAR(25)
	,GPSCoordinate		NVARCHAR(255)
	,SODDate			SMALLDATETIME
	,EODDate			SMALLDATETIME
	PRIMARY KEY(OurBranchID)
	)
	
	DECLARE @MinBranchID	NVARCHAR(6),
			@MaxBranchID	NVARCHAR(6)

	INSERT INTO #Branch
	(
	RegionID
	,OurBranchID
	,GPSCoordinate
	,SODDate
	,EODDate
	)

	SELECT 
		 t_SystemBranchRegion.RegionID
		,t_SystemBranchRegion.OurBranchID
		,t_SystemBranchSetting.GPSCoordinate
		,t_SystemBranchStatus.SODDate
		,t_SystemBranchStatus.EODDate
	FROM t_SystemBranchStatus WITH(NOLOCK)          
	INNER JOIN t_SystemBranchRegion WITH (NOLOCK)  
	ON t_SystemBranchRegion.BankID		 = @BankID  
	AND t_SystemBranchRegion.OurBranchID = t_SystemBranchStatus.OurBranchID
	INNER JOIN t_SystemBranchSetting WITH(NOLOCK)
	ON t_SystemBranchSetting.OurBranchID	= t_SystemBranchStatus.OurBranchID
	WHERE t_SystemBranchRegion.RegionID  BETWEEN ISNULL(@FromRegionID,t_SystemBranchRegion.RegionID) AND ISNULL(@ToRegionID,t_SystemBranchRegion.RegionID)
	AND t_SystembranchRegion.OurbranchID BETWEEN ISNULL(@FromBranchID,t_SystembranchRegion.OurbranchID) 
										AND ISNULL(@ToBranchID,t_SystembranchRegion.OurbranchID)
	--AND (t_SystemBranchSetting.ClosedDate IS NULL OR t_SystemBranchSetting.ClosedDate >= ISNULL(@FromDate,t_SystemBranchSetting.ClosedDate))
	


	SELECT	@EodDate		= MIN(EODDate),
			@MaxEODDate		= MAX(EODDate),
			@MinBranchID	= MIN(OurBranchID),
			@MaxBranchID	= MAX(OurBranchID)
	FROM #Branch

	IF ISNULL(@ApplicationTypeID,0) = 'GLOW'
	BEGIN

	    IF ISNULL(@IsDisbAccounts,0) = 0
	    BEGIN
	    	INSERT INTO #CPCDetail
	    	(
	    		OurBranchID			
	    		,ApplicationFileNo	
	    		,MemberID			
	    		,ApplicationID		
	    		,ClientID
	    		,[Center ID]
	    		,[Center Name]
	    		,[Group ID]
	    		,[Group Name]
	    		,[Application Current Stage]
	    		,[Branch ID]
	    		,[Application Number]
	    		,[Member ID]	
	    		,[Member Name]
	    		,SendBackStatusID
	    		,LOName
	    		,MobileNo
	    		,BranchGPSCoordinate
	    	)
	    
	    	SELECT t_GLOSClient.OurBranchID
	    		,t_GLOSClient.ApplicationFileNo
	    		,t_GLOSClient.MemberID 
	    		,t_GLOSClient.BRNETApplicationID
	    		,ISNULL(t_GLOSClient.ExistingClientID,t_GLOSClient.BRNetClientID)
	    		,t_GLOSApplication.CenterID
	    		,t_GLOSApplication.CenterName
	    		,t_GLOSApplication.SubGroupID
	    		,dbo.f_GetSubGroupName(t_GLOSApplication.OurBranchID,t_GLOSApplication.CenterID,t_GLOSApplication.SubGroupID)
	    		,dbo.fn_GetSystemCodeDesc('GLOSProcessStageID',t_GLOSApplication.GLOSProcessStageID,@LanguageID)
	    			+' '+dbo.fn_GetSystemCodeDesc('GLOSStageStatusID',t_GLOSApplication.GLOSStageStatusID,@LanguageID)
	    		,t_GLOSClient.OurBranchID
	    		,t_GLOSClient.ApplicationFileNo
	    		,t_GLOSClient.MemberID
	    		,t_GLOSClient.Name
	    		,t_GLOSApplication.SendBackStatusID
	    		,t_GLOSApplication.OfficerID
	    		,t_GLOSClient.MobileNo
	    		,#Branch.GPSCoordinate BranchGPSCoordinate 
	    	FROM CV_GLOSClient t_GLOSClient WITH(NOLOCK)
	    	INNER JOIN #Branch
	    	ON #Branch.OurBranchID = t_GLOSClient.OurBranchID
	    	INNER JOIN CV_GLOSApplication t_GLOSApplication WITH(NOLOCK)
	    	ON t_GLOSClient.OurBranchID			= t_GLOSApplication.OurBranchID
	    	AND t_GLOSClient.ApplicationFileNo	= t_GLOSApplication.ApplicationFileNo
	    	AND t_GLOSClient.GLOSMemberStatusID = 'A'
			AND t_GLOSClient.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
			AND t_GLOSApplication.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
	   	WHERE NOT EXISTS (SELECT 1
	    					FROM t_Loan WITH(NOLOCK)
	    					WHERE t_Loan.OurBranchID = t_GLOSClient.OurBranchID
	    					AND t_Loan.ApplicationID = t_GLOSClient.BrnetApplicationID
	    					AND t_Loan.FirstDisbursementDate IS NOT NULL
	    					)
	    
	    END
	    ELSE
	    BEGIN
	    	INSERT INTO #CPCDetail
	 	(
	    		OurBranchID			
	    		,ApplicationFileNo	
	    		,MemberID			
	    		,ApplicationID		
	    		,ClientID
	    		,[Center ID]
	    		,[Center Name]
	    		,[Group ID]
	    		,[Group Name]
	    		,[Application Current Stage]
	    		,[Branch ID]
	    		,[Application Number]
	    		,[Member ID]	
	    		,[Member Name]
	    		,SendBackStatusID
	    		,LOName
	    		,MobileNo
	    		,BranchGPSCoordinate
	    	)
	    
	    	SELECT t_GLOSClient.OurBranchID
	    		,t_GLOSClient.ApplicationFileNo
	    		,t_GLOSClient.MemberID 
	    		,t_GLOSClient.BRNETApplicationID
	    		,ISNULL(t_GLOSClient.ExistingClientID,t_GLOSClient.BRNetClientID)
	    		,t_GLOSApplication.CenterID
	    		,t_GLOSApplication.CenterName
	    		,t_GLOSApplication.SubGroupID
	    		,dbo.f_GetSubGroupName(t_GLOSApplication.OurBranchID,t_GLOSApplication.CenterID,t_GLOSApplication.SubGroupID)
	    		,dbo.fn_GetSystemCodeDesc('GLOSProcessStageID',t_GLOSApplication.GLOSProcessStageID,@LanguageID)
	    			+' '+dbo.fn_GetSystemCodeDesc('GLOSStageStatusID',t_GLOSApplication.GLOSStageStatusID,@LanguageID)
	    		,t_GLOSClient.OurBranchID
	    		,t_GLOSClient.ApplicationFileNo
	    		,t_GLOSClient.MemberID
	    		,t_GLOSClient.Name
	    		,t_GLOSApplication.SendBackStatusID
	    		,t_GLOSApplication.OfficerID
	    		,t_GLOSClient.MobileNo
	    		,#Branch.GPSCoordinate BranchGPSCoordinate
	    	FROM t_Loan WITH(NOLOCK)
	    	INNER JOIN #Branch
	    	ON #Branch.OurBranchID = t_Loan.OurBranchID
	    	INNER JOIN CV_GLOSClient t_GLOSClient WITH(NOLOCK)
	    	ON t_GLOSClient.OurBranchID			=  t_Loan.OurBranchID
	    	AND t_GLOSClient.BrnetApplicationID =  t_Loan.ApplicationID
	    	INNER JOIN CV_GLOSApplication t_GLOSApplication WITH(NOLOCK)
	    	ON t_GLOSClient.OurBranchID			= t_GLOSApplication.OurBranchID
	    	AND t_GLOSClient.ApplicationFileNo	= t_GLOSApplication.ApplicationFileNo
	    	WHERE t_Loan.FirstDisbursementDate BETWEEN ISNULL(@FromDate, t_Loan.FirstDisbursementDate) 
	    										AND ISNULL(@ToDate, t_Loan.FirstDisbursementDate)
	    	AND t_GLOSClient.GLOSMemberStatusID = 'A'
			AND t_GLOSClient.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
			AND t_GLOSApplication.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
	    
	    END
		IF NOT EXISTS (SELECT 1
					FROM #CPCDetail
					)
		BEGIN
			RAISERROR('BREXDB602201',16,1)  --No details found
			RETURN
		END

	UPDATE #CPCDetail
	SET ApplicationSourceID = t_WFLoanApplication.AppSourceID
	FROM #CPCDetail
	INNER JOIN t_WFLoanApplication WITH(NOLOCK)
	ON  t_WFLoanApplication.OurBranchID    = #CPCDetail.OurBranchID
	AND t_WFLoanApplication.ApplicationID  = #CPCDetail.ApplicationID
	WHERE t_WFLoanApplication.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	IF @ApplicationTypeID = 'GLOW'
	BEGIN
		DELETE FROM #CPCDetail
		WHERE ISNULL(#CPCDetail.ApplicationSourceID,'') = 'ILOS'
	END
	
	IF @ApplicationTypeID = 'ILOS'
	BEGIN
	   DELETE FROM #CPCDetail
	   WHERE ISNULL(#CPCDetail.ApplicationSourceID,'') <> 'ILOS'
	END

	UPDATE #CPCDetail
	SET #CPCDetail.[CPC Status]			= CASE WHEN t_GLOSActivityLog.ActivityStatusID = 'PEND' THEN 'Pending'
												WHEN t_GLOSActivityLog.ActivityStatusID = 'INPR' THEN 'In-Progress'
												WHEN t_GLOSActivityLog.ActivityStatusID = 'COMP' THEN 'Completed'
											END,
		#CPCDetail.[Owner Name]			= t_GLOSActivityLog.OfficerID,
		#CPCDetail.[CPC Done By]		= t_GLOSActivityLog.OfficerID,
		#CPCDetail.[CPC Started On]		= t_GLOSActivityLog.StartOn,
		#CPCDetail.[CPC Completed On]	= CASE WHEN t_GLOSActivityLog.ActivityStatusID = 'COMP' THEN t_GLOSActivityLog.StatusOn ELSE NULL END
	FROM v_GLOSActivityLog t_GLOSActivityLog WITH(NOLOCK)
	WHERE  #CPCDetail.OurBranchID			= t_GLOSActivityLog.OurBranchID
	AND #CPCDetail.ApplicationFileNo		= t_GLOSActivityLog.ApplicationFileNo
	AND t_GLOSActivityLog.GLOSProcessActivityID = 'CPCV'
	AND t_GLOSActivityLog.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET #CPCDetail.[CPC Status]			= CASE WHEN t_GLOSActivityLog.ActivityStatusID = 'PEND' THEN 'Pending'
												WHEN t_GLOSActivityLog.ActivityStatusID = 'INPR' THEN 'In-Progress'
												WHEN t_GLOSActivityLog.ActivityStatusID = 'COMP' THEN 'Completed'
											END,
		#CPCDetail.[Owner Name]			= dbo.f_GetOfficerName(@BankID,t_GLOSActivityLog.OfficerID) ,
		#CPCDetail.[CPC Done By]		= t_GLOSActivityLog.OfficerID,
		#CPCDetail.[CPC Started On]		= t_GLOSActivityLog.StartOn,
		#CPCDetail.[CPC Completed On]	= CASE WHEN t_GLOSActivityLog.ActivityStatusID = 'COMP' THEN t_GLOSActivityLog.StatusOn ELSE NULL END
	FROM v_GLOSActivityLog t_GLOSActivityLog WITH(NOLOCK)
	WHERE  #CPCDetail.OurBranchID			= t_GLOSActivityLog.OurBranchID
	AND #CPCDetail.ApplicationFileNo		= t_GLOSActivityLog.ApplicationFileNo
	AND t_GLOSActivityLog.GLOSProcessActivityID = 'CSOV'
	AND t_GLOSActivityLog.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
	AND [CPC Status] IS NULL

	UPDATE #CPCDetail
	SET #CPCDetail.[CPC Status]			= 'Not Started',
		#CPCDetail.[Owner Name]			= NULL,
		#CPCDetail.[CPC Done By]		= NULL,
		#CPCDetail.[CPC Started On]		= NULL,
		#CPCDetail.[CPC Completed On]	= NULL
	FROM #CPCDetail
	INNER JOIN v_GLOSActivityLog t_GLOSActivityLog WITH(NOLOCK)
	ON  #CPCDetail.OurBranchID				= t_GLOSActivityLog.OurBranchID
	AND #CPCDetail.ApplicationFileNo		= t_GLOSActivityLog.ApplicationFileNo
	WHERE t_GLOSActivityLog.GLOSProcessActivityID = 'BACV'
	AND t_GLOSActivityLog.StartOn IS NOT NULL
	AND t_GLOSActivityLog.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
	AND #CPCDetail.[CPC Status] IS NULL

	UPDATE #CPCDetail
	SET CreditApprovedBy = t_LOSLoanApprovalDetail.StatusBy
	FROM t_LOSLoanApprovalDetail WITH (NOLOCK)
	WHERE t_LOSLoanApprovalDetail.OurBranchID		= #CPCDetail.OurBranchID
	AND  t_LOSLoanApprovalDetail.ApplicationFileNo	= #CPCDetail.ApplicationFileNo
	AND t_LOSLoanApprovalDetail.MemberID			= #CPCDetail.MemberID
	AND t_LOSLoanApprovalDetail.SourceTypeID		= 'GLOS'
	AND t_LOSLoanApprovalDetail.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	IF ISNULL(@IsCPCNotStarted,0) = 1  -- Extra logic, else old logic
	BEGIN
		DELETE FROM #CPCDetail
		WHERE ISNULL([CPC Status],'') <> 'Not Started'
	END

	UPDATE #CPCDetail
	SET #CPCDetail.[Owner Name]			    = t_AccountOfficer.OfficerID,
		#CPCDetail.[CPC Done By]		    = t_AccountOfficer.OfficerID
	FROM cv_GLOSCheckListImgVerify t_GLOSCheckListImgVerify WITH(NOLOCK)
	INNER JOIN #CPCDetail
	ON  #CPCDetail.OurBranchID				= t_GLOSCheckListImgVerify.OurBranchID
	AND #CPCDetail.ApplicationFileNo		= t_GLOSCheckListImgVerify.ApplicationFileNo
	AND #CPCDetail.MemberID					= t_GLOSCheckListImgVerify.MemberID
	AND t_GLOSCheckListImgVerify.ActivityID = 'CPCV'
	INNER JOIN t_user  WITH(NOLOCK)
	ON t_GLOSCheckListImgVerify.CreatedBy =t_user.OperatorID
	INNER JOIN t_AccountOfficer  WITH(NOLOCK)
	ON t_AccountOfficer.BankID	= @BankID
	AND t_AccountOfficer.ClientID = t_user.ClientID
	WHERE #CPCDetail.[CPC Done By] IS NULL
	AND t_GLOSCheckListImgVerify.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET #CPCDetail.[Application Current Stage]	= (SELECT TOP 1 dbo.fn_GetSystemCodeDesc('GLOSProcessActivityID',t_GLOSActivityLog.GLOSProcessActivityID,@LanguageID)
													FROM t_GLOSActivityLog WITH(NOLOCK)
													WHERE  #CPCDetail.OurBranchID			= t_GLOSActivityLog.OurBranchID
													AND #CPCDetail.ApplicationFileNo		= t_GLOSActivityLog.ApplicationFileNo
													AND t_GLOSActivityLog.ActivityStatusID	IS NOT NULL 
													ORDER BY t_GLOSActivityLog.GLOSProcessStageID DESC
														,t_GLOSActivityLog.ActivityOrderNo DESC
													)
	
	UPDATE #CPCDetail
	SET #CPCDetail.[Loan Scheme]		= t_GLOSClientLoan.LoanSchemeID,
		#CPCDetail.Tenure				= t_GLOSClientLoan.LoanTerm,
		#CPCDetail.[Loan Amount]		= t_GLOSClientLoan.LoanAmount
	FROM CV_GLOSClientLoan t_GLOSClientLoan WITH(NOLOCK)
	WHERE #CPCDetail.OurBranchID		= t_GLOSClientLoan.OurBranchID
	AND #CPCDetail.ApplicationFileNo	= t_GLOSClientLoan.ApplicationFileNo
	AND #CPCDetail.MemberID				= t_GLOSClientLoan.MemberID
	AND t_GLOSClientLoan.RecordStatusID = 'A'
	AND t_GLOSClientLoan.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET #CPCDetail.[Loan Account ID]= t_Loan.AccountID,
		#CPCDetail.[Loan Amount]	= t_Loan.LoanAmount,
		#CPCDetail.Tenure			= t_Loan.RepaymentTerm
	FROM t_Loan WITH(NOLOCK)
	WHERE #CPCDetail.OurBranchID	= t_Loan.OurBranchID
	AND #CPCDetail.ApplicationID	= t_Loan.ApplicationID
	AND t_Loan.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET #CPCDetail.[Loan Disbursed By] = t_Loan.DisbursedBy,
		#CPCDetail.[Loan Disbursed On] = t_Loan.FirstDisbursementDate,
		#CPCDetail.AccountID		= t_Loan.AccountID,
		#CPCDetail.LoanSeries		= t_Loan.LoanSeries
	FROM t_Loan WITH(NOLOCK)
	WHERE #CPCDetail.OurBranchID	= t_Loan.OurBranchID
	AND #CPCDetail.ApplicationID	= t_Loan.ApplicationID
	AND t_Loan.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
    SET OldBranchID   = t_GroupMemberSchemeTransfer.OurBranchID,
        OldAccountID  = t_GroupMemberSchemeTransfer.LoanAccountID, 
        OldLoanSeries = t_GroupMemberSchemeTransfer.LoanSeries  
    FROM #CPCDetail
    INNER JOIN t_GroupMemberSchemeTransfer WITH(NOLOCK)
    ON t_GroupMemberSchemeTransfer.NewBranchID       = #CPCDetail.OurBranchID 
    AND t_GroupMemberSchemeTransfer.NewLoanAccountID = #CPCDetail.AccountID 
    AND t_GroupMemberSchemeTransfer.NewLoanSeries    = #CPCDetail.Loanseries
	AND t_GroupMemberSchemeTransfer.NewBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
    SET OurBranchID	 = t_Loan.OurBranchID,
        ApplicationID = t_Loan.ApplicationID
    FROM #CPCDetail
    INNER JOIN t_Loan WITH(NOLOCK)
    ON t_Loan.OurBranchID   = #CPCDetail.OldBranchID 
    AND t_Loan.AccountID    = #CPCDetail.OldAccountID 
    AND t_Loan.LoanSeries   = #CPCDetail.OldLoanseries
	AND t_Loan.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET #CPCDetail.[Center ID]		= t_WFLoanApplication.GroupID
		,#CPCDetail.[Center Name]	= dbo.f_GetGroupName(t_WFLoanApplication.OurBranchID,t_WFLoanApplication.GroupID)
		,#CPCDetail.[Group ID]		= t_WFLoanApplication.SubGroupID
		,#CPCDetail.[Group Name]	= dbo.f_GetSubGroupName(t_WFLoanApplication.OurBranchID,t_WFLoanApplication.GroupID,t_WFLoanApplication.SubGroupID)
		,#CPCDetail.[Loan Scheme]	= t_WFLoanApplication.LoanSchemeID
		,#CPCDetail.Tenure			= t_WFLoanApplication.LoanTerm	
		,#CPCDetail.[Loan Amount]	= t_WFLoanApplication.LoanAmount
		,#CPCDetail.[Application Current Stage] = dbo.fn_GetSystemCodeDesc('WFAdvStageID',t_WFLoanApplication.WFAdvStageID,@LanguageID)												
	FROM t_WFLoanApplication WITH(NOLOCK)
	WHERE #CPCDetail.OurBranchID	= t_WFLoanApplication.OurBranchID
	AND #CPCDetail.ApplicationID	= t_WFLoanApplication.ApplicationID
	AND t_WFLoanApplication.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET #CPCDetail.[CPC Status]	= CASE WHEN SendBackStatusID = 'SNT' THEN 'Query Raised'
										WHEN SendBackStatusID = 'SUB' THEN 'Query Responded'
									ELSE #CPCDetail.[CPC Status]
								END

	FROM #CPCDetail WITH(NOLOCK)
	WHERE #CPCDetail.[CPC Status] <> 'Completed'
	
	--Old Activities Case
	UPDATE #CPCDetail
	SET #CPCDetail.[Bene Check Status]		= CASE WHEN t_GLOSMemberRuleLog.GLOSRuleStatusID = 'FAIL' 
														AND Remarks LIKE '%Name Mismatch%' AND IsOverridden = 1
													THEN 'Name Mismatch Overridden'
												WHEN t_GLOSMemberRuleLog.GLOSRuleStatusID = 'FAIL' 
														AND Remarks LIKE '%Name Mismatch%' AND IsOverridden = 0
													THEN 'Name Mismatch'
												WHEN t_GLOSMemberRuleLog.GLOSRuleStatusID = 'FAIL' AND Remarks NOT LIKE '%Name Mismatch%'				
													THEN 'Failure'
												WHEN t_GLOSMemberRuleLog.GLOSRuleStatusID = 'FAIL' 
													THEN 'Failure'
												WHEN t_GLOSMemberRuleLog.GLOSRuleStatusID = 'PASS' 
													THEN 'Success'
												WHEN IsOverridden = 1													
												THEN 'Beneficiary Check Rule is '+ 'Overridden'
											END,
		#CPCDetail.[Bene Check Done By]		= ISNULL(t_GLOSMemberRuleLog.OverriddenBy,t_GLOSMemberRuleLog.PassedBy),
		#CPCDetail.[Bene check Done On]		= CASE WHEN ISNULL(t_GLOSMemberRuleLog.OverriddenBy,t_GLOSMemberRuleLog.PassedBy) IS NOT NULL 
													THEN t_GLOSMemberRuleLog.StatusOn ELSE NULL END--,
		--#CPCDetail.[HDFC Remarks]			= t_GLOSMemberRuleLog.Remarks
	FROM v_GLOSMemberRuleLog t_GLOSMemberRuleLog WITH(NOLOCK)
	WHERE #CPCDetail.OurBranchID			= t_GLOSMemberRuleLog.OurBranchID
	AND #CPCDetail.ApplicationFileNo		= t_GLOSMemberRuleLog.ApplicationFileNo
	AND #CPCDetail.MemberID					= t_GLOSMemberRuleLog.MemberID
	AND t_GLOSMemberRuleLog.RuleID			= 'BENCHK'
	AND t_GLOSMemberRuleLog.GLOSProcessActivityID = 'BACV'
	AND t_GLOSMemberRuleLog.GLOSProcessStageID <>  '20APP'
	AND t_GLOSMemberRuleLog.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID


	--1. First checkup for BENCHK Rule
	UPDATE #CPCDetail
	SET #CPCDetail.[Bene Check Status]		= CASE 
												WHEN t_GLOSMemberRuleLog.GLOSRuleStatusID = 'FAIL' 
													THEN 'Failure'
												WHEN t_GLOSMemberRuleLog.GLOSRuleStatusID = 'PASS' 
													THEN 'Success'
												WHEN t_GLOSMemberRuleLog.IsOverridden = 1
													THEN 'Beneficiary Check Rule is '+ 'Overridden'
												ELSE 'Beneficiary Check Rule is '+dbo.fn_getSystemcodedesc('GLOSRuleStatusID',t_GLOSMemberRuleLog.GLOSRuleStatusID,@LanguageID)
											END,
		#CPCDetail.[Bene Check Done By]		= ISNULL(t_GLOSMemberRuleLog.OverriddenBy,t_GLOSMemberRuleLog.PassedBy),
		#CPCDetail.[Bene check Done On]		= CASE WHEN ISNULL(t_GLOSMemberRuleLog.OverriddenBy,t_GLOSMemberRuleLog.PassedBy) IS NOT NULL 
													THEN t_GLOSMemberRuleLog.StatusOn ELSE NULL END
	FROM v_GLOSMemberRuleLog t_GLOSMemberRuleLog WITH(NOLOCK)
	WHERE #CPCDetail.OurBranchID					= t_GLOSMemberRuleLog.OurBranchID
	AND #CPCDetail.ApplicationFileNo				= t_GLOSMemberRuleLog.ApplicationFileNo
	AND #CPCDetail.MemberID							= t_GLOSMemberRuleLog.MemberID
	AND t_GLOSMemberRuleLog.RuleID					= 'BENVAL'
	AND t_GLOSMemberRuleLog.GLOSProcessActivityID	IN ('BACV','DAEN')
	AND t_GLOSMemberRuleLog.GLOSProcessStageID		= '20APP'
	AND #CPCDetail.[Bene Check Status] IS NULL
	AND t_GLOSMemberRuleLog.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET #CPCDetail.[Loan Booked By]	= t_WFLoanBooking.CreatedBy,
		#CPCDetail.[Loan Booked ON]	= t_WFLoanBooking.BookedDate
	FROM t_WFLoanBooking WITH(NOLOCK)
	WHERE #CPCDetail.OurBranchID	= t_WFLoanBooking.OurBranchID
	AND #CPCDetail.ApplicationID	= t_WFLoanBooking.ApplicationID
	AND t_WFLoanBooking.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET #CPCDetail.[Payment Amount]		= t_ClientBankTransaction.NetDisbursementAmount,
		#CPCDetail.[Payment Status]		= CASE WHEN #CPCDetail.[Loan Disbursed On] IS NOT NULL 
												AND t_ClientBankTransaction.TrxStatusID NOT IN ('COM','ERR') THEN 'In-Pending'
											WHEN #CPCDetail.[Loan Disbursed On] IS NOT NULL 
												AND t_ClientBankTransaction.TrxStatusID = 'COM' THEN 'Success'
											WHEN #CPCDetail.[Loan Disbursed On] IS NOT NULL 
												AND t_ClientBankTransaction.TrxStatusID = 'ERR' THEN 'Error' 
										END,
		#CPCDetail.[Payment Status On]	= t_ClientBankTransaction.TrxStatusOn,
		#CPCDetail.[UTR NO]				= t_ClientBankTransaction.UTRNo,
		#CPCDetail.[Application Current Stage]	= CASE WHEN t_ClientBankTransaction.TrxBatchID IS NOT NULL 
													THEN dbo.fn_GetSystemCodeDesc('TACSTatusID',t_ClientBankTransaction.TrxStatusID,@LanguageID)
												ELSE #CPCDetail.[Application Current Stage] END,
		#CPCDetail.TrxRowID				= t_ClientBankTransaction.TrxRowID,
		#CPCDetail.BatchID				= t_ClientBankTransaction.IMPSBatchID
	FROM #CPCDetail
	INNER JOIN cv_ClientBankTransaction t_ClientBankTransaction WITH(NOLOCK)
	ON #CPCDetail.OurBranchID		= t_ClientBankTransaction.OurBranchID
	AND #CPCDetail.AccountID		= t_ClientBankTransaction.LoanAccountID
	AND #CPCDetail.LoanSeries		= t_ClientBankTransaction.LoanSeries
	AND t_ClientBankTransaction.RecordStatusID = 'A'
	AND t_ClientBankTransaction.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID


	UPDATE #CPCDetail
	SET #CPCDetail.BatchID				= t_ClientBankTransaction.IMPSBatchID
	FROM #CPCDetail
	INNER JOIN cv_ClientBankTransaction t_ClientBankTransaction WITH(NOLOCK)
	ON #CPCDetail.OurBranchID		= t_ClientBankTransaction.OurBranchID
	AND #CPCDetail.ApplicationFileNo= t_ClientBankTransaction.ApplicationFileNo
	AND #CPCDetail.MemberID			= t_ClientBankTransaction.MemberID
	WHERE ISNULL(#CPCDetail.BatchID,'') = ''
	AND t_ClientBankTransaction.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET #CPCDetail.BeneficiaryName		= t_ClientBankTransaction.BeneficiaryName
		,NameMatchScore					= t_CLientBankTransaction.Score
		,TransactionAccountID			= t_CLientBankTransaction.AccountID
	FROM #CPCDetail
	INNER JOIN cv_ClientBankTransaction t_ClientBankTransaction WITH(NOLOCK)
	ON #CPCDetail.OurBranchID		= t_ClientBankTransaction.OurBranchID
	AND #CPCDetail.ApplicationFileNo= t_ClientBankTransaction.ApplicationFileNo
	AND #CPCDetail.MemberID			= t_ClientBankTransaction.MemberID
	AND t_ClientBankTransaction.RecordStatusID = 'A'
	AND t_ClientBankTransaction.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET #CPCDetail.[Payment Initiated by]= t_OnLineFundTransferLog.PassedBy,
		#CPCDetail.[Payment Initiated On]= t_OnLineFundTransferLog.PassedOn		
	FROM t_OnLineFundTransferLog WITH(NOLOCK)
	WHERE #CPCDetail.TrxRowID		= t_OnLineFundTransferLog.TrxRowID
	AND #CPCDetail.OurBranchID		= t_OnLineFundTransferLog.OurBranchID
	AND t_OnLineFundTransferLog.FTStageID		= 'FI'
	AND t_OnLineFundTransferLog.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET	#CPCDetail.[Payment Approved By]= t_OnLineFundTransferLog.PassedBy,
		#CPCDetail.[Payment Approved On]= t_OnLineFundTransferLog.PassedOn
	FROM t_OnLineFundTransferLog WITH(NOLOCK)
	WHERE #CPCDetail.TrxRowID		= t_OnLineFundTransferLog.TrxRowID
	AND #CPCDetail.OurBranchID		= t_OnLineFundTransferLog.OurBranchID
	AND t_OnLineFundTransferLog.FTStageID		= 'FA'
	AND t_OnLineFundTransferLog.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	IF NOT EXISTS (SELECT 1
				FROM #CPCDetail
				)
	BEGIN
		RAISERROR('BREXDB602201',16,1)  --No details found
		RETURN
	END
	
	UPDATE #CPCDetail
	SET #CPCDetail.[Branch Name] = t_SystemBranchSetting.BranchName
		,#CPCDetail.[BC ID]		 = t_SystemBranchSetting.BCCodeID
		,#CPCDetail.[BC Name]	 = t_BCMaintenance.BCDescription
		,#CPCDetail.RegionID	 = t_SystemBranchRegion.RegionID
	FROM #CPCDetail
	INNER JOIN t_SystemBranchSetting WITH(NOLOCK)
	ON #CPCDetail.OurBranchID	= t_SystemBranchSetting.OurBranchID
	INNER JOIN t_SystemBranchRegion WITH (NOLOCK)  
	ON t_SystemBranchRegion.BankID				= @BankID  
	AND	t_SystemBranchRegion.OurBranchID		= t_SystemBranchSetting.OurBranchID
	LEFT JOIN t_BCMaintenance WITH(NOLOCK)
	ON t_BCMaintenance.BankID	= @BankID
	AND t_SystemBranchSetting.BCCodeID = t_BCMaintenance.BCCodeID
	WHERE t_SystemBranchSetting.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET #CPCDetail.[Is Query Raised] = 'YES',
		#CPCDetail.[Query Raised On] = t_GLOSSendBackChkLstData.CreatedOn
	FROM #CPCDetail
	INNER JOIN CV_GLOSSendBackChkLstData t_GLOSSendBackChkLstData WITH(NOLOCK)
	ON #CPCDetail.OurBranchID		= t_GLOSSendBackChkLstData.OurBranchID
	AND #CPCDetail.ApplicationFileNo= t_GLOSSendBackChkLstData.ApplicationFileNo
	AND #CPCDetail.MemberID			= t_GLOSSendBackChkLstData.MemberID
	AND t_GLOSSendBackChkLstData.IsNotOK = 1
	INNER JOIN t_GLOSCheckList WITH(NOLOCK)
	ON t_GLOSCheckList.CheckListID = t_GLOSSendBackChkLstData.CheckListID
	WHERE t_GLOSSendBackChkLstData.ActivityID = 'CPCV'  --Hold ,'CSOV'
	AND t_GLOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET #CPCDetail.[Queries] = STUFF((SELECT 
										DISTINCT '|'+ t_GLOSCheckList.Description --ISNULL(dbo.fn_GetUserCodeDesc('SendBackreasonID',t_GLOSSendBackChkLstData.CheckListReasonID),'')
									FROM CV_GLOSSendBackChkLstData t_GLOSSendBackChkLstData WITH(NOLOCK)
									INNER JOIN t_GLOSCheckList WITH(NOLOCK)
									ON t_GLOSCheckList.CheckListID  = t_GLOSSendBackChkLstData.CheckListID
									WHERE #CPCDetail.OurBranchID	= t_GLOSSendBackChkLstData.OurBranchID
									AND #CPCDetail.ApplicationFileNo= t_GLOSSendBackChkLstData.ApplicationFileNo
									AND #CPCDetail.MemberID			= t_GLOSSendBackChkLstData.MemberID
									AND t_GLOSSendBackChkLstData.IsNotOK = 1
									AND t_GLOSSendBackChkLstData.ActivityID = 'CPCV'
									AND t_GLOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
									FOR XML PATH('')),1,1,'')										
							
	FROM #CPCDetail
	WHERE #CPCDetail.[Is Query Raised] = 'YES'

	UPDATE #CPCDetail
	SET #CPCDetail.[Query Raised Count] = (SELECT 
												COUNT(1)
											FROM CV_GLOSSendBackChkLstData t_GLOSSendBackChkLstData WITH(NOLOCK)
											INNER JOIN t_GLOSCheckList WITH(NOLOCK)
											ON t_GLOSCheckList.CheckListID = t_GLOSSendBackChkLstData.CheckListID
											WHERE #CPCDetail.OurBranchID	= t_GLOSSendBackChkLstData.OurBranchID
											AND #CPCDetail.ApplicationFileNo= t_GLOSSendBackChkLstData.ApplicationFileNo
											AND #CPCDetail.MemberID			= t_GLOSSendBackChkLstData.MemberID
											AND t_GLOSSendBackChkLstData.IsNotOK = 1
											AND t_GLOSSendBackChkLstData.ActivityID = 'CPCV'
											AND t_GLOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
										  )										
							
	FROM #CPCDetail
	WHERE #CPCDetail.[Is Query Raised] = 'YES'

	UPDATE #CPCDetail
	SET [Sendback Count] =SendCount.sendback
	FROM #CPCDetail
	LEFT JOIN (SELECT
				CV_GLOSSendBackChkLstData.OurBranchID,
				CV_GLOSSendBackChkLstData.ApplicationFileNo,
				#CPCDetail.[Member ID],
				COUNT( DISTINCT CV_GLOSSendBackChkLstData.SendBackRefNo) sendback
				FROM CV_GLOSSendBackChkLstData WITH(NOLOCK)
				INNER JOIN #CPCDetail WITH(NOLOCK)
				ON #CPCDetail.[Branch ID]				= CV_GLOSSendBackChkLstData.OurBranchID
				AND #CPCDetail.[Application Number]		= CV_GLOSSendBackChkLstData.ApplicationFileNo
				AND #CPCDetail.[Member ID]				= CV_GLOSSendBackChkLstData.MemberID
				WHERE CV_GLOSSendBackChkLstData.ActivityID='CPCV'
				AND CV_GLOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
				AND #CPCDetail.[Member ID] = (SELECT MIN(CPCDetail.MemberID)
											FROM #CPCDetail CPCDetail
											WHERE CPCDetail.[Branch ID]				= #CPCDetail.OurBranchID
											AND CPCDetail.[Application Number]		= #CPCDetail.ApplicationFileNo
											AND CPCDetail.MemberID				    = #CPCDetail.MemberID
											)
				GROUP BY 
					CV_GLOSSendBackChkLstData.OurBranchID,
					CV_GLOSSendBackChkLstData.ApplicationFileNo,
					#CPCDetail.[Member ID]
			)SendCount
	ON #CPCDetail.[Branch ID]				= SendCount.OurBranchID
	AND #CPCDetail.[Application Number]		= SendCount.ApplicationFileNo
	AND #CPCDetail.[Member ID]				= SendCount.[Member ID]

	UPDATE #CPCDetail
	SET BranchManager = t_Accountofficer.Name	
	FROM #CPCDetail
	INNER JOIN t_Accountofficer WITH(NOLOCK)
	ON t_Accountofficer.BankID		       = @BankID
	AND t_Accountofficer.ReportingBranchID =  #CPCDetail.[Branch ID]
	WHERE t_Accountofficer.OfficerTypeID   = 'BM'
	AND t_Accountofficer.ResignedDate IS NULL

	UPDATE #CPCDetail
	SET [File bucket] = CASE WHEN GLOSProcessActivityID='BACV' AND ActivityStatusID='PEND' THEN  'LO'
							 WHEN GLOSProcessActivityID='BACV' AND ActivityStatusID='INPR' THEN  'CPC'
						END
	FROM #CPCDetail
	INNER JOIN v_GLOSActivityLog t_GLOSActivityLog WITH(NOLOCK)
	ON #CPCDetail.OurBranchID		= t_GLOSActivityLog.OurBranchID
	AND #CPCDetail.ApplicationFileNo= t_GLOSActivityLog.ApplicationFileNo
	AND GLOSProcessActivityID='BACV'
	AND t_GLOSActivityLog.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET [HDFC Remarks] = t_ClientBankTransaction.ErrorMsg
	FROM #CPCDetail
	INNER JOIN cv_ClientBankTransaction  t_ClientBankTransaction WITH(NOLOCK)
	ON #CPCDetail.[Branch ID]				= t_ClientBankTransaction.OurBranchID
	AND #CPCDetail.[Application Number]		= t_ClientBankTransaction.ApplicationFileNo
	AND #CPCDetail.[Member ID]				= t_ClientBankTransaction.MemberID
	AND t_ClientBankTransaction.RecordStatusID='A'
	AND t_ClientBankTransaction.TrxRowID	= (SELECT MAX(transac.TrxRowID) FROM cv_ClientBankTransaction  transac
												WHERE transac.OurBranchID		= t_ClientBankTransaction.OurBranchID
												AND transac.ApplicationFileNo	= t_ClientBankTransaction.ApplicationFileNo
												AND transac.MemberID			= t_ClientBankTransaction.MemberID
												AND transac.ErrorMsg IS NOT NULL
												AND t_ClientBankTransaction.RecordStatusID='A'
												--AND transac.TrxStatusID <>'BAP'
												)
	AND t_ClientBankTransaction.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET TrxRefID	   = t_ClientBankTransaction.TrxRowID
	FROM #CPCDetail
	INNER JOIN cv_ClientBankTransaction  t_ClientBankTransaction WITH(NOLOCK)
	ON #CPCDetail.[Branch ID]				= t_ClientBankTransaction.OurBranchID
	AND #CPCDetail.[Application Number]		= t_ClientBankTransaction.ApplicationFileNo
	AND #CPCDetail.[Member ID]				= t_ClientBankTransaction.MemberID
	AND t_ClientBankTransaction.RecordStatusID='A'
	AND t_ClientBankTransaction.TrxRowID	= (SELECT MAX(transac.TrxRowID) FROM  cv_ClientBankTransaction transac
												WHERE transac.OurBranchID		= t_ClientBankTransaction.OurBranchID
												AND transac.ApplicationFileNo	= t_ClientBankTransaction.ApplicationFileNo
												AND transac.MemberID			= t_ClientBankTransaction.MemberID
												AND t_ClientBankTransaction.RecordStatusID='A'
												)
	AND t_ClientBankTransaction.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET [HDFC Remarks] = DET.ErrorMsg
	FROM #CPCDetail
	CROSS APPLY(SELECT TOP 1 
						t_rblbanktrxextractlog.ErrorMsg,
						#CPCDetail.TrxRefID	
				FROM cv_rblbanktrxextractlog t_rblbanktrxextractlog WITH(NOLOCK)
				WHERE #CPCDetail.TrxRefID				= t_rblbanktrxextractlog.TrxRefID
				AND t_rblbanktrxextractlog.ErrorMsg	IS NOT NULL 
				AND #CPCDetail.[HDFC Remarks] IS NULL
				ORDER BY RequestOn DESC
				)DET
	
	UPDATE #CPCDetail
	SET [Application current Stage Status]	= CASE WHEN t_GLOSActivityLog.ActivityStatusID = 'PEND' THEN 'Pending'
													WHEN t_GLOSActivityLog.ActivityStatusID = 'INPR' THEN 'In-Progress'
													WHEN t_GLOSActivityLog.ActivityStatusID = 'COMP' THEN 'Completed'
													WHEN t_GLOSActivityLog.ActivityStatusID = 'ERRR' THEN 'Error' 
												END 
	FROM #CPCDetail
	INNER JOIN v_GLOSActivityLog t_GLOSActivityLog WITH(NOLOCK)
	ON #CPCDetail.OurBranchID		= t_GLOSActivityLog.OurBranchID
	AND #CPCDetail.ApplicationFileNo= t_GLOSActivityLog.ApplicationFileNo
	AND t_GLOSActivityLog.StatusOn = (SELECT MAX(GLOSActivityLog.StatusOn)
									FROM t_GLOSActivityLog GLOSActivityLog  WITH(NOLOCK)
									WHERE GLOSActivityLog.OurBranchID		= t_GLOSActivityLog.OurBranchID
									AND GLOSActivityLog.ApplicationFileNo	= t_GLOSActivityLog.ApplicationFileNo
									)
	AND t_GLOSActivityLog.ActivityOrderNo = (SELECT MAX(GLOSActivityLog2.ActivityOrderNo)
										FROM t_GLOSActivityLog GLOSActivityLog2  WITH(NOLOCK)
										WHERE GLOSActivityLog2.OurBranchID		= t_GLOSActivityLog.OurBranchID
										AND GLOSActivityLog2.ApplicationFileNo	= t_GLOSActivityLog.ApplicationFileNo
										AND GLOSActivityLog2.StatusOn			= t_GLOSActivityLog.StatusOn
										)
	AND t_GLOSActivityLog.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	--Once brnet submission done
	UPDATE #CPCDetail
	SET [Application current Stage]			= dbo.fn_GetSystemCodeDesc('WFAdvStageID',t_WFLoanApplication.WFAdvStageID,@LanguageID)
		,[Application current Stage Status] = dbo.fn_GetSystemCodeDesc('WFAppStatusID',t_WFLoanApplication.WFAppStatusID,@LanguageID)
	FROM #CPCDetail
	INNER JOIN t_WFLoanApplication WITH(NOLOCK)
	ON t_WFLoanApplication.OurBranchID		= #CPCDetail.OUrBranchID
	AND t_WFLoanApplication.ApplicationID	= #CPCDetail.ApplicationID
	WHERE t_WFLoanApplication.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID




	DROP TABLE IF EXISTS #AllGLOWRemarks;
	CREATE TABLE #AllGLOWRemarks 
	(
	    OurBranchID         VARCHAR(6),
	    ApplicationFileNo   NVARCHAR(20),
	    MemberID            SMALLINT,
	    AllBACVRemarks      NVARCHAR(MAX)
	);
	
	INSERT INTO #AllGLOWRemarks 
	(
	    OurBranchID,
	    ApplicationFileNo,
	    MemberID,
	    AllBACVRemarks
	)
	SELECT 
	    t_GLOSClientBankAccount.OurBranchID,
	    t_GLOSClientBankAccount.ApplicationFileNo,
	    t_GLOSClientBankAccount.MemberID,
	    STUFF((
	        SELECT ',' + LTRIM(RTRIM(t2.PreviousBACVRemarks))
	        FROM t_GLOSClientBankAccount t2
	        WHERE t2.OurBranchID       = t_GLOSClientBankAccount.OurBranchID
	          AND t2.ApplicationFileNo = t_GLOSClientBankAccount.ApplicationFileNo
	          AND t2.MemberID          = t_GLOSClientBankAccount.MemberID
	          --AND t2.PreviousBACVRemarks IS NOT NULL
	        ORDER BY t2.SerialID
	        FOR XML PATH(''), TYPE
	    ).value('.', 'NVARCHAR(MAX)'), 1, 1, '') AS AllBACVRemarks
		FROM t_GLOSClientBankAccount
		INNER JOIN #CPCDetail
		ON t_GLOSClientBankAccount.OurBranchID			= #CPCDetail.OurBranchID
		AND t_GLOSClientBankAccount.ApplicationFileNo	= #CPCDetail.ApplicationFileNo
		AND t_GLOSClientBankAccount.MemberID			= #CPCDetail.MemberID
		WHERE t_GLOSClientBankAccount.AccountTypeID		= 'SB'
		GROUP BY t_GLOSClientBankAccount.OurBranchID, t_GLOSClientBankAccount.ApplicationFileNo,t_GLOSClientBankAccount.MemberID

			--SELECT * FROM ##AllGLOWRemarks;

	
	UPDATE #CPCDetail
	SET BankName			= t_GLOSClientBankAccount.InstitutionName,
		BankAcNo			= t_GLOSClientBankAccount.AccountID,
		BankBranch			= t_GLOSClientBankAccount.BranchName,
		AccountHoldername	= t_GLOSClientBankAccount.AccountName,
		IFSCcode			= t_GLOSClientBankAccount.IFSCCode,
		BACVRemarks			= t_GLOSClientBankAccount.BACVRemarks,
		--PreviousBenecheckRemarks = t_GLOSClientBankAccount.PreviousBACVRemarks,
		PreviousBenecheckRemarks = #AllGLOWRemarks.AllBACVRemarks,
		ModifiedBy          = t_GLOSClientBankAccount.ModifiedBy,
        Modifiedon          = t_GLOSClientBankAccount.Modifiedon,
		BenecheckSendbackCount = CASE 
		                             WHEN ISNULL(#AllGLOWRemarks.AllBACVRemarks, '') = '' THEN 0
		                             ELSE LEN(#AllGLOWRemarks.AllBACVRemarks) - LEN(REPLACE(#AllGLOWRemarks.AllBACVRemarks, ',', '')) + 1
		                          END
	FROM cv_GLOSClientBankAccount  t_GLOSClientBankAccount WITH (NOLOCK) --cv_GLOSClientBankAccount
	LEFT JOIN #AllGLOWRemarks 
	ON t_GLOSClientBankAccount.OurBranchID			= #AllGLOWRemarks.OurBranchID
	AND t_GLOSClientBankAccount.ApplicationFileNo	= #AllGLOWRemarks.ApplicationFileNo
	AND t_GLOSClientBankAccount.MemberID			= #AllGLOWRemarks.MemberID
	WHERE  t_GLOSClientBankAccount.OurBranchID		= #CPCDetail.OurBranchID
	AND t_GLOSClientBankAccount.ApplicationFileNo	= #CPCDetail.ApplicationFileNo
	AND t_GLOSClientBankAccount.MemberID			= #CPCDetail.MemberID
	AND t_GLOSClientBankAccount.AccountTypeID		= 'SB'
	AND t_GLOSClientBankAccount.SerialID			= (	SELECT MAX(DT.SerialID) 
														FROM cv_GLOSClientBankAccount DT WITH (NOLOCK)
														WHERE t_GLOSClientBankAccount.OurBranchID		= DT.OurBranchID
														AND t_GLOSClientBankAccount.ApplicationFileNo	= DT.ApplicationFileNo
														AND t_GLOSClientBankAccount.MemberID			= DT.MemberID
														AND DT.AccountTypeID		= 'SB'
													)
	AND t_GLOSClientBankAccount.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID


	UPDATE #CPCDetail	
	SET VillageID = t_Group.VillageID	
	FROM t_Group	
	WHERE t_Group.OurBranchID	= #CPCDetail.OurBranchID	
	AND	  t_Group.GroupID		= #CPCDetail.[Center ID]
	
	UPDATE #CPCDetail	
	SET Villagename		= 	t_BranchUserCode.Description				
	FROM t_BranchUserCode	WITH(NOLOCK)
	WHERE t_BranchUserCode.OurBranchID	= #CPCDetail.OurBranchID	
	AND	t_BranchUserCode.ID				= 'VillageID'	
	AND t_BranchUserCode.SubCodeID		= #CPCDetail.VillageID
	AND t_BranchUserCode.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID


	UPDATE #CPCDetail	
	SET Villagename		= 	t_Place.Description				
	FROM t_Place	
	WHERE t_Place.PlaceID	= #CPCDetail.VillageID
	AND ISNULL(#CPCDetail.Villagename,'') = ''
	
	SELECT t_GLOSCheckListImgVerify.* INTO #GLOSCheckListImgVerify
	FROM  CV_GLOSCheckListImgVerify t_GLOSCheckListImgVerify WITH(NOLOCK) ,#CPCDetail
	WHERE t_GLOSCheckListImgVerify.OurBranchID		= #CPCDetail.OurBranchID
	AND t_GLOSCheckListImgVerify.ApplicationFileNo  = #CPCDetail.ApplicationFileNo
	AND t_GLOSCheckListImgVerify.MemberID			= #CPCDetail.MemberID
	AND t_GLOSCheckListImgVerify.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
	
	SELECT t_GLOSSendBackChkLstData.* INTO #GLOSSendBackChkLstData
	FROM cv_GLOSSendBackChkLstData t_GLOSSendBackChkLstData WITH(NOLOCK) ,#CPCDetail
	WHERE t_GLOSSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
	AND t_GLOSSendBackChkLstData.ApplicationFileNo  = #CPCDetail.ApplicationFileNo
	AND t_GLOSSendBackChkLstData.MemberID			= #CPCDetail.MemberID
	AND t_GLOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail	
	SET --[Query Raised Count]			= GLOSQueryDetail.[Query Raised Count]
		[Member CPC Status]				= #CPCDetail.[CPC Status]
		,[Live CPC Query Raised On]		= FORMAT(GLOSQueryDetail.CreatedOn,'dd/MM/yyyy hh:mm tt')
		,[Live CPC Query Responded On]	= FORMAT(GLOSQueryDetail.ConverCreatedOn,'dd/MM/yyyy hh:mm tt') 
	FROM #CPCDetail
	CROSS APPLY (SELECT
					--COUNT(1) [Query Raised Count]
					MIN(ISNULL(t_GLOSSendBackChkLstData.CreatedOn,t_GLOSCheckListImgVerify.CreatedOn)) CreatedOn
					,MAX(t_GLOSSendBackChkLstData.ActionOn) ConverCreatedOn
				FROM #GLOSCheckListImgVerify t_GLOSCheckListImgVerify WITH(NOLOCK)
				LEFT JOIN #GLOSSendBackChkLstData t_GLOSSendBackChkLstData WITH(NOLOCK)
				ON t_GLOSSendBackChkLstData.OurBranchID		    = t_GLOSCheckListImgVerify.OurBranchID
				AND t_GLOSSendBackChkLstData.ApplicationFileNo  = t_GLOSCheckListImgVerify.ApplicationFileNo
				AND t_GLOSSendBackChkLstData.MemberID			= t_GLOSCheckListImgVerify.MemberID
				AND t_GLOSSendBackChkLstData.ActivityID			= t_GLOSCheckListImgVerify.ActivityID
				AND t_GLOSSendBackChkLstData.CheckListCategoryID= t_GLOSCheckListImgVerify.CheckListCategoryID
				AND t_GLOSSendBackChkLstData.CheckListID		= t_GLOSCheckListImgVerify.CheckListID
				INNER JOIN t_GLOSCheckList WITH(NOLOCK)
				ON t_GLOSCheckList.CheckListID = t_GLOSSendBackChkLstData.CheckListID
				WHERE t_GLOSCheckListImgVerify.OurBranchID		= #CPCDetail.OurBranchID
				AND t_GLOSCheckListImgVerify.ApplicationFileNo  = #CPCDetail.ApplicationFileNo
				AND t_GLOSCheckListImgVerify.MemberID			= #CPCDetail.MemberID
			    AND (ISNULL(t_GLOSCheckListImgVerify.ISNotOK,0) = 1 OR ISNULL(t_GLOSSendBackChkLstData.ISNotOK,0) = 1)
			    AND t_GLOSSendBackChkLstData.ActivityID = 'CPCV'
			    AND t_GLOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
			    AND t_GLOSSendBackChkLstData.CreatedOn = (SELECT MAX(GLOSSendBackChkLstData.CreatedOn)
			   											FROM #GLOSSendBackChkLstData GLOSSendBackChkLstData
															INNER JOIN t_GLOSCheckList WITH(NOLOCK)
															ON t_GLOSCheckList.CheckListID = GLOSSendBackChkLstData.CheckListID
															WHERE GLOSSendBackChkLstData.OurBranchID		    = t_GLOSSendBackChkLstData.OurBranchID
															AND GLOSSendBackChkLstData.ApplicationFileNo		= t_GLOSSendBackChkLstData.ApplicationFileNo
															AND GLOSSendBackChkLstData.MemberID					= t_GLOSSendBackChkLstData.MemberID
															AND GLOSSendBackChkLstData.ActivityID				= t_GLOSSendBackChkLstData.ActivityID
															AND GLOSSendBackChkLstData.CheckListCategoryID		= t_GLOSSendBackChkLstData.CheckListCategoryID
															AND GLOSSendBackChkLstData.CheckListID				= t_GLOSSendBackChkLstData.CheckListID
															AND ISNULL(t_GLOSSendBackChkLstData.ISNotOK,0) = 1
															AND GLOSSendBackChkLstData.ActivityID = 'CPCV'
															)
				)GLOSQueryDetail

	UPDATE #CPCDetail	
	SET	[Live Queries] = STUFF((SELECT 
							DISTINCT '|'+t_GLOSCheckList.Description
							FROM #GLOSSendBackChkLstData t_GLOSSendBackChkLstData WITH(NOLOCK)
							INNER JOIN t_GLOSCheckList WITH(NOLOCK)
							ON t_GLOSCheckList.CheckListID = t_GLOSSendBackChkLstData.CheckListID
							WHERE t_GLOSSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
							AND t_GLOSSendBackChkLstData.ApplicationFileNo	= #CPCDetail.ApplicationFileNo
							AND t_GLOSSendBackChkLstData.MemberID			= #CPCDetail.MemberID
							AND ISNULL(t_GLOSSendBackChkLstData.ISNotOK,0) = 1
							AND t_GLOSSendBackChkLstData.ActivityID = 'CPCV'
							AND t_GLOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
							AND t_GLOSSendBackChkLstData.CreatedOn = (SELECT MAX(GLOSSendBackChkLstData.CreatedOn)
														FROM #GLOSSendBackChkLstData GLOSSendBackChkLstData
														INNER JOIN t_GLOSCheckList WITH(NOLOCK)
														ON t_GLOSCheckList.CheckListID = GLOSSendBackChkLstData.CheckListID
														WHERE GLOSSendBackChkLstData.OurBranchID	= t_GLOSSendBackChkLstData.OurBranchID
														AND GLOSSendBackChkLstData.ApplicationFileNo= t_GLOSSendBackChkLstData.ApplicationFileNo
														AND GLOSSendBackChkLstData.MemberID			= t_GLOSSendBackChkLstData.MemberID		
														AND ISNULL(GLOSSendBackChkLstData.ISNotOK,0) = 1
														AND GLOSSendBackChkLstData.ActivityID = 'CPCV'
														)
							FOR XML PATH('')
							),1,1,'')
	FROM #CPCDetail

	UPDATE #CPCDetail	
	SET	[Live Remarks] = STUFF((SELECT 
								 '|'+t_GLOSSendBackChkLstData.CheckListRemarks
							FROM #GLOSSendBackChkLstData t_GLOSSendBackChkLstData WITH(NOLOCK)
							INNER JOIN t_GLOSCheckList WITH(NOLOCK)
							ON t_GLOSCheckList.CheckListID = t_GLOSSendBackChkLstData.CheckListID
							WHERE t_GLOSSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
							AND t_GLOSSendBackChkLstData.ApplicationFileNo	= #CPCDetail.ApplicationFileNo
							AND t_GLOSSendBackChkLstData.MemberID			= #CPCDetail.MemberID
							AND ISNULL(t_GLOSSendBackChkLstData.ISNotOK,0)  = 1
							AND t_GLOSSendBackChkLstData.ActivityID = 'CPCV'
							AND t_GLOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
							AND t_GLOSSendBackChkLstData.CreatedOn = (SELECT MAX(GLOSSendBackChkLstData.CreatedOn)
															FROM #GLOSSendBackChkLstData GLOSSendBackChkLstData
															INNER JOIN t_GLOSCheckList WITH(NOLOCK)
															ON t_GLOSCheckList.CheckListID = GLOSSendBackChkLstData.CheckListID
															WHERE GLOSSendBackChkLstData.OurBranchID	= t_GLOSSendBackChkLstData.OurBranchID
															AND GLOSSendBackChkLstData.ApplicationFileNo= t_GLOSSendBackChkLstData.ApplicationFileNo
															AND GLOSSendBackChkLstData.MemberID			= t_GLOSSendBackChkLstData.MemberID		
															AND ISNULL(GLOSSendBackChkLstData.ISNotOK,0) = 1
															AND GLOSSendBackChkLstData.ActivityID = 'CPCV'
															)
							FOR XML PATH('')
							),1,1,'')
	FROM #CPCDetail


	UPDATE #CPCDetail	
	SET	[Last CPC Query Raised On] = STUFF((SELECT 
									 			DISTINCT '|'+FORMAT(t_GLOSSendBackChkLstData.CreatedOn,'dd/MM/yyyy hh:mm tt')
											FROM #GLOSSendBackChkLstData t_GLOSSendBackChkLstData WITH(NOLOCK)
											INNER JOIN t_GLOSCheckList WITH(NOLOCK)
											ON t_GLOSCheckList.CheckListID = t_GLOSSendBackChkLstData.CheckListID
											WHERE t_GLOSSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
											AND t_GLOSSendBackChkLstData.ApplicationFileNo  = #CPCDetail.ApplicationFileNo
											AND t_GLOSSendBackChkLstData.MemberID			= #CPCDetail.MemberID
											AND ISNULL(t_GLOSSendBackChkLstData.ISNotOK,0) = 1
											AND t_GLOSSendBackChkLstData.ActivityID = 'CPCV'
											AND t_GLOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
											AND t_GLOSSendBackChkLstData.CreatedOn = (SELECT MAX(GLOSSendBackChkLstData.CreatedOn)
															FROM #GLOSSendBackChkLstData GLOSSendBackChkLstData
															INNER JOIN t_GLOSCheckList WITH(NOLOCK)
															ON t_GLOSCheckList.CheckListID = GLOSSendBackChkLstData.CheckListID
							
															WHERE GLOSSendBackChkLstData.OurBranchID	= t_GLOSSendBackChkLstData.OurBranchID
															AND GLOSSendBackChkLstData.ApplicationFileNo= t_GLOSSendBackChkLstData.ApplicationFileNo
															AND GLOSSendBackChkLstData.MemberID			= t_GLOSSendBackChkLstData.MemberID		
															AND ISNULL(GLOSSendBackChkLstData.ISNotOK,0) = 1
															AND GLOSSendBackChkLstData.ActivityID = 'CPCV'
															)
											 FOR XML PATH('')
											 ),1,1,'')
	FROM #CPCDetail

	

	UPDATE #CPCDetail	
	SET [Last CPC Query Responded On] = STUFF((SELECT 
									 			DISTINCT '|'+FORMAT(t_GLOSSendBackChkLstData.ActionOn,'dd/MM/yyyy hh:mm tt')
											 FROM #GLOSSendBackChkLstData t_GLOSSendBackChkLstData WITH(NOLOCK)
											 INNER JOIN t_GLOSCheckList WITH(NOLOCK)
											 ON t_GLOSCheckList.CheckListID = t_GLOSSendBackChkLstData.CheckListID
											 WHERE t_GLOSSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
											 AND t_GLOSSendBackChkLstData.ApplicationFileNo  = #CPCDetail.ApplicationFileNo
											 AND t_GLOSSendBackChkLstData.MemberID			= #CPCDetail.MemberID
											 AND ISNULL(t_GLOSSendBackChkLstData.ISNotOK,0) = 1
											 AND t_GLOSSendBackChkLstData.ActivityID = 'CPCV'
											 AND t_GLOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
											 AND t_GLOSSendBackChkLstData.ActionOn = (SELECT MAX(GLOSSendBackChkLstData.ActionOn)
															FROM #GLOSSendBackChkLstData GLOSSendBackChkLstData
															INNER JOIN t_GLOSCheckList WITH(NOLOCK)
															ON t_GLOSCheckList.CheckListID = GLOSSendBackChkLstData.CheckListID
															WHERE GLOSSendBackChkLstData.OurBranchID	= t_GLOSSendBackChkLstData.OurBranchID
															AND GLOSSendBackChkLstData.ApplicationFileNo= t_GLOSSendBackChkLstData.ApplicationFileNo
															AND GLOSSendBackChkLstData.MemberID			= t_GLOSSendBackChkLstData.MemberID		
															AND ISNULL(GLOSSendBackChkLstData.ISNotOK,0) = 1
															AND GLOSSendBackChkLstData.ActivityID = 'CPCV'
															)
											 FOR XML PATH('')					    
											 ),1,1,'')
	FROM #CPCDetail

	UPDATE #CPCDetail	
	SET	[Previous Queries] = STUFF((SELECT 
								 DISTINCT '|'+t_GLOSCheckList.Description
							 FROM #GLOSSendBackChkLstData t_GLOSSendBackChkLstData WITH(NOLOCK)
							 INNER JOIN t_GLOSCheckList WITH(NOLOCK)
							 ON t_GLOSCheckList.CheckListID = t_GLOSSendBackChkLstData.CheckListID
							 WHERE t_GLOSSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
							 AND t_GLOSSendBackChkLstData.ApplicationFileNo	= #CPCDetail.ApplicationFileNo
							 AND t_GLOSSendBackChkLstData.MemberID			= #CPCDetail.MemberID
							 AND ISNULL(t_GLOSSendBackChkLstData.ISNotOK,0) = 1
							 AND t_GLOSSendBackChkLstData.ActivityID = 'CPCV'
							 AND t_GLOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
							 AND t_GLOSSendBackChkLstData.CreatedOn < (SELECT MAX(GLOSSendBackChkLstData.CreatedOn)
															FROM #GLOSSendBackChkLstData GLOSSendBackChkLstData
															INNER JOIN t_GLOSCheckList WITH(NOLOCK)
															ON t_GLOSCheckList.CheckListID = GLOSSendBackChkLstData.CheckListID
															WHERE GLOSSendBackChkLstData.OurBranchID	= t_GLOSSendBackChkLstData.OurBranchID
															AND GLOSSendBackChkLstData.ApplicationFileNo= t_GLOSSendBackChkLstData.ApplicationFileNo
															AND GLOSSendBackChkLstData.MemberID			= t_GLOSSendBackChkLstData.MemberID		
															AND ISNULL(GLOSSendBackChkLstData.ISNotOK,0) = 1
															AND GLOSSendBackChkLstData.ActivityID = 'CPCV'
															)
							FOR XML PATH('')
							),1,1,'')
	FROM #CPCDetail

	UPDATE #CPCDetail	
	SET	[Previous Remarks] = STUFF((SELECT 
								 DISTINCT '|'+t_GLOSSendBackChkLstData.ResolvedRemarks
							  FROM #GLOSSendBackChkLstData t_GLOSSendBackChkLstData WITH(NOLOCK)
							  INNER JOIN t_GLOSCheckList WITH(NOLOCK)
							  ON t_GLOSCheckList.CheckListID = t_GLOSSendBackChkLstData.CheckListID
							  WHERE t_GLOSSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
							  AND t_GLOSSendBackChkLstData.ApplicationFileNo	= #CPCDetail.ApplicationFileNo
							  AND t_GLOSSendBackChkLstData.MemberID			= #CPCDetail.MemberID
							  AND ISNULL(t_GLOSSendBackChkLstData.ISNotOK,0)  = 1
							  AND t_GLOSSendBackChkLstData.ActivityID = 'CPCV'
							  AND t_GLOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
							  AND t_GLOSSendBackChkLstData.CreatedOn < (SELECT MAX(GLOSSendBackChkLstData.CreatedOn)
															FROM #GLOSSendBackChkLstData GLOSSendBackChkLstData
															INNER JOIN t_GLOSCheckList WITH(NOLOCK)
															ON t_GLOSCheckList.CheckListID = GLOSSendBackChkLstData.CheckListID
															WHERE GLOSSendBackChkLstData.OurBranchID	= t_GLOSSendBackChkLstData.OurBranchID
															AND GLOSSendBackChkLstData.ApplicationFileNo= t_GLOSSendBackChkLstData.ApplicationFileNo
															AND GLOSSendBackChkLstData.MemberID			= t_GLOSSendBackChkLstData.MemberID		
															AND ISNULL(GLOSSendBackChkLstData.ISNotOK,0) = 1
															AND GLOSSendBackChkLstData.ActivityID = 'CPCV'
															)
							FOR XML PATH('')
							),1,1,'')
	FROM #CPCDetail

	UPDATE #CPCDetail	
	SET [LO Mobile] = t_CLient.Mobile
	FROM #CPCDetail
	INNER JOIN t_AccountOfficer  WITH(NOLOCK)
	ON t_AccountOfficer.BankID		= @BankID
	AND t_AccountOfficer.OfficerID	= #CPCDetail.LOName
	INNER JOIN t_CLient WITH(NOLOCK)
	ON t_CLient.CLientID = t_AccountOfficer.CLientID

	UPDATE #CPCDetail
	SET MemberCreatedDate = v_GLOSActivitylog.StartOn
	FROM v_GLOSActivitylog WITH (NOLOCK)
	WHERE #CPCDetail.OurBranchID				= v_GLOSActivitylog.OurBranchID
	AND #CPCDetail.ApplicationFileNo			= v_GLOSActivitylog.ApplicationFileNo
	AND v_GLOSActivitylog.GLOSProcessActivityID = 'MDEN'
	AND v_GLOSActivitylog.ActivityStatusID IS NOT NULL
	AND v_GLOSActivitylog.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail	
	SET [Co-Applicant Mobile no] = t_GLOSClientRelation.Mobile
	FROM #CPCDetail
	INNER JOIN CV_GLOSClientRelation t_GLOSClientRelation WITH(NOLOCK)
	ON t_GLOSClientRelation.OurBranchID			= #CPCDetail.OurBranchID
	AND t_GLOSClientRelation.ApplicationFileNo	= #CPCDetail.ApplicationFileNo
	AND t_GLOSClientRelation.MemberID			= #CPCDetail.MemberID
	AND t_GLOSClientRelation.RelationRoleID = 'C'
	AND t_GLOSClientRelation.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail	
	SET District						= dbo.f_GetDistrictName(t_GLOSClientAddress.StateID,t_GLOSClientAddress.DistrictID) 
		,ClientAddressPlaceCOOrdinate	= t_GLOSClientAddress.AddressPlaceCOOrdinate
		,Pincode = t_GLOSClientAddress.Pincode
		--,[Area Name] = dbo.f_GetPlaceName(t_GLOSClientAddress.PlaceID) 

	FROM #CPCDetail
	INNER JOIN CV_GLOSClientAddress t_GLOSClientAddress WITH(NOLOCK)
	ON t_GLOSClientAddress.OurBranchID			= #CPCDetail.OurBranchID
	AND t_GLOSClientAddress.ApplicationFileNo	= #CPCDetail.ApplicationFileNo
	AND t_GLOSClientAddress.MemberID			= #CPCDetail.MemberID
	AND t_GLOSClientAddress.IsMailingAddress	= 1
	WHERE t_GLOSClientAddress.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET  BranchLatitude		= SUBSTRING(BranchGPSCoordinate,1,CHARINDEX(',',BranchGPSCoordinate)-1 )
		,BranchLangitude	= SUBSTRING(BranchGPSCoordinate,CHARINDEX(',',BranchGPSCoordinate)+1,LEN(BranchGPSCoordinate)-CHARINDEX(',',BranchGPSCoordinate))
	FROM #CPCDetail

	UPDATE #CPCDetail
	SET  [Area Name] = t_place.Description
		,PlaceID	 = t_place.PlaceID
	FROM #CPCDetail
	INNER JOIN CV_GLOSapplication t_GLOSapplication WITH(NOLOCK)
	ON t_GLOSapplication.OurBranchID		= #CPCDetail.OurBranchID
	AND t_GLOSapplication.ApplicationFileNo = #CPCDetail.ApplicationFileNo
	INNER JOIN t_place
	ON t_place.PlaceID = t_GLOSapplication.villageid
	WHERE t_GLOSapplication.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

	UPDATE #CPCDetail
	SET ClientAddressPlaceLatitude		= t_villagesurveydet.latitude
		,ClientAddressPlaceLangitude	= t_villagesurveydet.longitude
	FROM #CPCDetail
	INNER JOIN t_villagesurveydet  WITH(NOLOCK)
	ON 	t_villagesurveydet.OurBranchiD	= #CPCDetail.OurBranchID
	AND t_villagesurveydet.SurveyNo		= #CPCDetail.PlaceID

	UPDATE #CPCDetail
	SET BranchGeoGraphy = GEOGRAPHY::Point(BranchLatitude , BranchLangitude , 4326)
	FROM #CPCDetail
	WHERE BranchGPSCoordinate IS NOT NULL

	UPDATE #CPCDetail
	SET DifferenceinDistance = (BranchGeoGraphy.STDistance(GEOGRAPHY::Point(ISNULL(ClientAddressPlaceLatitude,0),ISNULL(ClientAddressPlaceLangitude,0), 4326))/1000.00) 
	FROM #CPCDetail
	WHERE LEN(BranchGPSCoordinate) >= 4
	AND LEN(ClientAddressPlaceLangitude) >= 4
 
	UPDATE #CPCDetail	
	SET [Applicant Mobile]			 = MobileNo
		,[Branch to Village Distance]= DifferenceinDistance
		,[CPC FTR Flag]				 = CASE WHEN ISNULL([Query Raised Count],0) = 0 AND [Previous Queries] IS NULL THEN 'FTR' ELSE 'NFTR' END
		,[Query Raised]				 = CASE WHEN ISNULL([Query Raised Count],0) = 0 AND [Previous Queries] IS NULL THEN 'No' ELSE 'Yes' END
		,[Is Query Raised] = CASE WHEN ISNULL([Query Raised Count],0) = 0 AND [Previous Queries] IS NULL THEN 'No' ELSE 'Yes' END
		,[Member CPC Status] =  CASE WHEN ISNULL([Query Raised Count],0) = 0 AND [Previous Queries] IS NULL AND [Member CPC Status] <> 'Not Started'
									THEN 'Completed' 
									WHEN [Last CPC Query Responded On] IS NOT NULL THEN 'Query Responded'
									WHEN [Last CPC Query Raised On] IS NOT NULL THEN 'Query Raised' 
									ELSE [Member CPC Status]
									END
	FROM #CPCDetail

	UPDATE #CPCDetail
	SET CurrentBMID = AccountOfficer.OfficerID,
		ReportingOfficerID = AccountOfficer.ReportingOfficerID
	FROM #CPCDetail
	INNER JOIN (SELECT TOP 1 
					t_AccountOfficer.OfficerID,
					t_AccountOfficer.ReportingOfficerID,
					t_AccountOfficer.ReportingBranchID
				FROM t_AccountOfficer
				INNER JOIN #CPCDetail
				ON t_AccountOfficer.ReportingBranchID = #CPCDetail.OurBranchID
				WHERE t_AccountOfficer.OfficertypeID = 'BM'
				AND t_AccountOfficer.Status = 'A'
				ORDER BY 
					t_AccountOfficer.JoinedDate ASC
				)AccountOfficer
	ON AccountOfficer.ReportingBranchID = #CPCDetail.OurBranchID

	UPDATE	#CPCDetail
	SET		CurrentASMID	= t_AccountOfficer.OfficerID
	FROM	#CPCDetail
	INNER JOIN	t_AccountOfficer WITH (NOLOCK)
	ON	t_AccountOfficer.BankID				= @BankID
	AND	t_AccountOfficer.OfficerID			= #CPCDetail.ReportingOfficerID
	WHERE	t_AccountOfficer.OfficerTypeID	= 'ARM'
	AND		t_AccountOfficer.Status			= 'A'

	UPDATE #CPCDetail
	SET	CurrentBMName			 = dbo.f_GetOfficerName(@BankID,CurrentBMID),
		CurrentASMName			 = dbo.f_GetOfficerName(@BankID,CurrentASMID)
	FROM #CPCDetail
	
	UPDATE #CPCDetail
	SET NoOfDependents = GLOSClientRelation.DependCOunt 
	FROM #CPCDetail
	INNER JOIN (SELECT 
					COUNT(1) DependCOunt,
					t_GLOSClientRelation.OurBranchID,
					t_GLOSClientRelation.ApplicationFileNo ,
					t_GLOSClientRelation.MemberID			  
				FROM CV_GLOSClientRelation t_GLOSClientRelation WITH (NOLOCK)
				INNER JOIN #CPCDetail
				ON  t_GLOSClientRelation.OurBranchID		   = #CPCDetail.OurBranchID
				AND t_GLOSClientRelation.ApplicationFileNo	   = #CPCDetail.ApplicationFileNo
				AND t_GLOSClientRelation.MemberID			   = #CPCDetail.MemberID
				WHERE t_GLOSClientRelation.RelationRoleID		   = 'G' 
				AND t_GLOSClientRelation.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
				GROUP BY
					t_GLOSClientRelation.OurBranchID,
					t_GLOSClientRelation.ApplicationFileNo ,
					t_GLOSClientRelation.MemberID	
				)GLOSClientRelation
	ON GLOSClientRelation.OurBranchID		   = #CPCDetail.OurBranchID
	AND GLOSClientRelation.ApplicationFileNo   = #CPCDetail.ApplicationFileNo
	AND GLOSClientRelation.MemberID			   = #CPCDetail.MemberID

	IF @ApplicationTypeID = 'GLOW'
	BEGIN
		UPDATE #CPCDetail
		SET ApplicationType = 'GLOW'
		FROM #CPCDetail
	END
	END

	IF @ApplicationTypeID = 'ILOS'
	BEGIN
		IF ISNULL(@IsDisbAccounts,0) = 0
		BEGIN
			INSERT INTO #CPCDetail
			(
				OurBranchID			
				,ApplicationFileNo	
				,MemberID			
				,ApplicationID		
				,ClientID
				,[Center ID]
				,[Center Name]
				,[Group ID]
				,[Group Name]
				,[Application Current Stage]
				,[Branch ID]
				,[Application Number]
				,[Member ID]	
				,[Member Name]
				,SendBackStatusID
				,LOName
				--,MobileNo
				,BranchGPSCoordinate
			)
			SELECT 
				 t_iLOSApplication.OurBranchID
				,t_iLOSClient.iLOSFileNo
				,t_iLOSClient.MemberID 
				,t_iLOSApplication.BRNETApplicationID
				,ISNULL(t_iLOSClient.ExistingClientID,t_iLOSClient.BRNetClientID)
				,''
				,''
				,''
				,''
				--,dbo.fn_GetSystemCodeDesc('iLOSProcessStageID',t_iLOSApplication.iLOSProcessStageID,@LanguageID)
				--	+' '+dbo.fn_GetSystemCodeDesc('iLOSStageStatusID',t_iLOSApplication.iLOSStageStatusID,@LanguageID)
				,dbo.fn_GetSystemCodeDesc('iLOSStageStatusID',t_iLOSApplication.iLOSStageStatusID,@LanguageID)
				,t_iLOSApplication.OurBranchID
				,t_iLOSClient.iLOSFileNo
				,t_iLOSClient.MemberID
				,t_iLOSClient.Name
				,t_iLOSApplication.SendBackStatusID
				,t_iLOSApplication.OfficerID
				--,t_iLOSClient.MobileNo
				,#Branch.GPSCoordinate BranchGPSCoordinate 
			FROM t_iLOSApplication WITH(NOLOCK) --cv_ilosclient
			INNER JOIN #Branch
			ON #Branch.OurBranchID = t_iLOSApplication.OurBranchID
			INNER JOIN t_iLOSClient WITH(NOLOCK) --CV_IlosApplication 
			ON t_iLOSClient.iLOSFileNo	= t_iLOSApplication.iLOSFileNo
			WHERE NOT EXISTS (SELECT 1
							FROM t_Loan WITH(NOLOCK)
							WHERE t_Loan.OurBranchID = t_iLOSApplication.OurBranchID
							AND t_Loan.ApplicationID = t_iLOSApplication.BrnetApplicationID
							AND t_Loan.FirstDisbursementDate IS NOT NULL
							)
			AND t_IlosClient.Deletedon IS NULL
			AND t_iLOSClient.ClientRoleID = 'A'
			AND t_iLOSApplication.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
			
		END
		ELSE
		BEGIN
			INSERT INTO #CPCDetail
			(
				OurBranchID			
				,ApplicationFileNo	
				,MemberID			
				,ApplicationID		
				,ClientID
				,[Center ID]
				,[Center Name]
				,[Group ID]
				,[Group Name]
				,[Application Current Stage]
				,[Branch ID]
				,[Application Number]
				,[Member ID]	
				,[Member Name]
				,SendBackStatusID
				,LOName
				--,MobileNo
				,BranchGPSCoordinate
			)
			SELECT
				 t_iLOSApplication.OurBranchID
				,t_iLOSClient.iLOSFileNo
				,t_iLOSClient.MemberID 
				,t_iLOSApplication.BRNETApplicationID
				,ISNULL(t_iLOSClient.ExistingClientID,t_iLOSClient.BRNetClientID)
				,''
				,''
				,''
				,''
				,dbo.fn_GetSystemCodeDesc('iLOSStageStatusID',t_iLOSApplication.iLOSStageStatusID,@LanguageID)
				,t_iLOSApplication.OurBranchID
				,t_iLOSClient.iLOSFileNo
				,t_iLOSClient.MemberID
				,t_iLOSClient.Name
				,t_iLOSApplication.SendBackStatusID
				,t_iLOSApplication.OfficerID
				--,t_iLOSClient.MobileNo
				,#Branch.GPSCoordinate BranchGPSCoordinate
			FROM t_Loan WITH(NOLOCK)
			INNER JOIN #Branch
			ON #Branch.OurBranchID = t_Loan.OurBranchID
			INNER JOIN t_iLOSApplication WITH(NOLOCK) --CV_ILOSApplication 
			ON  t_iLOSApplication.OurBranchID		  = t_Loan.OurBranchID
			AND t_iLOSApplication.BrnetApplicationID  = t_Loan.ApplicationID
			INNER JOIN t_iLOSClient WITH(NOLOCK) --CV_ILOSClient 
			ON  t_iLOSClient.iLOSFileNo	    =  t_iLOSApplication.iLOSFileNo	
			WHERE t_Loan.FirstDisbursementDate BETWEEN ISNULL(@FromDate, t_Loan.FirstDisbursementDate) 
												AND ISNULL(@ToDate, t_Loan.FirstDisbursementDate)
			AND t_IlosClient.Deletedon IS NULL
			AND t_iLOSClient.ClientRoleID = 'A'
			AND t_iLOSApplication.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
			
		END

		IF NOT EXISTS (SELECT 1
					  FROM #CPCDetail
					  )
		BEGIN
			RAISERROR('BREXDB602201',16,1)  --No details found
			RETURN
		END

		UPDATE #CPCDetail
		SET #CPCDetail.[CPC Status]			= CASE WHEN t_ILOSActivityLog.ActivityStatusID = 'PEND' THEN 'Pending'
													WHEN t_ILOSActivityLog.ActivityStatusID = 'INPR' THEN 'In-Progress'
													WHEN t_ILOSActivityLog.ActivityStatusID = 'COMP' THEN 'Completed'
											  END,
			#CPCDetail.[Owner Name]			= t_ILOSActivityLog.OfficerID,
			#CPCDetail.[CPC Done By]		= t_ILOSActivityLog.OfficerID,
			#CPCDetail.[CPC Started On]		= t_ILOSActivityLog.StartOn,
			#CPCDetail.[CPC Completed On]	= CASE WHEN t_ILOSActivityLog.ActivityStatusID = 'COMP' THEN t_ILOSActivityLog.StatusOn ELSE NULL END
		FROM t_ILOSActivityLog WITH(NOLOCK) --v_ILOSActivityLog
		WHERE  #CPCDetail.ApplicationFileNo		= t_ILOSActivityLog.iLOSFileNo
		AND t_ILOSActivityLog.ProcessActivityID = 'CPCV'
		
		UPDATE #CPCDetail
		SET #CPCDetail.[CPC Status]			= CASE WHEN t_ILOSActivityLog.ActivityStatusID = 'PEND' THEN 'Pending'
													WHEN t_ILOSActivityLog.ActivityStatusID = 'INPR' THEN 'In-Progress'
													WHEN t_ILOSActivityLog.ActivityStatusID = 'COMP' THEN 'Completed'
												END,
			#CPCDetail.[Owner Name]			= dbo.f_GetOfficerName(@BankID,t_ILOSActivityLog.OfficerID) ,
			#CPCDetail.[CPC Done By]		= t_ILOSActivityLog.OfficerID,
			#CPCDetail.[CPC Started On]		= t_ILOSActivityLog.StartOn,
			#CPCDetail.[CPC Completed On]	= CASE WHEN t_ILOSActivityLog.ActivityStatusID = 'COMP' THEN t_ILOSActivityLog.StatusOn ELSE NULL END
		FROM t_ILOSActivityLog WITH(NOLOCK) --V_ILOSActivityLog
		WHERE  #CPCDetail.ApplicationFileNo		= t_ILOSActivityLog.iLOSFileNo
		AND t_ILOSActivityLog.ProcessActivityID = 'CSOV'
		AND [CPC Status] IS NULL

		UPDATE #CPCDetail
		SET #CPCDetail.[CPC Status]			= 'Not Started',
			#CPCDetail.[Owner Name]			= NULL,
			#CPCDetail.[CPC Done By]		= NULL,
			#CPCDetail.[CPC Started On]		= NULL,
			#CPCDetail.[CPC Completed On]	= NULL
		FROM #CPCDetail
		INNER JOIN t_ILOSActivityLog WITH(NOLOCK) --V_ILOSActivityLog
		ON #CPCDetail.ApplicationFileNo			  = t_ILOSActivityLog.iLOSFileNo
		WHERE t_ILOSActivityLog.ProcessActivityID = 'BACV'
		AND t_ILOSActivityLog.StartOn IS NOT NULL
		AND #CPCDetail.[CPC Status] IS NULL
	
		UPDATE #CPCDetail
		SET CreditApprovedBy = ''
		FROM t_LOSLoanApprovalDetail WITH (NOLOCK)
		WHERE t_LOSLoanApprovalDetail.OurBranchID		= #CPCDetail.OurBranchID
		AND  t_LOSLoanApprovalDetail.ApplicationFileNo	= #CPCDetail.ApplicationFileNo
		AND t_LOSLoanApprovalDetail.MemberID			= #CPCDetail.MemberID
		--AND t_LOSLoanApprovalDetail.SourceTypeID		= 'GLOS'
		AND t_LOSLoanApprovalDetail.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
		
		UPDATE #CPCDetail	
		SET MobileNo = t_ilosClientAddress.Mobile
		FROM #CPCDetail
		INNER JOIN t_ilosClientAddress WITH(NOLOCK) --cv_ilosClientRelation
		ON  t_ilosClientAddress.iLOSFileNo	  = #CPCDetail.ApplicationFileNo
		AND t_ilosClientAddress.MemberID	  = #CPCDetail.MemberID
		INNER JOIN t_ilosClient WITH(NOLOCK)
		ON t_IlosClient.ilosFileno = t_ilosClientAddress.iLOSFileNo
		AND t_IlosClient.MemberID  = t_ilosClientAddress.MemberID
		AND t_ilosClient.ClientRoleID = 'A'

		IF ISNULL(@IsCPCNotStarted,0) = 1  -- Extra logic, else old logic
		BEGIN
			DELETE FROM #CPCDetail
			WHERE ISNULL([CPC Status],'') <> 'Not Started'
		END

		UPDATE #CPCDetail
		SET #CPCDetail.[Owner Name]			= t_AccountOfficer.OfficerID,
			#CPCDetail.[CPC Done By]		= t_AccountOfficer.OfficerID
		FROM t_ilosCheckListImgVerify WITH(NOLOCK)
		INNER JOIN #CPCDetail
		ON  #CPCDetail.OurBranchID				= t_ILOSCheckListImgVerify.OurBranchID
		AND #CPCDetail.ApplicationFileNo		= t_ILOSCheckListImgVerify.iLOSFileNo
		AND #CPCDetail.MemberID					= t_ILOSCheckListImgVerify.MemberID
		AND t_ILOSCheckListImgVerify.ActivityID = 'CPCV'
		INNER JOIN t_user  WITH(NOLOCK)
		ON t_ILOSCheckListImgVerify.CreatedBy =t_user.OperatorID
		INNER JOIN t_AccountOfficer  WITH(NOLOCK)
		ON t_AccountOfficer.BankID	= @BankID
		AND t_AccountOfficer.ClientID = t_user.ClientID
		WHERE #CPCDetail.[CPC Done By] IS NULL
		AND t_ILOSCheckListImgVerify.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET #CPCDetail.[Application Current Stage]	= (SELECT TOP 1 dbo.fn_GetSystemCodeDesc('ILOSProcessActivityID',t_ILOSActivityLog.ProcessActivityID,@LanguageID)
														FROM t_ILOSActivityLog WITH(NOLOCK)
														WHERE  #CPCDetail.ApplicationFileNo		= t_ILOSActivityLog.iLOSFileNo
														AND t_ILOSActivityLog.ActivityStatusID	IS NOT NULL 
														ORDER BY t_ILOSActivityLog.ProcessStageID DESC
															,t_ILOSActivityLog.ActivityOrderNo DESC
														)
		
		UPDATE #CPCDetail
		SET #CPCDetail.[Loan Scheme ID]		= t_iLOSClientLoan.ProductID,
			#CPCDetail.Tenure				= t_iLOSClientLoan.Term,
			#CPCDetail.[Loan Amount]		= t_iLOSClientLoan.LoanAmount
		FROM t_iLOSClientLoan WITH(NOLOCK) --t_iLOSClientLoan
		WHERE #CPCDetail.ApplicationFileNo	= t_iLOSClientLoan.iLOSFileNo
		AND #CPCDetail.MemberID				= t_iLOSClientLoan.MemberID
		--AND t_iLOSClientLoan.RecordStatusID = 'A'
	
		UPDATE #CPCDetail
		SET #CPCDetail.[Loan Account ID]= t_Loan.AccountID,
			#CPCDetail.[Loan Amount]	= t_Loan.LoanAmount,
			#CPCDetail.Tenure			= t_Loan.RepaymentTerm
		FROM t_Loan WITH(NOLOCK)
		WHERE #CPCDetail.OurBranchID	= t_Loan.OurBranchID
		AND #CPCDetail.ApplicationID	= t_Loan.ApplicationID
		AND t_Loan.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET #CPCDetail.[Loan Disbursed By] = t_Loan.DisbursedBy,
			#CPCDetail.[Loan Disbursed On] = t_Loan.FirstDisbursementDate,
			#CPCDetail.AccountID		= t_Loan.AccountID,
			#CPCDetail.LoanSeries		= t_Loan.LoanSeries
		FROM t_Loan WITH(NOLOCK)
		WHERE #CPCDetail.OurBranchID	= t_Loan.OurBranchID
		AND #CPCDetail.ApplicationID	= t_Loan.ApplicationID
		AND t_Loan.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET OldBranchID   = t_GroupMemberSchemeTransfer.OurBranchID,
		    OldAccountID  = t_GroupMemberSchemeTransfer.LoanAccountID, 
		    OldLoanSeries = t_GroupMemberSchemeTransfer.LoanSeries  
		FROM #CPCDetail
		INNER JOIN t_GroupMemberSchemeTransfer WITH(NOLOCK)
		ON t_GroupMemberSchemeTransfer.NewBranchID       = #CPCDetail.OurBranchID 
		AND t_GroupMemberSchemeTransfer.NewLoanAccountID = #CPCDetail.AccountID 
		AND t_GroupMemberSchemeTransfer.NewLoanSeries    = #CPCDetail.Loanseries
		--WHERE #CPCDetail.LoanTransferDate IS NOT NULL
		WHERE t_GroupMemberSchemeTransfer.NewBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET OurBranchID	 = t_Loan.OurBranchID,
		    ApplicationID = t_Loan.ApplicationID
		FROM #CPCDetail
		INNER JOIN t_Loan WITH(NOLOCK)
		ON t_Loan.OurBranchID   = #CPCDetail.OldBranchID 
		AND t_Loan.AccountID    = #CPCDetail.OldAccountID 
		AND t_Loan.LoanSeries   = #CPCDetail.OldLoanseries
		--WHERE #CPCDetail.LoanTransferDate IS NOT NULL
		WHERE t_Loan.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET #CPCDetail.[Loan Scheme ID]	= t_WFLoanApplication.LoanSchemeID
			,#CPCDetail.Tenure			= t_WFLoanApplication.LoanTerm	
			,#CPCDetail.[Loan Amount]	= t_WFLoanApplication.LoanAmount
			,#CPCDetail.[Application Current Stage] = dbo.fn_GetSystemCodeDesc('WFAdvStageID',t_WFLoanApplication.WFAdvStageID,@LanguageID)												
		FROM t_WFLoanApplication WITH(NOLOCK)
		WHERE #CPCDetail.OurBranchID	= t_WFLoanApplication.OurBranchID
		AND #CPCDetail.ApplicationID	= t_WFLoanApplication.ApplicationID
		AND t_WFLoanApplication.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET #CPCDetail.[Loan Scheme ID]	= t_WFLoanApplication.LoanSchemeID
		FROM t_WFLoanApplication WITH(NOLOCK)
		WHERE #CPCDetail.OurBranchID	= t_WFLoanApplication.OurBranchID
		AND #CPCDetail.ApplicationID	= t_WFLoanApplication.ApplicationID
		AND #CPCDetail.[Loan Scheme ID] IS NULL
		AND t_WFLoanApplication.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET [Loan Scheme] = t_Product.Description
		FROM #CPCDetail
		INNER JOIN t_Product WITH(NOLOCK)
		ON t_Product.BankID  = @BankID
		AND t_Product.ProductID = #CPCDetail.[Loan Scheme ID]

		UPDATE #CPCDetail
		SET #CPCDetail.[CPC Status]	= CASE WHEN SendBackStatusID = 'SNT' THEN 'Query Raised'
											WHEN SendBackStatusID = 'SUB' THEN 'Query Responded'
										ELSE #CPCDetail.[CPC Status]
									END

		FROM #CPCDetail WITH(NOLOCK)
		WHERE #CPCDetail.[CPC Status] <> 'Completed'


		--Old Activities Case
		UPDATE #CPCDetail
		SET #CPCDetail.[Bene Check Status]		= CASE WHEN t_ILOSappruleLog.RuleStatusID = 'FAIL' 
															AND Remarks LIKE '%Name Mismatch%' AND IsOverridden = 1
														THEN 'Name Mismatch Overridden'
													WHEN t_ILOSappruleLog.RuleStatusID = 'FAIL' 
															AND Remarks LIKE '%Name Mismatch%' AND IsOverridden = 0
														THEN 'Name Mismatch'
													WHEN t_ILOSappruleLog.RuleStatusID = 'FAIL' AND Remarks NOT LIKE '%Name Mismatch%'						
														THEN 'Failure'
													WHEN t_ILOSappruleLog.RuleStatusID = 'FAIL' 
														THEN 'Failure'
													WHEN t_ILOSappruleLog.RuleStatusID = 'PASS' 
														THEN 'Success'
													WHEN IsOverridden = 1													
													THEN 'Beneficiary Check Rule is '+ 'Overridden'
												END,
			#CPCDetail.[Bene Check Done By]		= ISNULL(t_ILOSappruleLog.OverriddenBy,t_ILOSappruleLog.PassedBy),
			#CPCDetail.[Bene check Done On]		= CASE WHEN ISNULL(t_ILOSappruleLog.OverriddenBy,t_ILOSappruleLog.PassedBy) IS NOT NULL 
														THEN t_ILOSappruleLog.StatusOn ELSE NULL END--,
		FROM t_ILOSappruleLog WITH(NOLOCK) 
		WHERE #CPCDetail.ApplicationFileNo		= t_ILOSappruleLog.iLOSFileNo
		AND t_ILOSappruleLog.RuleID			= 'ILBNVL'
		AND t_ILOSappruleLog.ProcessActivityID = 'PROF'
		AND t_ILOSappruleLog.ProcessStageID    <>  'APP'
	

		--1. First checkup for BENCHK Rule
		UPDATE #CPCDetail
		SET #CPCDetail.[Bene Check Status]		= CASE WHEN t_ILOSappruleLog.RuleStatusID = 'FAIL' 
															AND IsOverridden = 1
														THEN 'Success'
													WHEN t_ILOSappruleLog.RuleStatusID = 'FAIL' 
														THEN 'Failure'
													WHEN t_ILOSappruleLog.RuleStatusID = 'PASS' 
														THEN 'Success'
													WHEN t_ILOSappruleLog.IsOverridden = 1
														THEN 'Beneficiary Check Rule is '+ 'Overridden'
													ELSE 'Beneficiary Check Rule is '+dbo.fn_getSystemcodedesc('ILOSRuleStatusID',t_ILOSappruleLog.RuleStatusID,@LanguageID)
												END,
			#CPCDetail.[Bene Check Done By]		= ISNULL(t_ILOSappruleLog.OverriddenBy,t_ILOSappruleLog.PassedBy),
			#CPCDetail.[Bene check Done On]		= CASE WHEN ISNULL(t_ILOSappruleLog.OverriddenBy,t_ILOSappruleLog.PassedBy) IS NOT NULL 
														THEN t_ILOSappruleLog.StatusOn ELSE NULL END
		FROM t_ILOSappruleLog WITH(NOLOCK) --v_GLOSMemberRuleLog
		WHERE #CPCDetail.ApplicationFileNo	= t_ILOSappruleLog.iLOSFileNo
		AND t_ILOSappruleLog.RuleID		= 'ILBNVL'
		AND t_ILOSappruleLog.ProcessActivityID IN ('BACV','PROF')
		AND t_ILOSappruleLog.ProcessStageID	= 'APP'
		AND #CPCDetail.[Bene Check Status] IS NULL

		UPDATE #CPCDetail
		SET #CPCDetail.[Loan Booked By]	= t_WFLoanBooking.CreatedBy,
			#CPCDetail.[Loan Booked ON]	= t_WFLoanBooking.BookedDate
		FROM t_WFLoanBooking WITH(NOLOCK)
		WHERE #CPCDetail.OurBranchID	= t_WFLoanBooking.OurBranchID
		AND #CPCDetail.ApplicationID	= t_WFLoanBooking.ApplicationID
		AND t_WFLoanBooking.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
		
		UPDATE #CPCDetail
		SET #CPCDetail.[Payment Amount]		= t_ClientBankTransaction.NetDisbursementAmount,
			#CPCDetail.[Payment Status]		= CASE WHEN #CPCDetail.[Loan Disbursed On] IS NOT NULL 
													AND t_ClientBankTransaction.TrxStatusID NOT IN ('COM','ERR') THEN 'In-Pending'
												WHEN #CPCDetail.[Loan Disbursed On] IS NOT NULL 
													AND t_ClientBankTransaction.TrxStatusID = 'COM' THEN 'Success'
												WHEN #CPCDetail.[Loan Disbursed On] IS NOT NULL 
													AND t_ClientBankTransaction.TrxStatusID = 'ERR' THEN 'Error' 
											END,
			#CPCDetail.[Payment Status On]	= t_ClientBankTransaction.TrxStatusOn,
			#CPCDetail.[UTR NO]				= t_ClientBankTransaction.UTRNo,
			#CPCDetail.[Application Current Stage]	= CASE WHEN t_ClientBankTransaction.TrxBatchID IS NOT NULL 
														THEN dbo.fn_GetSystemCodeDesc('TACSTatusID',t_ClientBankTransaction.TrxStatusID,@LanguageID)
													ELSE #CPCDetail.[Application Current Stage] END,
			#CPCDetail.TrxRowID				= t_ClientBankTransaction.TrxRowID,
			#CPCDetail.BatchID				= t_ClientBankTransaction.IMPSBatchID
		FROM #CPCDetail
		INNER JOIN cv_ClientBankTransaction t_ClientBankTransaction WITH(NOLOCK)
		ON #CPCDetail.OurBranchID		= t_ClientBankTransaction.OurBranchID
		AND #CPCDetail.AccountID		= t_ClientBankTransaction.LoanAccountID
		AND #CPCDetail.LoanSeries		= t_ClientBankTransaction.LoanSeries
		AND t_ClientBankTransaction.RecordStatusID = 'A'
		WHERE t_ClientBankTransaction.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET #CPCDetail.BatchID				= t_ClientBankTransaction.IMPSBatchID
		FROM #CPCDetail
		INNER JOIN cv_ClientBankTransaction t_ClientBankTransaction WITH(NOLOCK)
		ON #CPCDetail.OurBranchID		= t_ClientBankTransaction.OurBranchID
		AND #CPCDetail.ApplicationFileNo= t_ClientBankTransaction.ApplicationFileNo
		AND #CPCDetail.MemberID			= t_ClientBankTransaction.MemberID
		WHERE ISNULL(#CPCDetail.BatchID,'') = ''
		AND t_ClientBankTransaction.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET #CPCDetail.BeneficiaryName		= t_ClientBankTransaction.BeneficiaryName
			,NameMatchScore					= t_CLientBankTransaction.Score
			,TransactionAccountID			= t_CLientBankTransaction.AccountID
		FROM #CPCDetail
		INNER JOIN cv_ClientBankTransaction t_ClientBankTransaction WITH(NOLOCK)
		ON #CPCDetail.OurBranchID		= t_ClientBankTransaction.OurBranchID
		AND #CPCDetail.ApplicationFileNo= t_ClientBankTransaction.ApplicationFileNo
		AND #CPCDetail.MemberID			= t_ClientBankTransaction.MemberID
		AND t_ClientBankTransaction.RecordStatusID = 'A'
		AND t_ClientBankTransaction.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET #CPCDetail.[Payment Initiated by]= t_OnLineFundTransferLog.PassedBy,
			#CPCDetail.[Payment Initiated On]= t_OnLineFundTransferLog.PassedOn		
		FROM t_OnLineFundTransferLog WITH(NOLOCK)
		WHERE #CPCDetail.TrxRowID		= t_OnLineFundTransferLog.TrxRowID
		AND #CPCDetail.OurBranchID		= t_OnLineFundTransferLog.OurBranchID
		AND t_OnLineFundTransferLog.FTStageID		= 'FI'
		AND t_OnLineFundTransferLog.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET	#CPCDetail.[Payment Approved By]= t_OnLineFundTransferLog.PassedBy,
			#CPCDetail.[Payment Approved On]= t_OnLineFundTransferLog.PassedOn
		FROM t_OnLineFundTransferLog WITH(NOLOCK)
		WHERE #CPCDetail.TrxRowID		= t_OnLineFundTransferLog.TrxRowID
		AND #CPCDetail.OurBranchID		= t_OnLineFundTransferLog.OurBranchID
		AND t_OnLineFundTransferLog.FTStageID		= 'FA'
		AND t_OnLineFundTransferLog.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET #CPCDetail.[Branch Name] = t_SystemBranchSetting.BranchName
			,#CPCDetail.[BC ID]		 = t_SystemBranchSetting.BCCodeID
			,#CPCDetail.[BC Name]	 = t_BCMaintenance.BCDescription
			,#CPCDetail.RegionID	 = t_SystemBranchRegion.RegionID
		FROM #CPCDetail
		INNER JOIN  t_SystemBranchSetting WITH(NOLOCK)
		ON #CPCDetail.OurBranchID	= t_SystemBranchSetting.OurBranchID
		INNER JOIN t_SystemBranchRegion WITH (NOLOCK)  
		ON t_SystemBranchRegion.BankID				= @BankID  
		AND	t_SystemBranchRegion.OurBranchID		= t_SystemBranchSetting.OurBranchID
		LEFT JOIN t_BCMaintenance WITH(NOLOCK)
		ON t_BCMaintenance.BankID	= @BankID
		AND t_SystemBranchSetting.BCCodeID = t_BCMaintenance.BCCodeID
		WHERE t_SystemBranchSetting.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET #CPCDetail.[Is Query Raised] = 'YES',
			#CPCDetail.[Query Raised On] = t_ILOSSendBackChkLstData.CreatedOn
		FROM #CPCDetail
		INNER JOIN t_ILOSSendBackChkLstData WITH(NOLOCK) --cv_ILOSSendBackChkLstData
		ON #CPCDetail.OurBranchID		= t_ILOSSendBackChkLstData.OurBranchID
		AND #CPCDetail.ApplicationFileNo= t_ILOSSendBackChkLstData.iLOSFileNo
		AND #CPCDetail.MemberID			= t_ILOSSendBackChkLstData.MemberID
		AND t_ILOSSendBackChkLstData.IsNotOK = 1
		INNER JOIN t_ILOSCheckList
		ON t_ILOSCheckList.CheckListID = t_ILOSSendBackChkLstData.CheckListID
		WHERE t_ILOSSendBackChkLstData.ActivityID = 'CPCV'  --Hold ,'CSOV'
		AND t_ILOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET #CPCDetail.[Queries] = STUFF((SELECT 
											DISTINCT '|'+ t_ILOSCheckList.Description --ISNULL(dbo.fn_GetUserCodeDesc('SendBackreasonID',t_GLOSSendBackChkLstData.CheckListReasonID),'')
										FROM t_ILOSSendBackChkLstData WITH(NOLOCK) --cv_ILOSSendBackChkLstData
										INNER JOIN t_ILOSCheckList WITH(NOLOCK)
										ON t_ILOSCheckList.CheckListID = t_ILOSSendBackChkLstData.CheckListID
										WHERE #CPCDetail.OurBranchID	= t_ILOSSendBackChkLstData.OurBranchID
										AND #CPCDetail.ApplicationFileNo= t_ILOSSendBackChkLstData.iLOSFileNo
										AND #CPCDetail.MemberID			= t_ILOSSendBackChkLstData.MemberID
										AND t_ILOSSendBackChkLstData.IsNotOK = 1
										AND t_ILOSSendBackChkLstData.ActivityID = 'CPCV'
										AND t_ILOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
										FOR XML PATH('')),1,1,'')										
								
		FROM #CPCDetail
		WHERE #CPCDetail.[Is Query Raised] = 'YES'

		UPDATE #CPCDetail
		SET #CPCDetail.[Query Raised Count] = (SELECT 
													COUNT(1)
												FROM t_ILOSSendBackChkLstData WITH(NOLOCK) --t_ILOSSendBackChkLstData
												INNER JOIN t_ILOSCheckList WITH(NOLOCK)
												ON t_ILOSCheckList.CheckListID = t_ILOSSendBackChkLstData.CheckListID
												WHERE #CPCDetail.OurBranchID	= t_ILOSSendBackChkLstData.OurBranchID
												AND #CPCDetail.ApplicationFileNo= t_ILOSSendBackChkLstData.iLOSFileNo
												AND #CPCDetail.MemberID			= t_ILOSSendBackChkLstData.MemberID
												AND t_ILOSSendBackChkLstData.IsNotOK = 1
												AND t_ILOSSendBackChkLstData.ActivityID = 'CPCV'
												AND t_ILOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
											  )																		
		FROM #CPCDetail
		WHERE #CPCDetail.[Is Query Raised] = 'YES'

		UPDATE #CPCDetail
		SET [Sendback Count] =SendCount.sendback
		FROM #CPCDetail
		LEFT JOIN (SELECT
					t_ILOSSendBackChkLstData.OurBranchID,
					t_ILOSSendBackChkLstData.ILOSFileNo,
					#CPCDetail.[Member ID],
					COUNT( DISTINCT t_ILOSSendBackChkLstData.SendBackRefNo) sendback
					FROM t_ILOSSendBackChkLstData WITH(NOLOCK) --CV_ILOSSendBackChkLstData
					INNER JOIN #CPCDetail WITH(NOLOCK)
					ON #CPCDetail.[Branch ID]				= t_ILOSSendBackChkLstData.OurBranchID
					AND #CPCDetail.[Application Number]		= t_ILOSSendBackChkLstData.iLOSFileNo
					AND #CPCDetail.[Member ID]				= t_ILOSSendBackChkLstData.MemberID
					WHERE t_ILOSSendBackChkLstData.ActivityID='CPCV'
					AND #CPCDetail.[Member ID] = (SELECT MIN(CPCDetail.MemberID)
												FROM #CPCDetail CPCDetail
												WHERE CPCDetail.[Branch ID]				= #CPCDetail.OurBranchID
												AND CPCDetail.[Application Number]		= #CPCDetail.ApplicationFileNo
												AND CPCDetail.MemberID				    = #CPCDetail.MemberID
												)
					AND t_ILOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
					GROUP BY 
						t_ILOSSendBackChkLstData.OurBranchID,
						t_ILOSSendBackChkLstData.ILOSFileNo,
						#CPCDetail.[Member ID]
				)SendCount
		ON #CPCDetail.[Branch ID]				= SendCount.OurBranchID
		AND #CPCDetail.[Application Number]		= SendCount.ILOSFileNo
		AND #CPCDetail.[Member ID]				= SendCount.[Member ID]

		UPDATE #CPCDetail
		SET BranchManager = t_Accountofficer.Name	
		FROM #CPCDetail
		INNER JOIN t_Accountofficer WITH(NOLOCK)
		ON t_Accountofficer.BankID		       = @BankID
		AND t_Accountofficer.ReportingBranchID =  #CPCDetail.[Branch ID]
		WHERE t_Accountofficer.OfficerTypeID   = 'BM'
		AND t_Accountofficer.ResignedDate IS NULL

		UPDATE #CPCDetail
		SET [File bucket] = CASE WHEN ProcessActivityID='BACV' AND ActivityStatusID='PEND' THEN  'LO'
								 WHEN ProcessActivityID='BACV' AND ActivityStatusID='INPR' THEN  'CPC'
							END
		FROM #CPCDetail
		INNER JOIN t_iLOSActivityLog WITH(NOLOCK)--cv_iLOSActivityLog
		ON  #CPCDetail.ApplicationFileNo= t_iLOSActivityLog.ILOSFileNo
		AND ProcessActivityID='BACV'
		AND EXISTS(SELECT 1 FROM t_iLOSActivityLog  ActivityLog 
					WHERE t_iLOSActivityLog.ILOSFileNo	= ActivityLog.ILOSFileNo
					AND ActivityLog.ProcessActivityID	='PROF'
					AND ActivityLog.ActivityStatusID	='COMP'
					)

		UPDATE #CPCDetail
		SET [HDFC Remarks] = t_ClientBankTransaction.ErrorMsg
		FROM #CPCDetail
		INNER JOIN cv_ClientBankTransaction t_ClientBankTransaction WITH(NOLOCK)
		ON #CPCDetail.[Branch ID]				= t_ClientBankTransaction.OurBranchID
		AND #CPCDetail.[Application Number]		= t_ClientBankTransaction.ApplicationFileNo
		AND #CPCDetail.[Member ID]				= t_ClientBankTransaction.MemberID
		AND t_ClientBankTransaction.RecordStatusID='A'
		AND t_ClientBankTransaction.TrxRowID	= (SELECT MAX(transac.TrxRowID) FROM  cv_ClientBankTransaction transac
													WHERE transac.OurBranchID		= t_ClientBankTransaction.OurBranchID
													AND transac.ApplicationFileNo	= t_ClientBankTransaction.ApplicationFileNo
													AND transac.MemberID			= t_ClientBankTransaction.MemberID
													AND transac.ErrorMsg IS NOT NULL
													AND t_ClientBankTransaction.RecordStatusID='A'
													--AND transac.TrxStatusID <>'BAP'
													)
		WHERE  t_ClientBankTransaction.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET TrxRefID	   = t_ClientBankTransaction.TrxRowID
		FROM #CPCDetail
		INNER JOIN cv_ClientBankTransaction t_ClientBankTransaction WITH(NOLOCK)
		ON #CPCDetail.[Branch ID]				= t_ClientBankTransaction.OurBranchID
		AND #CPCDetail.[Application Number]		= t_ClientBankTransaction.ApplicationFileNo
		AND #CPCDetail.[Member ID]				= t_ClientBankTransaction.MemberID
		AND t_ClientBankTransaction.RecordStatusID='A'
		AND t_ClientBankTransaction.TrxRowID	= (SELECT MAX(transac.TrxRowID) FROM cv_ClientBankTransaction transac
													WHERE transac.OurBranchID		= t_ClientBankTransaction.OurBranchID
													AND transac.ApplicationFileNo	= t_ClientBankTransaction.ApplicationFileNo
													AND transac.MemberID			= t_ClientBankTransaction.MemberID
													AND t_ClientBankTransaction.RecordStatusID='A'
													)
		WHERE  t_ClientBankTransaction.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail
		SET [HDFC Remarks] = DET.ErrorMsg
		FROM #CPCDetail
		CROSS APPLY(SELECT TOP 1 
							t_rblbanktrxextractlog.ErrorMsg,
							#CPCDetail.TrxRefID	
					FROM cv_rblbanktrxextractlog t_rblbanktrxextractlog WITH(NOLOCK)
					WHERE #CPCDetail.TrxRefID				= t_rblbanktrxextractlog.TrxRefID
					AND t_rblbanktrxextractlog.ErrorMsg	IS NOT NULL 
					AND #CPCDetail.[HDFC Remarks] IS NULL
					ORDER BY RequestOn DESC
					)DET

		UPDATE #CPCDetail
		SET [Application current Stage Status]	= CASE WHEN t_iLOSActivityLog.ActivityStatusID = 'PEND' THEN 'Pending'
														WHEN t_iLOSActivityLog.ActivityStatusID = 'INPR' THEN 'In-Progress'
														WHEN t_iLOSActivityLog.ActivityStatusID = 'COMP' THEN 'Completed'
														WHEN t_iLOSActivityLog.ActivityStatusID = 'ERRR' THEN 'Error' 
													END 
		FROM #CPCDetail
		INNER JOIN t_iLOSActivityLog WITH(NOLOCK) --v_iLOSActivityLog
		ON  #CPCDetail.ApplicationFileNo= t_iLOSActivityLog.iLOSFileNo
		AND t_iLOSActivityLog.StatusOn = (SELECT MAX(ilosActivityLog.StatusOn)
										FROM t_iLOSActivityLog ilosActivityLog 
										WHERE ilosActivityLog.ILOSFileNo	= t_iLOSActivityLog.iLOSFileNo
										)
		AND t_iLOSActivityLog.ActivityOrderNo = (SELECT MAX(ilosActivityLog2.ActivityOrderNo)
											FROM t_iLOSActivityLog ilosActivityLog2 
											WHERE  ilosActivityLog2.ILOSFileNo	= t_iLOSActivityLog.iLOSFileNo
											AND ilosActivityLog2.StatusOn			= t_iLOSActivityLog.StatusOn
											)
	
		--Once brnet submission done
		UPDATE #CPCDetail
		SET [Application current Stage]			= dbo.fn_GetSystemCodeDesc('WFAdvStageID',t_WFLoanApplication.WFAdvStageID,@LanguageID)
			,[Application current Stage Status] = dbo.fn_GetSystemCodeDesc('WFAppStatusID',t_WFLoanApplication.WFAppStatusID,@LanguageID)
		FROM #CPCDetail
		INNER JOIN t_WFLoanApplication WITH(NOLOCK)
		ON t_WFLoanApplication.OurBranchID		= #CPCDetail.OUrBranchID
		AND t_WFLoanApplication.ApplicationID	= #CPCDetail.ApplicationID

	
		DROP TABLE IF EXISTS #AllRemarks
		CREATE TABLE #AllRemarks 
		(
		    iLOSFileNo        BIGINT,
		    MemberID          INT,
		    AllBACVRemarks    NVARCHAR(MAX)
		);
		

		INSERT INTO #AllRemarks (iLOSFileNo, MemberID, AllBACVRemarks)
		SELECT 
		    t_iLOSClientBankAc.iLOSFileNo,
		    t_iLOSClientBankAc.MemberID,
		    STUFF((
		        SELECT 
		            ',' + ISNULL(LTRIM(RTRIM(t2.BACVRemarks)), 'NULL')
		        FROM t_iLOSClientBankAc t2
		        WHERE t2.iLOSFileNo = t_iLOSClientBankAc.iLOSFileNo
		          AND t2.MemberID   = t_iLOSClientBankAc.MemberID
		          AND t2.ProductTypeID = 'SB'
		        ORDER BY t2.SerialID
		        FOR XML PATH(''), TYPE
		    ).value('.', 'NVARCHAR(MAX)'), 1, 1, '')
		FROM t_iLOSClientBankAc
		INNER JOIN #CPCDetail
		    ON t_iLOSClientBankAc.iLOSFileNo = #CPCDetail.ApplicationFileNo
		   AND t_iLOSClientBankAc.MemberID   = #CPCDetail.MemberID
		WHERE t_iLOSClientBankAc.ProductTypeID = 'SB'
		GROUP BY t_iLOSClientBankAc.iLOSFileNo, t_iLOSClientBankAc.MemberID;

			--SELECT * FROM #AllRemarks;

		UPDATE #CPCDetail
		SET 
		    BankName                 = t_iLOSClientBankAc.InstitutionName,
		    BankAcNo                 = t_iLOSClientBankAc.AccountID,
		    BankBranch               = t_iLOSClientBankAc.BranchName,
		    AccountHoldername        = t_iLOSClientBankAc.AccountName,
		    IFSCcode                 = t_iLOSClientBankAc.ISFCCode,
		    BACVRemarks              = t_iLOSClientBankAc.BACVRemarks,               
		    PreviousBenecheckRemarks = ISNULL(#AllRemarks.AllBACVRemarks, ''),
		    BenecheckSendbackCount   = CASE 
		                                   WHEN ISNULL(#AllRemarks.AllBACVRemarks, '') = '' THEN 0
		                                   ELSE LEN(#AllRemarks.AllBACVRemarks) - LEN(REPLACE(#AllRemarks.AllBACVRemarks, ',', '')) + 1
		                               END,
		    ModifiedBy               = t_iLOSClientBankAc.ModifiedBy,
		    Modifiedon               = t_iLOSClientBankAc.Modifiedon
		FROM t_iLOSClientBankAc  WITH (NOLOCK)
		LEFT JOIN #AllRemarks 
		ON t_iLOSClientBankAc.iLOSFileNo = #AllRemarks.iLOSFileNo 
		AND t_iLOSClientBankAc.MemberID  = #AllRemarks.MemberID
		WHERE t_iLOSClientBankAc.iLOSFileNo = #CPCDetail.ApplicationFileNo
		AND t_iLOSClientBankAc.MemberID   = #CPCDetail.MemberID
		AND t_iLOSClientBankAc.ProductTypeID = 'SB'
		AND t_iLOSClientBankAc.SerialID = (
							SELECT MAX(DT.SerialID)
							FROM t_iLOSClientBankAc DT WITH (NOLOCK)
							WHERE DT.iLOSFileNo = t_iLOSClientBankAc.iLOSFileNo
							AND DT.MemberID		= t_iLOSClientBankAc.MemberID
							AND DT.ProductTypeID = 'SB'
		               )

		
		UPDATE #CPCDetail	
		SET VillageID = t_ilosclientaddress.PlaceID	
		FROM t_ilosclientaddress	
		WHERE t_ilosclientaddress.IlosFileNo	= #CPCDetail.ApplicationFileNo	
		AND	  t_ilosclientaddress.MemberID		= #CPCDetail.MemberID
		AND #CPCDetail.VillageID IS NULL

		UPDATE #CPCDetail	
		SET Villagename		= 	t_BranchUserCode.Description				
		FROM t_BranchUserCode	WITH(NOLOCK)
		WHERE t_BranchUserCode.OurBranchID	= #CPCDetail.OurBranchID	
		AND	t_BranchUserCode.ID				= 'VillageID'	
		AND t_BranchUserCode.SubCodeID		= #CPCDetail.VillageID
		AND t_BranchUserCode.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail	
		SET Villagename		= 	t_Place.Description				
		FROM t_Place	
		WHERE t_Place.PlaceID	= #CPCDetail.VillageID
		AND ISNULL(#CPCDetail.Villagename,'') = ''

		SELECT t_ILOSCheckListImgVerify.* INTO #ILOSCheckListImgVerify
		FROM t_ILOSCheckListImgVerify,#CPCDetail
		WHERE t_ILOSCheckListImgVerify.OurBranchID		= #CPCDetail.OurBranchID
		AND t_ILOSCheckListImgVerify.iLOSFileNo  = #CPCDetail.ApplicationFileNo
		AND t_ILOSCheckListImgVerify.MemberID			= #CPCDetail.MemberID
		AND t_ILOSCheckListImgVerify.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		
		SELECT t_ILOSSendBackChkLstData.* INTO #ILOSSendBackChkLstData
		FROM  t_ILOSSendBackChkLstData,#CPCDetail --CV_ILOSSendBackChkLstData
		WHERE t_ILOSSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
		AND t_ilosSendBackChkLstData.iLOSFileNo			= #CPCDetail.ApplicationFileNo
		AND t_ilosSendBackChkLstData.MemberID			= #CPCDetail.MemberID
		AND t_ILOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID

		UPDATE #CPCDetail	
		SET --[Query Raised Count]			= GLOSQueryDetail.[Query Raised Count]
			[Member CPC Status]				= #CPCDetail.[CPC Status]
			,[Live CPC Query Raised On]		= FORMAT(GLOSQueryDetail.CreatedOn,'dd/MM/yyyy hh:mm tt')
			,[Live CPC Query Responded On]	= FORMAT(GLOSQueryDetail.ConverCreatedOn,'dd/MM/yyyy hh:mm tt') 
		FROM #CPCDetail
		CROSS APPLY (SELECT
						--COUNT(1) [Query Raised Count]
						MIN(ISNULL(t_ILOSSendBackChkLstData.CreatedOn,t_ILOSCheckListImgVerify.CreatedOn)) CreatedOn
						,MAX(t_ILOSSendBackChkLstData.ActionOn) ConverCreatedOn
					FROM #ILOSCheckListImgVerify t_ILOSCheckListImgVerify WITH(NOLOCK)
					LEFT JOIN #ILOSSendBackChkLstData t_ILOSSendBackChkLstData WITH(NOLOCK)
					ON t_ILOSSendBackChkLstData.OurBranchID		    = t_ILOSCheckListImgVerify.OurBranchID
					AND t_ILOSSendBackChkLstData.iLOSFileNo         = t_ILOSCheckListImgVerify.iLOSFileNo
					AND t_ILOSSendBackChkLstData.MemberID			= t_ILOSCheckListImgVerify.MemberID
					AND t_ILOSSendBackChkLstData.ActivityID			= t_ILOSCheckListImgVerify.ActivityID
					AND t_ILOSSendBackChkLstData.CheckListCategoryID= t_ILOSCheckListImgVerify.CheckListCategoryID
					AND t_ILOSSendBackChkLstData.CheckListID		= t_ILOSCheckListImgVerify.CheckListID
					INNER JOIN t_ilosCheckList
					ON t_ilosCheckList.CheckListID = t_ILOSSendBackChkLstData.CheckListID
					WHERE t_ILOSCheckListImgVerify.OurBranchID		= #CPCDetail.OurBranchID
					AND t_ILOSCheckListImgVerify.iLOSFileNo  = #CPCDetail.ApplicationFileNo
					AND t_ILOSCheckListImgVerify.MemberID			= #CPCDetail.MemberID
					AND (ISNULL(t_ILOSCheckListImgVerify.ISNotOK,0) = 1 OR ISNULL(t_ilosSendBackChkLstData.ISNotOK,0) = 1)
					AND t_ILOSSendBackChkLstData.ActivityID = 'CPCV'
					AND t_ILOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
					AND t_ILOSSendBackChkLstData.CreatedOn = (SELECT MAX(ilosSendBackChkLstData.CreatedOn)
																FROM #ILOSSendBackChkLstData ilosSendBackChkLstData
																INNER JOIN t_ilosCheckList
																ON t_ilosCheckList.CheckListID = ilosSendBackChkLstData.CheckListID
																WHERE ilosSendBackChkLstData.OurBranchID		    = t_ILOSSendBackChkLstData.OurBranchID
																AND ilosSendBackChkLstData.iLOSFileNo		= t_ILOSSendBackChkLstData.iLOSFileNo
																AND ilosSendBackChkLstData.MemberID					= t_ILOSSendBackChkLstData.MemberID
																AND ilosSendBackChkLstData.ActivityID				= t_ILOSSendBackChkLstData.ActivityID
																AND ilosSendBackChkLstData.CheckListCategoryID		= t_ILOSSendBackChkLstData.CheckListCategoryID
																AND ilosSendBackChkLstData.CheckListID				= t_ILOSSendBackChkLstData.CheckListID
																AND ISNULL(t_ILOSSendBackChkLstData.ISNotOK,0) = 1
																AND ilosSendBackChkLstData.ActivityID = 'CPCV'
																)
					)GLOSQueryDetail

		UPDATE #CPCDetail	
		SET	[Live Queries] = STUFF((SELECT 
								DISTINCT '|'+t_ilosCheckList.Description
								FROM #ILOSSendBackChkLstData t_ilosSendBackChkLstData WITH(NOLOCK)
								INNER JOIN t_ilosCheckList
								ON t_ilosCheckList.CheckListID = t_ilosSendBackChkLstData.CheckListID
								WHERE t_ilosSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
								AND t_ilosSendBackChkLstData.iLOSFileNo	= #CPCDetail.ApplicationFileNo
								AND t_ilosSendBackChkLstData.MemberID			= #CPCDetail.MemberID
								AND ISNULL(t_ilosSendBackChkLstData.ISNotOK,0) = 1
								AND t_ilosSendBackChkLstData.ActivityID = 'CPCV'
								AND t_ILOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
								AND t_ilosSendBackChkLstData.CreatedOn = (SELECT MAX(ilosSendBackChkLstData.CreatedOn)
															FROM #ILOSSendBackChkLstData ilosSendBackChkLstData
															INNER JOIN t_ilosCheckList
															ON t_ilosCheckList.CheckListID = ilosSendBackChkLstData.CheckListID
															WHERE ilosSendBackChkLstData.OurBranchID	= t_ilosSendBackChkLstData.OurBranchID
															AND ilosSendBackChkLstData.iLOSFileNo= t_ilosSendBackChkLstData.iLOSFileNo
															AND ilosSendBackChkLstData.MemberID			= t_ilosSendBackChkLstData.MemberID		
															AND ISNULL(ilosSendBackChkLstData.ISNotOK,0) = 1
															AND ilosSendBackChkLstData.ActivityID = 'CPCV'
															)
								FOR XML PATH('')
								),1,1,'')
		FROM #CPCDetail

		UPDATE #CPCDetail	
		SET	[Live Remarks] = STUFF((SELECT 
									 '|'+t_ilosSendBackChkLstData.CheckListRemarks
								FROM #ILOSSendBackChkLstData t_ilosSendBackChkLstData WITH(NOLOCK)
								INNER JOIN t_ilosCheckList
								ON t_ilosCheckList.CheckListID = t_ilosSendBackChkLstData.CheckListID
								WHERE t_ilosSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
								AND t_ilosSendBackChkLstData.iLOSFileNo	= #CPCDetail.ApplicationFileNo
								AND t_ilosSendBackChkLstData.MemberID			= #CPCDetail.MemberID
								AND ISNULL(t_ilosSendBackChkLstData.ISNotOK,0)  = 1
								AND t_ilosSendBackChkLstData.ActivityID = 'CPCV'
								AND t_ILOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
								AND t_ilosSendBackChkLstData.CreatedOn = (SELECT MAX(IlosSendBackChkLstData.CreatedOn)
																FROM #ILOSSendBackChkLstData IlosSendBackChkLstData
																INNER JOIN t_ilosCheckList WITH(NOLOCK)
																ON t_ilosCheckList.CheckListID = IlosSendBackChkLstData.CheckListID
																WHERE IlosSendBackChkLstData.OurBranchID	= t_ilosSendBackChkLstData.OurBranchID
																AND IlosSendBackChkLstData.iLOSFileNo= t_ilosSendBackChkLstData.iLOSFileNo
																AND IlosSendBackChkLstData.MemberID			= t_ilosSendBackChkLstData.MemberID		
																AND ISNULL(IlosSendBackChkLstData.ISNotOK,0) = 1
																AND IlosSendBackChkLstData.ActivityID = 'CPCV'
																)
								FOR XML PATH('')
								),1,1,'')
		FROM #CPCDetail


		UPDATE #CPCDetail	
		SET	[Last CPC Query Raised On] = STUFF((SELECT 
										 			DISTINCT '|'+FORMAT(t_IlosSendBackChkLstData.CreatedOn,'dd/MM/yyyy hh:mm')
												 FROM #ILOSSendBackChkLstData t_IlosSendBackChkLstData WITH(NOLOCK)
												 INNER JOIN t_ilosCheckList
												 ON t_ilosCheckList.CheckListID = t_IlosSendBackChkLstData.CheckListID
												 WHERE t_IlosSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
												 AND t_IlosSendBackChkLstData.iLOSFileNo        = #CPCDetail.ApplicationFileNo
												 AND t_IlosSendBackChkLstData.MemberID			= #CPCDetail.MemberID
												 AND ISNULL(t_IlosSendBackChkLstData.ISNotOK,0) = 1
												 AND t_IlosSendBackChkLstData.ActivityID = 'CPCV'
												 AND t_ILOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
												 AND t_IlosSendBackChkLstData.CreatedOn = (SELECT MAX(ilosSendBackChkLstData.CreatedOn)
																							FROM #ILOSSendBackChkLstData ilosSendBackChkLstData
																							INNER JOIN t_ilosCheckList
																							ON t_ilosCheckList.CheckListID = ilosSendBackChkLstData.CheckListID
																							WHERE ilosSendBackChkLstData.OurBranchID	= t_IlosSendBackChkLstData.OurBranchID
																							AND ilosSendBackChkLstData.iLOSFileNo= t_IlosSendBackChkLstData.iLOSFileNo
																							AND ilosSendBackChkLstData.MemberID			= t_IlosSendBackChkLstData.MemberID		
																							AND ISNULL(ilosSendBackChkLstData.ISNotOK,0) = 1
																							AND ilosSendBackChkLstData.ActivityID = 'CPCV'
																							)
												 FOR XML PATH('')
												 ),1,1,'')
		FROM #CPCDetail

	

		UPDATE #CPCDetail	
		SET [Last CPC Query Responded On] = STUFF((SELECT 
										 			DISTINCT '|'+FORMAT(t_ilosSendBackChkLstData.ActionOn,'dd/MM/yyyy hh:mm')
												 FROM #ILOSSendBackChkLstData t_ilosSendBackChkLstData WITH(NOLOCK)
												 INNER JOIN t_IlosCheckList WITH(NOLOCK)
												 ON t_IlosCheckList.CheckListID = t_ilosSendBackChkLstData.CheckListID
												 WHERE t_ilosSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
												 AND t_ilosSendBackChkLstData.iLOSFileNo  = #CPCDetail.ApplicationFileNo
												 AND t_ilosSendBackChkLstData.MemberID			= #CPCDetail.MemberID
												 AND ISNULL(t_ilosSendBackChkLstData.ISNotOK,0) = 1
												 AND t_ilosSendBackChkLstData.ActivityID = 'CPCV'
												 AND t_ILOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
												 AND t_ilosSendBackChkLstData.ActionOn = (SELECT MAX(ilosSendBackChkLstData.ActionOn)
																FROM #ILOSSendBackChkLstData ilosSendBackChkLstData
																INNER JOIN t_IlosCheckList
																ON t_IlosCheckList.CheckListID = ilosSendBackChkLstData.CheckListID
																WHERE ilosSendBackChkLstData.OurBranchID	= t_ilosSendBackChkLstData.OurBranchID
																AND ilosSendBackChkLstData.iLOSFileNo= t_ilosSendBackChkLstData.iLOSFileNo
																AND ilosSendBackChkLstData.MemberID			= t_ilosSendBackChkLstData.MemberID		
																AND ISNULL(ilosSendBackChkLstData.ISNotOK,0) = 1
																AND ilosSendBackChkLstData.ActivityID = 'CPCV'
																)
												 FOR XML PATH('')					    
												 ),1,1,'')
		FROM #CPCDetail

		UPDATE #CPCDetail	
		SET	[Previous Queries] = STUFF((SELECT 
									 DISTINCT '|'+t_ilosCheckList.Description
								FROM #ILOSSendBackChkLstData t_ilosSendBackChkLstData WITH(NOLOCK)
								INNER JOIN t_ilosCheckList
								ON t_ilosCheckList.CheckListID = t_ilosSendBackChkLstData.CheckListID
								WHERE t_ilosSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
								AND t_ilosSendBackChkLstData.iLOSFileNo	        = #CPCDetail.ApplicationFileNo
								AND t_ilosSendBackChkLstData.MemberID			= #CPCDetail.MemberID
								AND ISNULL(t_ilosSendBackChkLstData.ISNotOK,0) = 1
								AND t_ilosSendBackChkLstData.ActivityID = 'CPCV'
								AND t_ILOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
								AND t_ilosSendBackChkLstData.CreatedOn < (SELECT MAX(ilosSendBackChkLstData.CreatedOn)
																FROM #ILOSSendBackChkLstData ilosSendBackChkLstData
																INNER JOIN t_ilosCheckList
																ON t_ilosCheckList.CheckListID = ilosSendBackChkLstData.CheckListID
																WHERE ilosSendBackChkLstData.OurBranchID	= t_ilosSendBackChkLstData.OurBranchID
																AND ilosSendBackChkLstData.iLOSFileNo= t_ilosSendBackChkLstData.iLOSFileNo
																AND ilosSendBackChkLstData.MemberID			= t_ilosSendBackChkLstData.MemberID		
																AND ISNULL(ilosSendBackChkLstData.ISNotOK,0) = 1
																AND ilosSendBackChkLstData.ActivityID = 'CPCV'
																)
								FOR XML PATH('')
								),1,1,'')
		FROM #CPCDetail

		UPDATE #CPCDetail	
		SET	[Previous Remarks] = STUFF((SELECT 
									 DISTINCT '|'+t_ilosSendBackChkLstData.ResolvedRemarks
								FROM #ILOSSendBackChkLstData t_ilosSendBackChkLstData WITH(NOLOCK)
								INNER JOIN t_ilosCheckList
								ON t_ilosCheckList.CheckListID = t_ilosSendBackChkLstData.CheckListID
								WHERE t_ilosSendBackChkLstData.OurBranchID		= #CPCDetail.OurBranchID
								AND t_ilosSendBackChkLstData.iLOSFileNo	= #CPCDetail.ApplicationFileNo
								AND t_ilosSendBackChkLstData.MemberID			= #CPCDetail.MemberID
								AND ISNULL(t_ilosSendBackChkLstData.ISNotOK,0)  = 1
								AND t_ilosSendBackChkLstData.ActivityID = 'CPCV'
								AND t_ILOSSendBackChkLstData.OurBranchID BETWEEN @MinBranchID AND @MaxBranchID
								AND t_ilosSendBackChkLstData.CreatedOn < (SELECT MAX(ilosSendBackChkLstData.CreatedOn)
																FROM #ILOSSendBackChkLstData ilosSendBackChkLstData
																INNER JOIN t_ilosCheckList
																ON t_ilosCheckList.CheckListID              = ilosSendBackChkLstData.CheckListID
																WHERE ilosSendBackChkLstData.OurBranchID	= t_ilosSendBackChkLstData.OurBranchID
																AND ilosSendBackChkLstData.iLOSFileNo= t_ilosSendBackChkLstData.iLOSFileNo
																AND ilosSendBackChkLstData.MemberID			= t_ilosSendBackChkLstData.MemberID		
																AND ISNULL(ilosSendBackChkLstData.ISNotOK,0) = 1
																AND ilosSendBackChkLstData.ActivityID = 'CPCV'
																)
								FOR XML PATH('')
								),1,1,'')
		FROM #CPCDetail

		UPDATE #CPCDetail	
		SET [LO Mobile] = t_CLient.Mobile
		FROM #CPCDetail
		INNER JOIN t_AccountOfficer  WITH(NOLOCK)
		ON t_AccountOfficer.BankID		= @BankID
		AND t_AccountOfficer.OfficerID	= #CPCDetail.LOName
		INNER JOIN t_CLient WITH(NOLOCK)
		ON t_CLient.CLientID = t_AccountOfficer.CLientID

		UPDATE #CPCDetail
		SET MemberCreatedDate = t_ilosClient.CreatedOn
		FROM #CPCDetail WITH (NOLOCK)
		INNER JOIN t_ilosClient WITH(NOLOCK) 
		ON  t_ilosClient.iLOSFileNo	  = #CPCDetail.ApplicationFileNo
		AND t_ilosClient.MemberID	  = #CPCDetail.MemberID

		--UPDATE #CPCDetail
		--SET MemberCreatedDate = t_ilosActivitylog.StartOn
		--FROM t_ilosActivitylog WITH (NOLOCK) --cv_ilosActivitylog
		--WHERE  #CPCDetail.ApplicationFileNo			= t_ilosActivitylog.iLOSFileNo
		--AND t_ilosActivitylog.ProcessActivityID = 'MDEN'
		--AND t_ilosActivitylog.ActivityStatusID IS NOT NULL

		UPDATE #CPCDetail	
		SET [Co-Applicant Mobile no] = t_ilosClientAddress.Mobile
		FROM #CPCDetail
		INNER JOIN t_ilosClientAddress WITH(NOLOCK) --cv_ilosClientRelation
		ON  t_ilosClientAddress.iLOSFileNo	= #CPCDetail.ApplicationFileNo
		AND t_ilosClientAddress.MemberID	= #CPCDetail.MemberID
		INNER JOIN t_ilosClient WITH(NOLOCK)
		ON t_IlosClient.ilosFileno = t_ilosClientAddress.iLOSFileNo
		AND t_IlosClient.MemberID  = t_ilosClientAddress.MemberID
		AND t_ilosClient.ClientRoleID = 'C'

		--UPDATE #CPCDetail	
		--SET [Co-Applicant Mobile no] = t_ilosClientRelation.MobileNo
		--FROM #CPCDetail
		--INNER JOIN t_ilosClientRelation WITH(NOLOCK) --cv_ilosClientRelation
		--ON  t_ilosClientRelation.iLOSFileNo	  = #CPCDetail.ApplicationFileNo
		--AND t_ilosClientRelation.MemberID	  = #CPCDetail.MemberID
		--AND t_ilosClientRelation.RelationRoleID = 'C'

		UPDATE #CPCDetail	
		SET District						= dbo.f_GetDistrictName(t_ilosClientAddress.StateID,t_ilosClientAddress.DistrictID) 
			,ClientAddressPlaceCOOrdinate	= ''
			,Pincode						= t_iLOSClientAddress.Pincode
			,[Area Name]					= dbo.f_GetPlaceName(t_ilosClientAddress.PlaceID) 
		FROM #CPCDetail
		INNER JOIN t_ilosClientAddress WITH(NOLOCK) --cv_ilosClientAddress
		ON  t_ilosClientAddress.iLOSFileNo	= #CPCDetail.ApplicationFileNo
		AND t_ilosClientAddress.MemberID			= #CPCDetail.MemberID
		AND t_ilosClientAddress.IsMailingAddress	= 1

		UPDATE #CPCDetail
		SET BranchLatitude		= SUBSTRING(BranchGPSCoordinate,1,CHARINDEX(',',BranchGPSCoordinate)-1 )
			,BranchLangitude	= SUBSTRING(BranchGPSCoordinate,CHARINDEX(',',BranchGPSCoordinate)+1,LEN(BranchGPSCoordinate)-CHARINDEX(',',BranchGPSCoordinate))
		FROM #CPCDetail


		UPDATE #CPCDetail
		SET [Area Name] = dbo.f_GetPlaceName(t_ClientMultipleAddress.PlaceID)
		FROM #CPCDetail
		INNER JOIN t_ClientMultipleAddress WITH(NOLOCK)
		ON t_ClientMultipleAddress.ClientID = #CPCDetail.ClientID

		UPDATE #CPCDetail
		SET ClientAddressPlaceLatitude		= t_villagesurveydet.latitude
			,ClientAddressPlaceLangitude	= t_villagesurveydet.longitude
		FROM #CPCDetail
		INNER JOIN t_villagesurveydet
		ON t_villagesurveydet.OurBranchiD	= #CPCDetail.OurBranchID
		AND t_villagesurveydet.SurveyNo		= #CPCDetail.VillageID

		UPDATE #CPCDetail
		SET BranchGeoGraphy = GEOGRAPHY::Point(BranchLatitude , BranchLangitude , 4326)
		FROM #CPCDetail
		WHERE BranchGPSCoordinate IS NOT NULL

		UPDATE #CPCDetail
		SET DifferenceinDistance = (BranchGeoGraphy.STDistance(GEOGRAPHY::Point(ISNULL(ClientAddressPlaceLatitude,0),ISNULL(ClientAddressPlaceLangitude,0), 4326))/1000.00) 
		FROM #CPCDetail
		WHERE LEN(BranchGPSCoordinate) >= 4
		AND LEN(ClientAddressPlaceLangitude) >= 4
 
		UPDATE #CPCDetail	
		SET [Applicant Mobile]			 = MobileNo
			,[Branch to Village Distance]= DifferenceinDistance
			,[CPC FTR Flag]				 = CASE WHEN ISNULL([Query Raised Count],0) = 0 AND [Previous Queries] IS NULL THEN 'FTR' ELSE 'NFTR' END
			,[Query Raised]				 = CASE WHEN ISNULL([Query Raised Count],0) = 0 AND [Previous Queries] IS NULL THEN 'No' ELSE 'Yes' END
			,[Is Query Raised]   = CASE WHEN ISNULL([Query Raised Count],0) = 0 AND [Previous Queries] IS NULL THEN 'No' ELSE 'Yes' END
			,[Member CPC Status] =  CASE WHEN ISNULL([Query Raised Count],0) = 0 AND [Previous Queries] IS NULL AND [Member CPC Status] <> 'Not Started'
										THEN 'Completed' 
										WHEN [Last CPC Query Responded On] IS NOT NULL THEN 'Query Responded'
										WHEN [Last CPC Query Raised On] IS NOT NULL THEN 'Query Raised' 
										ELSE [Member CPC Status]
										END
		FROM #CPCDetail

		UPDATE #CPCDetail
		SET CurrentBMID = AccountOfficer.OfficerID,
			ReportingOfficerID = AccountOfficer.ReportingOfficerID
		FROM #CPCDetail
		CROSS APPLY (SELECT TOP 1 
						t_AccountOfficer.OfficerID,
						t_AccountOfficer.ReportingOfficerID
					FROM t_AccountOfficer
					WHERE t_AccountOfficer.OfficertypeID = 'BM'
					AND t_AccountOfficer.Status = 'A'
					AND t_AccountOfficer.ReportingBranchID = #CPCDetail.OurBranchID
					ORDER BY 
						t_AccountOfficer.JoinedDate ASC
					)AccountOfficer

		UPDATE	#CPCDetail
		SET		CurrentASMID	= t_AccountOfficer.OfficerID
		FROM	#CPCDetail
		INNER JOIN	t_AccountOfficer WITH (NOLOCK)
		ON	t_AccountOfficer.BankID = @BankID
		AND	t_AccountOfficer.OfficerID = #CPCDetail.ReportingOfficerID
		WHERE	t_AccountOfficer.OfficerTypeID	= 'ARM'
		AND		t_AccountOfficer.Status = 'A'

		UPDATE #CPCDetail
		SET	CurrentBMName	= dbo.f_GetOfficerName(@BankID,CurrentBMID),
			CurrentASMName	= dbo.f_GetOfficerName(@BankID,CurrentASMID)
		FROM #CPCDetail

		UPDATE #CPCDetail
		SET NoOfDependents = iLOSClientRelation.DependCOunt 
		FROM #CPCDetail
		CROSS APPLY(SELECT COUNT(1) DependCOunt
					FROM t_iLOSClientRelation WITH (NOLOCK)
					WHERE t_iLOSClientRelation.iLOSFileNo		   = #CPCDetail.ApplicationFileNo
					AND t_iLOSClientRelation.MemberID			   = #CPCDetail.MemberID
					AND t_iLOSClientRelation.RelationRoleID		   = 'G' 
					)iLOSClientRelation

		UPDATE #CPCDetail
		SET [Center ID]		= '',
			[Center Name]	= '',
			[Group ID]		= '',
			[Group Name]	= '',
			ApplicationType = 'ILOS'
		FROM #CPCDetail
	END


		UPDATE #CPCDetail
        SET ZoneID = t_TCL_ZoneRegionMap.ZoneID
        FROM #CPCDetail
        INNER JOIN t_TCL_ZoneRegionMap 
        ON #CPCDetail.RegionID=t_TCL_ZoneRegionMap.RegionID
        WHERE t_TCL_ZoneRegionMap.Status = 1
        
        UPDATE #CPCDetail
        SET Zone =t_bankusercode.Description
        FROM #CPCDetail
        INNER JOIN t_bankusercode 
        ON #CPCDetail.ZoneID = t_bankusercode.SubCodeID
        WHERE t_bankusercode.ID = 'BankZoneID'

	IF @ApplicationTypeID = 'GLOW'
	BEGIN
		IF @IsDataLakeJob = 0 
		BEGIN
		SELECT 
			 [BC ID]					
			,[BC Name]		
			,RegionID
			--,dbo.f_GetBankUserCodeDesc(@BankID,'BankRegionID',RegionID)	[Zone]
			,Zone	[Zone]
			,dbo.f_GetBankUserCodeDesc(@BankID,'BankRegionID',RegionID)	[RegionName]
			,[Branch ID]				
			,[Branch Name]				
			,[Center ID]				
			,[Center Name]				
			,[Group ID]					
			,[Group Name]	
			,ApplicationType    [Application Type]
			,[Application Number]		
			,[Member ID]				
			,[Member Name]				
			,dbo.f_GetLoanSchemeName(@BankID,[Loan Scheme])[Loan Scheme]				
			,[Loan Account ID]			
			,[Loan Amount]				
			,[Tenure]					
			,[CPC Status]				
			,[Application Current Stage]
			,[Application current Stage Status]
			,[Owner Name]				
			,[CPC Done By]				
			,CONVERT(VARCHAR,[CPC Started On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[CPC Started On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[CPC Started On])), 2) AS [CPC Started On]			
			,CONVERT(VARCHAR,[CPC Completed On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[CPC Completed On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[CPC Completed On])), 2) AS [CPC Completed On]			
			,[Is Query Raised]			
			,CONVERT(VARCHAR,[Query Raised On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Query Raised On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Query Raised On])), 2) AS [Query Raised On]			
			,LEFT(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Queries],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&'),100) [Queries]					
			,CASE WHEN TransactionAccountID = BankAcNo THEN [Bene Check Status] ELSE NULL END [Bene Check Status]	
			,CASE WHEN TransactionAccountID = BankAcNo THEN NameMatchScore ELSE NULL END [Name Match Score]
			,CASE WHEN TransactionAccountID = BankAcNo THEN [Bene check Done By] ELSE NULL END [Bene check Done By]		
			,CONVERT(VARCHAR,[Bene check Done On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Bene check Done On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Bene check Done On])), 2) AS [Bene check Done On]		
			,[Loan Booked By]			
			,CONVERT(VARCHAR,[Loan Booked ON],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Loan Booked ON])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Loan Booked ON])), 2) AS [Loan Booked ON]			
			,[Loan Disbursed By]		
			,CONVERT(VARCHAR,[Loan Disbursed On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Loan Disbursed On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Loan Disbursed On])), 2) AS [Loan Disbursed On]		
			,[Payment Amount]			
			,[Payment Initiated by]		
			,CONVERT(VARCHAR,[Payment Initiated On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Payment Initiated On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Payment Initiated On])), 2) AS [Payment Initiated On]		
			,[Payment Approved By]		
			,CONVERT(VARCHAR,[Payment Approved On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Payment Approved On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Payment Approved On])), 2) AS [Payment Approved On]		
			,[Payment Status]			
			,CONVERT(VARCHAR,[Payment Status On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Payment Status On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Payment Status On])), 2) AS [Payment Status On]		
			,[UTR NO]
			,CASE WHEN TransactionAccountID = BankAcNo THEN  REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([HDFC Remarks],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') ELSE NULL END  [HDFC Remarks] 
			,[Sendback Count]
			,BranchManager	[Branch Manager] 
			,Dbo.f_GetOfficerName(@BankID,LOName)			[LOName] 
			,CASE WHEN [Bene Check Status]='Success' THEN 'Completed' ELSE [File bucket] END  [Beneficary Member bucket]
			,CASE WHEN TransactionAccountID = BankAcNo THEN BeneficiaryName ELSE NULL END BeneficiaryName
			,'="'+BankAcNo +'"'  [Bank Account No]
			,IFSCCode
			,BatchID
			,VillageID			[VillageID]	
			,VillageName		[Village Name]
			,[Query Raised Count]
			,[Member CPC Status]
			,[Last CPC Query Raised On]
			,[Last CPC Query Responded On]
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Previous Queries],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Previous Queries] 
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Previous Remarks],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Previous Remarks] 
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live CPC Query Raised On],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Live CPC Query Raised On] 
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live CPC Query Responded On],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Live CPC Query Responded On] 
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live Queries],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Live Queries]
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live Remarks],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Live Remarks]
			,[LO Mobile]
			,[Applicant Mobile]
			,[Co-Applicant Mobile no]
			,[Branch to Village Distance]
			,[District]
			,[Pincode]
			,[Area Name]
			,[CPC FTR Flag]
			,[Query Raised]  
			,NoOfDependents [No of dependents]
			,format(MemberCreatedDate,'dd-MMM-yyyy')  [Member Created Date]
			,CreditApprovedBy
			,RTRIM(LTRIM(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(BACVRemarks,CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),',',''),'-','')))  [Beni check Rejection Remarks]
			,ModifiedBy
			,Modifiedon
			,BenecheckSendbackCount             
	        --,PreviousBenecheckRemarks 
			,RTRIM(LTRIM(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(PreviousBenecheckRemarks,CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'-',''),'  ',' '))) PreviousBenecheckRemarks
			FROM #CPCDetail
		END
		ELSE
		BEGIN

			SELECT
				[BC ID]		,			
				[BC Name]	,	
				RegionID   ,
				--dbo.f_GetBankUserCodeDesc(@BankID,'BankRegionID',RegionID)	[Zone]		,
				Zone	[Zone],
				dbo.f_GetBankUserCodeDesc(@BankID,'BankRegionID',RegionID)	[RegionName],
				[Branch ID]				,		
				[Branch Name]			,	
				[Center ID]				,
				[Center Name]			,	
				[Group ID]				,	
				[Group Name]			,
				ApplicationType			[Application Type],
				[Application Number]	,	
				[Member ID]				,
				[Member Name]			,	
				dbo.f_GetLoanSchemeName(@BankID,[Loan Scheme])				[Loan Scheme]	,			
				[Loan Account ID]					,
				[Loan Amount]						,
				[Tenure]							,
				[CPC Status]						,
				[Application Current Stage]			,
				[Application current Stage Status]	,
				[Owner Name]						,
				[CPC Done By]						,
				CONVERT(VARCHAR,[CPC Started On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[CPC Started On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[CPC Started On])), 2) AS				[CPC Started On]	,		
				CONVERT(VARCHAR,[CPC Completed On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[CPC Completed On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[CPC Completed On])), 2) AS		[CPC Completed On]	,		
				[Is Query Raised]	,
				CONVERT(VARCHAR,[Query Raised On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Query Raised On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Query Raised On])), 2) AS			[Query Raised On]	,		
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Queries],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')													[Queries]	,				
				[Bene Check Status]					,
				NameMatchScore [Name Match Score]	,
				[Bene check Done By]				,
				CONVERT(VARCHAR,[Bene check Done On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Bene check Done On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Bene check Done On])), 2) AS [Bene check Done On],		
				[Loan Booked By]			,
				CONVERT(VARCHAR,[Loan Booked ON],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Loan Booked ON])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Loan Booked ON])), 2) AS				[Loan Booked ON],			
				[Loan Disbursed By]		,
				CONVERT(VARCHAR,[Loan Disbursed On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Loan Disbursed On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Loan Disbursed On])), 2) AS	[Loan Disbursed On]	,	
				[Payment Amount]			,	
				[Payment Initiated by]		,
				CONVERT(VARCHAR,[Payment Initiated On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Payment Initiated On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Payment Initiated On])), 2) AS [Payment Initiated On],		
				[Payment Approved By]		,
				CONVERT(VARCHAR,[Payment Approved On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Payment Approved On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Payment Approved On])), 2) AS		[Payment Approved On],		
				[Payment Status]	,		
				CONVERT(VARCHAR,[Payment Status On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Payment Status On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Payment Status On])), 2) AS			[Payment Status On]	,	
				[UTR NO],
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([HDFC Remarks],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [HDFC Remarks] ,
				[Sendback Count],
				BranchManager									[Branch Manager] ,
				Dbo.f_GetOfficerName(@BankID,LOName)			[LOName] 		 ,
				CASE WHEN [Bene Check Status]='Success' THEN 'Completed' ELSE [File bucket] END  [Beneficary Member bucket],
				BeneficiaryName,
				'="'+BankAcNo +'"'  [Bank Account No],
				IFSCCode,
				BatchID	,
				VillageID			[VillageID]	,
				VillageName			[Village Name],
				[Query Raised Count]			,
				[Member CPC Status]				,
				[Last CPC Query Raised On]		,
				[Last CPC Query Responded On]	,
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Previous Queries],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')				[Previous Queries]				,
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Previous Remarks],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')				[Previous Remarks] 				,
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live CPC Query Raised On],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')		[Live CPC Query Raised On] 		,
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live CPC Query Responded On],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')  [Live CPC Query Responded On] 	,
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live Queries],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')					[Live Queries]					,
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live Remarks],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')					[Live Remarks]					,
				[LO Mobile]						,
				[Applicant Mobile]				,
				[Co-Applicant Mobile no]		,
				[Branch to Village Distance]	,
				[District]						,
				[Pincode]						,
				[Area Name]						,
				[CPC FTR Flag]					,
				[Query Raised]  				,
				NoOfDependents [No of dependents],
				format(MemberCreatedDate,'dd-MMM-yyyy')  [Member Created Date],
				CreditApprovedBy,
				RTRIM(LTRIM(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(BACVRemarks,CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),',',''),'-','')))  [Beni check Rejection Remarks],
				@MaxEODDate
				FROM #CPCDetail

      END
	 	
	  END

	IF @ApplicationTypeID = 'ILOS'
	BEGIN
		IF @IsDataLakeJob = 0 
		BEGIN
		SELECT 
			 [BC ID]					
			,[BC Name]		
			,RegionID
			--,dbo.f_GetBankUserCodeDesc(@BankID,'BankRegionID',RegionID)	[Zone]
			,Zone	[Zone]
			,dbo.f_GetBankUserCodeDesc(@BankID,'BankRegionID',RegionID)	[RegionName]
			,[Branch ID]				
			,[Branch Name]				
			,[Center ID]				
			,[Center Name]				
			,[Group ID]					
			,[Group Name]	
			,ApplicationType  [Application Type]
			,[Application Number]		
			,[Member ID]				
			,[Member Name]				
			,[Loan Scheme]				
			,[Loan Account ID]			
			,[Loan Amount]				
			,[Tenure]					
			,[CPC Status]				
			,[Application Current Stage]
			,[Application current Stage Status]
			,[Owner Name]				
			,[CPC Done By]				
			,CONVERT(VARCHAR,[CPC Started On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[CPC Started On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[CPC Started On])), 2) AS [CPC Started On]			
			,CONVERT(VARCHAR,[CPC Completed On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[CPC Completed On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[CPC Completed On])), 2) AS [CPC Completed On]			
			,[Is Query Raised]			
			,CONVERT(VARCHAR,[Query Raised On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Query Raised On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Query Raised On])), 2) AS [Query Raised On]			
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Queries],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Queries]					
			,CASE WHEN TransactionAccountID = BankAcNo THEN [Bene Check Status] ELSE NULL END [Bene Check Status]	
			,CASE WHEN TransactionAccountID = BankAcNo THEN NameMatchScore ELSE NULL END [Name Match Score]
			,CASE WHEN TransactionAccountID = BankAcNo THEN [Bene check Done By] ELSE NULL END [Bene check Done By]				
			,CONVERT(VARCHAR,[Bene check Done On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Bene check Done On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Bene check Done On])), 2) AS [Bene check Done On]		
			,[Loan Booked By]			
			,CONVERT(VARCHAR,[Loan Booked ON],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Loan Booked ON])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Loan Booked ON])), 2) AS [Loan Booked ON]			
			,[Loan Disbursed By]		
			,CONVERT(VARCHAR,[Loan Disbursed On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Loan Disbursed On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Loan Disbursed On])), 2) AS [Loan Disbursed On]		
			,[Payment Amount]			
			,[Payment Initiated by]		
			,CONVERT(VARCHAR,[Payment Initiated On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Payment Initiated On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Payment Initiated On])), 2) AS [Payment Initiated On]		
			,[Payment Approved By]		
			,CONVERT(VARCHAR,[Payment Approved On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Payment Approved On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Payment Approved On])), 2) AS [Payment Approved On]		
			,[Payment Status]			
			,CONVERT(VARCHAR,[Payment Status On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Payment Status On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Payment Status On])), 2) AS [Payment Status On]		
			,[UTR NO]
			,CASE WHEN TransactionAccountID = BankAcNo THEN  REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([HDFC Remarks],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') ELSE NULL END  [HDFC Remarks] 
			,[Sendback Count]
			,BranchManager	[Branch Manager] 
			,Dbo.f_GetOfficerName(@BankID,LOName)			[LOName] 
			,CASE WHEN [Bene Check Status]='Success' THEN 'Completed' ELSE [File bucket] END  [Beneficary Member bucket]
			,CASE WHEN TransactionAccountID = BankAcNo THEN BeneficiaryName ELSE NULL END BeneficiaryName
			,'="'+BankAcNo +'"'  [Bank Account No]
			,IFSCCode
			,BatchID
			,VillageID			[VillageID]	
			,VillageName		[Village Name]
			,[Query Raised Count]
			,[Member CPC Status]
			,[Last CPC Query Raised On]
			,[Last CPC Query Responded On]
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Previous Queries],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Previous Queries] 
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Previous Remarks],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Previous Remarks] 
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live CPC Query Raised On],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Live CPC Query Raised On] 
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live CPC Query Responded On],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Live CPC Query Responded On] 
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live Queries],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Live Queries]
			,REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live Remarks],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [Live Remarks]
			,[LO Mobile]
			,[Applicant Mobile]
			,[Co-Applicant Mobile no]
			,[Branch to Village Distance]
			,[District]
			,[Pincode]
			,[Area Name]
			,[CPC FTR Flag]
			,[Query Raised]  
			,NoOfDependents [No of dependents]
			,format(MemberCreatedDate,'dd-MMM-yyyy')  [Member Created Date]
			,CreditApprovedBy
			,RTRIM(LTRIM(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(BACVRemarks,CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),',',''),'-','')))  [Beni check Rejection Remarks]
			,ModifiedBy
			,Modifiedon
			,BenecheckSendbackCount             
	        --,PreviousBenecheckRemarks
			,RTRIM(LTRIM(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(PreviousBenecheckRemarks,CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'-',''),'  ',' '))) PreviousBenecheckRemarks
			FROM #CPCDetail
		END
		ELSE
		BEGIN
			SELECT
				[BC ID]		,			
				[BC Name]	,	
				RegionID   ,
				--dbo.f_GetBankUserCodeDesc(@BankID,'BankRegionID',RegionID)	[Zone]		,
				Zone	[Zone],
				dbo.f_GetBankUserCodeDesc(@BankID,'BankRegionID',RegionID)	[RegionName],
				[Branch ID]				,		
				[Branch Name]			,	
				[Center ID]				,
				[Center Name]			,	
				[Group ID]				,	
				[Group Name]			,
				ApplicationType			[Application Type],
				[Application Number]	,	
				[Member ID]				,
				[Member Name]			,	
				[Loan Scheme]	,			
				[Loan Account ID]					,
				[Loan Amount]						,
				[Tenure]							,
				[CPC Status]						,
				[Application Current Stage]			,
				[Application current Stage Status]	,
				[Owner Name]						,
				[CPC Done By]						,
				CONVERT(VARCHAR,[CPC Started On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[CPC Started On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[CPC Started On])), 2) AS				[CPC Started On]	,		
				CONVERT(VARCHAR,[CPC Completed On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[CPC Completed On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[CPC Completed On])), 2) AS		[CPC Completed On]	,		
				[Is Query Raised]	,
				CONVERT(VARCHAR,[Query Raised On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Query Raised On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Query Raised On])), 2) AS			[Query Raised On]	,		
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Queries],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')													[Queries]	,				
				[Bene Check Status]					,
				NameMatchScore [Name Match Score]	,
				[Bene check Done By]				,
				CONVERT(VARCHAR,[Bene check Done On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Bene check Done On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Bene check Done On])), 2) AS [Bene check Done On],		
				[Loan Booked By]			,
				CONVERT(VARCHAR,[Loan Booked ON],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Loan Booked ON])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Loan Booked ON])), 2) AS				[Loan Booked ON],			
				[Loan Disbursed By]		,
				CONVERT(VARCHAR,[Loan Disbursed On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Loan Disbursed On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Loan Disbursed On])), 2) AS	[Loan Disbursed On]	,	
				[Payment Amount]			,	
				[Payment Initiated by]		,
				CONVERT(VARCHAR,[Payment Initiated On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Payment Initiated On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Payment Initiated On])), 2) AS [Payment Initiated On],		
				[Payment Approved By]		,
				CONVERT(VARCHAR,[Payment Approved On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Payment Approved On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Payment Approved On])), 2) AS		[Payment Approved On],		
				[Payment Status]	,		
				CONVERT(VARCHAR,[Payment Status On],103)+ ' ' +CONVERT(VARCHAR,DATEPART(hh,[Payment Status On])) + ':' +RIGHT('0' + CONVERT(VARCHAR,DATEPART(mi,[Payment Status On])), 2) AS			[Payment Status On]	,	
				[UTR NO],
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([HDFC Remarks],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&') [HDFC Remarks] ,
				[Sendback Count],
				BranchManager									[Branch Manager] ,
				Dbo.f_GetOfficerName(@BankID,LOName)			[LOName] 		 ,
				CASE WHEN [Bene Check Status]='Success' THEN 'Completed' ELSE [File bucket] END  [Beneficary Member bucket],
				BeneficiaryName,
				'="'+BankAcNo +'"'  [Bank Account No],
				IFSCCode,
				BatchID	,
				VillageID			[VillageID]	,
				VillageName			[Village Name],
				[Query Raised Count]			,
				[Member CPC Status]				,
				[Last CPC Query Raised On]		,
				[Last CPC Query Responded On]	,
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Previous Queries],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')				[Previous Queries]				,
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Previous Remarks],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')				[Previous Remarks] 				,
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live CPC Query Raised On],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')		[Live CPC Query Raised On] 		,
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live CPC Query Responded On],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')  [Live CPC Query Responded On] 	,
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live Queries],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')					[Live Queries]					,
				REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE([Live Remarks],CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),'&amp;','&')					[Live Remarks]					,
				[LO Mobile]						,
				[Applicant Mobile]				,
				[Co-Applicant Mobile no]		,
				[Branch to Village Distance]	,
				[District]						,
				[Pincode]						,
				[Area Name]						,
				[CPC FTR Flag]					,
				[Query Raised]  				,
				NoOfDependents [No of dependents],
				format(MemberCreatedDate,'dd-MMM-yyyy')  [Member Created Date],
				CreditApprovedBy,
				RTRIM(LTRIM(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(BACVRemarks,CHAR(9),''),CHAR(10),''),CHAR(13),''),'"',''),'  ',' '),',',''),'-','')))  [Beni check Rejection Remarks],
				@MaxEODDate
				FROM #CPCDetail

		END
	  END

	DROP TABLE #CPCDetail,#Branch
	
	SET NOCOUNT OFF
END
