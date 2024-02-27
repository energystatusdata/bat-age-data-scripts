from enum import IntEnum
import numpy as np


# --- path definitions ---
CSV_RESULT_DIR = "H:\\Luh\\bat\\analysis\\preprocessing\\result\\"

LOG_DIR = CSV_RESULT_DIR + "log\\"
IMAGE_OUTPUT_DIR = CSV_RESULT_DIR + "images\\"
MODEL_OUTPUT_DIR = CSV_RESULT_DIR + "model\\"
CHECK_OUTPUT_DIR = CSV_RESULT_DIR + "check\\"

ORCA_PATH = 'C:\\Users\\AVT\\AppData\\Local\\Programs\\orca\\orca.exe'

CSV_FILENAME_05_RESULT_BASE_SLAVE = f"slave_%s_%s%02u.csv"  # slave + thermal management
CSV_FILENAME_05_RESULT_BASE_SLAVE_RE = f"slave_(\w)_(\w)(\d+).csv"  # same as above, but for "re" library
CSV_FILENAME_05_RESULT_BASE_CELL = f"cell_%s_P%03u_%u_S%02u_C%02u.csv"  # cell_log_P017_2_S04_C07.csv
CSV_FILENAME_05_RESULT_BASE_CELL_RE = f"cell_(\w)_P(\d+)_(\d+)_S(\d+)_C(\d+).csv"  # same as above, but for "re" library
CSV_FILENAME_05_RESULT_BASE_POOL = f"pool_%s_T%02u_P%u.csv"
CSV_FILENAME_05_RESULT_BASE_POOL_RE = f"pool_(\w)_T(\d+)_P(\d+).csv"  # same as above, but for "re" library
CSV_FILENAME_05_TYPE_CONFIG = "cfg"
CSV_FILENAME_05_TYPE_LOG = "log"
CSV_FILENAME_05_TYPE_LOG_EXT = "logext"
CSV_FILENAME_05_TYPE_EIS = "eis"
CSV_FILENAME_05_TYPE_EIS_FIXED = "eisv2"
CSV_FILENAME_05_TYPE_EOC = "eoc"
CSV_FILENAME_05_TYPE_EOC_FIXED = "eocv2"
CSV_FILENAME_05_TYPE_PULSE = "pls"
CSV_FILENAME_05_TYPE_PULSE_FIXED = "plsv2"
CSV_FILENAME_08_TYPE_LOG_AGE = "log_age_%us"  # for 30 second resolution: log_age_30s
CSV_FILENAME_08_TYPE_LOG_AGE_RE = "log_age_(\d+)s"  # same as above, but for "re" library

# CSV row names
CSV_SEP = ";"
CSV_NEWLINE = "\n"
CSV_NAN = "nan"
DELTA_T_LOG = 1.99950336  # CM0 * 2^16 / f_STM = 3051 * 65536 / 100 000 000
DELTA_T_STM_TICK = 0.01048576  # seconds per STM tick
DELTA_T_REBOOT = 4  # assume a reboot takes 4 seconds

# slave general configuration
NUM_SLAVES_MAX = 20
NUM_CELLS_PER_SLAVE = 12
NUM_POOLS_PER_TMGMT = 4
NUM_PELTIERS_PER_POOL = 4


# enum type definitions, gathered comparing LOG/TLOG from SD & Influx. Other packets receive timestamp of last LOG/TLOG.
class TimestampOrigin(IntEnum):
    UNKNOWN = 0  # timestamp unknown (this should only be used in the scripts, not in final data output)
    INFLUX_EXACT = 1  # data from SD, timestamp: exact match with SD data and influx timestamp
    INFLUX_ESTIMATED = 2  # data from SD, timestamp: no exact (only a rough) match with SD data and influx timestamp
    INTERPOLATED = 3  # data from SD, timestamp: no influx data, timestamp interpolated using uptime or fixed steps
    EXTRAPOLATED = 4  # data from SD, timestamp: no influx data, timestamp extrapolated (likely to be wrong)
    INSERTED = 5  # newly inserted timestamp, no data from cycler, measurements: interpolate linearly, states: use last
    ERROR = 6  # timestamp that is known to be false, but this is still the best estimation possible


