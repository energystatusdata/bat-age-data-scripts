# Checks the plausibility of all battery aging data sets (.csv files), generates an Excel spreadsheet (see
# OUTPUT_SHEET_NAME) with the results. See comments marked with ToDo

import time
import math
import pandas as pd
import config_main as cfg
import helper_tools as ht
import multiprocessing
from datetime import datetime
import os
import re
import numpy as np
import config_labels as csv_label
import config_logging  # as logging
# import openpyxl
# import xlsxwriter
# import xlwt


# --- logging ----------------------------------------------------------------------------------------------------------
logging_filename = "log_check_plausibility.txt"
logging = config_logging.bat_data_logger(cfg.LOG_DIR + logging_filename)


# --- file handling (input / output) -----------------------------------------------------------------------------------
DATA_STRUCTURE_DIR = "D:\\bat\\analysis\\preprocessing\\"  # ToDo: define directory of the Data Structure Excel sheet
INPUT_DIR = cfg.CSV_RESULT_DIR  # define the directory of the data records to be analyzed
OUTPUT_DIR = cfg.CHECK_OUTPUT_DIR  # define the directory of the analysis reports (Excel Sheet, HTML)

DATA_STRUCTURE_SHEET_NAME = "Data Structure v05.xlsx"
OUTPUT_SHEET_NAME = "Battery Aging Data Plausibility Check v05.xlsx"  # ToDo: adjust output filename if necessary


# --- plausibility checks ----------------------------------------------------------------------------------------------
NUM_CELLS_EXPERIMENT = 228  # expected number of cells in the experiment
NUM_CYCLERS_EXPERIMENT = 19  # expected number of cycler boards in the experiment
NUM_TMGMT_EXPERIMENT = 1  # expected number of thermal management boards in the experiment
NUM_POOLS_EXPERIMENT = 4  # expected number of pools in the experiment
number_of_expected_files = {  # ToDo: all files in this list are checked -> comment out the ones you don't need
    cfg.DataRecordType.CFG_CELL: NUM_CELLS_EXPERIMENT,
    cfg.DataRecordType.CFG_POOL: NUM_POOLS_EXPERIMENT,
    cfg.DataRecordType.CFG_TMGMT: NUM_TMGMT_EXPERIMENT,
    cfg.DataRecordType.CFG_CYCLER: NUM_CYCLERS_EXPERIMENT,
    cfg.DataRecordType.CELL_EOC_FIXED: NUM_CELLS_EXPERIMENT,
    cfg.DataRecordType.CELL_EIS_FIXED: NUM_CELLS_EXPERIMENT,
    cfg.DataRecordType.CELL_PULSE_FIXED: NUM_CELLS_EXPERIMENT,
    cfg.DataRecordType.CELL_LOG_EXT: NUM_CELLS_EXPERIMENT,
    cfg.DataRecordType.CELL_LOG_AGE: NUM_CELLS_EXPERIMENT,
    cfg.DataRecordType.POOL_LOG_RAW: NUM_POOLS_EXPERIMENT,
    cfg.DataRecordType.CYCLER_LOG_RAW: NUM_CYCLERS_EXPERIMENT,
    cfg.DataRecordType.TMGMT_LOG_RAW: NUM_TMGMT_EXPERIMENT,
}


# --- data structure sheet settings ------------------------------------------------------------------------------------
DATA_STRUCTURE_FILE_SKIP_ROWS = 4
DATA_STRUCTURE_FILE_COL_MIN = "min ≤ x"
DATA_STRUCTURE_FILE_COL_MAX = "x ≤ max"
DATA_STRUCTURE_FILE_COL_DTYPE = "script data type"

