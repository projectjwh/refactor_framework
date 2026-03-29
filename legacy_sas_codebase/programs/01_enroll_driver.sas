/*****************************************************************************
* PROGRAM:    01_enroll_driver.sas
* PURPOSE:    Driver program - orchestrates parallel execution of enrollment
*             processing across 100 mod partitions, 10 at a time.
* AUTHOR:     Legacy Team
* CREATED:    2014-03-15
* MODIFIED:   2017-08-10 - increased batch size from 5 to 10
*             2019-11-22 - added post-batch QA checks
*             2021-06-10 - added retry logic for failed partitions
*             2023-01-05 - added cross-partition duplicate check
*
* USAGE:      Submit this program. It will:
*             1. Include config and processing macro
*             2. Loop through mods 00-99 in batches of 10
*             3. Launch each batch via SYSTASK (parallel SAS sessions)
*             4. Wait for batch completion
*             5. Run QA checks after each batch
*             6. Produce final summary log
*
* PREREQS:    - 00_config.sas must define all macro vars
*             - 02_enroll_process.sas must define %PROCESS_ENROLLMENT
*             - Input CSV files must exist in &DATA_IN.
*             - Output library must be writable
*             - Scratch library for temp datasets
*             - Sufficient OS file handles for 10 concurrent SAS sessions
*
* KNOWN ISSUES:
*   - SYSTASK spawns separate SAS sessions; macro vars must be
*     re-established in each child session via generated .sas files
*   - No graceful recovery if a batch partially fails
*   - Memory: each child session loads its own copy of work datasets
*   - On some servers, WAITFOR _ALL_ hangs if a child session crashes
*   - The retry loop can mask persistent data quality issues
*****************************************************************************/

OPTIONS NOSOURCE2;

/* Include configuration */
%INCLUDE "&PROJ_ROOT./programs/00_config.sas";

/* Include processing macro */
%INCLUDE "&PROJ_ROOT./programs/02_enroll_process.sas";

/*----------------------------------------------------------------------
 * INITIALIZATION: Clean scratch, create tracking dataset
 *----------------------------------------------------------------------*/

/* Clear any leftover scratch datasets */
PROC DATASETS LIBRARY=SCRATCH NOLIST KILL; QUIT;

/* Tracking table for batch results */
DATA work.batch_tracker;
    LENGTH MOD_NUM $2.
           BATCH_NUM 8.
           STATUS $10.
           START_TIME END_TIME 8.
           DURATION 8.
           OUTPUT_NOBS 8.
           RETRY_COUNT 8.;
    FORMAT START_TIME END_TIME DATETIME20.;
    STOP;
RUN;

%PUT NOTE: ================================================================;
%PUT NOTE: ENROLLMENT PROCESSING DRIVER - START;
%PUT NOTE: Year range: &START_YEAR. - &END_YEAR.;
%PUT NOTE: Batch size: &BATCH_SIZE. partitions;
%PUT NOTE: Total partitions: &TOTAL_MODS.;
%PUT NOTE: ================================================================;

/*----------------------------------------------------------------------
 * MAIN LOOP: Process mods 00-99 in batches of &BATCH_SIZE
 *----------------------------------------------------------------------*/