class sch_state_ph(IntEnum):  # scheduler phase state, used to extend LOG file (_06_fix_issues_mc.py)
    NONE = 0
    CYCLING = 1
    CHECKUP = 2


class sch_state_cu(IntEnum):  # scheduler check-up state, used to extend LOG file (_06_fix_issues_mc.py)
    NONE = 0
    WAIT_FOR_RT = 1
    PREPARE_SET = 2
    PREPARE_DISCHG = 3
    CAP_MEAS_CHG = 4
    CAP_MEAS_DISCHG = 5
    RT_EIS_PULSE = 6
    WAIT_FOR_OT = 7
    OT_EIS_PULSE = 8
    FOLLOW_UP = 9
    TMGMT_OT = 10
    TMGMT_RT = 11


class sch_state_sub(IntEnum):  # scheduler sub state, used to extend LOG file (_06_fix_issues_mc.py)
    IDLE_PREPARE = 0  # idle or prepare
    WAIT_FOR_START = 1
    START = 2
    RESTART = 3
    RUNNING = 4
    FINISH = 10
    FINISHED = 9
    PAUSE = 14
    PAUSED = 13


class sch_state_chg(IntEnum):  # scheduler charging state, used to extend LOG file (_06_fix_issues_mc.py)
    IDLE = 0
    CHARGE = 1
    DISCHARGE = 2
    DYNAMIC = 3
    CALENDAR_AGING = 4


class condition(IntEnum):  # condition_t, e.g., for measurement and BMS state (is the cell usable?)
    UNKNOWN = 0
    PERMANENT_FAULT = 1
    TEMPORARY_FAULT = 2
    TEMPORARY_FAULT_WAIT_FOR_TURN_ON = 3
    OK = 4


class age_type(IntEnum):  # ageing type (how is the cell operated/aged? calendar/cyclic/profile aging)
    MANUAL = 0
    CALENDAR = 1
    CYCLIC = 2
    PROFILE = 3


class cyc_cond(IntEnum):  # cycling condition (for EOC file)
    OTHER = 0
    REGULAR_OP = 1
    CHECKUP_RT = 2
    # CHECKUP_OT = 3 -> unused


class cell_used(IntEnum):  # cell used config (for CFG file)
    DISABLED = 0
    AUTO = 1
    MANUAL = 2


class DataRecordType(IntEnum):  # identify the type of data records -> also see DATA_RECORD_REGEX_PATTERN !
    UNDEFINED = 0,
    CFG_CELL = 1,  # cell configuration
    CFG_POOL = 2,  # pool configuration
    CFG_TMGMT = 3,  # thermal management configuration
    CFG_CYCLER = 4,  # cycler configuration
    CELL_LOG_RAW = 5,  # raw, unprocessed, unrepaired cell LOG
    CELL_LOG_EXT = 6,  # extended, fixed cell log
    CELL_LOG_AGE = 7,  # compact cell log, gaps filled, reduced time resolution
    CELL_EOC_RAW = 8,  # raw cell end of charge/discharge file, collected after each chg/dischg/dyn process ("run")
    CELL_EOC_FIXED = 9,  # extended cell end of charge/discharge file
    CELL_EIS = 10,  # cell electrochemical impedance spectroscopy (EIS) measurement
    CELL_EIS_FIXED = 11,  # extended & compensated cell electrochemical impedance spectroscopy (EIS) measurement
    CELL_PULSE_RAW = 12,  # raw, unprocessed, unrepaired cell pulse pattern measurement
    CELL_PULSE_FIXED = 13,  # fixed cell pulse pattern measurement
    POOL_LOG_RAW = 14,  # raw, unprocessed, unrepaired pool LOG
    TMGMT_LOG_RAW = 15,  # raw, unprocessed, unrepaired thermal management slave LOG
    CYCLER_LOG_RAW = 16,  # raw, unprocessed, unrepaired cycler slave LOG


class DataRecordBaseType(IntEnum):  # identify the base type of data records -> also see DATA_RECORD_BASE_TYPE !
    UNDEFINED = 0,
    CELL = 1,  # cell-related
    POOL = 2,  # pool-related
    CYCLER_SLAVE = 3,  # cycler slave-related
    TMGMT_SLAVE = 4,  # thermal management slave-related


