# Generate the log_age csv files from the post-processed logext csv files.
# You may adjust the temporal resolution or precision of the columns. See comments marked with ToDo

# import time
import gc
import pandas as pd
import config_main as cfg
from config_main import sch_state_sub as state_sub
import helper_tools as ht
import multiprocessing
from datetime import datetime
import os
import re
import numpy as np
# import math
import cmath
import pyarrow as pa
from pyarrow import csv
import config_labels as csv_label
import config_logging  # as logging

logging_filename = "log_generate_log_age.txt"
logging = config_logging.bat_data_logger(cfg.LOG_DIR + logging_filename)

OUTPUT_FORMAT = "{:.4f}"  # -> float with 4 digits precision ToDo: adjust if wanted
TIME_FORMAT = "{:d}"  # -> unsigned with 0 digits precision (logext timestamps have .0 precision -> use int here)
T_RESOLUTION_S_DEFAULT = 30  # ToDo: adjust resolution for calendar/cyclic aging (minimum meaningful resolution: 2 s)
T_RESOLUTION_S = {  # comment out the lines of the aging types you don't need:
    cfg.age_type.CALENDAR: T_RESOLUTION_S_DEFAULT,  # 30 is very likely sufficient (60 might be too high -> CYC/CU)
    cfg.age_type.CYCLIC: T_RESOLUTION_S_DEFAULT,  # 30 is very likely sufficient (60 might be too high -> CU)
    cfg.age_type.PROFILE: 2,  # ToDo: adjust resolution for profile aging - 30 is likely way to low, use 2, 4, or 10 s?
}  # in seconds, save file with average of this amount of seconds
RELATIVE_TIME = cfg.EXPERIMENT_START_TIMESTAMP  # ToDo: use 0 if you want absolute unix timestamps instead

# If a cell was inactive at the end of the log file, the end of the log file will be stripped. If available, use data..
# until at least the time of the last running state + (T_LOG_END_EXTRA_S + T_RESOLUTION_S) seconds
T_LOG_END_EXTRA_S = max(2 * T_RESOLUTION_S_DEFAULT, (24 * 60 * 60))  # in seconds, (24 * 60 * 60) = 1 day
T_MAX_EARLY_AGEING_DATA_INSERTION = (24 * 60 * 60)  # in seconds, if EOC/EIS data point was collected up to..
# T_MAX_EARLY_AGEING_DATA_INSERTION seconds after the LOG finished, insert it at the end anyway


REQUIRE_EOC = True  # if True, cells with no EOC .csv file are skipped - set False if you don't want/need EOC data
REQUIRE_EIS = True  # if True, cells with no EIS .csv file are skipped - set False if you don't want/need EIS data

# R0: the internal resistance is determined using the intersection with the real axis (Im(Z0) = 0), typically at 1 kHz
# R1: difference between R0 and the real part of the point which has minimum phase (knee point between charge transfer
#     and diffusion), typically roughly around 2 Hz
R0_FREQ_MIN = 200.0
R0_FREQ_MAX = 3300.0
R1_FREQ_MIN = 0.49
R1_FREQ_MAX = 33.0
R0_INITIAL = 15.0  # 13.8 ... 17.4 for the first CU
# R0 + R1: 21.7 ... 28.5 for 10%, 17.8 ... 20.6 for 30-90% for the first CU -> avg: 20.4
R1_INITIAL = 20.4 - R0_INITIAL  # R1 is less certain
R0_RT_MIN_PLAUSIBLE = 0.6 * R0_INITIAL  # in Milliohms, minimum plausible R0 value at room temperature
R0_RT_MAX_PLAUSIBLE = 5.0 * R0_INITIAL  # in Milliohms, maximum plausible R0 value at room temperature
R1_RT_MIN_PLAUSIBLE = 0.1 * R1_INITIAL  # in Milliohms, minimum plausible R1 value at room temperature
R1_RT_MAX_PLAUSIBLE = 15.0 * R1_INITIAL  # in Milliohms, maximum plausible R1 value at room temperature

# drop EIS data point if for the specified R0/R1 min to max frequencies, the amplitude of phase differ by > threshold
EIS_POINT_INVALID_PHASE_DIFF = 10.0  # in Milliohms
EIS_POINT_INVALID_AMP_DIFF = 10.0  # in degree

MIN_CU_DISTANCE_S = (60 * 60 * 60)  # in seconds, (60 * 60 * 60) = 2.5 days
LOG_INTERPOLATION_MIN_GAP_S = 10  # if there is a gap that is > than this in the log, interpolate values in between
# if T_RESOLUTION_S is smaller, use T_RESOLUTION_S! otherwise, we will end up with NaNs again...
INTERPOLATION_PERIOD_S = round(cfg.DELTA_T_LOG)  # interpolate with this time period

SAVE_COLUMNS_LOG = [csv_label.TIMESTAMP, csv_label.V_CELL, csv_label.OCV_EST, csv_label.I_CELL, csv_label.T_CELL,
                    csv_label.SOC_EST, csv_label.DELTA_Q]  # ToDo: you may also remove or add additional LOG columns
LOAD_COLUMNS_LOG = [csv_label.TOTAL_Q_CHG_SUM, csv_label.TOTAL_Q_DISCHG_SUM, csv_label.SCH_STATE_SUB]
LOAD_COLUMNS_LOG.extend(SAVE_COLUMNS_LOG)
INTERPOLATE_COLUMNS_LOG = SAVE_COLUMNS_LOG.copy()
INTERPOLATE_COLUMNS_LOG.extend([csv_label.EFC])
BACKWARD_FILL_COLUMNS_LOG = [csv_label.SCH_STATE_SUB]

SAVE_COLUMNS_EOC = [csv_label.CAP_CHARGED_EST]  # if you change this, you may also adjust the script below.
LOAD_COLUMNS_EOC = [csv_label.TIMESTAMP, csv_label.AGE_TYPE, csv_label.EOC_CYC_CONDITION, csv_label.EOC_CYC_CHARGED]
LOAD_COLUMNS_EOC.extend(SAVE_COLUMNS_EOC)

SAVE_COLUMNS_R = [csv_label.R0, csv_label.R1]
COLUMNS_R = [csv_label.TIMESTAMP]
COLUMNS_R.extend(SAVE_COLUMNS_R)
SAVE_COLUMNS_EIS = []  # if you change this, you may also adjust the script below.
LOAD_COLUMNS_EIS = [csv_label.TIMESTAMP, csv_label.IS_ROOM_TEMP, csv_label.SOC_NOM, csv_label.EIS_VALID,
                    csv_label.EIS_FREQ, csv_label.Z_AMP_MOHM, csv_label.Z_PH_DEG]
