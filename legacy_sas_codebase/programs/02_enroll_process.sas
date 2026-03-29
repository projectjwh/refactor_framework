/*****************************************************************************
* PROGRAM:    02_enroll_process.sas
* PURPOSE:    Process a single mod partition - ingest CSV, validate,
*             concatenate monthly enrollment status into annual strings,
*             produce beneficiary-level output.
*
* CALLED BY:  01_enroll_driver.sas via SYSTASK
* PARAMETERS: MOD_NUM (2-digit partition 00-99)
*
* INPUT:      &DATA_IN./enroll_mod_XX.csv
* OUTPUT:     OUT.bene_enroll_XX  (sas7bdat)
*
* REFACTORED: 2026-03-27
*   - Replaced 24-line IF/ELSE contract assignment with ARRAY indexing
*   - Consolidated validation into single pass with ARRAY of valid codes
*   - Removed dead code (_INVALID_FLAG output both branches)
*   - Removed redundant PROC SQL record counts mid-pipeline
*   - Combined type coercion + validation into single DATA step
*****************************************************************************/

%MACRO PROCESS_ENROLLMENT(MOD_NUM);

    %LOCAL INFILE DSNAME START_TS END_TS N_BENE;

    %LET START_TS = %SYSFUNC(DATETIME());
    %LET INFILE = &DATA_IN./&IN_PREFIX.&MOD_NUM.&IN_SUFFIX.;
    %LET DSNAME = work.enroll_raw_&MOD_NUM.;

    %PUT NOTE: ========================================================;
    %PUT NOTE: Processing MOD &MOD_NUM. - START %SYSFUNC(DATETIME(), DATETIME20.);
    %PUT NOTE: Input file: &INFILE.;
    %PUT NOTE: ========================================================;

    /*--- STEP 1: Import CSV ----------------------------------------*/

    %IF %SYSFUNC(FILEEXIST(&INFILE.)) = 0 %THEN %DO;
        %PUT ERROR: Input file not found: &INFILE.;
        %GOTO EXIT_MACRO;
    %END;

    PROC IMPORT DATAFILE="&INFILE."
                OUT=&DSNAME.
                DBMS=CSV REPLACE;
        GETNAMES=YES;
        GUESSINGROWS=5000;
    RUN;

    %IF &SYSERR. > 4 %THEN %DO;
        %PUT ERROR: PROC IMPORT failed for MOD &MOD_NUM. (SYSERR=&SYSERR.);
        %GOTO EXIT_MACRO;
    %END;

    /*--- STEP 2: Type coercion + validation in single pass ---------*/

    DATA &DSNAME. (DROP=_YEAR _MONTH YEAR MONTH
                   RENAME=(YEAR_NUM=YEAR MONTH_NUM=MONTH));
        SET &DSNAME.;

        LENGTH BENE_ID $15. MDCR_ENTLMT_BUYIN_IND $1. HMO_IND $1.
               DUAL_STUS_CD $2. PTC_CNTRCT_ID $5. PTC_PBP_ID $3.
               PTC_PLAN_TYPE_CD $2. PTD_CNTRCT_ID $5. PTD_PBP_ID $3.
               PTD_SGMT_ID $3. ESRD_IND $1. CRNT_BIC_CD $2.
               STATE_CD $2. CNTY_CD $3.;

        /* Standardize character fields */
        BENE_ID           = LEFT(PUT(BENE_ID, $15.));
        MDCR_ENTLMT_BUYIN_IND = UPCASE(STRIP(MDCR_ENTLMT_BUYIN_IND));
        HMO_IND           = UPCASE(STRIP(HMO_IND));
        DUAL_STUS_CD      = UPCASE(STRIP(DUAL_STUS_CD));
        PTC_CNTRCT_ID     = UPCASE(STRIP(PTC_CNTRCT_ID));
        PTC_PBP_ID        = STRIP(PTC_PBP_ID);
        PTC_PLAN_TYPE_CD  = STRIP(PTC_PLAN_TYPE_CD);
        PTD_CNTRCT_ID     = UPCASE(STRIP(PTD_CNTRCT_ID));
        PTD_PBP_ID        = STRIP(PTD_PBP_ID);
        PTD_SGMT_ID       = STRIP(PTD_SGMT_ID);
        ESRD_IND          = UPCASE(STRIP(ESRD_IND));
        CRNT_BIC_CD       = UPCASE(STRIP(CRNT_BIC_CD));
        STATE_CD          = STRIP(STATE_CD);
        CNTY_CD           = STRIP(CNTY_CD);

        /* Coerce year/month to numeric and filter invalid */
        _YEAR  = INPUT(YEAR, ?? BEST4.);
        _MONTH = INPUT(MONTH, ?? BEST2.);
        IF MISSING(_YEAR) OR MISSING(_MONTH) THEN DELETE;
        IF NOT (1 <= _MONTH <= 12) THEN DELETE;
        IF NOT (2000 <= _YEAR <= 2099) THEN DELETE;
        YEAR_NUM  = _YEAR;
        MONTH_NUM = _MONTH;

        /* Validate enrollment codes (default invalid to '0' or 'NA') */
        IF MDCR_ENTLMT_BUYIN_IND NOT IN ('0','1','2','3','A','B','C')
            THEN MDCR_ENTLMT_BUYIN_IND = '0';
        IF HMO_IND NOT IN ('0','1','2','4','A','B','C')
            THEN HMO_IND = '0';
        IF DUAL_STUS_CD NOT IN ('NA','00','01','02','03','04','05','06','08','09','10')
            THEN DUAL_STUS_CD = 'NA';
        IF ESRD_IND NOT IN ('0','Y','N')
            THEN ESRD_IND = '0';
    RUN;

    /*--- STEP 3: Deduplicate on BENE_ID x YEAR x MONTH ------------*/

    PROC SORT DATA=&DSNAME. NODUPKEY;
        BY BENE_ID YEAR MONTH;
    RUN;

    /*--- STEP 4: Fill missing months with 12-month skeleton --------*/

    PROC SQL;
        CREATE TABLE work.skeleton_&MOD_NUM. AS
        SELECT DISTINCT A.BENE_ID, A.YEAR, B.MONTH
        FROM &DSNAME. A,
             (SELECT 1 AS MONTH FROM SASHELP.CLASS(OBS=1) UNION ALL
              SELECT 2 FROM SASHELP.CLASS(OBS=1) UNION ALL
              SELECT 3 FROM SASHELP.CLASS(OBS=1) UNION ALL
              SELECT 4 FROM SASHELP.CLASS(OBS=1) UNION ALL
              SELECT 5 FROM SASHELP.CLASS(OBS=1) UNION ALL
              SELECT 6 FROM SASHELP.CLASS(OBS=1) UNION ALL
              SELECT 7 FROM SASHELP.CLASS(OBS=1) UNION ALL
              SELECT 8 FROM SASHELP.CLASS(OBS=1) UNION ALL
              SELECT 9 FROM SASHELP.CLASS(OBS=1) UNION ALL
              SELECT 10 FROM SASHELP.CLASS(OBS=1) UNION ALL
              SELECT 11 FROM SASHELP.CLASS(OBS=1) UNION ALL
              SELECT 12 FROM SASHELP.CLASS(OBS=1)) B
        ORDER BY A.BENE_ID, A.YEAR, B.MONTH;
    QUIT;

    PROC SQL;
        CREATE TABLE work.filled_&MOD_NUM. AS
        SELECT S.BENE_ID, S.YEAR, S.MONTH,
               COALESCE(R.MDCR_ENTLMT_BUYIN_IND, '0') AS MDCR_ENTLMT_BUYIN_IND,
               COALESCE(R.HMO_IND,                '0') AS HMO_IND,
               COALESCE(R.DUAL_STUS_CD,           'NA') AS DUAL_STUS_CD,
               COALESCE(R.PTC_CNTRCT_ID,          '')   AS PTC_CNTRCT_ID,
               COALESCE(R.PTD_CNTRCT_ID,          '')   AS PTD_CNTRCT_ID,
               COALESCE(R.ESRD_IND,               '0')  AS ESRD_IND,
               COALESCE(R.CRNT_BIC_CD,            '')   AS CRNT_BIC_CD,
               COALESCE(R.STATE_CD,               '')   AS STATE_CD,
               COALESCE(R.CNTY_CD,                '')   AS CNTY_CD
        FROM work.skeleton_&MOD_NUM. S
        LEFT JOIN &DSNAME. R
            ON S.BENE_ID = R.BENE_ID AND S.YEAR = R.YEAR AND S.MONTH = R.MONTH
        ORDER BY S.BENE_ID, S.YEAR, S.MONTH;
    QUIT;

    PROC DELETE DATA=work.skeleton_&MOD_NUM. &DSNAME.; RUN;

    /*--- STEP 5: Concatenate monthly values via ARRAY indexing -----*/

    DATA work.annual_&MOD_NUM. (DROP=MONTH MDCR_ENTLMT_BUYIN_IND HMO_IND
                                     DUAL_STUS_CD PTC_CNTRCT_ID PTD_CNTRCT_ID
                                     ESRD_IND CRNT_BIC_CD STATE_CD CNTY_CD
                                     _DUAL_POS _MONTHS_ENROLLED I);
        SET work.filled_&MOD_NUM.;
        BY BENE_ID YEAR MONTH;

        LENGTH BENE_MDCR_BUYIN_IND $12. BENE_HMO_IND $12.
               BENE_DUAL_STUS_CD $24.   BENE_ESRD_IND $12.;

        /* Part C and Part D contract arrays - replaces 24-line IF/ELSE */
        LENGTH BENE_PTC_CNTRCT_01-BENE_PTC_CNTRCT_12 $5.;
        LENGTH BENE_PTD_CNTRCT_01-BENE_PTD_CNTRCT_12 $5.;
        ARRAY _PTC{12} $ BENE_PTC_CNTRCT_01-BENE_PTC_CNTRCT_12;
        ARRAY _PTD{12} $ BENE_PTD_CNTRCT_01-BENE_PTD_CNTRCT_12;

        LENGTH BENE_STATE_CD $2. BENE_CNTY_CD $3. BENE_CRNT_BIC_CD $2.
               ENRL_SRC_MOD $2.;

        RETAIN BENE_MDCR_BUYIN_IND BENE_HMO_IND BENE_DUAL_STUS_CD BENE_ESRD_IND
               BENE_PTC_CNTRCT_01-BENE_PTC_CNTRCT_12
               BENE_PTD_CNTRCT_01-BENE_PTD_CNTRCT_12
               BENE_STATE_CD BENE_CNTY_CD BENE_CRNT_BIC_CD
               _MONTHS_ENROLLED;

        /* Reset at start of each BENE_ID x YEAR group */
        IF FIRST.YEAR THEN DO;
            BENE_MDCR_BUYIN_IND = REPEAT(' ', 11);
            BENE_HMO_IND        = REPEAT(' ', 11);
            BENE_DUAL_STUS_CD   = REPEAT(' ', 23);
            BENE_ESRD_IND       = REPEAT(' ', 11);
            DO I = 1 TO 12;
                _PTC{I} = '';
                _PTD{I} = '';
            END;
            BENE_STATE_CD = ''; BENE_CNTY_CD = ''; BENE_CRNT_BIC_CD = '';
            _MONTHS_ENROLLED = 0;
        END;

        /* Place monthly values into concatenated strings */
        SUBSTR(BENE_MDCR_BUYIN_IND, MONTH, 1) = MDCR_ENTLMT_BUYIN_IND;
        SUBSTR(BENE_HMO_IND,        MONTH, 1) = HMO_IND;
        SUBSTR(BENE_ESRD_IND,       MONTH, 1) = ESRD_IND;
        _DUAL_POS = (MONTH - 1) * 2 + 1;
        SUBSTR(BENE_DUAL_STUS_CD, _DUAL_POS, 2) = DUAL_STUS_CD;

        /* Contract IDs via ARRAY — single line replaces 12 IF/ELSEs each */
        _PTC{MONTH} = PTC_CNTRCT_ID;
        _PTD{MONTH} = PTD_CNTRCT_ID;

        /* Track last known geo and BIC */
        IF STATE_CD    NE '' THEN BENE_STATE_CD    = STATE_CD;
        IF CNTY_CD     NE '' THEN BENE_CNTY_CD     = CNTY_CD;
        IF CRNT_BIC_CD NE '' THEN BENE_CRNT_BIC_CD = CRNT_BIC_CD;

        IF MDCR_ENTLMT_BUYIN_IND NOT IN ('0', ' ', '') THEN
            _MONTHS_ENROLLED + 1;

        /* Output at end of each BENE_ID x YEAR group */
        IF LAST.YEAR THEN DO;
            ENRL_SRC_MOD    = "&MOD_NUM.";
            MONTHS_ENROLLED = _MONTHS_ENROLLED;
            OUTPUT;
        END;
    RUN;

    PROC DELETE DATA=work.filled_&MOD_NUM.; RUN;

    /*--- STEP 6: Final output to permanent library -----------------*/

    PROC SORT DATA=work.annual_&MOD_NUM.; BY BENE_ID YEAR; RUN;

    DATA OUT.&OUT_PREFIX.&MOD_NUM. (COMPRESS=YES);
        SET work.annual_&MOD_NUM.;
        LABEL BENE_ID             = "Beneficiary ID"
              YEAR                = "Enrollment Year"
              BENE_MDCR_BUYIN_IND = "Medicare Entitlement/Buy-In (12-char Jan-Dec)"
              BENE_HMO_IND       = "HMO Indicator (12-char Jan-Dec)"
              BENE_DUAL_STUS_CD  = "Dual Status Code (24-char, 2/month Jan-Dec)"
              BENE_ESRD_IND      = "ESRD Indicator (12-char Jan-Dec)"
              ENRL_SRC_MOD       = "Source Partition Modulo (00-99)"
              MONTHS_ENROLLED    = "Months with Medicare Entitlement"
              BENE_STATE_CD      = "Last Known State FIPS"
              BENE_CNTY_CD       = "Last Known County FIPS"
              BENE_CRNT_BIC_CD   = "Current Beneficiary ID Code";
    RUN;

    PROC DELETE DATA=work.annual_&MOD_NUM.; RUN;

    PROC SQL NOPRINT;
        SELECT COUNT(*) INTO :N_BENE TRIMMED FROM OUT.&OUT_PREFIX.&MOD_NUM.;
    QUIT;

    %LET END_TS = %SYSFUNC(DATETIME());
    %PUT NOTE: MOD &MOD_NUM. COMPLETE - &N_BENE. records in %SYSEVALF(&END_TS. - &START_TS.)s;

    %EXIT_MACRO:
%MEND PROCESS_ENROLLMENT;