DATA_RECORD_REGEX_PATTERN = {
    DataRecordType.CFG_CELL:
        CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", CSV_FILENAME_05_TYPE_CONFIG),
    DataRecordType.CFG_POOL:
        CSV_FILENAME_05_RESULT_BASE_POOL_RE.replace("(\w)", CSV_FILENAME_05_TYPE_CONFIG),
    DataRecordType.CFG_TMGMT:
        CSV_FILENAME_05_RESULT_BASE_SLAVE_RE.replace("(\w)", CSV_FILENAME_05_TYPE_CONFIG, 1).replace("(\w)", "T"),
    DataRecordType.CFG_CYCLER:
        CSV_FILENAME_05_RESULT_BASE_SLAVE_RE.replace("(\w)", CSV_FILENAME_05_TYPE_CONFIG, 1).replace("(\w)", "S"),
    DataRecordType.CELL_LOG_RAW:
        CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", CSV_FILENAME_05_TYPE_LOG),
    DataRecordType.CELL_LOG_EXT:
        CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", CSV_FILENAME_05_TYPE_LOG_EXT),
    DataRecordType.CELL_LOG_AGE:
        CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", CSV_FILENAME_08_TYPE_LOG_AGE_RE),
    DataRecordType.CELL_EOC_RAW:
        CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", CSV_FILENAME_05_TYPE_EOC),
    DataRecordType.CELL_EOC_FIXED:
        CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", CSV_FILENAME_05_TYPE_EOC_FIXED),
    DataRecordType.CELL_EIS:
        CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", CSV_FILENAME_05_TYPE_EIS),
    DataRecordType.CELL_EIS_FIXED:
        CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", CSV_FILENAME_05_TYPE_EIS_FIXED),
    DataRecordType.CELL_PULSE_RAW:
        CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", CSV_FILENAME_05_TYPE_PULSE),
    DataRecordType.CELL_PULSE_FIXED:
        CSV_FILENAME_05_RESULT_BASE_CELL_RE.replace("(\w)", CSV_FILENAME_05_TYPE_PULSE_FIXED),
    DataRecordType.POOL_LOG_RAW:
        CSV_FILENAME_05_RESULT_BASE_POOL_RE.replace("(\w)", CSV_FILENAME_05_TYPE_LOG),
    DataRecordType.TMGMT_LOG_RAW:
        CSV_FILENAME_05_RESULT_BASE_SLAVE_RE.replace("(\w)", CSV_FILENAME_05_TYPE_LOG, 1).replace("(\w)", "T"),
    DataRecordType.CYCLER_LOG_RAW:
        CSV_FILENAME_05_RESULT_BASE_SLAVE_RE.replace("(\w)", CSV_FILENAME_05_TYPE_LOG, 1).replace("(\w)", "S"),
}


DATA_RECORD_BASE_TYPE = {
    DataRecordType.CFG_CELL: DataRecordBaseType.CELL,
    DataRecordType.CFG_POOL: DataRecordBaseType.POOL,
    DataRecordType.CFG_TMGMT: DataRecordBaseType.TMGMT_SLAVE,
    DataRecordType.CFG_CYCLER: DataRecordBaseType.CYCLER_SLAVE,
    DataRecordType.CELL_LOG_RAW: DataRecordBaseType.CELL,
    DataRecordType.CELL_LOG_EXT: DataRecordBaseType.CELL,
    DataRecordType.CELL_LOG_AGE: DataRecordBaseType.CELL,
    DataRecordType.CELL_EOC_RAW: DataRecordBaseType.CELL,
    DataRecordType.CELL_EOC_FIXED: DataRecordBaseType.CELL,
    DataRecordType.CELL_EIS: DataRecordBaseType.CELL,
    DataRecordType.CELL_EIS_FIXED: DataRecordBaseType.CELL,
    DataRecordType.CELL_PULSE_RAW: DataRecordBaseType.CELL,
    DataRecordType.CELL_PULSE_FIXED: DataRecordBaseType.CELL,
    DataRecordType.POOL_LOG_RAW: DataRecordBaseType.POOL,
    DataRecordType.TMGMT_LOG_RAW: DataRecordBaseType.TMGMT_SLAVE,
    DataRecordType.CYCLER_LOG_RAW: DataRecordBaseType.CYCLER_SLAVE,
}