%MACRO RUN_ALL_BATCHES;

    %LOCAL BATCH_START BATCH_END BATCH_NUM
           I MOD_STR TASK_NAME
           BATCH_START_TS BATCH_END_TS
           FAIL_COUNT RETRY_I;

    %LET BATCH_NUM = 0;
    %LET BATCH_START = 0;

    %DO %WHILE (&BATCH_START. < &TOTAL_MODS.);

        %LET BATCH_NUM  = %EVAL(&BATCH_NUM. + 1);
        %LET BATCH_END  = %EVAL(&BATCH_START. + &BATCH_SIZE. - 1);
        %IF &BATCH_END. >= &TOTAL_MODS. %THEN %LET BATCH_END = %EVAL(&TOTAL_MODS. - 1);

        %LET BATCH_START_TS = %SYSFUNC(DATETIME());

        %PUT NOTE: --------------------------------------------------------;
        %PUT NOTE: BATCH &BATCH_NUM. - Mods %SYSFUNC(PUTN(&BATCH_START., Z2.)) to %SYSFUNC(PUTN(&BATCH_END., Z2.));
        %PUT NOTE: --------------------------------------------------------;

        /*--------------------------------------------------------------
         * Generate a temporary .sas file for each mod in this batch,
         * then launch it via SYSTASK.
         *
         * Each generated file:
         *   1. Re-establishes macro variables and libnames
         *   2. Includes the processing macro
         *   3. Calls %PROCESS_ENROLLMENT with the mod number
         *   4. Writes a completion flag file
         *--------------------------------------------------------------*/

        %DO I = &BATCH_START. %TO &BATCH_END.;

            %LET MOD_STR  = %SYSFUNC(PUTN(&I., Z2.));
            %LET TASK_NAME = ENRL_&MOD_STR.;

            /* Write the child SAS program */
            DATA _NULL_;
                FILE "&TEMP_DIR./run_mod_&MOD_STR..sas" LRECL=256;
                PUT "/* Auto-generated child session for mod &MOD_STR. */";
                PUT '%LET PROJ_ROOT   = '"&PROJ_ROOT."';';
                PUT '%LET DATA_IN     = '"&DATA_IN."';';
                PUT '%LET DATA_OUT    = '"&DATA_OUT."';';
                PUT '%LET LOG_DIR     = '"&LOG_DIR."';';
                PUT '%LET TEMP_DIR    = '"&TEMP_DIR."';';
                PUT '%LET START_YEAR  = '"&START_YEAR."';';
                PUT '%LET END_YEAR    = '"&END_YEAR."';';
                PUT '%LET IN_PREFIX   = '"&IN_PREFIX."';';
                PUT '%LET IN_SUFFIX   = '"&IN_SUFFIX."';';
                PUT '%LET OUT_PREFIX  = '"&OUT_PREFIX."';';
                PUT " ";
                PUT "LIBNAME OUT '&DATA_OUT.';";
                PUT "LIBNAME SCRATCH '&TEMP_DIR.';";
                PUT " ";
                PUT "OPTIONS MPRINT COMPRESS=YES REUSE=YES FULLSTIMER;";
                PUT " ";
                PUT '%INCLUDE "'"&PROG_DIR./02_enroll_process.sas"'";';
                PUT " ";
                PUT "%PROCESS_ENROLLMENT(&MOD_STR.);";
                PUT " ";
                PUT "/* Write completion flag */";
                PUT "DATA _NULL_;";
                PUT "   FILE '&TEMP_DIR./done_&MOD_STR..flag';";
                PUT "   PUT 'COMPLETE';";
                PUT "RUN;";
            RUN;

            /* Launch the child session */
            SYSTASK COMMAND
                "sas -sysin &TEMP_DIR./run_mod_&MOD_STR..sas -log &LOG_DIR./mod_&MOD_STR..log -nosplash -noicon"
                TASKNAME=&TASK_NAME.
                STATUS=_RC_&MOD_STR.
                ;

            %PUT NOTE: Launched SYSTASK &TASK_NAME. for mod &MOD_STR.;

        %END;  /* end loop over mods in this batch */

        /*--------------------------------------------------------------
         * WAIT for all tasks in this batch to complete
         *--------------------------------------------------------------*/
        WAITFOR _ALL_
            %DO I = &BATCH_START. %TO &BATCH_END.;
                ENRL_%SYSFUNC(PUTN(&I., Z2.))
            %END;
            ;

        %LET BATCH_END_TS = %SYSFUNC(DATETIME());

        %PUT NOTE: BATCH &BATCH_NUM. completed in %SYSEVALF(&BATCH_END_TS. - &BATCH_START_TS.) seconds;

        /*--------------------------------------------------------------
         * POST-BATCH: Check return codes, log results, retry failures
         *--------------------------------------------------------------*/

        %LET FAIL_COUNT = 0;

        %DO I = &BATCH_START. %TO &BATCH_END.;

            %LET MOD_STR = %SYSFUNC(PUTN(&I., Z2.));

            /* Check if completion flag exists */
            %IF %SYSFUNC(FILEEXIST(&TEMP_DIR./done_&MOD_STR..flag)) = 0 %THEN %DO;
                %PUT ERROR: Mod &MOD_STR. did not produce completion flag;
                %LET FAIL_COUNT = %EVAL(&FAIL_COUNT. + 1);

                /* Log failure to tracker */
                PROC SQL;
                    INSERT INTO work.batch_tracker
                    VALUES ("&MOD_STR.", &BATCH_NUM., "FAILED",
                            &BATCH_START_TS., &BATCH_END_TS.,
                            %SYSEVALF(&BATCH_END_TS. - &BATCH_START_TS.),
                            0, 0);
                QUIT;

            %END;
            %ELSE %DO;

                /* Get output record count */
                %LOCAL _NOBS;
                %LET _NOBS = 0;

                %IF %SYSFUNC(EXIST(OUT.&OUT_PREFIX.&MOD_STR.)) %THEN %DO;
                    PROC SQL NOPRINT;
                        SELECT COUNT(*) INTO :_NOBS TRIMMED
                        FROM OUT.&OUT_PREFIX.&MOD_STR.;
                    QUIT;
                %END;

                PROC SQL;
                    INSERT INTO work.batch_tracker
                    VALUES ("&MOD_STR.", &BATCH_NUM., "SUCCESS",
                            &BATCH_START_TS., &BATCH_END_TS.,
                            %SYSEVALF(&BATCH_END_TS. - &BATCH_START_TS.),
                            &_NOBS., 0);
                QUIT;

                %PUT NOTE: Mod &MOD_STR. - SUCCESS (&_NOBS. records);

                /* Clean up completion flag */
                %SYSEXEC DEL "&TEMP_DIR./done_&MOD_STR..flag";
                %SYSEXEC DEL "&TEMP_DIR./run_mod_&MOD_STR..sas";

            %END;

        %END;  /* end post-batch check loop */

        /*--------------------------------------------------------------
         * RETRY: Re-run failed mods sequentially (up to MAX_RETRIES)
         *--------------------------------------------------------------*/

        %IF &FAIL_COUNT. > 0 %THEN %DO;

            %PUT WARNING: BATCH &BATCH_NUM. had &FAIL_COUNT. failures. Retrying...;

            %DO RETRY_I = 1 %TO &MAX_RETRIES.;

                %DO I = &BATCH_START. %TO &BATCH_END.;
                    %LET MOD_STR = %SYSFUNC(PUTN(&I., Z2.));

                    /* Only retry if it failed */
                    %IF %SYSFUNC(FILEEXIST(&TEMP_DIR./done_&MOD_STR..flag)) = 0
                        AND %SYSFUNC(EXIST(OUT.&OUT_PREFIX.&MOD_STR.)) = 0 %THEN %DO;

                        %PUT NOTE: Retry &RETRY_I. for mod &MOD_STR.;

                        /* Run synchronously this time */
                        %PROCESS_ENROLLMENT(&MOD_STR.);

                        /* Check success */
                        %IF %SYSFUNC(EXIST(OUT.&OUT_PREFIX.&MOD_STR.)) %THEN %DO;
                            %PUT NOTE: Retry &RETRY_I. for mod &MOD_STR. - SUCCESS;

                            PROC SQL;
                                UPDATE work.batch_tracker
                                SET STATUS = "RETRIED",
                                    RETRY_COUNT = &RETRY_I.
                                WHERE MOD_NUM = "&MOD_STR.";
                            QUIT;
                        %END;

                    %END;
                %END;  /* end retry mod loop */

            %END;  /* end retry count loop */

        %END;  /* end retry block */

        /*--------------------------------------------------------------
         * QA: Basic integrity checks per batch
         *--------------------------------------------------------------*/

        %DO I = &BATCH_START. %TO &BATCH_END.;
            %LET MOD_STR = %SYSFUNC(PUTN(&I., Z2.));

            %IF %SYSFUNC(EXIST(OUT.&OUT_PREFIX.&MOD_STR.)) %THEN %DO;

                /* Check: no duplicate BENE_ID x YEAR */
                PROC SQL NOPRINT;
                    SELECT COUNT(*) INTO :_DUP_CHECK TRIMMED
                    FROM (
                        SELECT BENE_ID, YEAR, COUNT(*) AS CNT
                        FROM OUT.&OUT_PREFIX.&MOD_STR.
                        GROUP BY BENE_ID, YEAR
                        HAVING CNT > 1
                    );
                QUIT;

                %IF &_DUP_CHECK. > 0 %THEN %DO;
                    %PUT ERROR: QA FAIL - Mod &MOD_STR. has &_DUP_CHECK. duplicate BENE_ID x YEAR;
                %END;

                /* Check: BENE_MDCR_BUYIN_IND should be exactly 12 chars */
                PROC SQL NOPRINT;
                    SELECT COUNT(*) INTO :_LEN_CHECK TRIMMED
                    FROM OUT.&OUT_PREFIX.&MOD_STR.
                    WHERE LENGTH(STRIP(BENE_MDCR_BUYIN_IND)) NE 12;
                QUIT;

                %IF &_LEN_CHECK. > 0 %THEN %DO;
                    %PUT WARNING: QA - Mod &MOD_STR. has &_LEN_CHECK. rows with BUYIN length != 12;
                %END;

                /* Check: MONTHS_ENROLLED between 0 and 12 */
                PROC SQL NOPRINT;
                    SELECT COUNT(*) INTO :_MONTHS_CHECK TRIMMED
                    FROM OUT.&OUT_PREFIX.&MOD_STR.
                    WHERE MONTHS_ENROLLED < 0 OR MONTHS_ENROLLED > 12;
                QUIT;

                %IF &_MONTHS_CHECK. > 0 %THEN %DO;
                    %PUT ERROR: QA FAIL - Mod &MOD_STR. has &_MONTHS_CHECK. invalid MONTHS_ENROLLED;
                %END;

            %END;
        %END;  /* end QA loop */

        /* Advance to next batch */
        %LET BATCH_START = %EVAL(&BATCH_END. + 1);

    %END;  /* end main batch while loop */

