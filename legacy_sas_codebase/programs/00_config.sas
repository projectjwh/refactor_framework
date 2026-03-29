/*****************************************************************************
* PROGRAM:    00_config.sas
* PURPOSE:    Global configuration - paths, macro variables, libnames
* AUTHOR:     Legacy Team
* CREATED:    2014-03-15
* MODIFIED:   2019-11-22 - added Part D fields
*             2021-06-10 - updated paths for server migration
*             2023-01-05 - added 2023 year
*
* NOTES:      Must be %INCLUDEd before any other program.
*             Paths are hard-coded to prod server mount.
*             Parallel batch size is fixed at 10.
*****************************************************************************/

%LET PROJ_ROOT   = /sas/prod/enrollment;
%LET DATA_IN     = &PROJ_ROOT./data/input;
%LET DATA_OUT    = &PROJ_ROOT./data/output;
%LET LOG_DIR     = &PROJ_ROOT./logs;
%LET PROG_DIR    = &PROJ_ROOT./programs;
%LET TEMP_DIR    = /sas/temp/enroll_scratch;

/* Processing parameters */
%LET START_YEAR  = 2019;
%LET END_YEAR    = 2023;
%LET BATCH_SIZE  = 10;      /* number of mods to run in parallel */
%LET TOTAL_MODS  = 100;     /* 00-99 */
%LET MAX_RETRIES = 3;

/* Input file naming convention: enroll_mod_XX.csv  where XX = 00-99 */
%LET IN_PREFIX   = enroll_mod_;
%LET IN_SUFFIX   = .csv;

/* Output file naming: bene_enroll_XX.sas7bdat where XX = 00-99 */
%LET OUT_PREFIX  = bene_enroll_;

/* CME Enrollment status code valid values */
/* MDCR_ENTLMT_BUYIN_IND: Monthly Medicare entitlement/buy-in indicator */
/*   0 = Not entitled                                                   */
/*   1 = Part A only                                                    */
/*   2 = Part B only                                                    */
/*   3 = Part A and Part B                                              */
/*   A = Part A, state buy-in                                           */
/*   B = Part B, state buy-in                                           */
/*   C = Part A and Part B, state buy-in                                */
%LET VALID_BUYIN = 0 1 2 3 A B C;

/* HMO_IND: Monthly HMO indicator */
/*   0 = Not a member of HMO                                           */
/*   1 = Non lock-in, CMS to process claims                            */
/*   2 = Non lock-in, CMS NOT to process claims                        */
/*   4 = Fee-for-service participant in CMP                             */
/*   A = Lock-in, CMS to process claims                                */
/*   B = Lock-in, CMS NOT to process claims                            */
/*   C = Lock-in, CMS to process, ESRD                                 */
%LET VALID_HMO = 0 1 2 4 A B C;

/* DUAL_STUS_CD: Dual eligible status code */
/*   NA/blank = Non-dual                                               */
/*   00 = Not dually eligible (used pre-2006)                          */
/*   01 = QMB only                                                     */
/*   02 = QMB+full Medicaid                                            */
/*   03 = SLMB only                                                    */
/*   04 = SLMB+full Medicaid                                           */
/*   05 = QDWI                                                         */
/*   06 = Qualifying individuals                                       */
/*   08 = Other full dual                                               */
/*   09 = Other non-Medicaid                                           */
/*   10 = Full Medicaid, non-QMB                                       */
%LET VALID_DUAL = NA 00 01 02 03 04 05 06 08 09 10;

/* PTC_CNTRCT_ID: Part C contract ID (H-number or blank) */
/* PTD_CNTRCT_ID: Part D contract ID (S/H/R/E-number or blank) */

/* Libnames */
LIBNAME RAW "&DATA_IN." ACCESS=READONLY;
LIBNAME OUT "&DATA_OUT.";
LIBNAME SCRATCH "&TEMP_DIR.";

OPTIONS MPRINT MLOGIC SYMBOLGEN NOFMTERR
        COMPRESS=YES REUSE=YES
        FULLSTIMER MSGLEVEL=I
        ERRORABEND;