AGE_TYPE_SHORTNAMES = {
    age_type.CALENDAR: 'CAL',
    age_type.CYCLIC: 'CYC',
    age_type.PROFILE: 'PRF'
}

DATA_RECORD_SHORTNAMES = {
    DataRecordType.CFG_CELL: 'CFGc',
    DataRecordType.CFG_POOL: 'CFGp',
    DataRecordType.CFG_TMGMT: 'CFGt',
    DataRecordType.CFG_CYCLER: 'CFGs',
    DataRecordType.CELL_LOG_RAW: 'LOGr',
    DataRecordType.CELL_LOG_EXT: 'LOG',
    DataRecordType.CELL_LOG_AGE: 'LOGa',
    DataRecordType.CELL_EOC_RAW: 'EOCr',
    DataRecordType.CELL_EOC_FIXED: 'EOC',
    DataRecordType.CELL_EIS: 'EISr',
    DataRecordType.CELL_EIS_FIXED: 'EIS',
    DataRecordType.CELL_PULSE_RAW: 'PLSr',
    DataRecordType.CELL_PULSE_FIXED: 'PLS',
    DataRecordType.POOL_LOG_RAW: 'LOGpr',
    DataRecordType.TMGMT_LOG_RAW: 'LOGtr',
    DataRecordType.CYCLER_LOG_RAW: 'LOGsr',
}

AGE_TEMPERATURE_UNDEFINED = 126
AGE_TEMPERATURE_MANUAL = 127

AGE_SOC_UNDEFINED = 254
AGE_SOC_MANUAL = 255

AGE_RATE_UNDEFINED = 0

AGE_PROFILE_TEXTS = ["none", "test", "WLTP 3b complete, SoC: 10 - 100 %",
                     "WLTP 3b complete, SoC: 10 - 90 %", "WLTP 3b extra high, SoC: 10 - 90 %"]
AGE_PROFILE_TEXTS_SHORT = ["-", "test profile", "10-100 %, +0.33 Cc, WLTP 3b",
                           "10-90 %, +0.33 Cc, WLTP 3b", "10-90 %, +1.67 Cc, WLTP 3b high"]

AGE_PROFILE_SOC_MIN = [np.nan, 10, 10, 10, 10]
AGE_PROFILE_SOC_MAX = [np.nan, 90, 100, 90, 90]
AGE_PROFILE_CHG_RATE = [np.nan, 90, 100, 90, 90]


# definitions for experiment
EXPERIMENT_START_TIMESTAMP = 1665593100  # -> Mi, 12.10.2022  16:45:00 UTC see schedule_2022-10-12_experiment_LG_HG2.txt
# FIRST_USE_START_TIMESTAMP = EXPERIMENT_START_TIMESTAMP - (5 * 60)  # in LOG ext, delete data >5 min before experiment
FIRST_USE_START_TIMESTAMP = 1665598800  # in LOG ext, delete data before Mi, 12.10.2022  18:20:00 UTC, because there
# were issues with slave 4 (needed multiple reboots, first few hundred data sets have invalid timestamps with test data

CELL_PRODUCTION_TIMESTAMP = 1606392000  # 26.11.2020 12:00 UTC (estimated, based on the printed "+DT331K262A -")
CELL_STORAGE_VOLTAGE = 3.555  # in V, +/- 50 mV, voltage at which the cell was stored before the experiment
# CELL_STORAGE_SOC = 26.7  # in % (100 = 100%), +/- 1%, SoC at which the cell was stored before the experiment
CELL_STORAGE_TEMPERATURE = 20  # in °C, average temperature at which the cell was stored before the experiment

CELL_CAPACITY_NOMINAL = 3.0  # in Ah
CELL_ENERGY_NOMINAL = 11.0  # in Wh

CELL_CAPACITY_MAX_PLAUSIBLE_CHG = 1.05 * CELL_CAPACITY_NOMINAL  # 3.15 Ah
CELL_CAPACITY_MAX_PLAUSIBLE_DISCHG = 1.05 * CELL_CAPACITY_NOMINAL  # 3.15 Ah
CELL_ENERGY_MAX_PLAUSIBLE_CHG = 1.2 * CELL_ENERGY_NOMINAL  # 13.2 Wh
CELL_ENERGY_MAX_PLAUSIBLE_DISCHG = 1.2 * CELL_ENERGY_NOMINAL  # 13.2 Wh