%MEND RUN_ALL_BATCHES;

/*----------------------------------------------------------------------
 * EXECUTE
 *----------------------------------------------------------------------*/

%LET DRIVER_START = %SYSFUNC(DATETIME());

%RUN_ALL_BATCHES;

%LET DRIVER_END = %SYSFUNC(DATETIME());

/*----------------------------------------------------------------------
 * FINAL SUMMARY
 *----------------------------------------------------------------------*/

TITLE "Enrollment Processing Summary";
PROC FREQ DATA=work.batch_tracker;
    TABLES STATUS / NOCUM;
RUN;

PROC MEANS DATA=work.batch_tracker N SUM MEAN MIN MAX;
    VAR DURATION OUTPUT_NOBS RETRY_COUNT;
RUN;

PROC PRINT DATA=work.batch_tracker NOOBS;
    WHERE STATUS = "FAILED";
    TITLE2 "Failed Partitions";
RUN;
TITLE;

/* Cross-partition duplicate check: same BENE_ID in multiple mods */
/* This shouldn't happen if partitioning is by MOD(BENE_ID, 100) */
/* But data quality issues can cause it */

%MACRO CROSS_PARTITION_CHECK;

    %LOCAL I MOD_STR;

    /* Stack all output into one view */
    PROC SQL;
        CREATE VIEW work.all_enroll AS
        %DO I = 0 %TO 99;
            %LET MOD_STR = %SYSFUNC(PUTN(&I., Z2.));
            %IF %SYSFUNC(EXIST(OUT.&OUT_PREFIX.&MOD_STR.)) %THEN %DO;
                %IF &I. > 0 %THEN UNION ALL;
                SELECT BENE_ID, YEAR, ENRL_SRC_MOD
                FROM OUT.&OUT_PREFIX.&MOD_STR.
            %END;
        %END;
        ;
    QUIT;

    PROC SQL;
        CREATE TABLE work.cross_dups AS
        SELECT BENE_ID, YEAR, COUNT(DISTINCT ENRL_SRC_MOD) AS N_MODS
        FROM work.all_enroll
        GROUP BY BENE_ID, YEAR
        HAVING N_MODS > 1;
    QUIT;

    PROC SQL NOPRINT;
        SELECT COUNT(*) INTO :_CROSS_DUP TRIMMED FROM work.cross_dups;
    QUIT;

    %IF &_CROSS_DUP. > 0 %THEN %DO;
        %PUT ERROR: CROSS-PARTITION DUPLICATES FOUND: &_CROSS_DUP. BENE x YEAR across multiple mods;
        PROC PRINT DATA=work.cross_dups (OBS=20) NOOBS;
            TITLE "Cross-Partition Duplicates (first 20)";
        RUN;
        TITLE;
    %END;
    %ELSE %DO;
        %PUT NOTE: Cross-partition check PASSED - no duplicates found;
    %END;

    PROC SQL; DROP VIEW work.all_enroll; QUIT;

%MEND CROSS_PARTITION_CHECK;

%CROSS_PARTITION_CHECK;

%PUT NOTE: ================================================================;
%PUT NOTE: ENROLLMENT PROCESSING COMPLETE;
%PUT NOTE: Total duration: %SYSEVALF(&DRIVER_END. - &DRIVER_START.) seconds;
%PUT NOTE: ================================================================;