DATA_STRUCTURE_FILE_SHEET_RULE = {
    cfg.DataRecordType.CFG_CELL: {"sheet": "CFG", "filter_row": "cell"},
    cfg.DataRecordType.CFG_POOL: {"sheet": "CFG", "filter_row": "pool"},
    cfg.DataRecordType.CFG_CYCLER: {"sheet": "CFG", "filter_row": "S [cycler]"},
    cfg.DataRecordType.CFG_TMGMT: {"sheet": "CFG", "filter_row": "T [t.mgmt]"},
    cfg.DataRecordType.CELL_EOC_FIXED: {"sheet": "EOCV2"},
    cfg.DataRecordType.CELL_EIS_FIXED: {"sheet": "EISV2"},
    cfg.DataRecordType.CELL_PULSE_FIXED: {"sheet": "PLSV2"},
    cfg.DataRecordType.CELL_LOG_EXT: {"sheet": "LOGEXT"},
    cfg.DataRecordType.CELL_LOG_AGE: {"sheet": "LOG_AGE"},
    cfg.DataRecordType.POOL_LOG_RAW: {"sheet": "POOL_LOG"},
    cfg.DataRecordType.CYCLER_LOG_RAW: {"sheet": "SLAVE_LOG", "filter_row": "S [cycler]"},
    cfg.DataRecordType.TMGMT_LOG_RAW: {"sheet": "SLAVE_LOG", "filter_row": "T [t.mgmt]"},
}

# --- output sheet settings --------------------------------------------------------------------------------------------
# OUTPUT_SHEET_ROW_NUM = "number:"
# OUTPUT_SHEET_COL_COLUMNS = "column:"
OUTPUT_SHEET_COL_MIN = "min"  # minimum value of the data column
OUTPUT_SHEET_COL_MEAN = "mean"  # mean value of the data column
OUTPUT_SHEET_COL_MAX = "max"  # maximum value of the data column
OUTPUT_SHEET_COL_MAX_NEG_DX_DT = "min dx/dt"  # maximum negative change rate (dx/dt < 0)
OUTPUT_SHEET_COL_MAX_POS_DX_DT = "max dx/dt"  # maximum positive change rate (dx/dt > 0)
OUTPUT_SHEET_COL_VAL = "value"  # value (if only one in this data type -> CFG)
OUTPUT_SHEET_COL_NUM_NANS = "#NaN"  # number of NaN values in the data column
OUTPUT_SHEET_COL_LT_MIN = "# < min"  # number of values smaller than the plausible minimum in the data column
OUTPUT_SHEET_COL_GT_MAX = "# > max"  # number of values greater than the plausible maximum the data column

OUTPUT_SHEET_SUB_COLUMNS_DEFAULT = [OUTPUT_SHEET_COL_MIN, OUTPUT_SHEET_COL_MEAN, OUTPUT_SHEET_COL_MAX,
                                    OUTPUT_SHEET_COL_NUM_NANS, OUTPUT_SHEET_COL_LT_MIN, OUTPUT_SHEET_COL_GT_MAX]
OUTPUT_SHEET_SUB_COLUMNS_TIME_BASED = [OUTPUT_SHEET_COL_MIN, OUTPUT_SHEET_COL_MEAN, OUTPUT_SHEET_COL_MAX,
                                       OUTPUT_SHEET_COL_MAX_NEG_DX_DT, OUTPUT_SHEET_COL_MAX_POS_DX_DT,
                                       OUTPUT_SHEET_COL_NUM_NANS, OUTPUT_SHEET_COL_LT_MIN, OUTPUT_SHEET_COL_GT_MAX]
OUTPUT_SHEET_SUB_COLUMNS_CFG = [OUTPUT_SHEET_COL_VAL,
                                OUTPUT_SHEET_COL_NUM_NANS, OUTPUT_SHEET_COL_LT_MIN, OUTPUT_SHEET_COL_GT_MAX]

TIME_BASED_RECORDS = [cfg.DataRecordType.CELL_EOC_FIXED, cfg.DataRecordType.CELL_PULSE_FIXED,
                      cfg.DataRecordType.CELL_LOG_EXT, cfg.DataRecordType.POOL_LOG_RAW,
                      cfg.DataRecordType.TMGMT_LOG_RAW, cfg.DataRecordType.CYCLER_LOG_RAW,
                      cfg.DataRecordType.CELL_LOG_AGE]