LOAD_COLUMNS_EIS.extend(SAVE_COLUMNS_EIS)

SAVE_COLUMNS_NEW_LOG_VARS = [csv_label.EFC]

# this determines the order of the columns in the .csv file output:
OUTPUT_COLUMNS_ALL = []
OUTPUT_COLUMNS_ALL.extend(SAVE_COLUMNS_LOG)
OUTPUT_COLUMNS_ALL.extend(SAVE_COLUMNS_NEW_LOG_VARS)
OUTPUT_COLUMNS_ALL.extend(SAVE_COLUMNS_EOC)
OUTPUT_COLUMNS_ALL.extend(SAVE_COLUMNS_EIS)
OUTPUT_COLUMNS_ALL.extend(SAVE_COLUMNS_R)
OUTPUT_COLUMNS_ALL_INDEXES = np.unique(OUTPUT_COLUMNS_ALL, return_index=True)[1]
OUTPUT_COLUMNS_ALL = [OUTPUT_COLUMNS_ALL[idx] for idx in sorted(OUTPUT_COLUMNS_ALL_INDEXES)]

COLUMN_DTYPES = {  # for all
    csv_label.TIMESTAMP: np.float64,
    csv_label.V_CELL: np.float32,
    csv_label.OCV_EST: np.float32,
    csv_label.I_CELL: np.float32,
    csv_label.T_CELL: np.float32,
    csv_label.SOC_EST: np.float32,
    csv_label.DELTA_Q: np.float32,
    csv_label.SCH_STATE_SUB: np.uint8,
    csv_label.TOTAL_Q_CHG_SUM: np.float64,
    csv_label.TOTAL_Q_DISCHG_SUM: np.float64,
    csv_label.CAP_CHARGED_EST: np.float32,
    csv_label.AGE_TYPE: np.uint8,
    csv_label.EOC_CYC_CONDITION: np.uint8,
    csv_label.EOC_CYC_CHARGED: np.bool_,
    csv_label.IS_ROOM_TEMP: np.bool_,
    csv_label.SOC_NOM: np.uint8,
    csv_label.EIS_VALID: np.bool_,
    csv_label.EIS_FREQ: np.float32,
    csv_label.Z_AMP_MOHM: np.float32,
    csv_label.Z_PH_DEG: np.float32,
    csv_label.EFC: np.float32,
    csv_label.R0: np.float32,
    csv_label.R1: np.float32
}

# logext_dtype = {csv_label.TIMESTAMP: np.float64, csv_label.V_CELL: np.float32, csv_label.OCV_EST: np.float32,
#                 csv_label.I_CELL: np.float32,  csv_label.T_CELL: np.float32, csv_label.SOC_EST: np.float32,
#                 csv_label.DELTA_Q: np.float32, csv_label.TOTAL_Q_CHG_SUM: np.float64,
#                 csv_label.TOTAL_Q_DISCHG_SUM: np.float64, csv_label.SCH_STATE_SUB: np.uint8}


# constants
NUMBER_OF_PROCESSORS_TO_USE = 1
generate_log_age_csv_task_queue = multiprocessing.Queue()

COLUMN_DTYPES_LOG = {key: COLUMN_DTYPES[key] for key in LOAD_COLUMNS_LOG}
COLUMN_DTYPES_EOC = {key: COLUMN_DTYPES[key] for key in LOAD_COLUMNS_EOC}
COLUMN_DTYPES_EIS = {key: COLUMN_DTYPES[key] for key in LOAD_COLUMNS_EIS}
COLUMN_DTYPES_OUTPUT = {key: COLUMN_DTYPES[key] for key in OUTPUT_COLUMNS_ALL}


# exceptions
class ProcessingFailure(Exception):
    pass


def run():
    start_timestamp = datetime.now()
    logging.log.info(os.path.basename(__file__))
    # report_queue = multiprocessing.Queue()
    report_manager = multiprocessing.Manager()
    report_queue = report_manager.Queue()

    generate_log_age_csv(report_queue)

    logging.log.info("\n\n========== All tasks ended - summary ==========\n")

    r_report = range(0, report_queue.qsize())
    report_df = pd.DataFrame(index=r_report,
                             columns=[csv_label.PARAMETER_ID, csv_label.PARAMETER_NR, "msg", "level"])
    for i in r_report:
        if (report_queue is None) or report_queue.empty():
            break  # no more reports

        try:
            slave_report = report_queue.get_nowait()
        except multiprocessing.queues.Empty:
            break  # no more reports

        if slave_report is None:
            break  # no more reports

        report_df.loc[i, csv_label.PARAMETER_ID] = slave_report[csv_label.PARAMETER_ID]
        report_df.loc[i, csv_label.PARAMETER_NR] = slave_report[csv_label.PARAMETER_NR]
        report_df.loc[i, "msg"] = slave_report["msg"]
        report_df.loc[i, "level"] = slave_report["level"]

    report_df.sort_values(by=[csv_label.PARAMETER_ID, csv_label.PARAMETER_NR], inplace=True)
    for _, row in report_df.iterrows():
        report_msg = row["msg"]
        report_level = row["level"]

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

    stop_timestamp = datetime.now()

    logging.log.info("\nScript runtime: %s h:mm:ss.ms" % str(stop_timestamp - start_timestamp))