# parameter set id / nr from slave + cell id
PARAMETER_SET_ID_FROM_SXX_CXX = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # slave 00 --> not used for cell cycling --> use param ID 0
    [20, 24, 67, 65, 19, 27, 18, 26, 17, 25, 1, 3],  # slave 01
    [20, 28, 67, 66, 19, 27, 18, 26, 21, 25, 2, 3],  # slave 02
    [20, 28, 65, 66, 23, 27, 22, 26, 21, 25, 2, 4],  # slave 03
    [24, 28, 65, 66, 23, 18, 22, 17, 21, 1, 2, 4],  # slave 04
    [24, 67, 19, 23, 22, 17, 1, 3, 4, 36, 39, 37],  # slave 05
    [32, 40, 70, 68, 31, 39, 30, 38, 29, 37, 6, 7],  # slave 06
    [32, 40, 70, 68, 31, 39, 34, 38, 33, 5, 6, 8],  # slave 07
    [32, 40, 69, 68, 35, 30, 34, 29, 33, 5, 6, 8],  # slave 08
    [36, 70, 69, 31, 35, 30, 34, 29, 33, 5, 7, 8],  # slave 09
    [36, 69, 35, 38, 37, 7, 48, 72, 51, 50, 49, 11],  # slave 10
    [44, 52, 73, 71, 43, 51, 42, 50, 41, 49, 10, 11],  # slave 11
    [44, 52, 73, 71, 43, 51, 46, 50, 45, 9, 10, 12],  # slave 12
    [44, 52, 72, 71, 47, 42, 46, 41, 45, 9, 10, 12],  # slave 13
    [48, 73, 72, 43, 47, 42, 46, 41, 45, 9, 11, 12],  # slave 14
    [48, 47, 49, 60, 76, 55, 59, 58, 53, 13, 15, 16],  # slave 15
    [56, 60, 76, 75, 55, 63, 54, 62, 53, 61, 13, 15],  # slave 16
    [56, 64, 76, 74, 55, 63, 54, 62, 57, 61, 14, 15],  # slave 17
    [56, 64, 75, 74, 59, 63, 58, 62, 57, 61, 14, 16],  # slave 18
    [60, 64, 75, 74, 59, 54, 58, 53, 57, 13, 14, 16]]  # slave 19

# a "1" at PARAMETER_SET_CELL_NR_FROM_SXX_CXX[x][y] means, that this is the first index with the parameter set ID from
# PARAMETER_SET_ID_FROM_SXX_CXX[x][y]. Filling order: The lowest slave has the lowest cell PARAMETER_SET_CELL_NR.
PARAMETER_SET_CELL_NR_FROM_SXX_CXX = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # slave 00 --> not used for cell cycling --> use index 0
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],  # slave 01
    [2, 1, 2, 1, 2, 2, 2, 2, 1, 2, 1, 2],  # slave 02
    [3, 2, 2, 2, 1, 3, 1, 3, 2, 3, 2, 1],  # slave 03
    [2, 3, 3, 3, 2, 3, 2, 2, 3, 2, 3, 2],  # slave 04
    [3, 3, 3, 3, 3, 3, 3, 3, 3, 1, 1, 1],  # slave 05
    [1, 1, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1],  # slave 06
    [2, 2, 2, 2, 2, 3, 1, 2, 1, 1, 2, 1],  # slave 07
    [3, 3, 1, 3, 1, 2, 2, 2, 2, 2, 3, 2],  # slave 08
    [2, 3, 2, 3, 2, 3, 3, 3, 3, 3, 2, 3],  # slave 09
    [3, 3, 3, 3, 3, 3, 1, 1, 1, 1, 1, 1],  # slave 10
    [1, 1, 1, 1, 1, 2, 1, 2, 1, 2, 1, 2],  # slave 11
    [2, 2, 2, 2, 2, 3, 1, 3, 1, 1, 2, 1],  # slave 12
    [3, 3, 2, 3, 1, 2, 2, 2, 2, 2, 3, 2],  # slave 13
    [2, 3, 3, 3, 2, 3, 3, 3, 3, 3, 3, 3],  # slave 14
    [3, 3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1],  # slave 15
    [1, 2, 2, 1, 2, 1, 1, 1, 2, 1, 2, 2],  # slave 16
    [2, 1, 3, 1, 3, 2, 2, 2, 1, 2, 1, 3],  # slave 17
    [3, 2, 2, 2, 2, 3, 2, 3, 2, 3, 2, 2],  # slave 18
    [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]]  # slave 19