# --- global variables -------------------------------------------------------------------------------------------------
file_queue = multiprocessing.Queue()
CPU_COUNT = multiprocessing.cpu_count()
if CPU_COUNT > 1:
    # NUMBER_OF_PROCESSORS_TO_USE = math.ceil(CPU_COUNT / 4)  # use 1/4 of processors (avoid freeze and memory overflow)
    NUMBER_OF_PROCESSORS_TO_USE = 1  # use this if you don't have much RAM


def run():
    start_timestamp = datetime.now()
    logging.log.info(os.path.basename(__file__))

    logging.log.info("\n\n========== CHECK PLAUSIBILITY ==========\n")

    for data_record_type, num_expected_files in number_of_expected_files.items():
        _, items, _, message = ht.find_files_of_type(INPUT_DIR, data_record_type)
        logging.log.info(message)
        num_files = len(items)
        if num_files != num_expected_files:
            logging.log.warning("Warning: Expected %u %s files, but only found %u."
                                % (num_expected_files, data_record_type.name, num_files))
        for i in items:  # append all items to the queue (including the data_record_type)
            i.update({"data_record_type": data_record_type})
            file_queue.put(i)

    logging.log.debug("Reading data structure from %s" % DATA_STRUCTURE_SHEET_NAME)
    struct_df_dict, result_df_dict = fill_struct_df_dict()

    processes = []
    report_manager = multiprocessing.Manager()
    report_queue = report_manager.Queue()
    total_queue_size = file_queue.qsize()
    logging.log.info("Starting threads...")
    for processor_number in range(0, NUMBER_OF_PROCESSORS_TO_USE):
        logging.log.debug("  Starting process %u" % processor_number)
        processes.append(multiprocessing.Process(target=checker_thread,
                                                  args=(processor_number, file_queue, report_queue, total_queue_size,
                                                        struct_df_dict)))
    # time.sleep(3)  # thread exiting before queue is ready? -> wait here
    for processor_number in range(0, NUMBER_OF_PROCESSORS_TO_USE):
        processes[processor_number].start()
    for processor_number in range(0, NUMBER_OF_PROCESSORS_TO_USE):
        processes[processor_number].join()
        logging.log.debug("Joined process %u" % processor_number)

    while True:
        if (report_queue is None) or report_queue.empty():
            break  # no more reports

        try:
            this_report = report_queue.get_nowait()
        except multiprocessing.queues.Empty:
            break  # no more reports

        if this_report is None:
            break  # no more reports

        stat_df = this_report["stat_df"]
        data_record_type = this_report["data_record_type"]
        report_msg = this_report["msg"]
        report_level = this_report["level"]

        if report_level == config_logging.ERROR:
            logging.log.error(report_msg)
        elif report_level == config_logging.WARNING:
            logging.log.warning(report_msg)
        elif report_level == config_logging.INFO:
            logging.log.info(report_msg)
        elif report_level == config_logging.DEBUG:
            logging.log.debug(report_msg)
        elif report_level == config_logging.CRITICAL:
            logging.log.critical(report_msg)

        if len(result_df_dict[data_record_type].columns) == 0:
            result_df_dict[data_record_type] = stat_df.copy()
        else:
            result_df_dict[data_record_type] = pd.concat([result_df_dict[data_record_type], stat_df], axis=1)

    # generate summary stat
    summary_col = "summary"
    for data_record_type, _ in number_of_expected_files.items():
        if len(result_df_dict[data_record_type].columns) > 0:
            first_col = result_df_dict[data_record_type].columns.get_level_values(0)[0]
            df = result_df_dict[data_record_type]
            # stat_df = result_df_dict[data_record_type].loc[:, first_col:first_col].copy()
            stat_df = result_df_dict[data_record_type].xs(first_col, axis=1, level=0, drop_level=False).copy()
            stat_df.rename(inplace=True, columns={first_col: summary_col})

            if OUTPUT_SHEET_COL_VAL in stat_df.columns.get_level_values(1):
                # replace with min/mean/max
                stat_df.loc[:, (summary_col, OUTPUT_SHEET_COL_MIN)] = np.nan
                stat_df.loc[:, (summary_col, OUTPUT_SHEET_COL_MEAN)] = np.nan
                stat_df.loc[:, (summary_col, OUTPUT_SHEET_COL_MAX)] = np.nan
                if data_record_type in TIME_BASED_RECORDS:
                    stat_df.loc[:, (summary_col, OUTPUT_SHEET_COL_MAX_NEG_DX_DT)] = np.nan
                    stat_df.loc[:, (summary_col, OUTPUT_SHEET_COL_MAX_POS_DX_DT)] = np.nan
                    stat_df = stat_df.reindex(pd.MultiIndex.from_product([[summary_col],
                                              OUTPUT_SHEET_SUB_COLUMNS_TIME_BASED]), axis=1)
                else:
                    stat_df = stat_df.reindex(pd.MultiIndex.from_product([[summary_col],
                                              OUTPUT_SHEET_SUB_COLUMNS_DEFAULT]), axis=1)
                col_min = OUTPUT_SHEET_COL_VAL
                col_mean = OUTPUT_SHEET_COL_VAL
                col_max = OUTPUT_SHEET_COL_VAL
            else:
                col_min = OUTPUT_SHEET_COL_MIN
                col_mean = OUTPUT_SHEET_COL_MEAN
                col_max = OUTPUT_SHEET_COL_MAX

            for sub_col in stat_df.columns.get_level_values(1):
                if sub_col == OUTPUT_SHEET_COL_MIN:
                    stat_df.loc[:, (summary_col, OUTPUT_SHEET_COL_MIN)] = df.groupby(level=1, axis=1).min()[col_min]
                elif sub_col == OUTPUT_SHEET_COL_MEAN:
                    cond = (struct_df_dict[data_record_type][DATA_STRUCTURE_FILE_COL_DTYPE] != "string")
                    stat_df.loc[:, (summary_col, OUTPUT_SHEET_COL_MEAN)] = np.nan
                    stat_df.loc[cond, (summary_col, OUTPUT_SHEET_COL_MEAN)] = (
                        df.loc[cond, :].astype(float).groupby(level=1, axis=1).mean(numeric_only=True)[col_mean])
                elif sub_col == OUTPUT_SHEET_COL_MAX:
                    stat_df.loc[:, (summary_col, OUTPUT_SHEET_COL_MAX)] = df.groupby(level=1, axis=1).max()[col_max]
                elif sub_col == OUTPUT_SHEET_COL_MAX_NEG_DX_DT:
                    stat_df.loc[:, (summary_col, OUTPUT_SHEET_COL_MAX_NEG_DX_DT)] = (
                        df.groupby(level=1, axis=1).min())[OUTPUT_SHEET_COL_MAX_NEG_DX_DT]
                elif sub_col == OUTPUT_SHEET_COL_MAX_POS_DX_DT:
                    stat_df.loc[:, (summary_col, OUTPUT_SHEET_COL_MAX_POS_DX_DT)] = (
                        df.groupby(level=1, axis=1).max())[OUTPUT_SHEET_COL_MAX_POS_DX_DT]
                else:  # OUTPUT_SHEET_COL_NUM_NANS, OUTPUT_SHEET_COL_LT_MIN, OUTPUT_SHEET_COL_GT_MAX -> sum()
                    stat_df.loc[:, (summary_col, sub_col)] = df.groupby(level=1, axis=1).sum()[sub_col].astype(np.int64)
                    for row in stat_df.index:
                        num = stat_df.loc[row, (summary_col, sub_col)]
                        if num > 0:
                            logging.log.warning("%s: %s is %u in %s column" % (data_record_type, sub_col, num, row))

            sorted_cols = sorted(df.columns, key=lambda x: x[0])
            result_df_dict[data_record_type] = pd.concat([stat_df, df.reindex(sorted_cols, axis=1)], axis=1)

    # make directory if not already present
    if not os.path.exists(OUTPUT_DIR):
        os.mkdir(OUTPUT_DIR)

    # with pd.ExcelWriter(OUTPUT_DIR + OUTPUT_SHEET_NAME, engine='openpyxl') as writer:  # alternative engine
    with pd.ExcelWriter(OUTPUT_DIR + OUTPUT_SHEET_NAME, engine='xlsxwriter') as writer:
        for data_record_type, _ in number_of_expected_files.items():
            df = result_df_dict[data_record_type]
            # sort
            # df = df.reindex(sorted(df.columns), axis=1)
            # sheet_name = DATA_STRUCTURE_FILE_SHEET_RULE.get(data_record_type)["sheet"]
            sheet_name = data_record_type.name
            df.to_excel(writer, sheet_name=sheet_name, merge_cells=True)

    stop_timestamp = datetime.now()
    logging.log.info("\nScript runtime: %s h:mm:ss.ms" % str(stop_timestamp - start_timestamp))