def generate_log_age_csv(report_queue):
    cell_log_csv = []  # find .csv files: cell_logext_P012_3_S14_C11.csv
    cell_eoc_csv = []  # find .csv files: cell_eocv2_P012_3_S14_C11.csv
    cell_eis_csv = []  # find .csv files: cell_eis_P012_3_S14_C11.csv
    slave_cell_found = [[" "] * cfg.NUM_CELLS_PER_SLAVE for _ in range(cfg.NUM_SLAVES_MAX)]
    with os.scandir(cfg.CSV_RESULT_DIR) as iterator:
        re_str_log_csv = cfg.CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", cfg.CSV_FILENAME_05_TYPE_LOG_EXT)
        re_pat_log_csv = re.compile(re_str_log_csv)
        re_str_eoc_csv = cfg.CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", cfg.CSV_FILENAME_05_TYPE_EOC_FIXED)
        re_pat_eoc_csv = re.compile(re_str_eoc_csv)
        re_str_eis_csv = cfg.CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", cfg.CSV_FILENAME_05_TYPE_EIS)
        re_pat_eis_csv = re.compile(re_str_eis_csv)
        for entry in iterator:
            re_match_log_csv = re_pat_log_csv.fullmatch(entry.name)
            re_match_eoc_csv = re_pat_eoc_csv.fullmatch(entry.name)
            re_match_eis_csv = re_pat_eis_csv.fullmatch(entry.name)
            if re_match_log_csv:
                param_id = int(re_match_log_csv.group(1))
                param_nr = int(re_match_log_csv.group(2))
                slave_id = int(re_match_log_csv.group(3))
                cell_id = int(re_match_log_csv.group(4))
                cell_csv = {csv_label.PARAMETER_ID: param_id, csv_label.PARAMETER_NR: param_nr,
                            csv_label.SLAVE_ID: slave_id, csv_label.CELL_ID: cell_id, "log_filename": entry.name}
                cell_log_csv.append(cell_csv)
                if (slave_id < 0) or (slave_id >= cfg.NUM_SLAVES_MAX):
                    logging.log.warning("Found unusual slave_id: %u" % slave_id)
                    num_warnings = num_warnings + 1
                else:
                    if (cell_id < 0) or (cell_id >= cfg.NUM_CELLS_PER_SLAVE):
                        logging.log.warning("Found unusual cell_id: %u" % cell_id)
                        num_warnings = num_warnings + 1
                    else:
                        if ((slave_cell_found[slave_id][cell_id] == "b")
                                or (slave_cell_found[slave_id][cell_id] == "d")
                                or (slave_cell_found[slave_id][cell_id] == "x")
                                or (slave_cell_found[slave_id][cell_id] == "l")):
                            logging.log.warning("Found more than one entry for S%02u:C%02u" % (slave_id, cell_id))
                            num_warnings = num_warnings + 1
                        elif slave_cell_found[slave_id][cell_id] == "e":
                            slave_cell_found[slave_id][cell_id] = "b"
                        elif slave_cell_found[slave_id][cell_id] == "i":
                            slave_cell_found[slave_id][cell_id] = "d"
                        elif slave_cell_found[slave_id][cell_id] == "f":
                            slave_cell_found[slave_id][cell_id] = "x"
                        else:
                            slave_cell_found[slave_id][cell_id] = "l"
            elif re_match_eoc_csv:
                param_id = int(re_match_eoc_csv.group(1))
                param_nr = int(re_match_eoc_csv.group(2))
                slave_id = int(re_match_eoc_csv.group(3))
                cell_id = int(re_match_eoc_csv.group(4))
                cell_csv = {csv_label.PARAMETER_ID: param_id, csv_label.PARAMETER_NR: param_nr,
                            csv_label.SLAVE_ID: slave_id, csv_label.CELL_ID: cell_id, "eoc_filename": entry.name}
                cell_eoc_csv.append(cell_csv)
                if (slave_id < 0) or (slave_id >= cfg.NUM_SLAVES_MAX):
                    logging.log.warning("Found unusual slave_id: %u" % slave_id)
                    num_warnings = num_warnings + 1
                else:
                    if (cell_id < 0) or (cell_id >= cfg.NUM_CELLS_PER_SLAVE):
                        logging.log.warning("Found unusual cell_id: %u" % cell_id)
                        num_warnings = num_warnings + 1
                    else:
                        if ((slave_cell_found[slave_id][cell_id] == "b")
                                or (slave_cell_found[slave_id][cell_id] == "f")
                                or (slave_cell_found[slave_id][cell_id] == "x")
                                or (slave_cell_found[slave_id][cell_id] == "e")):
                            logging.log.warning("Found more than one entry for S%02u:C%02u" % (slave_id, cell_id))
                            num_warnings = num_warnings + 1
                        elif slave_cell_found[slave_id][cell_id] == "l":
                            slave_cell_found[slave_id][cell_id] = "b"
                        elif slave_cell_found[slave_id][cell_id] == "i":
                            slave_cell_found[slave_id][cell_id] = "f"
                        elif slave_cell_found[slave_id][cell_id] == "d":
                            slave_cell_found[slave_id][cell_id] = "x"
                        else:
                            slave_cell_found[slave_id][cell_id] = "e"
            elif re_match_eis_csv:
                param_id = int(re_match_eis_csv.group(1))
                param_nr = int(re_match_eis_csv.group(2))
                slave_id = int(re_match_eis_csv.group(3))
                cell_id = int(re_match_eis_csv.group(4))
                cell_csv = {csv_label.PARAMETER_ID: param_id, csv_label.PARAMETER_NR: param_nr,
                            csv_label.SLAVE_ID: slave_id, csv_label.CELL_ID: cell_id, "eis_filename": entry.name}
                cell_eis_csv.append(cell_csv)
                if (slave_id < 0) or (slave_id >= cfg.NUM_SLAVES_MAX):
                    logging.log.warning("Found unusual slave_id: %u" % slave_id)
                    num_warnings = num_warnings + 1
                else:
                    if (cell_id < 0) or (cell_id >= cfg.NUM_CELLS_PER_SLAVE):
                        logging.log.warning("Found unusual cell_id: %u" % cell_id)
                        num_warnings = num_warnings + 1
                    else:
                        if ((slave_cell_found[slave_id][cell_id] == "d")
                                or (slave_cell_found[slave_id][cell_id] == "f")
                                or (slave_cell_found[slave_id][cell_id] == "x")
                                or (slave_cell_found[slave_id][cell_id] == "i")):
                            logging.log.warning("Found more than one entry for S%02u:C%02u" % (slave_id, cell_id))
                            num_warnings = num_warnings + 1
                        elif slave_cell_found[slave_id][cell_id] == "l":
                            slave_cell_found[slave_id][cell_id] = "d"
                        elif slave_cell_found[slave_id][cell_id] == "e":
                            slave_cell_found[slave_id][cell_id] = "f"
                        elif slave_cell_found[slave_id][cell_id] == "b":
                            slave_cell_found[slave_id][cell_id] = "x"
                        else:
                            slave_cell_found[slave_id][cell_id] = "i"

    num_parameters = 0
    num_cells_per_parameter = 0
    for cell_log in cell_log_csv:
        found_eoc = False
        for cell_eoc in cell_eoc_csv:
            if ((cell_log[csv_label.PARAMETER_ID] == cell_eoc[csv_label.PARAMETER_ID])
                    and (cell_log[csv_label.PARAMETER_NR] == cell_eoc[csv_label.PARAMETER_NR])
                    and (cell_log[csv_label.SLAVE_ID] == cell_eoc[csv_label.SLAVE_ID])
                    and (cell_log[csv_label.CELL_ID] == cell_eoc[csv_label.CELL_ID])):
                cell_log["eoc_filename"] = cell_eoc["eoc_filename"]
                found_eoc = True
                break
        if not found_eoc:
            if REQUIRE_EOC:
                continue  # skip cell
            cell_log["eoc_filename"] = ""  # else -> set empty

        found_eis = False
        for cell_eis in cell_eis_csv:
            if ((cell_log[csv_label.PARAMETER_ID] == cell_eis[csv_label.PARAMETER_ID])
                    and (cell_log[csv_label.PARAMETER_NR] == cell_eis[csv_label.PARAMETER_NR])
                    and (cell_log[csv_label.SLAVE_ID] == cell_eis[csv_label.SLAVE_ID])
                    and (cell_log[csv_label.CELL_ID] == cell_eis[csv_label.CELL_ID])):
                cell_log["eis_filename"] = cell_eis["eis_filename"]
                found_eis = True
                break
        if not found_eis:
            if REQUIRE_EIS:
                continue  # skip cell
            cell_log["eis_filename"] = ""  # else -> set empty

        slave_id = cell_log[csv_label.SLAVE_ID]
        cell_id = cell_log[csv_label.CELL_ID]
        if ((slave_id >= 0) and (slave_id < cfg.NUM_SLAVES_MAX)
                and (cell_id >= 0) and (cell_id < cfg.NUM_CELLS_PER_SLAVE)):
            cell_str = slave_cell_found[slave_id][cell_id]
            slave_cell_found[slave_id][cell_id] = str.capitalize(cell_str)
            param_id = cell_log[csv_label.PARAMETER_ID]
            param_nr = cell_log[csv_label.PARAMETER_NR]
            if param_id > num_parameters:
                num_parameters = param_id
            if param_nr > num_cells_per_parameter:
                num_cells_per_parameter = param_nr

        generate_log_age_csv_task_queue.put(cell_log)

    # List found slaves/cells for user
    pre_text = ("Found the following files:\n"
                "' ' = no file found, 'l' = only LOG, 'e' = only EOC, 'i' = only EIS,\n"
                "'b' = LOG+EOC, 'd' = LOG+EIS, 'f' = EOC+EIS, 'x' = all found,\n"
                "capital letter, e.g., 'X' = found & matching -> added\n")
    logging.log.info(ht.get_found_cells_text(slave_cell_found, pre_text))

    total_queue_size = generate_log_age_csv_task_queue.qsize()

    # Create processes
    processes = []
    logging.log.info("Starting processes to generate LOG_AGE data...")
    for processorNumber in range(0, NUMBER_OF_PROCESSORS_TO_USE):
        logging.log.debug("  Starting process %u" % processorNumber)
        processes.append(multiprocessing.Process(target=generate_log_age_csv_thread,
                                                 args=(processorNumber, generate_log_age_csv_task_queue, report_queue,
                                                       total_queue_size)))
    for processorNumber in range(0, NUMBER_OF_PROCESSORS_TO_USE):
        processes[processorNumber].start()
    for processorNumber in range(0, NUMBER_OF_PROCESSORS_TO_USE):
        processes[processorNumber].join()
        logging.log.debug("Joined process %u" % processorNumber)