PARAMETER_SET_AGE_TYPE_FROM_SXX_CXX = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # slave 00 --> not used for cell cycling --> use index 0
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1],  # slave 01
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1],  # slave 02
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1],  # slave 03
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1],  # slave 04
    [2, 3, 2, 2, 2, 2, 1, 1, 1, 2, 2, 2],  # slave 05
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1],  # slave 06
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1],  # slave 07
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1],  # slave 08
    [2, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1, 1],  # slave 09
    [2, 3, 2, 2, 2, 1, 2, 3, 2, 2, 2, 1],  # slave 10
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1],  # slave 11
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1],  # slave 12
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1],  # slave 13
    [2, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1, 1],  # slave 14
    [2, 2, 2, 2, 3, 2, 2, 2, 2, 1, 1, 1],  # slave 15
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1],  # slave 16
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1],  # slave 17
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1],  # slave 18
    [2, 2, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1]]  # slave 19


# pulse pattern definition
NUM_PULSE_LOG_POINTS = 61  # 9 * 3 + 11 * 3 + 1 = 61
PULSE_TIME_OFFSET_S = [0, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1, 3,  # short pulse (10s) high (9 points)
                       10, 10.001, 10.003, 10.01, 10.03, 10.1, 10.3, 11, 13,  # short pulse low (9)
                       20, 20.001, 20.003, 20.01, 20.03, 20.1, 20.3, 21, 23,  # short pulse relax (9)
                       30, 30.001, 30.003, 30.01, 30.03, 30.1, 30.3, 31, 33, 40, 60,  # long pulse (30s) high (11)
                       90, 90.001, 90.003, 90.01, 90.03, 90.1, 90.3, 91, 93, 100, 120,  # long pulse low (11)
                       150, 150.001, 150.003, 150.01, 150.03, 150.1, 150.3, 151, 153, 160, 180,  # long pulse relax (11)
                       210]  # end (1)
# IPN = 1  # nominal pulse current for PULSE_CURRENT_NOMINAL
# PULSE_CURRENT_NOMINAL = [0, IPN, IPN, IPN, IPN, IPN, IPN, IPN, IPN, ...]
PULSE_TIME_OFFSET_S_MAX_DECIMALS = 3  # how many numbers after decimal point in PULSE_TIME_OFFSET_S

# electrochemical impedance spectroscopy (EIS) definition
NUM_EIS_SOCS_MAX = 10
NUM_EIS_POINTS_MAX_EXPECTED_ON_SD = 29  # typically, a maximum of 29 points are written to the SD card
NUM_EIS_POINTS_MAX_FITTING_ON_SD = 39  # max. num. of points that fit into SD block (if someone extends the experiment)
# NUM_EIS_POINTS_MAX = 37
# EIS_FREQ_LIST_HZ = [50000, 31250, 20833.3333, 14705.8824, 10000,
#                     6756.7568, 5000, 3125, 2083.3333, 1470.5882, 1000,
#                     675.6757, 500, 312.5000, 208.3333, 147.0588, 100,
#                     67.5676, 50, 31.2500, 20.8333, 14.7059, 10,
#                     6.7568, 5, 3.1250, 2.0833, 1.4706, 1,
#                     0.6757, 0.5000, 0.3125, 0.2083, 0.1471, 0.1000,
#                     0.0676, 0.0500]
# EIS_USE_LIST = [False, False, False, True, True,
#                 True, True, True, True, True, True,
#                 True, True, True, True, True, True,
#                 True, True, True, True, True, True,
#                 True, True, True, True, False, True,
#                 False, True, False, True, False, True,
#                 False, True]

LIMIT_END_OF_LIFE_CAPACITY_FAC_CU = 0.5
LIMIT_END_OF_LIFE_CAPACITY_FAC_CYC = 0.4
LIMIT_END_OF_LIFE_IMPEDANCE_FAC_IMP = 3.0

T0 = 273.15  # in Kelvin, temperature at 0°C