def checker_thread(processor_number, task_queue, report_queue, total_queue_size, struct_df_dict):
    time.sleep(2)  # sometimes the thread is called before task_queue is ready? wait, and keep retrying a few times
    retry_counter = 0
    remaining_size = 1
    while True:
        try:
            remaining_size = task_queue.qsize()
            # queue_entry = task_queue.get(block=False)
            queue_entry = task_queue.get_nowait()
        except multiprocessing.queues.Empty:
            if remaining_size > 0:
                if retry_counter < 100:
                    retry_counter = retry_counter + 1
                    time.sleep(1)
                    continue
                else:
                    break
            else:
                break  # no more files

        if queue_entry is None:
            break  # no more files

        num_errors = 0
        num_warnings = 0

        retry_counter = 0
        filename_csv = queue_entry["filename"]
        data_record_type = queue_entry["data_record_type"]
        data_record_base_type = cfg.DATA_RECORD_BASE_TYPE.get(data_record_type)

        slave_id = queue_entry[csv_label.SLAVE_ID]
        if data_record_base_type == cfg.DataRecordBaseType.CELL:
            cell_id = queue_entry[csv_label.CELL_ID]
            param_id = queue_entry[csv_label.PARAMETER_ID]
            param_nr = queue_entry[csv_label.PARAMETER_NR]
            instance_string = "P%03u-%u (S%02u:C%02u)" % (param_id, param_nr, slave_id, cell_id)
        elif data_record_base_type == cfg.DataRecordBaseType.POOL:
            pool_id = queue_entry[csv_label.POOL_ID]
            instance_string = "T%02u:P%u" % (slave_id, pool_id)
        else:
            slave_base_type = queue_entry["slave_base_type"]
            if slave_base_type == cfg.DataRecordBaseType.TMGMT_SLAVE:
                instance_string = "T%02u" % slave_id
            else:
                instance_string = "S%02u" % slave_id

        progress = 0.0
        if total_queue_size > 0:
            progress = (1.0 - remaining_size / total_queue_size) * 100.0
        logging.log.debug("Thread %u - analyzing %s data of %s (progress: %.1f %%)"
                          % (processor_number, data_record_type.name, instance_string, progress))

        struct_df = pd.DataFrame()
        if data_record_type in struct_df_dict:
            struct_df: pd.DataFrame = struct_df_dict.get(data_record_type)
        else:
            num_errors = num_errors + 1
            logging.log.error("%s %s - I don't know the structure (and thus the min/max limits) - check %s file"
                              % (instance_string, data_record_type.name, DATA_STRUCTURE_SHEET_NAME))

        # read .csv file
        logging.log.debug("Reading '%s'" % filename_csv)
        # pd.read_csv(INPUT_DIR + filename_csv, header=0, sep=cfg.CSV_SEP)  # <- this is significantly slower than this:
        df: pd.DataFrame = pd.read_csv(INPUT_DIR + filename_csv, header=0, sep=cfg.CSV_SEP, engine="pyarrow")

        # check if data structure matches
        n_col_expect = len(struct_df.index)
        n_col_actual = len(df.columns)
        if n_col_expect != n_col_actual:
            num_errors = num_errors + 1
            logging.log.error("%s %s - expected %u columns but found %u"
                              % (instance_string, data_record_type.name, n_col_expect, n_col_actual))
        else:
            # noinspection PyTypeChecker
            if not all(np.array(struct_df.index) == np.array(df.columns)):
                num_errors = num_errors + 1
                logging.log.error("%s %s - expected %u columns but found %u"
                                  % (instance_string, data_record_type.name, n_col_expect, n_col_actual))

        # check for min / max ...
        num_rows = df.shape[0]
        main_col_name = "%s (%u rows)" % (instance_string, num_rows)
        if ((data_record_type == cfg.DataRecordType.CFG_CELL)
                or (data_record_type == cfg.DataRecordType.CFG_POOL)
                or (data_record_type == cfg.DataRecordType.CFG_CYCLER)
                or (data_record_type == cfg.DataRecordType.CFG_TMGMT)):
            # config should only have exactly one row
            if num_rows > 1:
                num_errors = num_errors + 1
                logging.log.error("%s %s - should have exactly one data row but has %u (using first)"
                                  % (instance_string, data_record_type.name, num_rows))
            elif num_rows <= 0:
                num_errors = num_errors + 1
                logging.log.error("%s %s - should have exactly one data row but has none (skipping)"
                                  % (instance_string, data_record_type.name))
            mx_col = pd.MultiIndex.from_product([[main_col_name], OUTPUT_SHEET_SUB_COLUMNS_CFG])
            stat_df = pd.DataFrame(index=df.columns, columns=mx_col)
            if num_rows >= 0:
                stat_df.loc[:, (main_col_name, OUTPUT_SHEET_COL_VAL)] = df.iloc[0]
        else:
            # data record type other than config
            if data_record_type in TIME_BASED_RECORDS:
                mx_col = pd.MultiIndex.from_product([[main_col_name], OUTPUT_SHEET_SUB_COLUMNS_TIME_BASED])
            else:
                mx_col = pd.MultiIndex.from_product([[main_col_name], OUTPUT_SHEET_SUB_COLUMNS_DEFAULT])
            stat_df = pd.DataFrame(index=df.columns, columns=mx_col)
            stat_df.loc[:, (main_col_name, OUTPUT_SHEET_COL_MIN)] = df.min()
            stat_df.loc[:, (main_col_name, OUTPUT_SHEET_COL_MEAN)] = df.mean()
            stat_df.loc[:, (main_col_name, OUTPUT_SHEET_COL_MAX)] = df.max()
            if data_record_type in TIME_BASED_RECORDS:
                t_col = None
                if csv_label.TIMESTAMP in df.columns:
                    t_col = csv_label.TIMESTAMP
                    dt_diff = df[csv_label.TIMESTAMP].diff().fillna(cfg.DELTA_T_LOG)
                elif "timestamp" in df.columns:
                    t_col = "timestamp"
                    dt_diff = df["timestamp"].diff().fillna(cfg.DELTA_T_LOG)
                else:
                    dt_diff = None  # cfg.DELTA_T_LOG  # assume default time steps
                if dt_diff is not None:
                    devi = df.diff().fillna(0).divide(dt_diff, axis="rows")
                    devi[t_col] = dt_diff  # use time column for dt/d_step (since dt/dt is always 1 anyway) -> find gaps
                    stat_df.loc[:, (main_col_name, OUTPUT_SHEET_COL_MAX_NEG_DX_DT)] = devi.min()
                    stat_df.loc[:, (main_col_name, OUTPUT_SHEET_COL_MAX_POS_DX_DT)] = devi.max()

        stat_df.loc[:, (main_col_name, OUTPUT_SHEET_COL_NUM_NANS)] = df.isnull().sum()
        # ignore the following "Unresolved attribute reference" errors if you're using PyCharm, likely caused by:
        # https://youtrack.jetbrains.com/issue/PY-44125/pandas.DataFrame-or-Series-comparison-result-is-wrongly-inferred-as-boolean
        stat_df.loc[:, (main_col_name, OUTPUT_SHEET_COL_LT_MIN)] = (df < struct_df[OUTPUT_SHEET_COL_MIN]).sum().T
        stat_df.loc[:, (main_col_name, OUTPUT_SHEET_COL_GT_MAX)] = (df > struct_df[OUTPUT_SHEET_COL_MAX]).sum().T

        report_msg = (f"%s %s - finished (%u errors, %u warnings)"
                      % (instance_string, data_record_type.name, num_errors, num_warnings))
        report_level = config_logging.INFO
        if num_errors > 0:
            report_level = config_logging.ERROR
        elif num_warnings > 0:
            report_level = config_logging.WARNING

        report_entry = {"stat_df": stat_df, "data_record_type": data_record_type,
                        "msg": report_msg, "level": report_level}
        report_queue.put(report_entry)

    task_queue.close()
    logging.log.debug("exiting thread")