def generate_log_age_csv_thread(processor_number, slave_queue, thread_report_queue, total_queue_size):
    while True:
        if (slave_queue is None) or slave_queue.empty():
            break  # no more files

        try:
            remaining_size = slave_queue.qsize()
            queue_entry = slave_queue.get_nowait()
        # except multiprocessing.queue.Empty:
        except multiprocessing.queues.Empty:
            break  # no more files

        if queue_entry is None:
            break  # no more files

        slave_id = queue_entry[csv_label.SLAVE_ID]
        cell_id = queue_entry[csv_label.CELL_ID]

        param_id = queue_entry[csv_label.PARAMETER_ID]
        param_nr = queue_entry[csv_label.PARAMETER_NR]
        # if not (param_id >= 17):
        #     continue  # for debugging individual parameters

        # if not (slave_id == 6):
        #     continue  # for debugging individual slaves

        # if not ((slave_id == 11) and (cell_id == 2)):
        #     continue  # for debugging individual cells

        # if not ((slave_id == 4) and (
        #         (cell_id == 0) or (cell_id == 1) or (cell_id == 2) or (cell_id == 3) or (cell_id == 5))):
        #     continue  # for debugging individual cells

        filename_log_csv = queue_entry["log_filename"]
        filename_eoc_csv = queue_entry["eoc_filename"]
        filename_eis_csv = queue_entry["eis_filename"]

        output_file_type = cfg.CSV_FILENAME_08_TYPE_LOG_AGE % T_RESOLUTION_S_DEFAULT
        filename_output = "no csv output"

        progress = 0.0
        if total_queue_size > 0:
            progress = (1.0 - remaining_size / total_queue_size) * 100.0
        logging.log.info("Thread %u S%02u:C%02u - generating %s data (progress: %.1f %%)"
                         % (processor_number, slave_id, cell_id, cfg.CSV_FILENAME_08_TYPE_LOG_AGE, progress))

        # num_runs = 0
        num_points_log_used = 0
        num_points_eoc_used = 0
        num_points_eis_used = 0
        num_points_output = 0
        num_infos = 0
        num_warnings = 0
        num_errors = 0

        try:
            # I. read EOCv2 file -> filter what we want (columns, condition)
            logging.log.debug("Thread %u S%02u:C%02u - I. reading EOCv2 file" % (processor_number, slave_id, cell_id))
            eoc_df = pd.read_csv(cfg.CSV_RESULT_DIR + filename_eoc_csv, header=0, sep=cfg.CSV_SEP, engine="pyarrow",
                                 usecols=LOAD_COLUMNS_EOC, dtype=COLUMN_DTYPES_EOC)

            eoc_df = eoc_df[(eoc_df[csv_label.EOC_CYC_CONDITION] == cfg.cyc_cond.CHECKUP_RT)
                            & (eoc_df[csv_label.EOC_CYC_CHARGED] == 0)]

            if eoc_df.shape[0] == 0:
                base_msg = "Thread %u S%02u:C%02u - EOCv2 file has no check-ups" % (processor_number, slave_id, cell_id)
                if REQUIRE_EOC:
                    logging.log.error(base_msg + " -> skip cell")
                    num_errors = num_errors + 1
                    raise ProcessingFailure
                logging.log.warning(base_msg +
                                    " -> ignore EOC, use default time_resolution (%u s)" % T_RESOLUTION_S_DEFAULT)
                num_warnings = num_warnings + 1
                time_resolution = T_RESOLUTION_S_DEFAULT
            else:
                age_type = eoc_df[csv_label.AGE_TYPE].iloc[0]
                if age_type not in T_RESOLUTION_S:
                    # warning -> resolution not given -> assume it shall be skipped (report as warning)
                    logging.log.warning("Thread %u S%02u:C%02u - age_type %s not in T_RESOLUTION_S -> assume it shall "
                                        "not be exported -> skip cell"
                                        % (processor_number, slave_id, cell_id, str(age_type)))
                    num_warnings = num_warnings + 1
                    raise ProcessingFailure
                time_resolution = T_RESOLUTION_S.get(age_type)
                output_file_type = cfg.CSV_FILENAME_08_TYPE_LOG_AGE % time_resolution

            log_interp_min_gap_s = LOG_INTERPOLATION_MIN_GAP_S
            if time_resolution < log_interp_min_gap_s:
                log_interp_min_gap_s = time_resolution

            # II. read EIS file -> filter + search + calculate what we want (columns, condition)
            logging.log.debug("Thread %u S%02u:C%02u - II. reading EIS file" % (processor_number, slave_id, cell_id))
            eis_df = pd.read_csv(cfg.CSV_RESULT_DIR + filename_eis_csv, header=0, sep=cfg.CSV_SEP, engine="pyarrow",
                                 usecols=LOAD_COLUMNS_EIS, dtype=COLUMN_DTYPES_EIS)

            eis_df = eis_df[(eis_df[csv_label.IS_ROOM_TEMP] == 1) & (eis_df[csv_label.EIS_VALID] == 1)
                            & ~pd.isna(csv_label.Z_AMP_MOHM) & ~pd.isna(csv_label.Z_AMP_MOHM)
                            & (((eis_df[csv_label.EIS_FREQ] > R0_FREQ_MIN)
                                & (eis_df[csv_label.EIS_FREQ] < R0_FREQ_MAX))
                               | ((eis_df[csv_label.EIS_FREQ] > R1_FREQ_MIN)
                                  & (eis_df[csv_label.EIS_FREQ] < R1_FREQ_MAX)))]

            r_df = pd.DataFrame(columns=COLUMNS_R)
            if eis_df.shape[0] == 0:
                base_msg = "Thread %u S%02u:C%02u - no usable EIS data points" % (processor_number, slave_id, cell_id)
                if REQUIRE_EIS:
                    logging.log.error(base_msg + " -> skip cell")
                    num_errors = num_errors + 1
                    raise ProcessingFailure
                logging.log.warning(base_msg + " -> ignore EIS")
                num_warnings = num_warnings + 1
            else:
                eis_df.reset_index(inplace=True, drop=True)
                # eis_timestamps = eis_df[csv_label.TIMESTAMP].drop_duplicates().tolist()
                # eis_socs = eis_df[csv_label.SOC_NOM].drop_duplicates().tolist()
                dt_1 = eis_df[csv_label.TIMESTAMP] - eis_df[csv_label.TIMESTAMP].shift(1)
                dt_2 = eis_df[csv_label.TIMESTAMP].shift(-1) - eis_df[csv_label.TIMESTAMP]
                dti_1 = dt_1[dt_1 > MIN_CU_DISTANCE_S].index.tolist()
                dti_2 = dt_2[dt_2 > MIN_CU_DISTANCE_S].index.tolist()
                dti_start = [0]
                dti_start.extend(dti_1)
                dti_end = dti_2
                dti_end.extend([eis_df.shape[0] - 1])
                num_eis_cus = len(dti_start)
                for i_cu in range(0, num_eis_cus):
                    eis_cu_df = eis_df.loc[dti_start[i_cu]:dti_end[i_cu], :]
                    # use last valid EIS if 2x at same condition
                    eis_cu_df = eis_cu_df.drop_duplicates(subset=[csv_label.SOC_NOM, csv_label.EIS_FREQ], keep="last")
                    runs_t = eis_cu_df[csv_label.TIMESTAMP].drop_duplicates()
                    last_timestamp = runs_t.iloc[-1]
                    r0_avg = 0.0
                    r1_avg = 0.0
                    num_r0 = 0
                    num_r1 = 0
                    for this_run_t in runs_t:
                        eis_run_df = eis_cu_df[eis_cu_df[csv_label.TIMESTAMP] == this_run_t]
                        # drop implausible values
                        d_ph_1 = eis_run_df[csv_label.Z_PH_DEG].diff().abs()
                        d_ph_2 = eis_run_df[csv_label.Z_PH_DEG].diff(-1).abs()
                        d_amp_1 = eis_run_df[csv_label.Z_AMP_MOHM].diff().abs()
                        d_amp_2 = eis_run_df[csv_label.Z_AMP_MOHM].diff(-1).abs()
                        drop_cond = (((d_ph_1 > EIS_POINT_INVALID_PHASE_DIFF)
                                      & (d_ph_2 > EIS_POINT_INVALID_PHASE_DIFF))
                                     | ((d_amp_1 > EIS_POINT_INVALID_AMP_DIFF)
                                        & (d_amp_2 > EIS_POINT_INVALID_AMP_DIFF)))
                        if any(drop_cond):
                            logging.log.debug("Thread %u S%02u:C%02u - dropped the following EIS values at i_cu = %u at"
                                              " %u (%s UTC)\n%s"
                                              % (processor_number, slave_id, cell_id, i_cu, last_timestamp,
                                                 pd.to_datetime(last_timestamp, unit="s"),
                                                 eis_run_df[drop_cond].to_string()))
                        eis_run_df = eis_run_df[~drop_cond]

                        # linear interpolation of R0 using Z values with phase >= 0 and <= 0
                        cond = ((eis_run_df[csv_label.EIS_FREQ] >= R0_FREQ_MIN)
                                & (eis_run_df[csv_label.EIS_FREQ] <= R0_FREQ_MAX))
                        phs_neg = eis_run_df[csv_label.Z_PH_DEG][cond & (eis_run_df[csv_label.Z_PH_DEG] <= 0)]
                        phs_pos = eis_run_df[csv_label.Z_PH_DEG][cond & (eis_run_df[csv_label.Z_PH_DEG] >= 0)]
                        if (phs_neg.shape[0] == 0) or (phs_pos.shape[0] == 0):
                            continue  # skip this run - can't calculate R1 if R0 is unknown
                        i_z_neg = phs_neg.idxmax()
                        i_z_pos = phs_pos.idxmin()
                        z0_amp_neg = eis_run_df[csv_label.Z_AMP_MOHM][i_z_pos]
                        z0_amp_pos = eis_run_df[csv_label.Z_AMP_MOHM][i_z_neg]
                        z0_ph_neg = eis_run_df[csv_label.Z_PH_DEG][i_z_pos]
                        z0_ph_pos = eis_run_df[csv_label.Z_PH_DEG][i_z_neg]
                        z0_neg = z0_amp_neg * cmath.exp(1j * (z0_ph_neg * (cmath.pi / 180.0)))
                        z0_pos = z0_amp_pos * cmath.exp(1j * (z0_ph_pos * (cmath.pi / 180.0)))
                        d_imag = (z0_neg.imag - z0_pos.imag)
                        if d_imag < 0.01:  # both close around real axis, avoid division by zero
                            r0_avg = r0_avg + z0_pos.real
                        else:
                            fac = z0_neg.imag / (z0_neg.imag - z0_pos.imag)
                            z_interpol = (1.0 - fac) * z0_neg + fac * z0_pos
                            r0_avg = r0_avg + z_interpol.real
                        num_r0 = num_r0 + 1

                        # linear interpolation of R1 using real part of value with minimal phase
                        cond = ((eis_run_df[csv_label.EIS_FREQ] >= R1_FREQ_MIN)
                                & (eis_run_df[csv_label.EIS_FREQ] <= R1_FREQ_MAX))
                        phs = eis_run_df[csv_label.Z_PH_DEG][cond]
                        if phs.shape[0] == 0:
                            continue  # skip R1 calculation
                        i_z = phs.idxmin()
                        z1_amp = eis_run_df[csv_label.Z_AMP_MOHM][i_z]
                        z1_ph = eis_run_df[csv_label.Z_PH_DEG][i_z]
                        z1 = z1_amp * cmath.exp(1j * (z1_ph * (cmath.pi / 180.0)))
                        r1_avg = r1_avg + z1.real
                        num_r1 = num_r1 + 1

                    if num_r1 == 0:
                        if num_r0 > 0:
                            txt1 = "R1"
                            txt2 = " -> only use R0"
                            skip = False
                        else:
                            txt1 = "R0 and R1"
                            txt2 = " -> skip this CU"
                            skip = True
                        logging.log.warning("Thread %u S%02u:C%02u - couldn't determine %s in EIS with i_cu = %u at %u "
                                            "(%s UTC)%s"
                                            % (processor_number, slave_id, cell_id, txt1, i_cu, last_timestamp,
                                               pd.to_datetime(last_timestamp, unit="s"), txt2))
                        num_warnings = num_warnings + 1
                        if skip:
                            continue  # no usable values -> skip this CU
                    else:
                        r1_avg = r1_avg / num_r1
                    r0_avg = r0_avg / num_r0
                    r1_avg = r1_avg - r0_avg

                    if ((r0_avg < R0_RT_MIN_PLAUSIBLE) or (r0_avg > R0_RT_MAX_PLAUSIBLE)
                            or (r1_avg < R1_RT_MIN_PLAUSIBLE) or (r1_avg > R1_RT_MAX_PLAUSIBLE)):
                        logging.log.warning("Thread %u S%02u:C%02u - implausible values for R0 (%.1f mOhm), "
                                            "R1 (%.1f mOhm) at i_cu = %u, %u (%s UTC) -> skip CU"
                                            % (processor_number, slave_id, cell_id, r0_avg, r1_avg, i_cu,
                                               last_timestamp, pd.to_datetime(last_timestamp, unit="s")))
                        num_warnings = num_warnings + 1
                        continue  # no usable values -> skip this CU
                    i_new = r_df.shape[0]
                    r_df.loc[i_new, csv_label.TIMESTAMP] = last_timestamp
                    r_df.loc[i_new, csv_label.R0] = r0_avg
                    r_df.loc[i_new, csv_label.R1] = r1_avg

            # III. read LOGEXT file
            logging.log.debug("Thread %u S%02u:C%02u - III. reading LOG file, this might take some time..."
                              % (processor_number, slave_id, cell_id))
            t_read_start = datetime.now()
            log_fullpath = cfg.CSV_RESULT_DIR + filename_log_csv
            log_df = pd.read_csv(log_fullpath, header=0, sep=cfg.CSV_SEP, engine="pyarrow",
                                 usecols=LOAD_COLUMNS_LOG, dtype=COLUMN_DTYPES_LOG)
            t_read_stop = datetime.now()
            dt = t_read_stop - t_read_start
            logging.log.debug("Thread %u S%02u:C%02u - ...reading log complete (%.0f seconds)"
                              % (processor_number, slave_id, cell_id, dt.total_seconds()))

            if log_df.shape[0] == 0:
                logging.log.error("Thread %u S%02u:C%02u - Error: empty LOGEXT file: %s"
                                  % (processor_number, slave_id, cell_id, log_fullpath))
                num_errors = num_errors + 1
                raise ProcessingFailure

            # cut at the end
            if log_df[csv_label.SCH_STATE_SUB].iloc[-1] == state_sub.PAUSED:
                i_last_running = log_df[log_df[csv_label.SCH_STATE_SUB] == state_sub.RUNNING].index[-1]
                t_last_running = log_df[csv_label.TIMESTAMP][i_last_running]
                t_max_include = t_last_running + T_LOG_END_EXTRA_S + time_resolution
                i_last = log_df[log_df[csv_label.TIMESTAMP] <= t_max_include].index[-1]
                keep_cond = (log_df.index < i_last)
                log_df = log_df[keep_cond].copy()

            num_points_log_used = log_df.shape[0]
            if num_points_log_used == 0:
                logging.log.error("Thread %u S%02u:C%02u - Error: LOGEXT file doesn't contain usable data: %s"
                                  % (processor_number, slave_id, cell_id, log_fullpath))
                num_errors = num_errors + 1
                raise ProcessingFailure

            # a. create EFC column from csv_label.TOTAL_Q_CHG_SUM and csv_label.TOTAL_Q_DISCHG_SUM
            log_df[csv_label.TOTAL_Q_CHG_SUM] =\
                ((log_df[csv_label.TOTAL_Q_CHG_SUM] + log_df[csv_label.TOTAL_Q_DISCHG_SUM])
                 / (2.0 * cfg.CELL_CAPACITY_NOMINAL))
            log_df.drop(columns=csv_label.TOTAL_Q_DISCHG_SUM, inplace=True)
            log_df.rename(columns={csv_label.TOTAL_Q_CHG_SUM: csv_label.EFC}, inplace=True)

            # b. find gaps, linear interpolation in between -> we already made sure states and measurements fit
            dt_1 = log_df[csv_label.TIMESTAMP].shift(-1) - log_df[csv_label.TIMESTAMP]
            dt_2 = log_df[csv_label.TIMESTAMP] - log_df[csv_label.TIMESTAMP].shift(1)
            dti_start = dt_1[dt_1 > log_interp_min_gap_s].index
            dti_end = dt_2[dt_2 > log_interp_min_gap_s].index
            # pd.DataFrame(columns=log_df.columns) -> can't assign individual dtypes!
            log_gaps_df = log_df.head(0).copy()  # better than pd.DataFrame(columns=log_df.columns)
            for i_gap in range(0, len(dti_start)):
                i_start = dti_start[i_gap]
                i_end = dti_end[i_gap]
                t_start = round(log_df[csv_label.TIMESTAMP][i_start])
                t_end = round(log_df[csv_label.TIMESTAMP][i_end])
                new_timestamps = range(t_start, t_end, int(INTERPOLATION_PERIOD_S))
                i_gdf_end = (len(new_timestamps) - 1)
                if (t_end - t_start) > LOG_INTERPOLATION_MIN_GAP_S:
                    if ((log_df.loc[i_start, csv_label.SCH_STATE_SUB] != state_sub.PAUSED)
                            or (log_df.loc[i_start, csv_label.SCH_STATE_SUB] != state_sub.PAUSED)):
                        logging.log.warning("Thread %u S%02u:C%02u - gap at i_gap = %u, %u - %u (%s - %s UTC) is not "
                                            "properly marked -> interpolation may give unwanted results"
                                            % (processor_number, slave_id, cell_id, i_gap, t_start, t_end,
                                               pd.to_datetime(t_start, unit="s"), pd.to_datetime(t_end, unit="s")))
                        num_warnings = num_warnings + 1

                this_gap_df = pd.DataFrame(index=range(0, len(new_timestamps)), columns=log_gaps_df.columns,
                                           dtype="float64")
                # this_gap_df = log_gaps_df.head(0).copy() -> how to insert multiple empty rows?
                this_gap_df.loc[0, :] = log_df.loc[i_start, :]
                this_gap_df.loc[i_gdf_end, :] = log_df.loc[i_end, :]
                this_gap_df.loc[0:i_gdf_end, csv_label.TIMESTAMP] = new_timestamps
                this_gap_df.loc[:, INTERPOLATE_COLUMNS_LOG] = (
                    this_gap_df.loc[:, INTERPOLATE_COLUMNS_LOG].astype(np.float64).interpolate())
                for col in BACKWARD_FILL_COLUMNS_LOG:
                    this_gap_df.loc[1:(i_gdf_end - 1), col] = \
                        this_gap_df.loc[i_gdf_end, col]
                # delete first and last index
                this_gap_df.drop(index=[0, i_gdf_end], inplace=True)
                # restore dtypes
                for col in this_gap_df:
                    if col in COLUMN_DTYPES:
                        dty = COLUMN_DTYPES.get(col)
                        this_gap_df.loc[:, col] = this_gap_df.loc[:, col].astype(dty)

                # append to log_gaps_df
                log_gaps_df = pd.concat([log_gaps_df, this_gap_df], ignore_index=True)

            # append to log_df
            log_df = pd.concat([log_df, log_gaps_df], ignore_index=True).copy()

            # sort by timestamp
            log_df.sort_values(by=csv_label.TIMESTAMP, inplace=False)

            # convert timestamp to datetime to apply stuff
            log_df.loc[:, csv_label.TIMESTAMP] = pd.to_datetime(log_df[csv_label.TIMESTAMP], unit="s", origin='unix')

            # Create a new DataFrame with a uniformly spaced time series
            pd_resolution = (f'%uS' % time_resolution)

            # resample with time_resolution (use averaging)
            log_df = log_df.set_index(csv_label.TIMESTAMP).resample(pd_resolution).mean().copy()
            NAN_CHECK_COLUMNS = [csv_label.V_CELL, csv_label.OCV_EST, csv_label.I_CELL, csv_label.T_CELL,
                                 csv_label.SOC_EST, csv_label.DELTA_Q, csv_label.EFC]
            if time_resolution <= (3 * cfg.DELTA_T_LOG):
                # resample can introduce NaNs if pd_resolution is larger than any time difference in the LOG
                # -> fill with interpolation
                log_df.loc[:, NAN_CHECK_COLUMNS] = log_df[NAN_CHECK_COLUMNS].interpolate("linear")
            num_nans_cols = log_df[NAN_CHECK_COLUMNS].isna().sum()
            num_nans = num_nans_cols.sum()
            if num_nans > 0:
                logging.log.warning("Thread %u S%02u:C%02u - there are %u NaN values in columns where they shouldn't "
                                    "be:\n%s" % (processor_number, slave_id, cell_id, num_nans, num_nans_cols))
                num_warnings = num_warnings + 1

            log_df.loc[:, csv_label.TIMESTAMP] = (log_df.index - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
            log_df.reset_index(drop=True, inplace=True)

            # plt.scatter(log_df[csv_label.TIMESTAMP], log_df[csv_label.V_CELL], c="b")
            # plt.scatter(log_df[csv_label.TIMESTAMP], log_df[csv_label.I_CELL], c="r")
            # # plt.plot(log_df[csv_label.TIMESTAMP], log_df[csv_label.V_CELL], c='b')
            # # plt.plot(log_df[csv_label.TIMESTAMP], log_df[csv_label.I_CELL], c='r')
            # plt.xlabel("Timestamp")
            # plt.ylabel("V (blue), I (red)")
            # plt.grid(True)
            # plt.show()

            # add EIS and EOC values where they fit best
            log_df.loc[:, SAVE_COLUMNS_EOC] = np.nan
            log_df.loc[:, SAVE_COLUMNS_R] = np.nan

            for _, eoc_row in eoc_df.iterrows():
                t_eoc = eoc_row[csv_label.TIMESTAMP]
                filt_df = log_df[csv_label.TIMESTAMP][log_df[csv_label.TIMESTAMP] >= t_eoc]
                if filt_df.shape[0] > 0:
                    i_log = filt_df.idxmin()
                elif (t_eoc - log_df[csv_label.TIMESTAMP].iloc[-1]) < T_MAX_EARLY_AGEING_DATA_INSERTION:
                    i_log = log_df[csv_label.TIMESTAMP].index[-1]
                else:
                    logging.log.info("Thread %u S%02u:C%02u - EOC data points after the end of the AGE_LOG at t = %u "
                                     "(%s UTC)-> skipped" % (processor_number, slave_id, cell_id, t_eoc,
                                                             pd.to_datetime(t_eoc, unit="s")))
                    num_infos = num_infos + 1
                    break
                log_df.loc[i_log, SAVE_COLUMNS_EOC] = eoc_row[SAVE_COLUMNS_EOC]
                num_points_eoc_used = num_points_eoc_used + 1

            for _, r_row in r_df.iterrows():
                t_r = r_row[csv_label.TIMESTAMP]
                filt_df = log_df[csv_label.TIMESTAMP][log_df[csv_label.TIMESTAMP] >= t_r]
                if filt_df.shape[0] > 0:
                    i_log = filt_df.idxmin()
                elif (t_r - log_df[csv_label.TIMESTAMP].iloc[-1]) < T_MAX_EARLY_AGEING_DATA_INSERTION:
                    i_log = log_df[csv_label.TIMESTAMP].index[-1]
                else:
                    logging.log.info("Thread %u S%02u:C%02u - EIS data points after the end of the AGE_LOG at t = %u "
                                     "(%s UTC)-> skipped" % (processor_number, slave_id, cell_id, t_r,
                                                             pd.to_datetime(t_r, unit="s")))
                    num_infos = num_infos + 1
                    break
                log_df.loc[i_log, SAVE_COLUMNS_R] = r_row[SAVE_COLUMNS_R]
                num_points_eis_used = num_points_eis_used + 1

            log_df = log_df[OUTPUT_COLUMNS_ALL].copy()
            log_df.loc[:, csv_label.TIMESTAMP] = log_df[csv_label.TIMESTAMP] - RELATIVE_TIME

            # write csv (quickest method?)
            logging.log.debug("Thread %u S%02u:C%02u - formatting and writing new LOG file - this may take a while..."
                              % (processor_number, slave_id, cell_id))
            t_read_start = datetime.now()
            for col in log_df.columns:
                if col is csv_label.TIMESTAMP:
                    this_format = TIME_FORMAT
                else:
                    this_format = OUTPUT_FORMAT
                log_df.loc[:, col] = log_df[col].map(this_format.format)

            num_points_output = log_df.shape[0]

            # noinspection PyArgumentList
            pd_log_df = pa.Table.from_pandas(df=log_df, preserve_index=False)
            # "parameter 'type_cls' unfilled" -> bug in pyarrows?
            log_df = ""
            del log_df
            gc.collect()
            filename_output = (cfg.CSV_FILENAME_05_RESULT_BASE_CELL
                               % (output_file_type, param_id, param_nr, slave_id, cell_id))
            write_options = csv.WriteOptions(include_header=True, batch_size=1024, delimiter=cfg.CSV_SEP,
                                             quoting_style="none")
            csv.write_csv(pd_log_df, cfg.CSV_RESULT_DIR + filename_output, write_options)
            t_read_stop = datetime.now()
            dt = t_read_stop - t_read_start
            logging.log.debug("Thread %u S%02u:C%02u - ...writing AGE_LOG complete (%.0f seconds)"
                              % (processor_number, slave_id, cell_id, dt.total_seconds()))

        except ProcessingFailure:
            # logging.log.warning("Thread %u S%02u:C%02u - generating AGE_LOG failed!"
            #                     % (processor_number, slave_id, cell_id))
            pass

        # we land here on success or any error

        # reporting to main thread
        report_msg = (f"%s - P%03u-%u(S%02u:C%02u) - generated age log data: used %u LOGEXT, %u EOC, and %u EIS rows, "
                      f"exported %u rows. %u infos, %u warnings, %u errors"
                      % (filename_output, param_id, param_nr, slave_id, cell_id,
                         num_points_log_used, num_points_eoc_used, num_points_eis_used,
                         num_points_output, num_infos, num_warnings, num_errors))
        report_level = config_logging.INFO
        if num_errors > 0:
            report_level = config_logging.ERROR
        elif num_warnings > 0:
            report_level = config_logging.WARNING

        cell_report = {"msg": report_msg, "level": report_level,
                       csv_label.PARAMETER_ID: param_id, csv_label.PARAMETER_NR: param_nr}
        thread_report_queue.put(cell_report)

    slave_queue.close()
    # thread_report_queue.close()
    logging.log.info("Thread %u - no more slaves - exiting" % processor_number)


def print_found_cells(slave_cell_found, pre_text):
    tmp = pre_text + "   Cells:   "
    for cell_id in range(0, cfg.NUM_CELLS_PER_SLAVE):
        tmp += "x"
    tmp += "\n"
    for slave_id in range(0, cfg.NUM_SLAVES_MAX):
        tmp += f"Slave %2u:   " % slave_id
        for cell_id in range(0, cfg.NUM_CELLS_PER_SLAVE):
            tmp += str(slave_cell_found[slave_id][cell_id])
        tmp += "\n"
    logging.log.info(tmp)


def print_found_cells_of_slave(slave_cell_found, slave_id):
    tmp = "   Cells:   "
    for cell_id in range(0, cfg.NUM_CELLS_PER_SLAVE):
        tmp += "x"
    tmp += f"\nSlave %2u:   " % slave_id
    for cell_id in range(0, cfg.NUM_CELLS_PER_SLAVE):
        tmp += str(slave_cell_found[cell_id])
    tmp += "\n"
    logging.log.info(tmp)


if __name__ == "__main__":
    run()