def fill_struct_df_dict():
    # if something fails here, make sure you didn't change anything in the "Data Structure ... .xlsx" file
    struct_xls = pd.read_excel(DATA_STRUCTURE_DIR + DATA_STRUCTURE_SHEET_NAME, sheet_name=None,
                               skiprows=DATA_STRUCTURE_FILE_SKIP_ROWS, index_col=0, header=0)
    struct_df_dict = {}
    result_df_dict = {}
    for drt, _ in number_of_expected_files.items():
        if drt in DATA_STRUCTURE_FILE_SHEET_RULE:
            rule = DATA_STRUCTURE_FILE_SHEET_RULE.get(drt)
            sheet_name = rule["sheet"]
            if "filter_row" in rule:
                filter_row = rule["filter_row"]
                cond = (struct_xls[sheet_name][filter_row] == 1)
                df_filt = struct_xls[sheet_name].loc[cond, [DATA_STRUCTURE_FILE_COL_MIN, DATA_STRUCTURE_FILE_COL_MAX,
                                                            DATA_STRUCTURE_FILE_COL_DTYPE]]
            else:
                df_filt = struct_xls[sheet_name].loc[:, [DATA_STRUCTURE_FILE_COL_MIN, DATA_STRUCTURE_FILE_COL_MAX,
                                                         DATA_STRUCTURE_FILE_COL_DTYPE]]

            struct_df = df_filt.copy()
            struct_df.rename(inplace=True, columns={DATA_STRUCTURE_FILE_COL_MIN: OUTPUT_SHEET_COL_MIN,
                                                    DATA_STRUCTURE_FILE_COL_MAX: OUTPUT_SHEET_COL_MAX})
            struct_df_dict.update({drt: struct_df})

            str_cond = (struct_xls[sheet_name][DATA_STRUCTURE_FILE_COL_DTYPE] != "string")
            df_filt.loc[str_cond, :] = np.nan
            df_filt.rename(inplace=True, columns={DATA_STRUCTURE_FILE_COL_MIN: OUTPUT_SHEET_COL_MIN,
                                                  DATA_STRUCTURE_FILE_COL_MAX: OUTPUT_SHEET_COL_MAX})
            df_empty = pd.DataFrame(index=df_filt.index)
            result_df_dict.update({drt: df_empty.copy()})
        else:
            logging.log.error("Error: Data type %s not defined in DATA_STRUCTURE_FILE_SHEET_RULE -> skip" % drt)
    return struct_df_dict, result_df_dict


if __name__ == "__main__":
    run()
