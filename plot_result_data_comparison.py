# Plot script for battery degradation result data.
# If you want to use this script, e.g., to customize the plots, see comments marked with ToDo
import time
import traceback
import pandas as pd
import config_main as cfg
import helper_tools as ht
import color_tools as clr
import multiprocessing
from datetime import datetime
import os
import re
import math
import numpy as np
import plotly.io as pio
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import config_labels as csv_label
import config_logging  # as logging


in_dir = "D:\\bat\\analysis\\preprocessing\\result\\"  # ToDo: Please adjust path to where the .csv files are located.


# --- logging ----------------------------------------------------------------------------------------------------------
logging_filename = "log_plot_result_data_comparison.txt"
log_dir = in_dir + "log\\"
# logging = config_logging.bat_data_logger(cfg.LOG_DIR + logging_filename)
logging = config_logging.bat_data_logger(log_dir + logging_filename)


# --- general file handling (input / output) ---------------------------------------------------------------------------
# ToDo: check paths in config_preprocessing - you can also overwrite INPUT_DIR / OUTPUT_DIR according to your needs here
# INPUT_DIR = cfg.CSV_RESULT_DIR  # define the directory of the data records to be plotted
# OUTPUT_DIR = cfg.IMAGE_OUTPUT_DIR + "result_data\\"  # define the directory of the plot outputs (HTML and/or image)
INPUT_DIR = in_dir  # define the directory of the data records to be plotted
OUTPUT_DIR = in_dir + "result_data\\"  # define the directory of the plot outputs (HTML and/or image)

# --- plot file format -------------------------------------------------------------------------------------------------
# ToDo: select output format here
SHOW_IN_BROWSER = False  # if True, open interactive plots in the browser --> can be annoying if you have many plots
EXPORT_HTML = True  # save interactive plots as html
EXPORT_IMAGE = False  # save static plot images -> the image generation might take quite some time! -> only if needed

# IMAGE_FORMAT = "jpg"  # -> tends to be larger than png since we don#t have many different colors
IMAGE_FORMAT = "png"  # -> easiest to view
# IMAGE_FORMAT = "svg"  # -> vector graphics
# IMAGE_FORMAT = "pdf"  # -> vector graphics (but might have rendering issues)
# IMAGE_FORMAT = "eps"  # -> vector graphics

# plot filename: prefix, data record type (EOC/EIS/PLS), plot variable, age mode (CAL/CYC/PRF), version
PLOT_FILENAME_BASE = f"%s%s_%s_%s_v%03u"
PLOT_FILENAME_PREFIX = "plot_"
PLOT_FILENAME_CUSTOM_APPENDIX = f"_%s_v%03u"  # age mode (CAL/CYC/PRF), version

PLOT_SCALE_FACTOR = 1.0  # for image export (to have better/higher resolution than specified in PLOT_WIDTH/PLOT_HEIGHT)
if (IMAGE_FORMAT == "jpg") or (IMAGE_FORMAT == "png"):
    PLOT_SCALE_FACTOR = 3.0

IMAGE_EXPORT_ENGINE = 'kaleido'
# ToDo: for complex/big figures, kaleido might throw:
#   message->data_num_bytes() <= Channel::kMaximumMessageSize
#   in this case, you can use another export engine (need to install orca):
# IMAGE_EXPORT_ENGINE = 'orca'  # alternative image export engine


# --- general plot options ---------------------------------------------------------------------------------------------
TIME_DIV = 24.0 * 60.0 * 60.0  # seconds (data) -> days (plot)
UNIT_TIME = "days"
USE_RELATIVE_TIME = True  # use time relative to start of experiment (recommended)

LARGE_FONT_SIZE = True
COMPACT_AX_LABELS = True

# --- color definitions ------------------------------------------------------------------------------------------------
COLOR_BLACK = 'rgb(0,0,0)'
COLOR_BLUE = 'rgb(29,113,171)'
COLOR_CYAN = 'rgb(22,180,197)'
COLOR_ORANGE = 'rgb(242,121,13)'
COLOR_RED = 'rgb(203,37,38)'
COLOR_GRAY = 'rgb(127,127,127)'
COLOR_LIGHT_GRAY = 'rgb(200,200,200)'

COLOR_RED_DARK = 'rgb(196,22,42)'
COLOR_ORANGE_DARK = 'rgb(250,100,0)'
COLOR_YELLOW_DARK = 'rgb(224,180,0)'
COLOR_GREEN_DARK = 'rgb(55,135,45)'
COLOR_BLUE_DARK = 'rgb(31,96,196)'
COLOR_PURPLE_DARK = 'rgb(143,59,184)'

COLOR_RED_LIGHT = 'rgb(255,115,131)'
COLOR_ORANGE_LIGHT = 'rgb(255,179,87)'
COLOR_YELLOW_LIGHT = 'rgb(255,238,0)'
COLOR_GREEN_LIGHT = 'rgb(150,217,141)'
COLOR_BLUE_LIGHT = 'rgb(138,184,255)'
COLOR_PURPLE_LIGHT = 'rgb(202,149,229)'


COLOR_V_CELL = 'rgb(31,96,196)'  # dark blue
COLOR_OCV_CELL = 'rgb(138,184,255)'  # light blue
COLOR_I_CELL = 'rgb(255,152,48)'  # orange
COLOR_P_CELL = 'rgb(196,22,42)'  # red
COLOR_T_CELL = 'rgb(115,191,105)'  # light green
COLOR_SOC_CELL = 'rgb(250,222,42)'  # yellow
COLOR_DQ_CELL = 'rgb(202,149,229)'  # light purple
COLOR_DE_CELL = 'rgb(143,59,184)'  # dark purple
COLOR_EIS = 'rgb(227,119,194)'  # pink
COLOR_SOH_CAP = 'rgb(143,59,184)'  # dark purple
COLOR_COULOMB_EFFICIENCY = 'rgb(255,203,125)'  # light orange
COLOR_ENERGY_EFFICIENCY = 'rgb(255,166,176)'  # light red

# ToDO: you can also define own colors here to use them in the PLOT_TASKS_LIST

COLOR_SOCS_ARR = [COLOR_RED_DARK, COLOR_ORANGE_DARK, COLOR_YELLOW_DARK, COLOR_GREEN_DARK, COLOR_BLUE_DARK]
# usage, for example:
# PTL_FILT_COLUMNS: [csv_label.SOC_NOM, csv_label.IS_ROOM_TEMP],
# PTL_FILT_VALUES: [[10, 30, 50, 70, 90], [0]],
# PTL_FILT_COLORS: COLOR_SOCS_ARR,

TEMPERATURE_COLORS = {0: COLOR_BLUE, 10: COLOR_CYAN, 25: COLOR_ORANGE, 40: COLOR_RED}
SOC_VALUE_ARRAY = [10, 30, 50, 70, 90]


# --- custom mouse hover functions (see hover_template_fun) ------------------------------------------------------------
def get_hover_default(x_var, y_var, x_unit, y_unit, append_str):
    return x_var + ": %{x} " + x_unit + "<br>" + y_var + ": %{y} " + y_unit + "<br>" + append_str + "<extra></extra>"


def get_hover_eis(x_var, y_var, x_unit, y_unit, append_str):  # use this for EIS plots to see the frequency
    return ("Re: %{x} " + x_unit + ", Im: %{y} " + y_unit + "<br>at f = %{text:.3f} Hz<br>"
            + append_str + "<extra></extra>")


def get_hover_minimal(x_var, y_var, x_unit, y_unit, append_str):
    return "%{x}: %{y}<br><extra></extra>"


# --- other helper functions -------------------------------------------------------------------------------------------
def ttl(string_arr):  # merge strings (for title)
    return ", ".join(string_arr)


def fn(string_arr):  # merge strings (for filename)
    return "_".join(string_arr)


# --- plot variable definition -----------------------------------------------------------------------------------------
COL_EFC = "EFC"  # equivalent full cycles, this is a new row that will be created in the EOC data (used for plots)
COL_T_REL = "t_rel"  # relative time (used for pulse pattern -> always starts at 0, so all pulses can be overlaid)
COL_DV = "dv"  # voltage difference (used for pulse pattern -> always starts at 0, so all pulses can be overlaid)

AGE_VAR_BY_AGE_TYPE = {cfg.age_type.CALENDAR: csv_label.TIMESTAMP,
                       cfg.age_type.CYCLIC: COL_EFC,
                       cfg.age_type.PROFILE: COL_EFC}

# TITLE_BASE_EOC = "End Of Charge (EOC) Data"  # too wide for some plots?
TITLE_BASE_EOC = "EOC"
# TITLE_BASE_EIS = "Electrochemical Impedance Spectroscopy (EIS) measurements"  # too wide for some plots
TITLE_BASE_EIS = "EIS"
TITLE_BASE_PULSE = "Pulse pattern measurements"

TITLE_RT = "at room temperature (25°)"
TITLE_OT = "at operating temperature (0-40°)"

TITLE_SOC_RE = f"SoC = %u %%"
TITLE_SOC_ALL = "SoC = 10/30/50/70/90 %"

TITLE_CAP_REMAINING = "estimated remaining capacity"

FILENAME_BASE_EOC = "EOC"
FILENAME_BASE_EIS = "EIS"
FILENAME_BASE_PULSE = "PLS"

FILENAME_RT = "RT"
FILENAME_OT = "OT"

FILENAME_SOC_RE = f"SoC_%03u"
FILENAME_SOC_ALL = "SoC_all"

AX_TITLE_TIME = "Time"
AX_TITLE_EFC = "Equivalent full cycles"
AX_TITLE_VOLTAGE = "Voltage"
AX_TITLE_SOC = "SoC"
AX_TITLE_DV = "ΔV"
AX_TITLE_OCV = "OCV (est.)"
AX_TITLE_CURRENT = "Current"
AX_TITLE_RESISTANCE = "Resistance"
AX_TITLE_TEMPERATURE = "Temperature"
AX_TITLE_Z_RE = "Re{Z}"
AX_TITLE_Z_IM = "-Im{Z}"
AX_TITLE_Z_AMP = "|Z|"
AX_TITLE_Z_PH = "-arg{Z}"
AX_TITLE_Z_REF = "Z_ref"
AX_TITLE_FREQUENCY = "Frequency"
AX_TITLE_SOH_CAP = "SoH (capacity)"
AX_TITLE_SOH_IMP = "SoH (impedance)"
AX_TITLE_CAP_REMAINING = "est. rem. capacity"
AX_TITLE_DELTA_Q = "ΔQ"
AX_TITLE_DELTA_E = "ΔE"
AX_TITLE_TOTAL_Q = "Total Q"
AX_TITLE_TOTAL_E = "Total E"
AX_TITLE_EFFICIENCY = "Efficiency"
AX_TITLE_CYCLES = "Cycles"

UNIT_EFC = "EFC"
UNIT_VOLTAGE = "V"
UNIT_CURRENT = "A"
UNIT_RESISTANCE_MILLI = "mΩ"
UNIT_TEMPERATURE = "°C"
UNIT_PHASE = "°"
UNIT_FREQUENCY = "Hz"
UNIT_PERCENT = "%"
UNIT_Q = "Ah"
UNIT_E = "Wh"
UNIT_TIME_S = "s"

OPACITY_EOC = 0.25
OPACITY_PULSE = 0.25
OPACITY_EIS = 0.2

EIS_X_LIM = [0, 120]  # in mOhm, x-axis limit for EIS plots. For auto-sizing, use "EIS_X_LIM = None"
EIS_Y_LIM = [-35, 25]  # in mOhm, y-axis limit for EIS plots. For auto-sizing, use "EIS_Y_LIM = None"

USE_LOG_FOR_FREQ_X_AXIS = True  # if True, use semi-logarithmic plot when the x-axis is csv_label.EIS_FREQ

Y_VARS_DQ_ALL = [csv_label.DELTA_Q, csv_label.DELTA_Q_CHG, csv_label.DELTA_Q_DISCHG]
COLORS_DQ_ALL = [COLOR_GRAY, COLOR_ORANGE_DARK, COLOR_GREEN_DARK]

Y_VARS_DE_ALL = [csv_label.DELTA_E, csv_label.DELTA_E_CHG, csv_label.DELTA_E_DISCHG]
COLORS_DE_ALL = COLORS_DQ_ALL

Y_VARS_EFFI_QE = [csv_label.COULOMB_EFFICIENCY, csv_label.ENERGY_EFFICIENCY]
COLORS_EFFI_QE = [COLOR_COULOMB_EFFICIENCY, COLOR_ENERGY_EFFICIENCY]

Y_VARS_OCV_SE = [csv_label.OCV_EST_START, csv_label.OCV_EST_END]
COLORS_OCV_SE = [COLOR_RED_DARK, COLOR_GREEN_DARK]

Y_VARS_T_SE = [csv_label.T_CELL_START, csv_label.T_CELL_END]
COLORS_T_SE = COLORS_OCV_SE

Y_VARS_SOC_SE = [csv_label.SOC_EST_START, csv_label.SOC_EST_END]
COLORS_SOC_SE = COLORS_OCV_SE

Y_VARS_Q_TOT_ALL = [csv_label.TOTAL_Q_CHG_CU_RT, csv_label.TOTAL_Q_DISCHG_CU_RT,
                    csv_label.TOTAL_Q_CHG_CYC_OT, csv_label.TOTAL_Q_DISCHG_CYC_OT,
                    csv_label.TOTAL_Q_CHG_OTHER_RT, csv_label.TOTAL_Q_DISCHG_OTHER_RT,
                    csv_label.TOTAL_Q_CHG_OTHER_OT, csv_label.TOTAL_Q_DISCHG_OTHER_OT,
                    csv_label.TOTAL_Q_CHG_SUM, csv_label.TOTAL_Q_DISCHG_SUM]
COLORS_Q_TOT_ALL = [COLOR_RED_DARK, COLOR_BLUE_DARK,
                    COLOR_ORANGE_LIGHT, COLOR_GREEN_LIGHT,
                    COLOR_RED_LIGHT, COLOR_BLUE_LIGHT,
                    COLOR_YELLOW_LIGHT, COLOR_PURPLE_LIGHT,
                    COLOR_ORANGE_DARK, COLOR_GREEN_DARK]

Y_VARS_E_TOT_ALL = [csv_label.TOTAL_E_CHG_CU_RT, csv_label.TOTAL_E_DISCHG_CU_RT,
                    csv_label.TOTAL_E_CHG_CYC_OT, csv_label.TOTAL_E_DISCHG_CYC_OT,
                    csv_label.TOTAL_E_CHG_OTHER_RT, csv_label.TOTAL_E_DISCHG_OTHER_RT,
                    csv_label.TOTAL_E_CHG_OTHER_OT, csv_label.TOTAL_E_DISCHG_OTHER_OT,
                    csv_label.TOTAL_E_CHG_SUM, csv_label.TOTAL_E_DISCHG_SUM]
COLORS_E_TOT_ALL = COLORS_Q_TOT_ALL


# plot task list structure entry definition  # information in comment: (non-exhaustive!) List of examples
PTL_X_VAR = "PTL_X_VAR"  # * x-variable column used for plotting: e.g., csv_label.TIMESTAMP or COL_EFC or COL_Z_RE
PTL_Y_VARS = "PTL_Y_VARS"  # * array of y-variables used for plotting, e.g., [csv_label.CAP_CHARGED_EST] or
#                              [csv_label.TOTAL_Q_CHG_SUM, csv_label.TOTAL_Q_DISCHG_SUM] or COL_Z_IM
PTL_FILT_COLUMNS = "PTL_FILT_COLUMNS"  # filter data using an array of columns: e.g., [] or [csv_label.IS_ROOM_TEMP] or
#                                        [csv_label.SOC_NOM, csv_label.IS_ROOM_TEMP]
PTL_FILT_VALUES = "PTL_FILT_VALUES"  # select values for filtering: e.g., [[30, 50, 70], [1, 0]]
PTL_GROUP_BY = "PTL_GROUP_BY"  # set to None or leave away to "just" plot all values of a column in a trace. If multiple
#                                traces shall be plotted, grouped by column values, indicate this here, e.g.,
#                                csv_label.SD_BLOCK_ID for PULSE data or csv_label.TIMESTAMP for EIS data
PTL_GROUP_BY_AGING_COL = "PTL_GROUP_BY_AGING_COL"  # if PTL_GROUP_BY is used, PTL_GROUP_BY_AGING_COL can be used to
#                                                    select a variable that is treated as an "aging" variable to color
#                                                    the individual traces according to the age at that point, e.g.,
#                                                    COL_EFC or csv_label.TIMESTAMP or None (no aging-based colors) or
#                                                    AGE_VAR_BY_AGE_TYPE (time or EFC, based on aging type)
PTL_GROUP_TEMPERATURES = "PTL_GROUP_TEMPERATURES"  # if True, group data of all temperatures into single plot
#                                                    (more compact view). In this case, PTL_COLORS is not used!
PTL_COLORS = "PTL_COLORS"  # single or array of plot colors for each PTL_Y_VARS entry, e.g.,
#                            'rgb(239,65,54)' or ['rgb(239,65,54<)', 'rgb(1,147,70)']
I_FILT_COLOR = 0  # array of PTL_FILT_COLORS corresponding to each filter value in the FIRST array in PTL_FILT_VALUES
I_FILT_OPACITY = 1  # array of PTL_FILT_OPACITY corresponding to each filter val. in the SECOND array in PTL_FILT_VALUES
I_FILT_LINESTYLE = 2  # array of PTL_FILT_LINESTYLE corresp. to each filter val. in the THIRD array in PTL_FILT_VALUES
PTL_FILT_COLORS = "PTL_FILT_COLORS"  # colors for PTL_FILT_COLUMNS[I_FILT_COLOR], i.e., the first variable in filter,
#                                      e.g., ['rgb(0,0,255)', 'rgb(0,255,0)', 'rgb(255,0,0)']
PTL_FILT_OPACITY = "PTL_FILT_OPACITY"  # opacity for PTL_FILT_COLUMNS[I_FILT_OPACITY], e.g., [1.0, 0.3]
PTL_FILT_LINESTYLE = "PTL_FILT_LINESTYLE"  # line styles for PTL_FILT_COLUMNS[I_FILT_LINESTYLE],
#                                            see comment behind DEFAULT_LINE_STYLE), e.g.,
#                                            ["solid", "dot", "dash", "longdash", "dashdot", "longdashdot"]
PTL_SHOW_MARKER = "PTL_SHOW_MARKER"  # if True, show a marker (circle) for every data point, not just a line. If there
#                                      are many points, this might cause very large and slow interactive figures.
PTL_OPACITY = "PTL_OPACITY"  # trace opacity, e.g., None (to use TRACE_OPACITY_DEFAULT) or 1.0 (no transparency) or 0.6
PTL_X_AX_TITLE = "PTL_X_AX_TITLE"  # x-axis title (excluding unit), e.g., "Capacity throughput" or "Re{Z}" or "Time"
PTL_Y_AX_TITLE = "PTL_Y_AX_TITLE"  # y-axis title (excluding unit), e.g., "Voltage" or "-Im{Z}" or "Remaining Capacity"
PTL_X_UNIT = "PTL_X_UNIT"  # x-axis unit, e.g., "EFC" or "Ah" or "mΩ" or UNIT_TIME or None
PTL_Y_UNIT = "PTL_Y_UNIT"  # y-axis unit, e.g., "V" or "mΩ" or CAP_UNIT or None
PTL_X_DIV = "PTL_X_DIV"  # divide x-data by this value, e.g., None or TIME_DIV or cfg.CELL_CAPACITY_NOMINAL
PTL_Y_DIV = "PTL_Y_DIV"  # divide y-data by this value, e.g., None or 0.01 or [0.01, 0.02] (for each item in PTL_Y_VARS)
PTL_X_LIMS = "PTL_X_LIMS"  # x-axis limits, e.g., None (automatic) or [0, 1000]
PTL_Y_LIMS = "PTL_Y_LIMS"  # y-axis limits, e.g., None (automatic) or [0, 100]
PTL_TITLE = "PTL_TITLE"  # plot title, e.g., "Remaining usable capacity"
PTL_HOVER_DATA_COL = "PTL_HOVER_DATA_COL"  # add this column to hover data, e.g., use csv_label.EIS_FREQ to see the EIS
# frequency when using get_hover_eis as the PTL_HOVER_TEMPLATE_FUNCTION
PTL_HOVER_TEMPLATE_FUNCTION = "PTL_HOVER_TEMPLATE_FUNCTION"  # hover template function, e.g., None or get_hover_default
PTL_PLOT_ALL_IN_BACKGROUND = "PTL_PLOT_ALL_IN_BACKGROUND"  # if True, plot traces of ALL parameters of this aging type
#   in the background to easier compare them (THIS CAN SIGNIFICANTLY SLOW DOWN PLOTTING AND VISUALIZATION FOR LARGE
#   DATA, esp. for PULSE and EIS data. For EOC: use filter! e.g., only plot CU data using '' with '').
#   If not used, None of False: regular plotting.
PTL_FILENAME = "PTL_FILENAME"  # output figure filename (without file ending). if None or empty, the script chooses
#                                filenames automatically, while trying not to overwrite anything (version appendix)
PTL_MINIMAL_X_AX_LABELS = "PTL_MINIMAL_X_AX_LABELS"  # reduce x-axis labels (only show in the lower row - this will
#                                                      enable shared x-axes with similar limits) - compared to
#                                                      "COMPACT_AX_LABELS", this will also eliminate tick labels
PTL_MINIMAL_Y_AX_LABELS = "PTL_MINIMAL_Y_AX_LABELS"  # reduce y-axis labels (only show in the leftmost column - this
#                                                      will enable shared y-axes with similar limits) - compared to
#                                                      "COMPACT_AX_LABELS", this will also eliminate tick labels
# * mandatory -> only PTL_X_VAR and PTL_Y_VARS are mandatory, the rest is optional (can leave away or make "None")


def get_eoc_plot_task(x_var, y_vars, var_colors, group_temperature, cyc_cond, cyc_chg, show_bg, relative_cap,
                      minimal_x_ax_labels=None, minimal_y_ax_labels=None):
    filt_opacity = None
    if cyc_chg is not None:
        if len(cyc_chg) > 1:
            # opacity
            filt_opacity = [1.0, OPACITY_EOC]
    filt_linestyle = None
    show_marker = False
    if cyc_cond is not None:
        if len(cyc_cond) > 1:
            # line style
            filt_linestyle = ["solid", "dash", "dot"]
        elif len(cyc_cond) == 1:
            if cyc_cond[0] == cfg.cyc_cond.CHECKUP_RT:
                show_marker = True
    cond_title_arr = []
    cond_file_arr = []
    if 2 in cyc_cond:
        cond_title_arr.append("CU")
        cond_file_arr.append("cu")
    if 1 in cyc_cond:
        cond_title_arr.append("regular op.")
        cond_file_arr.append("cy")
    if 0 in cyc_cond:
        cond_title_arr.append("other")
        cond_file_arr.append("ot")
    cond_title_text = "" + " & ".join(cond_title_arr)
    cond_file_text = "" + "+".join(cond_file_arr)
    chg_title_text = ""
    chg_file_text = ""
    if (0 in cyc_chg) and (1 in cyc_chg):
        chg_title_text = "discharging & charging"
        chg_file_text = "c+d"
    elif 0 in cyc_chg:
        chg_title_text = "discharging"
        chg_file_text = "dis"
    elif 1 in cyc_chg:
        chg_title_text = "charging"
        chg_file_text = "chg"
    is_capacity_var = False
    is_energy_var = False
    if len(y_vars) > 1:
        if y_vars[0] == csv_label.DELTA_Q:
            y_ax_title = AX_TITLE_DELTA_Q
            title_var = "charged/discharged charge"
            y_unit = UNIT_Q
            file_unit = "dQcd"
            is_capacity_var = True
        elif y_vars[0] == csv_label.DELTA_E:
            y_ax_title = AX_TITLE_DELTA_E
            title_var = "charged/discharged energy"
            y_unit = UNIT_E
            file_unit = "dEcd"
            is_energy_var = True
        elif (csv_label.TOTAL_Q_DISCHG_SUM in y_vars) or (csv_label.TOTAL_Q_CHG_SUM in y_vars):
            y_ax_title = AX_TITLE_TOTAL_Q
            title_var = "total processed charge"
            y_unit = UNIT_Q
            file_unit = "totalQcd"
            is_capacity_var = True
        elif (csv_label.TOTAL_E_DISCHG_SUM in y_vars) or (csv_label.TOTAL_E_CHG_SUM in y_vars):
            y_ax_title = AX_TITLE_TOTAL_E
            title_var = "total processed energy"
            y_unit = UNIT_E
            file_unit = "totalEcd"
            is_energy_var = True
        elif (y_vars[0] == csv_label.ENERGY_EFFICIENCY) or (y_vars[0] == csv_label.COULOMB_EFFICIENCY):
            y_ax_title = AX_TITLE_EFFICIENCY
            title_var = "efficiency"
            y_unit = UNIT_PERCENT
            file_unit = "effQE"
        elif (y_vars[0] == csv_label.OCV_EST_START) or (y_vars[0] == csv_label.OCV_EST_END):
            y_ax_title = AX_TITLE_OCV
            title_var = "est. start/end OCV"
            y_unit = UNIT_VOLTAGE
            file_unit = "OCVse"
        elif (y_vars[0] == csv_label.T_START) or (y_vars[0] == csv_label.T_END):
            y_ax_title = AX_TITLE_TEMPERATURE
            title_var = "start/end temperature"
            y_unit = UNIT_TEMPERATURE
            file_unit = "Tse"
        elif (y_vars[0] == csv_label.SOC_EST_START) or (y_vars[0] == csv_label.SOC_EST_END):
            y_ax_title = AX_TITLE_SOC
            title_var = "est. start/end SoC"
            y_unit = UNIT_PERCENT
            file_unit = "SoCse"
        else:
            print("get_eoc_plot_task: unimplemented y_vars = %s" % y_vars)
            return None
    elif y_vars[0] == csv_label.CAP_CHARGED_EST:
        y_ax_title = AX_TITLE_CAP_REMAINING
        title_var = TITLE_CAP_REMAINING
        y_unit = UNIT_Q
        file_unit = "Crem"
        is_capacity_var = True
    elif y_vars[0] == csv_label.DELTA_Q:
        y_ax_title = AX_TITLE_DELTA_Q
        title_var = "charged/discharged charge"
        y_unit = UNIT_Q
        file_unit = "dQ"
        is_capacity_var = True
    elif y_vars[0] == csv_label.DELTA_E:
        y_ax_title = AX_TITLE_DELTA_E
        title_var = "charged/discharged energy"
        y_unit = UNIT_E
        file_unit = "dE"
        is_energy_var = True
    elif y_vars[0] == csv_label.ENERGY_EFFICIENCY:
        y_ax_title = AX_TITLE_EFFICIENCY
        title_var = "energy efficiency"
        y_unit = UNIT_PERCENT
        file_unit = "effE"
    elif y_vars[0] == csv_label.COULOMB_EFFICIENCY:
        y_ax_title = AX_TITLE_EFFICIENCY
        title_var = "coulomb efficiency"
        y_unit = UNIT_PERCENT
        file_unit = "effQ"
    elif y_vars[0] == csv_label.EOC_NUM_CYCLES_OP:
        y_ax_title = AX_TITLE_CYCLES
        title_var = "number of cycles"
        y_unit = None
        file_unit = "Ncyc"
    elif y_vars[0] == csv_label.EOC_NUM_CYCLES_CU:
        y_ax_title = AX_TITLE_CYCLES
        title_var = "number of check-ups"
        y_unit = None
        file_unit = "Ncu"
    elif y_vars[0] == csv_label.CYC_DURATION:
        y_ax_title = AX_TITLE_TIME
        title_var = "cycling duration"
        y_unit = UNIT_TIME_S
        file_unit = "tcyc"
    else:
        print("get_eoc_plot_task: unimplemented y_vars = %s" % y_vars)
        return None

    y_div = None
    if relative_cap:
        if is_capacity_var:
            y_div = cfg.CELL_CAPACITY_NOMINAL
            y_unit = "%"
            file_unit = file_unit + "_rel"
        elif is_energy_var:
            y_div = cfg.CELL_ENERGY_NOMINAL
            y_unit = "%"
            file_unit = file_unit + "rel"

    if show_bg:
        bg_text = "bg"
    else:
        bg_text = ""

    if x_var == csv_label.TIMESTAMP:
        x_ax_title = AX_TITLE_TIME
        x_unit = UNIT_TIME
        x_div = TIME_DIV
        title_var = "Time vs. " + title_var
        file_unit = "t_vs_" + file_unit
    elif x_var == COL_EFC:
        x_ax_title = AX_TITLE_EFC
        x_unit = UNIT_EFC
        x_div = None
        title_var = "EFC vs. " + title_var
        file_unit = "EFC_vs_" + file_unit
    else:
        print("get_eoc_plot_task: unimplemented x_var = %s" % x_var)
        return None

    return {
        PTL_X_VAR: x_var,
        PTL_Y_VARS: y_vars,
        PTL_GROUP_TEMPERATURES: group_temperature,
        PTL_COLORS: var_colors,
        PTL_FILT_COLUMNS: [None, csv_label.EOC_CYC_CHARGED, csv_label.EOC_CYC_CONDITION],
        PTL_FILT_VALUES: [None, cyc_chg, cyc_cond],
        PTL_FILT_COLORS: None,
        PTL_FILT_OPACITY: filt_opacity,
        PTL_FILT_LINESTYLE: filt_linestyle,
        PTL_SHOW_MARKER: show_marker,
        PTL_X_AX_TITLE: x_ax_title,
        PTL_Y_AX_TITLE: y_ax_title,
        PTL_X_UNIT: x_unit,
        PTL_Y_UNIT: y_unit,
        PTL_X_DIV: x_div,
        PTL_Y_DIV: y_div,
        PTL_TITLE: ttl([TITLE_BASE_EOC, title_var, cond_title_text, chg_title_text]),
        PTL_FILENAME: fn([FILENAME_BASE_EOC, file_unit, bg_text, cond_file_text, chg_file_text]),
        PTL_PLOT_ALL_IN_BACKGROUND: show_bg,
        PTL_MINIMAL_X_AX_LABELS: minimal_x_ax_labels,
        PTL_MINIMAL_Y_AX_LABELS: minimal_y_ax_labels,
    }


def get_pulse_plot_task(y_vars, socs, is_rt, minimal_x_ax_labels=None, minimal_y_ax_labels=None):
    if (len(y_vars) == 2) and ((y_vars[0] == COL_DV) and (y_vars[1] == csv_label.I_CELL)
                               or (y_vars[1] == COL_DV) and (y_vars[0] == csv_label.I_CELL)):
        ax_title = AX_TITLE_VOLTAGE + " and " + AX_TITLE_CURRENT
        unit = UNIT_VOLTAGE + " or " + UNIT_CURRENT
        file_unit = "VI"
    elif y_vars[0] == csv_label.V_CELL:
        ax_title = AX_TITLE_VOLTAGE
        unit = UNIT_VOLTAGE
        file_unit = "V"
    elif y_vars[0] == csv_label.I_CELL:
        ax_title = AX_TITLE_CURRENT
        unit = UNIT_CURRENT
        file_unit = "I"
    elif y_vars[0] == COL_DV:
        ax_title = AX_TITLE_DV
        unit = UNIT_VOLTAGE
        file_unit = "DV"
    else:
        print("get_pulse_plot_task: unimplemented y_vars = %s" % y_vars)
        return None
    if len(socs) == 1:
        title_socs = TITLE_SOC_RE % socs[0]
        file_socs = FILENAME_SOC_RE % socs[0]
        aging_col = AGE_VAR_BY_AGE_TYPE
    elif len(socs) == 5:
        title_socs = TITLE_SOC_ALL
        file_socs = FILENAME_SOC_ALL
        aging_col = None
    else:
        print("get_pulse_plot_task: unimplemented socs = %s" % socs)
        return None
    if is_rt:
        title_t = TITLE_RT
        file_t = FILENAME_RT
        rt_filt = 1
    else:
        title_t = TITLE_OT
        file_t = FILENAME_OT
        rt_filt = 0
    return {
        PTL_X_VAR: COL_T_REL,
        PTL_Y_VARS: y_vars,
        PTL_FILT_COLUMNS: [csv_label.SOC_NOM, csv_label.IS_ROOM_TEMP],
        PTL_FILT_VALUES: [socs, [rt_filt]],
        PTL_GROUP_BY: csv_label.SD_BLOCK_ID,
        PTL_FILT_COLORS: COLOR_SOCS_ARR,
        PTL_OPACITY: OPACITY_PULSE,
        PTL_X_AX_TITLE: AX_TITLE_TIME,
        PTL_Y_AX_TITLE: ax_title,
        PTL_X_UNIT: UNIT_TIME_S,
        PTL_Y_UNIT: unit,
        PTL_TITLE: ttl([TITLE_BASE_PULSE, ax_title, title_t, title_socs]),
        PTL_FILENAME: fn([FILENAME_BASE_PULSE, file_unit, file_t, file_socs]),
        PTL_GROUP_BY_AGING_COL: aging_col,
        PTL_MINIMAL_X_AX_LABELS: minimal_x_ax_labels,
        PTL_MINIMAL_Y_AX_LABELS: minimal_y_ax_labels,
    }


def get_pulse_auxiliary_plot_task(y_vars, show_bg):
    if y_vars[0] == csv_label.PULSE_R_10_MS_MOHM:
        ax_title = AX_TITLE_RESISTANCE
        title_var = "Pulse resistance [10 ms]"
        unit = UNIT_RESISTANCE_MILLI
        file_unit = "R10ms"
    elif y_vars[0] == csv_label.PULSE_R_1_S_MOHM:
        ax_title = AX_TITLE_RESISTANCE
        title_var = "Pulse resistance [1 s]"
        unit = UNIT_RESISTANCE_MILLI
        file_unit = "R1s"
    elif y_vars[0] == csv_label.PULSE_T_AVG:
        ax_title = AX_TITLE_TEMPERATURE
        title_var = "Average temperature"
        unit = UNIT_TEMPERATURE
        file_unit = "Tavg"
    else:
        print("get_pulse_auxiliary_plot_task: unimplemented y_vars = %s" % y_vars)
        return None
    if show_bg:
        bg_text = "bg"
    else:
        bg_text = ""
    return {
        PTL_X_VAR: csv_label.TIMESTAMP,
        PTL_Y_VARS: y_vars,
        PTL_FILT_COLUMNS: [csv_label.SOC_NOM, csv_label.IS_ROOM_TEMP, csv_label.PULSE_SEQUENCE_NUMBER],
        PTL_FILT_VALUES: [SOC_VALUE_ARRAY, [0, 1], [0]],
        PTL_FILT_COLORS: COLOR_SOCS_ARR,
        PTL_FILT_OPACITY: [1.0, 0.45],
        PTL_SHOW_MARKER: True,
        PTL_X_AX_TITLE: AX_TITLE_TIME,
        PTL_Y_AX_TITLE: ax_title,
        PTL_X_UNIT: UNIT_TIME,
        PTL_Y_UNIT: unit,
        PTL_X_DIV: TIME_DIV,
        PTL_TITLE: ttl([TITLE_BASE_PULSE, title_var, TITLE_SOC_ALL]),
        PTL_FILENAME: fn([FILENAME_BASE_PULSE, file_unit, FILENAME_SOC_ALL, bg_text]),
        PTL_PLOT_ALL_IN_BACKGROUND: show_bg,
    }


def get_eis_plot_task(x_var, y_vars, socs, is_rt, group_temperature, x_lim, y_lim, show_bg,
                      minimal_x_ax_labels=None, minimal_y_ax_labels=None):
    hover_template = None
    hover_data = None
    if x_var == csv_label.Z_RE_COMP_MOHM:
        x_ax_title = AX_TITLE_Z_RE
        unit_x = UNIT_RESISTANCE_MILLI
        file_unit_x = "reZ"
    elif x_var == csv_label.EIS_FREQ:
        x_ax_title = AX_TITLE_FREQUENCY
        unit_x = UNIT_FREQUENCY
        file_unit_x = "f"
    else:
        print("get_eis_plot_task: unimplemented x_var = %s" % x_var)
        return None
    if y_vars[0] == csv_label.Z_IM_COMP_MOHM:
        y_ax_title = AX_TITLE_Z_IM
        unit_y = UNIT_RESISTANCE_MILLI
        file_unit_y = "imZ"
        hover_template = get_hover_eis
        hover_data = csv_label.EIS_FREQ
    elif y_vars[0] == csv_label.Z_AMP_COMP_MOHM:
        y_ax_title = AX_TITLE_Z_AMP
        unit_y = UNIT_RESISTANCE_MILLI
        file_unit_y = "absZ"
    elif y_vars[0] == csv_label.Z_PH_COMP_DEG:
        y_ax_title = AX_TITLE_Z_PH
        unit_y = UNIT_PHASE
        file_unit_y = "argZ"
    elif y_vars[0] == csv_label.Z_AMP_MOHM:
        y_ax_title = AX_TITLE_Z_AMP + " (raw)"
        unit_y = UNIT_RESISTANCE_MILLI
        file_unit_y = "absZ_raw"
    elif y_vars[0] == csv_label.Z_PH_DEG:
        y_ax_title = AX_TITLE_Z_PH + " (raw)"
        unit_y = UNIT_PHASE
        file_unit_y = "argZ_raw"
    else:
        print("get_eis_plot_task: unimplemented y_vars = %s" % y_vars)
        return None
    filt_colors = None
    if len(socs) == 1:
        title_socs = TITLE_SOC_RE % socs[0]
        file_socs = FILENAME_SOC_RE % socs[0]
        if group_temperature:
            aging_col = None
        else:
            aging_col = AGE_VAR_BY_AGE_TYPE
    elif len(socs) == 5:
        title_socs = TITLE_SOC_ALL
        file_socs = FILENAME_SOC_ALL
        aging_col = None
        filt_colors = COLOR_SOCS_ARR
    else:
        print("get_eis_plot_task: unimplemented socs = %s" % socs)
        return None
    if group_temperature:
        file_socs = file_socs + "_Tgroup"
    if is_rt:
        title_t = TITLE_RT
        file_t = FILENAME_RT
        rt_filt = 1
    else:
        title_t = TITLE_OT
        file_t = FILENAME_OT
        rt_filt = 0
    if show_bg:
        bg_text = "bg"
    else:
        bg_text = ""
    if (x_lim is not None) or (y_lim is not None):
        lim_text = "lim"
    else:
        lim_text = ""
    return {
        PTL_X_VAR: x_var,
        PTL_Y_VARS: y_vars,
        PTL_FILT_COLUMNS: [csv_label.SOC_NOM, csv_label.IS_ROOM_TEMP],
        PTL_FILT_VALUES: [socs, [rt_filt]],
        PTL_GROUP_BY: csv_label.TIMESTAMP,
        PTL_GROUP_TEMPERATURES: group_temperature,
        PTL_FILT_COLORS: filt_colors,
        PTL_OPACITY: OPACITY_EIS,
        PTL_X_AX_TITLE: x_ax_title,
        PTL_Y_AX_TITLE: y_ax_title,
        PTL_X_UNIT: unit_x,
        PTL_Y_UNIT: unit_y,
        PTL_TITLE: ttl([TITLE_BASE_EIS, x_ax_title, y_ax_title, title_t, title_socs]),
        PTL_FILENAME: fn([FILENAME_BASE_EIS, file_unit_x, file_unit_y, file_t, file_socs, bg_text, lim_text]),
        PTL_GROUP_BY_AGING_COL: aging_col,
        PTL_HOVER_TEMPLATE_FUNCTION: hover_template,
        PTL_HOVER_DATA_COL: hover_data,
        PTL_X_LIMS: x_lim,
        PTL_Y_LIMS: y_lim,
        PTL_PLOT_ALL_IN_BACKGROUND: show_bg,
        PTL_MINIMAL_X_AX_LABELS: minimal_x_ax_labels,
        PTL_MINIMAL_Y_AX_LABELS: minimal_y_ax_labels,
    }


def get_eis_auxiliary_plot_task(y_vars, show_bg,
                                socs=None, rt_only=False, group_temperature=False, x_var=csv_label.TIMESTAMP,
                                minimal_x_ax_labels=None, minimal_y_ax_labels=None):
    if y_vars[0] == csv_label.Z_REF_NOW:
        ax_title = AX_TITLE_RESISTANCE
        title_var = "Reference impedance"
        unit = UNIT_RESISTANCE_MILLI
        file_unit = "Zref"
    elif y_vars[0] == csv_label.SOH_IMP:
        ax_title = AX_TITLE_SOH_IMP
        title_var = "Impedance-based SoH"
        unit = UNIT_PERCENT
        file_unit = "SoH_imp"
    elif y_vars[0] == csv_label.EIS_T_AVG:
        ax_title = AX_TITLE_TEMPERATURE
        title_var = "Average temperature"
        unit = UNIT_TEMPERATURE
        file_unit = "Tavg"
    elif y_vars[0] == csv_label.EIS_OCV_AVG:
        ax_title = AX_TITLE_OCV
        title_var = "Average estimated open-circuit voltage (OCV)"
        unit = UNIT_VOLTAGE
        file_unit = "OCV"
    else:
        print("get_eis_auxiliary_plot_task: unimplemented y_vars = %s" % y_vars)
        return None
    if show_bg:
        bg_text = "bg"
    else:
        bg_text = ""
    if socs is None:
        soc_values = SOC_VALUE_ARRAY
        soc_colors = COLOR_SOCS_ARR
        soc_title = TITLE_SOC_ALL
        soc_filename = FILENAME_SOC_ALL
    else:
        soc_values = socs
        soc_colors = []
        for i in range(len(socs)):
            soc_colors.append(COLOR_SOCS_ARR[socs[i] % len(COLOR_SOCS_ARR)])
        soc_title = "SoC = " + "/".join(str(soc) for soc in socs) + " %"
        soc_filename = "SoC_" + "+".join(str(soc) for soc in socs)
    if rt_only:
        filt_rt = [1]
        filt_rt_opacity = [1.0]
        filt_rt_title = " (only RT)"
        filt_rt_filename = "_RT"
    else:
        filt_rt = [0, 1]
        filt_rt_opacity = [1.0, 0.45]
        filt_rt_title = ""
        filt_rt_filename = ""
    if group_temperature:
        soc_filename = soc_filename + "_Tgroup"
        colors = None
    else:
        colors = soc_colors
    if x_var == csv_label.TIMESTAMP:
        x_ax_title = AX_TITLE_TIME
        x_unit = UNIT_TIME
        x_div = TIME_DIV
        title_var = "Time vs. " + title_var
        file_unit = "t_vs_" + file_unit
    elif x_var == COL_EFC:
        x_ax_title = AX_TITLE_EFC
        x_unit = UNIT_EFC
        x_div = None
        title_var = "EFC vs. " + title_var
        file_unit = "EFC_vs_" + file_unit
    else:
        print("get_eis_auxiliary_plot_task: unimplemented x_var = %s" % x_var)
        return None
    return {
        PTL_X_VAR: x_var,
        PTL_Y_VARS: y_vars,
        PTL_FILT_COLUMNS: [csv_label.SOC_NOM, csv_label.IS_ROOM_TEMP, csv_label.EIS_SEQUENCE_NUMBER],
        PTL_FILT_VALUES: [soc_values, filt_rt, [0]],
        PTL_FILT_COLORS: colors,
        PTL_FILT_OPACITY: filt_rt_opacity,
        PTL_GROUP_TEMPERATURES: group_temperature,
        PTL_SHOW_MARKER: True,
        PTL_X_AX_TITLE: x_ax_title,
        PTL_Y_AX_TITLE: ax_title,
        PTL_X_UNIT: x_unit,
        PTL_Y_UNIT: unit,
        PTL_X_DIV: x_div,
        PTL_TITLE: ttl([TITLE_BASE_EIS, title_var + filt_rt_title, soc_title]),
        PTL_FILENAME: fn([FILENAME_BASE_EIS, file_unit + filt_rt_filename, soc_filename, bg_text]),
        PTL_PLOT_ALL_IN_BACKGROUND: show_bg,
        PTL_MINIMAL_X_AX_LABELS: minimal_x_ax_labels,
        PTL_MINIMAL_Y_AX_LABELS: minimal_y_ax_labels,
    }


# ToDo: you may adjust the PLOT_TASKS_LIST according to your needs - each entry results in three plots (one for each
#   aging mode: calendar, cyclic, profile). See comments above for usage. You can comment out things you don't need.
#   There are two methods to define the PLOT_TASKS_LIST:
#     1. using helper functions, such as get_eis_plot_task(), get_eis_auxiliary_plot_task(), get_pulse_plot_task(), ...
#        --> very efficient, since almost no code is needed to plot many different variants
#     2. using manually defined structures --> very customizable, see examples further below

# ToDo: PLOT_TASKS_LIST definition using helper functions
PLOT_TASKS_LIST = {
    cfg.DataRecordType.CELL_EOC_FIXED: [
        # --- EOC individual variables --------------------------------------------------
        # DELTA_Q, grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_Q],
                          None, True, [2, 1, 0], [0, 1], False, False),  # CU/CYC/other, dis/ch, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_Q],
                          None, True, [1], [0, 1], False, False),  # CYC, dis/chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_Q],
                          None, True, [2], [0, 1], False, False),  # CU, dis/chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_Q],
                          None, True, [2, 1, 0], [1], False, False),  # CU/CYC/other, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_Q],
                          None, True, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_Q],
                          None, True, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_Q],
                          None, True, [2, 1, 0], [0], False, False),  # CU/CYC/other, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_Q],
                          None, True, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_Q],
                          None, True, [2], [0], True, False),  # CU, dischg, yes (all in backgr.)

        # CAP_CHARGED_EST, grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CAP_CHARGED_EST],
                          None, True, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CAP_CHARGED_EST],
                          None, True, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CAP_CHARGED_EST],
                          None, True, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CAP_CHARGED_EST],
                          None, True, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CAP_CHARGED_EST],
                          None, True, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CAP_CHARGED_EST],
                          None, True, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CAP_CHARGED_EST],
                          None, True, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CAP_CHARGED_EST],
                          None, True, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CAP_CHARGED_EST],
                          None, True, [2], [0], True, False),  # CU, dischg, yes
        # ... vs EFC
        get_eoc_plot_task(COL_EFC, [csv_label.CAP_CHARGED_EST],
                          None, True, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(COL_EFC, [csv_label.CAP_CHARGED_EST],
                          None, True, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(COL_EFC, [csv_label.CAP_CHARGED_EST],
                          None, True, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(COL_EFC, [csv_label.CAP_CHARGED_EST],
                          None, True, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(COL_EFC, [csv_label.CAP_CHARGED_EST],
                          None, True, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(COL_EFC, [csv_label.CAP_CHARGED_EST],
                          None, True, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(COL_EFC, [csv_label.CAP_CHARGED_EST],
                          None, True, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(COL_EFC, [csv_label.CAP_CHARGED_EST],
                          None, True, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(COL_EFC, [csv_label.CAP_CHARGED_EST],
                          None, True, [2], [0], True, False),  # CU, dischg, yes

        # DELTA_E, grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_E],
                          None, True, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_E],
                          None, True, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_E],
                          None, True, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_E],
                          None, True, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_E],
                          None, True, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_E],
                          None, True, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_E],
                          None, True, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_E],
                          None, True, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.DELTA_E],
                          None, True, [2], [0], True, False),  # CU, dischg, yes

        # ENERGY_EFFICIENCY, grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.ENERGY_EFFICIENCY],
                          None, True, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.ENERGY_EFFICIENCY],
                          None, True, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.ENERGY_EFFICIENCY],
                          None, True, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.ENERGY_EFFICIENCY],
                          None, True, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.ENERGY_EFFICIENCY],
                          None, True, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.ENERGY_EFFICIENCY],
                          None, True, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.ENERGY_EFFICIENCY],
                          None, True, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.ENERGY_EFFICIENCY],
                          None, True, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.ENERGY_EFFICIENCY],
                          None, True, [2], [0], True, False),  # CU, dischg, yes

        # COULOMB_EFFICIENCY, grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.COULOMB_EFFICIENCY],
                          None, True, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.COULOMB_EFFICIENCY],
                          None, True, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.COULOMB_EFFICIENCY],
                          None, True, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.COULOMB_EFFICIENCY],
                          None, True, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.COULOMB_EFFICIENCY],
                          None, True, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.COULOMB_EFFICIENCY],
                          None, True, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.COULOMB_EFFICIENCY],
                          None, True, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.COULOMB_EFFICIENCY],
                          None, True, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.COULOMB_EFFICIENCY],
                          None, True, [2], [0], True, False),  # CU, dischg, yes

        # EOC_NUM_CYCLES_OP, grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_OP],
                          None, True, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_OP],
                          None, True, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_OP],
                          None, True, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_OP],
                          None, True, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_OP],
                          None, True, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_OP],
                          None, True, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_OP],
                          None, True, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_OP],
                          None, True, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_OP],
                          None, True, [2], [0], True, False),  # CU, dischg, yes

        # EOC_NUM_CYCLES_CU, grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_CU],
                          None, True, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_CU],
                          None, True, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_CU],
                          None, True, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_CU],
                          None, True, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_CU],
                          None, True, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_CU],
                          None, True, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_CU],
                          None, True, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_CU],
                          None, True, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.EOC_NUM_CYCLES_CU],
                          None, True, [2], [0], True, False),  # CU, dischg, yes

        # CYC_DURATION, grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CYC_DURATION],
                          None, True, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CYC_DURATION],
                          None, True, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CYC_DURATION],
                          None, True, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CYC_DURATION],
                          None, True, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CYC_DURATION],
                          None, True, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CYC_DURATION],
                          None, True, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CYC_DURATION],
                          None, True, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CYC_DURATION],
                          None, True, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CYC_DURATION],
                          None, True, [2], [0], True, False),  # CU, dischg, yes

        # --- EOC multiple variables ----------------------------------------------------
        # delta_Q_all/chg/dischg, not grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DQ_ALL,
                          COLORS_DQ_ALL, False, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DQ_ALL,
                          COLORS_DQ_ALL, False, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DQ_ALL,
                          COLORS_DQ_ALL, False, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DQ_ALL,
                          COLORS_DQ_ALL, False, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DQ_ALL,
                          COLORS_DQ_ALL, False, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DQ_ALL,
                          COLORS_DQ_ALL, False, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DQ_ALL,
                          COLORS_DQ_ALL, False, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DQ_ALL,
                          COLORS_DQ_ALL, False, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DQ_ALL,
                          COLORS_DQ_ALL, False, [2], [0], True, False),  # CU, dischg, yes

        # delta_E_all/chg/dischg, not grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DE_ALL,
                          COLORS_DE_ALL, False, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DE_ALL,
                          COLORS_DE_ALL, False, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DE_ALL,
                          COLORS_DE_ALL, False, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DE_ALL,
                          COLORS_DE_ALL, False, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DE_ALL,
                          COLORS_DE_ALL, False, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DE_ALL,
                          COLORS_DE_ALL, False, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DE_ALL,
                          COLORS_DE_ALL, False, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DE_ALL,
                          COLORS_DE_ALL, False, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_DE_ALL,
                          COLORS_DE_ALL, False, [2], [0], True, False),  # CU, dischg, yes

        # coulomb/energy efficiency, not grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_EFFI_QE,
                          COLORS_EFFI_QE, False, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_EFFI_QE,
                          COLORS_EFFI_QE, False, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_EFFI_QE,
                          COLORS_EFFI_QE, False, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_EFFI_QE,
                          COLORS_EFFI_QE, False, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_EFFI_QE,
                          COLORS_EFFI_QE, False, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_EFFI_QE,
                          COLORS_EFFI_QE, False, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_EFFI_QE,
                          COLORS_EFFI_QE, False, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_EFFI_QE,
                          COLORS_EFFI_QE, False, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_EFFI_QE,
                          COLORS_EFFI_QE, False, [2], [0], True, False),  # CU, dischg, yes

        # OCV (start/end), not grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_OCV_SE,
                          COLORS_OCV_SE, False, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_OCV_SE,
                          COLORS_OCV_SE, False, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_OCV_SE,
                          COLORS_OCV_SE, False, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_OCV_SE,
                          COLORS_OCV_SE, False, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_OCV_SE,
                          COLORS_OCV_SE, False, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_OCV_SE,
                          COLORS_OCV_SE, False, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_OCV_SE,
                          COLORS_OCV_SE, False, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_OCV_SE,
                          COLORS_OCV_SE, False, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_OCV_SE,
                          COLORS_OCV_SE, False, [2], [0], True, False),  # CU, dischg, yes

        # temperature (start/end), not grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_T_SE,
                          COLORS_T_SE, False, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_T_SE,
                          COLORS_T_SE, False, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_T_SE,
                          COLORS_T_SE, False, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_T_SE,
                          COLORS_T_SE, False, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_T_SE,
                          COLORS_T_SE, False, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_T_SE,
                          COLORS_T_SE, False, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_T_SE,
                          COLORS_T_SE, False, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_T_SE,
                          COLORS_T_SE, False, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_T_SE,
                          COLORS_T_SE, False, [2], [0], True, False),  # CU, dischg, yes

        # SoC (start/end), not grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_SOC_SE,
                          COLORS_SOC_SE, False, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_SOC_SE,
                          COLORS_SOC_SE, False, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_SOC_SE,
                          COLORS_SOC_SE, False, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_SOC_SE,
                          COLORS_SOC_SE, False, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_SOC_SE,
                          COLORS_SOC_SE, False, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_SOC_SE,
                          COLORS_SOC_SE, False, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_SOC_SE,
                          COLORS_SOC_SE, False, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_SOC_SE,
                          COLORS_SOC_SE, False, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_SOC_SE,
                          COLORS_SOC_SE, False, [2], [0], True, False),  # CU, dischg, yes

        # Q_total_... (10x), not grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_Q_TOT_ALL,
                          COLORS_Q_TOT_ALL, False, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_Q_TOT_ALL,
                          COLORS_Q_TOT_ALL, False, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_Q_TOT_ALL,
                          COLORS_Q_TOT_ALL, False, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_Q_TOT_ALL,
                          COLORS_Q_TOT_ALL, False, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_Q_TOT_ALL,
                          COLORS_Q_TOT_ALL, False, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_Q_TOT_ALL,
                          COLORS_Q_TOT_ALL, False, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_Q_TOT_ALL,
                          COLORS_Q_TOT_ALL, False, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_Q_TOT_ALL,
                          COLORS_Q_TOT_ALL, False, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_Q_TOT_ALL,
                          COLORS_Q_TOT_ALL, False, [2], [0], True, False),  # CU, dischg, yes

        # E_total_... (10x), not grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_E_TOT_ALL,
                          COLORS_E_TOT_ALL, False, [2, 1, 0], [0, 1], False, False),  # all, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_E_TOT_ALL,
                          COLORS_E_TOT_ALL, False, [1], [0, 1], False, False),  # CYC, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_E_TOT_ALL,
                          COLORS_E_TOT_ALL, False, [2], [0, 1], False, False),  # CU, all, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_E_TOT_ALL,
                          COLORS_E_TOT_ALL, False, [2, 1, 0], [1], False, False),  # all, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_E_TOT_ALL,
                          COLORS_E_TOT_ALL, False, [1], [1], False, False),  # CYC, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_E_TOT_ALL,
                          COLORS_E_TOT_ALL, False, [2], [1], False, False),  # CU, chg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_E_TOT_ALL,
                          COLORS_E_TOT_ALL, False, [2, 1, 0], [0], False, False),  # all, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_E_TOT_ALL,
                          COLORS_E_TOT_ALL, False, [1], [0], False, False),  # CYC, dischg, no
        get_eoc_plot_task(csv_label.TIMESTAMP, Y_VARS_E_TOT_ALL,
                          COLORS_E_TOT_ALL, False, [2], [0], True, False),  # CU, dischg, yes
    ],
    cfg.DataRecordType.CELL_EIS_FIXED: [
        # --- EIS overview --------------------------------------------------------------
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # Re{Z} vs. -Im{Z}, RT, lim
                          SOC_VALUE_ARRAY, True, False, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # Re{Z} vs. -Im{Z}, OT, lim
                          SOC_VALUE_ARRAY, False, False, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # Re{Z} vs. -Im{Z}, RT
                          SOC_VALUE_ARRAY, True, False, None, None, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # Re{Z} vs. -Im{Z}, OT
                          SOC_VALUE_ARRAY, False, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, RT - comp.
                          SOC_VALUE_ARRAY, True, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, OT - comp.
                          SOC_VALUE_ARRAY, False, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, RT - comp.
                          SOC_VALUE_ARRAY, True, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, OT - comp.
                          SOC_VALUE_ARRAY, False, False, None, None, False),
        # get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_MOHM],  # f vs. |Z|, RT - raw
        #                   SOC_VALUE_ARRAY, True, False, None, None, False),
        # get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_MOHM],  # f vs. |Z|, OT - raw
        #                   SOC_VALUE_ARRAY, False, False, None, None, False),
        # get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_DEG],  # f vs. -arg{Z}, RT - raw
        #                   SOC_VALUE_ARRAY, True, False, None, None, False),
        # get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_DEG],  # f vs. -arg{Z}, OT - raw
        #                   SOC_VALUE_ARRAY, False, False, None, None, False),

        # --- EIS detail (one per SoC) --------------------------------------------------
        # get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, no grp, bg -> big
        #                   [10], True, False, EIS_X_LIM, EIS_Y_LIM, True),
        # get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, grp, bg -> big
        #                   [10], True, True, EIS_X_LIM, EIS_Y_LIM, True),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, no grp, no bg, lim
                          [10], True, False, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, grp, no bg, lim
                          [10], True, True, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, no grp, no bg, no lim
                          [10], True, False, None, None, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, grp, no bg, no lim
                          [10], True, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, RT, no grp - comp.
                          [10], True, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, RT, grp - comp.
                          [10], True, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, RT, no grp - comp.
                          [10], True, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, RT, grp - comp.
                          [10], True, True, None, None, False),

        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, no grp, no bg, lim
                          [10], False, False, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, grp, no bg, lim
                          [10], False, True, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, no grp, no bg, no lim
                          [10], False, False, None, None, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, grp, no bg, no lim
                          [10], False, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, OT, no grp - comp.
                          [10], False, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, OT, grp - comp.
                          [10], False, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, OT, no grp - comp.
                          [10], False, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, OT, grp - comp.
                          [10], False, True, None, None, False),

        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, no grp, no bg, lim
                          [30], True, False, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, grp, no bg, lim
                          [30], True, True, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, no grp, no bg, no lim
                          [30], True, False, None, None, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, grp, no bg, no lim
                          [30], True, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, RT, no grp - comp.
                          [30], True, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, RT, grp - comp.
                          [30], True, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, RT, no grp - comp.
                          [30], True, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, RT, grp - comp.
                          [30], True, True, None, None, False),

        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, no grp, no bg, lim
                          [30], False, False, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, grp, no bg, lim
                          [30], False, True, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, no grp, no bg, no lim
                          [30], False, False, None, None, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, grp, no bg, no lim
                          [30], False, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, OT, no grp - comp.
                          [30], False, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, OT, grp - comp.
                          [30], False, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, OT, no grp - comp.
                          [30], False, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, OT, grp - comp.
                          [30], False, True, None, None, False),

        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, no grp, no bg, lim
                          [50], True, False, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, grp, no bg, lim
                          [50], True, True, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, no grp, no bg, no lim
                          [50], True, False, None, None, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, grp, no bg, no lim
                          [50], True, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, RT, no grp - comp.
                          [50], True, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, RT, grp - comp.
                          [50], True, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, RT, no grp - comp.
                          [50], True, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, RT, grp - comp.
                          [50], True, True, None, None, False),

        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, no grp, no bg, lim
                          [50], False, False, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, grp, no bg, lim
                          [50], False, True, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, no grp, no bg, no lim
                          [50], False, False, None, None, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, grp, no bg, no lim
                          [50], False, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, OT, no grp - comp.
                          [50], False, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, OT, grp - comp.
                          [50], False, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, OT, no grp - comp.
                          [50], False, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, OT, grp - comp.
                          [50], False, True, None, None, False),

        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, no grp, no bg, lim
                          [70], True, False, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, grp, no bg, lim
                          [70], True, True, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, no grp, no bg, no lim
                          [70], True, False, None, None, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, grp, no bg, no lim
                          [70], True, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, RT, no grp - comp.
                          [70], True, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, RT, grp - comp.
                          [70], True, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, RT, no grp - comp.
                          [70], True, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, RT, grp - comp.
                          [70], True, True, None, None, False),

        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, no grp, no bg, lim
                          [70], False, False, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, grp, no bg, lim
                          [70], False, True, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, no grp, no bg, no lim
                          [70], False, False, None, None, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, grp, no bg, no lim
                          [70], False, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, OT, no grp - comp.
                          [70], False, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, OT, grp - comp.
                          [70], False, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, OT, no grp - comp.
                          [70], False, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, OT, grp - comp.
                          [70], False, True, None, None, False),

        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, no grp, no bg, lim
                          [90], True, False, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, grp, no bg, lim
                          [90], True, True, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, no grp, no bg, no lim
                          [90], True, False, None, None, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, RT, grp, no bg, no lim
                          [90], True, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, RT, no grp - comp.
                          [90], True, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, RT, grp - comp.
                          [90], True, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, RT, no grp - comp.
                          [90], True, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, RT, grp - comp.
                          [90], True, True, None, None, False),

        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, no grp, no bg, lim
                          [90], False, False, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, grp, no bg, lim
                          [90], False, True, EIS_X_LIM, EIS_Y_LIM, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, no grp, no bg, no lim
                          [90], False, False, None, None, False),
        get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 10%, OT, grp, no bg, no lim
                          [90], False, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, OT, no grp - comp.
                          [90], False, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_AMP_COMP_MOHM],  # f vs. |Z|, 10%, OT, grp - comp.
                          [90], False, True, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, OT, no grp - comp.
                          [90], False, False, None, None, False),
        get_eis_plot_task(csv_label.EIS_FREQ, [csv_label.Z_PH_COMP_DEG],  # f vs. -arg{Z}, 10%, OT, grp - comp.
                          [90], False, True, None, None, False),

        # --- EIS other variables -------------------------------------------------------
        get_eis_auxiliary_plot_task([csv_label.Z_REF_NOW], False),
        get_eis_auxiliary_plot_task([csv_label.SOH_IMP], False),
        get_eis_auxiliary_plot_task([csv_label.EIS_T_AVG], False),
        get_eis_auxiliary_plot_task([csv_label.EIS_OCV_AVG], False),
        get_eis_auxiliary_plot_task([csv_label.Z_REF_NOW], True),  # pretty large & slow plots?
        get_eis_auxiliary_plot_task([csv_label.SOH_IMP], True),
        get_eis_auxiliary_plot_task([csv_label.EIS_T_AVG], True),
        get_eis_auxiliary_plot_task([csv_label.EIS_OCV_AVG], True),
    ],
    cfg.DataRecordType.CELL_PULSE_FIXED:  [
        # --- PULSE overview ------------------------------------------------------------
        get_pulse_plot_task([csv_label.V_CELL], SOC_VALUE_ARRAY, True),
        get_pulse_plot_task([csv_label.I_CELL], SOC_VALUE_ARRAY, True),
        get_pulse_plot_task([COL_DV], SOC_VALUE_ARRAY, True),
        get_pulse_plot_task([csv_label.V_CELL], SOC_VALUE_ARRAY, False),
        get_pulse_plot_task([csv_label.I_CELL], SOC_VALUE_ARRAY, False),
        get_pulse_plot_task([COL_DV], SOC_VALUE_ARRAY, False),
        # --- PULSE detail (one per SoC) ------------------------------------------------
        get_pulse_plot_task([csv_label.V_CELL], [10], True),
        get_pulse_plot_task([csv_label.I_CELL], [10], True),
        get_pulse_plot_task([COL_DV], [10], True),
        # get_pulse_plot_task([COL_DV, csv_label.I_CELL], [10], True),
        get_pulse_plot_task([csv_label.V_CELL], [10], False),
        get_pulse_plot_task([csv_label.I_CELL], [10], False),
        get_pulse_plot_task([COL_DV], [10], False),
        # get_pulse_plot_task([COL_DV, csv_label.I_CELL], [10], False),

        get_pulse_plot_task([csv_label.V_CELL], [30], True),
        get_pulse_plot_task([csv_label.I_CELL], [30], True),
        get_pulse_plot_task([COL_DV], [30], True),
        # get_pulse_plot_task([COL_DV, csv_label.I_CELL], [30], True),
        get_pulse_plot_task([csv_label.V_CELL], [30], False),
        get_pulse_plot_task([csv_label.I_CELL], [30], False),
        get_pulse_plot_task([COL_DV], [30], False),
        # get_pulse_plot_task([COL_DV, csv_label.I_CELL], [30], False),

        get_pulse_plot_task([csv_label.V_CELL], [50], True),
        get_pulse_plot_task([csv_label.I_CELL], [50], True),
        get_pulse_plot_task([COL_DV], [50], True),
        # get_pulse_plot_task([COL_DV, csv_label.I_CELL], [50], True),
        get_pulse_plot_task([csv_label.V_CELL], [50], False),
        get_pulse_plot_task([csv_label.I_CELL], [50], False),
        get_pulse_plot_task([COL_DV], [50], False),
        # get_pulse_plot_task([COL_DV, csv_label.I_CELL], [50], False),

        get_pulse_plot_task([csv_label.V_CELL], [70], True),
        get_pulse_plot_task([csv_label.I_CELL], [70], True),
        get_pulse_plot_task([COL_DV], [70], True),
        # get_pulse_plot_task([COL_DV, csv_label.I_CELL], [70], True),
        get_pulse_plot_task([csv_label.V_CELL], [70], False),
        get_pulse_plot_task([csv_label.I_CELL], [70], False),
        get_pulse_plot_task([COL_DV], [70], False),
        # get_pulse_plot_task([COL_DV, csv_label.I_CELL], [70], False),

        get_pulse_plot_task([csv_label.V_CELL], [90], True),
        get_pulse_plot_task([csv_label.I_CELL], [90], True),
        get_pulse_plot_task([COL_DV], [90], True),
        # get_pulse_plot_task([COL_DV, csv_label.I_CELL], [90], True),
        get_pulse_plot_task([csv_label.V_CELL], [90], False),
        get_pulse_plot_task([csv_label.I_CELL], [90], False),
        get_pulse_plot_task([COL_DV], [90], False),
        # get_pulse_plot_task([COL_DV, csv_label.I_CELL], [90], False),

        # --- PULSE other variables -----------------------------------------------------
        get_pulse_auxiliary_plot_task([csv_label.PULSE_R_10_MS_MOHM], False),
        get_pulse_auxiliary_plot_task([csv_label.PULSE_R_1_S_MOHM], False),
        get_pulse_auxiliary_plot_task([csv_label.PULSE_T_AVG], False),
        # get_pulse_auxiliary_plot_task([csv_label.PULSE_R_10_MS_MOHM], True),  # pretty large & slow plots
        # get_pulse_auxiliary_plot_task([csv_label.PULSE_R_1_S_MOHM], True),  # ...
        # get_pulse_auxiliary_plot_task([csv_label.PULSE_T_AVG], True),  # ...
    ],
}

# # ToDo: some of these plots are in the paper:
# PLOT_TASKS_LIST = {
#     cfg.DataRecordType.CELL_EOC_FIXED: [
#         # --- EOC individual variables --------------------------------------------------
#         # CAP_CHARGED_EST, grouped by T, absolute capacity/energy, ... [cyc_cond, cyc_chg, show_bg]
#         get_eoc_plot_task(csv_label.TIMESTAMP, [csv_label.CAP_CHARGED_EST],  # CU, dischg, yes
#                           None, True, [2], [0], True, False, minimal_x_ax_labels=True, minimal_y_ax_labels=True),
#         # ... vs EFC
#         get_eoc_plot_task(COL_EFC, [csv_label.CAP_CHARGED_EST],  # CU, dischg, yes
#                           None, True, [2], [0], True, False, minimal_x_ax_labels=True, minimal_y_ax_labels=True),
#     ],
#     cfg.DataRecordType.CELL_EIS_FIXED: [
#         # --- EIS detail (one per SoC) --------------------------------------------------
#         get_eis_plot_task(csv_label.Z_RE_COMP_MOHM, [csv_label.Z_IM_COMP_MOHM],  # 50%, RT, no grp, no bg, no lim
#                           [50], True, False, None, None, False, minimal_y_ax_labels=True),
#
#         # --- EIS other variables -------------------------------------------------------
#         get_eis_auxiliary_plot_task([csv_label.Z_REF_NOW], True, group_temperature=False, x_var=csv_label.TIMESTAMP,
#                                     minimal_y_ax_labels=True),
#         get_eis_auxiliary_plot_task([csv_label.Z_REF_NOW], True, group_temperature=False, x_var=COL_EFC,
#                                     minimal_y_ax_labels=True),
#     ],
#     cfg.DataRecordType.CELL_PULSE_FIXED: [
#         # --- PULSE overview ------------------------------------------------------------
#         get_pulse_plot_task([csv_label.V_CELL], [50], True, minimal_y_ax_labels=True),
#     ],
# }

# ToDo: PLOT_TASKS_LIST definition using manually defined structures:
# PLOT_TASKS_LIST = {
#     cfg.DataRecordType.CELL_EOC_FIXED: [
#         # {
#         #     PTL_X_VAR: COL_EFC,
#         #     PTL_Y_VARS: [csv_label.CAP_CHARGED_EST],
#         # },
#         {   # minimal plot configuration:
#             PTL_X_VAR: csv_label.TIMESTAMP,  # timestamp in seconds by default -> use 'PTL_X_DIV: TIME_DIV,' for days
#             PTL_Y_VARS: [csv_label.ENERGY_EFFICIENCY],
#         },
#         {
#             PTL_X_VAR: csv_label.TIMESTAMP,  # may also use 'COL_EFC' -> comment out 'PTL_X_DIV: TIME_DIV,'
#             PTL_Y_VARS: [csv_label.ENERGY_EFFICIENCY, csv_label.COULOMB_EFFICIENCY],
#             PTL_COLORS: [COLOR_ENERGY_EFFICIENCY, COLOR_COULOMB_EFFICIENCY],
#             PTL_X_DIV: TIME_DIV,
#         },
#         {
#             PTL_X_VAR: csv_label.TIMESTAMP,  # COL_EFC,
#             PTL_Y_VARS: [csv_label.CAP_CHARGED_EST],
#             PTL_X_DIV: TIME_DIV,
#             PTL_Y_DIV: 100.0 * cfg.CELL_CAPACITY_NOMINAL,  # plot as relative capacity
#             PTL_HOVER_TEMPLATE_FUNCTION: get_hover_minimal,
#             PTL_FILT_COLUMNS: [csv_label.EOC_CYC_CONDITION, csv_label.EOC_CYC_CHARGED],
#             PTL_FILT_VALUES: [[cfg.cyc_cond.CHECKUP_RT], [0]],  # check-up -> discharge
#             PTL_PLOT_ALL_IN_BACKGROUND: True,  # use with caution, this may generale huge figures -> filter!
#             PTL_GROUP_TEMPERATURES: True,
#         },
#     ],
#     cfg.DataRecordType.CELL_EIS_FIXED: [
#         # {   # minimal (useful) plot configuration for EIS:
#         #     PTL_X_VAR: csv_label.Z_RE_COMP_MOHM,
#         #     PTL_Y_VARS: [csv_label.Z_IM_COMP_MOHM],
#         #     PTL_GROUP_BY: csv_label.TIMESTAMP,
#         # },
#         {  # maximal plot configuration:
#             PTL_X_VAR: csv_label.Z_RE_COMP_MOHM,  # COL_EFC,
#             PTL_Y_VARS: [csv_label.Z_IM_COMP_MOHM],
#             PTL_GROUP_BY: csv_label.TIMESTAMP,
#             PTL_GROUP_BY_AGING_COL: csv_label.TIMESTAMP,  # you may also use COL_EFC or AGE_VAR_BY_AGE_TYPE here
#             PTL_X_LIMS: [0, 120],
#             PTL_Y_LIMS: [-35, 25],
#             PTL_FILT_COLUMNS: [csv_label.SOC_NOM, csv_label.IS_ROOM_TEMP],
#             PTL_FILT_VALUES: [[50], [0]],
#             PTL_OPACITY: 0.2,
#             PTL_X_AX_TITLE: "Re{Z}",
#             PTL_Y_AX_TITLE: "-Im{Z}",
#             PTL_X_UNIT: "mΩ",
#             PTL_Y_UNIT: "mΩ",
#             PTL_TITLE: 'Electrochemical Impedance Spectroscopy (EIS)',
#             PTL_HOVER_DATA_COL: csv_label.EIS_FREQ,
#             PTL_HOVER_TEMPLATE_FUNCTION: get_hover_eis,
#         },
#         {  # maximal plot configuration:
#             PTL_X_VAR: csv_label.Z_RE_COMP_MOHM,  # COL_EFC,
#             PTL_Y_VARS: [csv_label.Z_IM_COMP_MOHM],
#             PTL_GROUP_BY: csv_label.TIMESTAMP,
#             PTL_GROUP_BY_AGING_COL: AGE_VAR_BY_AGE_TYPE,  # you may also use COL_EFC or csv_label.TIMESTAMP here
#             PTL_X_LIMS: [0, 120],
#             PTL_Y_LIMS: [-35, 25],
#             PTL_FILT_COLUMNS: [csv_label.SOC_NOM, csv_label.IS_ROOM_TEMP],
#             PTL_FILT_VALUES: [[50], [0]],
#             PTL_COLORS: COLOR_EIS,
#             PTL_OPACITY: 0.2,
#             PTL_X_AX_TITLE: "Re{Z}",
#             PTL_Y_AX_TITLE: "-Im{Z}",
#             PTL_X_UNIT: "mΩ",
#             PTL_Y_UNIT: "mΩ",
#             PTL_TITLE: 'Electrochemical Impedance Spectroscopy (EIS)',
#             PTL_HOVER_DATA_COL: csv_label.EIS_FREQ,
#             PTL_HOVER_TEMPLATE_FUNCTION: get_hover_eis,
#         },
#         {  # maximal plot configuration:
#             PTL_X_VAR: csv_label.Z_RE_COMP_MOHM,  # COL_EFC,
#             PTL_Y_VARS: [csv_label.Z_IM_COMP_MOHM],
#             PTL_GROUP_BY: csv_label.TIMESTAMP,
#             PTL_X_LIMS: [0, 120],
#             PTL_Y_LIMS: [-35, 25],
#             PTL_FILT_COLUMNS: [csv_label.SOC_NOM, csv_label.IS_ROOM_TEMP],
#             PTL_FILT_VALUES: [SOC_VALUE_ARRAY, [0]],
#             PTL_FILT_COLORS: COLOR_SOCS_ARR,  # for first array in PTL_FILT_COLUMNS / PTL_FILT_VALUES
#             PTL_COLORS: COLOR_EIS,
#             PTL_OPACITY: 0.2,
#             PTL_X_AX_TITLE: "Re{Z}",
#             PTL_Y_AX_TITLE: "-Im{Z}",
#             PTL_X_UNIT: "mΩ",
#             PTL_Y_UNIT: "mΩ",
#             PTL_TITLE: 'Electrochemical Impedance Spectroscopy (EIS)',
#             PTL_HOVER_DATA_COL: csv_label.EIS_FREQ,
#             PTL_HOVER_TEMPLATE_FUNCTION: get_hover_eis,
#         },
#     ],
#     cfg.DataRecordType.CELL_PULSE_FIXED:  [
#         {
#             PTL_X_VAR: COL_T_REL,
#             PTL_Y_VARS: [csv_label.V_CELL],
#             PTL_GROUP_BY: csv_label.SD_BLOCK_ID,
#         },
#     ],
# }

# --- plot formatting --------------------------------------------------------------------------------------------------
if COMPACT_AX_LABELS:
    SUBPLOT_H_SPACING_REL = 0.15
    if LARGE_FONT_SIZE:
        SUBPLOT_V_SPACING_REL = 0.3
    else:
        SUBPLOT_V_SPACING_REL = 0.25
else:
    SUBPLOT_H_SPACING_REL = 0.25
    SUBPLOT_V_SPACING_REL = 0.3
SUBPLOT_LR_MARGIN = 10
SUBPLOT_TOP_MARGIN = 120  # 60
SUBPLOT_BOT_MARGIN = 0
SUBPLOT_PADDING = 0

PLOT_WIDTH_PER_COLUMN = 400  # in px - PLOT_WIDTH = PLOT_WIDTH_PER_COLUMN * SUBPLOT_COLS -> dynamically calculated
PLOT_HEIGHT_PER_ROW = 300  # in px - PLOT_HEIGHT = PLOT_HEIGHT_PER_ROW * SUBPLOT_ROWS -> dynamically calculated
PLOT_HEIGHT_PER_ROW_SINGLE = 400  # in px - PLOT_HEIGHT = PLOT_HEIGHT_PER_ROW_SINGLE if only one row

PLOT_TITLE_Y_POS_REL = 30.0  # 5.0
AGE_TYPE_TITLES = {cfg.age_type.CALENDAR: "calendar aging",
                   cfg.age_type.CYCLIC: "cyclic aging",
                   cfg.age_type.PROFILE: "profile aging"
                   }

TRACE_COLOR_DEFAULT = COLOR_BLACK
TRACE_LINE_WIDTH = 1.5
TRACE_OPACITY_DEFAULT = 0.8
SHOW_MARKER_BY_DEFAULT = False
# USE_MARKER = False  # if True, use markers (circles by default) for data points (for small a number of data points)
# FORCE_MARKER = False  # for a large number of data points, plotly decides to leave away markers, this forces their use
MARKER_DEFAULT = dict(size=5, opacity=0.8, line=None, symbol='circle')

DEFAULT_LINE_STYLE = "solid"  # "solid", "dot", "dash", "longdash", "dashdot", "longdashdot", ... see:
# https://plotly.com/python-api-reference/generated/plotly.graph_objects.scatter.html#plotly.graph_objects.scatter.Line.dash

COLOR_BACKGROUND = COLOR_LIGHT_GRAY
TRACE_BG_LINE_WIDTH = 1
OPACITY_BACKGROUND = 0.25

FIGURE_TEMPLATE = "custom_theme"  # "custom_theme" "plotly_white" "plotly" "none"

# create custom theme from default plotly theme
BG_COLOR = '#fff'
MAJOR_GRID_COLOR = '#bbb'
MINOR_GRID_COLOR = '#e8e8e8'  # '#ddd'
pio.templates["custom_theme"] = pio.templates["plotly"]
pio.templates["custom_theme"]['layout']['paper_bgcolor'] = BG_COLOR
pio.templates["custom_theme"]['layout']['plot_bgcolor'] = BG_COLOR
pio.templates["custom_theme"]['layout']['hoverlabel']['namelength'] = -1
pio.templates['custom_theme']['layout']['xaxis']['gridcolor'] = MAJOR_GRID_COLOR
pio.templates['custom_theme']['layout']['yaxis']['gridcolor'] = MAJOR_GRID_COLOR
pio.templates['custom_theme']['layout']['yaxis']['zerolinecolor'] = MAJOR_GRID_COLOR
pio.templates['custom_theme']['layout']['xaxis']['linecolor'] = MAJOR_GRID_COLOR
pio.templates['custom_theme']['layout']['yaxis']['linecolor'] = MAJOR_GRID_COLOR
pio.templates['custom_theme']['layout']['yaxis']['zerolinecolor'] = MAJOR_GRID_COLOR
if LARGE_FONT_SIZE:
    pio.templates['custom_theme']['layout']['xaxis']['title']['standoff'] = 15
    pio.templates['custom_theme']['layout']['yaxis']['title']['standoff'] = 15
    TITLE_FONT_SIZE = 21  # 20
    SUBPLOT_TITLE_FONT_SIZE = 19  # 18
    AXIS_FONT_SIZE = 19  # 18
    AXIS_TICK_FONT_SIZE = 19  # 18
    pio.templates['custom_theme']['layout']['title']['font']['size'] = TITLE_FONT_SIZE
    pio.templates['custom_theme']['layout']['xaxis']['title']['font']['size'] = AXIS_FONT_SIZE
    pio.templates['custom_theme']['layout']['yaxis']['title']['font']['size'] = AXIS_FONT_SIZE
    pio.templates['custom_theme']['layout']['xaxis']['tickfont']['size'] = AXIS_TICK_FONT_SIZE
    pio.templates['custom_theme']['layout']['yaxis']['tickfont']['size'] = AXIS_TICK_FONT_SIZE
    pio.templates['custom_theme']['layout']['annotationdefaults']['font']['size'] = SUBPLOT_TITLE_FONT_SIZE
else:
    pio.templates['custom_theme']['layout']['xaxis']['title']['standoff'] = 10
    pio.templates['custom_theme']['layout']['yaxis']['title']['standoff'] = 10


# --- classes ----------------------------------------------------------------------------------------------------------
# exceptions
class PlotException(Exception):
    pass


# --- other constants --------------------------------------------------------------------------------------------------
# ToDo: if you have limited memory or CPU, consider using less cores:
# NUMBER_OF_PROCESSORS_TO_USE = 1  # only use one processor for plotting
# NUMBER_OF_PROCESSORS_TO_USE = max(multiprocessing.cpu_count() - 1, 1)  # leave one free
# NUMBER_OF_PROCESSORS_TO_USE = max(math.ceil(multiprocessing.cpu_count() / 2), 1)  # use half of the processors
# NUMBER_OF_PROCESSORS_TO_USE = max(multiprocessing.cpu_count() - 4, 1)  # leave four free
NUMBER_OF_PROCESSORS_TO_USE = max(math.ceil(multiprocessing.cpu_count() / 4), 1)  # use 1/4 of the processors


file_queue = multiprocessing.Queue()
plot_task_queue = multiprocessing.Queue()

pio.orca.config.executable = cfg.ORCA_PATH
# pio.kaleido.scope.mathjax = None
# pio.kaleido.scope.chromium_args += ("--single-process",)
pio.orca.config.timeout = 600  # increase timeout from 30 seconds to 10 minutes


# --- global variables -------------------------------------------------------------------------------------------------
version = 1  # if there are files in the target directory, the script finds the maximum file version and sets this to +1


def run():
    start_timestamp = datetime.now()
    logging.log.info(os.path.basename(__file__))
    report_manager = multiprocessing.Manager()
    report_queue = report_manager.Queue()

    report_queue = plotter_main(report_queue)

    logging.log.info("\n\n========== All tasks ended ==========\n")
    while True:
        if (report_queue is None) or report_queue.empty():
            break  # no more reports
        try:
            task_report = report_queue.get_nowait()
        except multiprocessing.queues.Empty:
            break  # no more reports
        if task_report is None:
            break  # no more reports

        report_msg = task_report["msg"]
        report_level = task_report["level"]
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


def plotter_main(report_queue):
    global version
    # find files in target directory to determine next version number
    version = get_next_plot_version()

    # === Load all used csv files to RAM ===============================================================================
    max_param_id = 0
    max_param_nr = 0
    data_record_types_load = list(PLOT_TASKS_LIST.keys())
    data_record_types_plot = data_record_types_load.copy()
    if cfg.DataRecordType.CELL_EOC_FIXED not in PLOT_TASKS_LIST:
        data_record_types_load.append(cfg.DataRecordType.CELL_EOC_FIXED)  # always load EOCv2 (for EFC calculation)
    for drt in data_record_types_load:
        # clean PLOT_TASKS_LIST
        t_list = PLOT_TASKS_LIST.get(drt)
        if t_list is None:
            if drt in PLOT_TASKS_LIST:
                del PLOT_TASKS_LIST[drt]
                continue
        elif len(t_list) == 0:
            if drt in PLOT_TASKS_LIST:
                del PLOT_TASKS_LIST[drt]
                continue
        _, items, _, message = ht.find_files_of_type(INPUT_DIR, drt)
        logging.log.info(message)
        num_files = len(items)
        if num_files == 0:
            logging.log.warning("Warning: Did not find any %s files -> skip" % drt.name)
        else:
            for i in items:  # append all items to the file queue (including the data_record_type)
                p_id = i[csv_label.PARAMETER_ID]
                p_nr = i[csv_label.PARAMETER_NR]
                if p_id > max_param_id:
                    max_param_id = p_id
                if p_nr > max_param_nr:
                    max_param_nr = p_nr
                i.update({"data_record_type": drt})
                file_queue.put(i)
    if len(PLOT_TASKS_LIST) == 0:
        logging.log.error("PLOT_TASKS_LIST empty. Did you (properly) define the PLOT_TASKS_LIST?")
        return report_queue

    df_dict, param_df = read_data_records(file_queue, max_param_id, max_param_nr)

    if len(df_dict) == 0:
        logging.log.error("df_dict empty. Are all files needed for PLOT_TASKS_LIST in the (correct) INPUT_DIR?")
        return report_queue
    if len(param_df) == 0:
        logging.log.error("param_df empty. Are all cell config files in the (correct) INPUT_DIR?")
        return report_queue

    # === Create new columns (if necessary) ============================================================================
    logging.log.debug("Adding custom columns")
    df_dict = add_custom_record_columns(df_dict, max_param_id, max_param_nr)

    # === Generate plot queue ==========================================================================================
    for drt in data_record_types_plot:
        t_list = PLOT_TASKS_LIST.get(drt)
        for plot_task in t_list:
            plot_item = {"data_record_type": drt, "plot_task": plot_task}
            plot_task_queue.put(plot_item)

    total_queue_size = plot_task_queue.qsize()

    # Create processes
    num_processors = min(math.ceil(NUMBER_OF_PROCESSORS_TO_USE), total_queue_size)
    processes = []
    logging.log.info("Starting processes to plot...")
    for processor_number in range(0, num_processors):
        logging.log.debug("  Starting process %u" % processor_number)
        processes.append(multiprocessing.Process(target=plot_thread,
                                                 args=(processor_number, plot_task_queue, report_queue,
                                                       total_queue_size, df_dict, param_df, version)))
    for processor_number in range(0, num_processors):
        processes[processor_number].start()
    for processor_number in range(0, num_processors):
        processes[processor_number].join()
        logging.log.debug("Joined process %u" % processor_number)

    return report_queue


def plot_thread(processor_number, task_queue, rep_queue, total_queue_size, df_dict,
                param_df: pd.DataFrame, file_version):
    time.sleep(2)  # sometimes the thread is called before task_queue is ready? wait a few seconds here.
    retry_counter = 0
    remaining_size = 1
    while True:
        try:
            remaining_size = task_queue.qsize()
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
        retry_counter = 0

        num_warnings = 0
        num_errors = 0
        critical_error = False
        drt = queue_entry["data_record_type"]
        plot_task = queue_entry["plot_task"]
        instance_text = "???"

        # noinspection PyBroadException
        try:
            x_var = plot_task[PTL_X_VAR]
            y_vars = plot_task[PTL_Y_VARS]
            if (x_var is None) or (y_vars is None):
                logging.log.error("Thread %u - empty x or y vars for %s please check PLOT_TASKS_LIST. plot_task:\n%s"
                                  % (processor_number, drt.name, plot_task))
                raise PlotException
            if not hasattr(y_vars, "__len__"):
                y_vars = [y_vars]  # user didn't enter y_vars as array? -> fix

            instance_text = "%s: %s vs. %s" % (drt.name, x_var, y_vars)

            progress = 0.0
            if total_queue_size > 0:
                progress = (1.0 - remaining_size / total_queue_size) * 100.0
            logging.log.debug("(progress: %.1f %%) Plotting next %s"
                              % (progress, instance_text))

            # get optional variables
            (filt_cols, filt_vals, filt_colors, filt_opacity, filt_linestyle, group_by, group_by_aging_col,
             group_temperatures, plot_colors, opacity, show_marker, x_ax_title, y_ax_title, x_unit, y_unit, x_div,
             y_div, x_lim, y_lim, plot_title, hover_data_col, hover_template_fun, plot_all_in_background,
             custom_filename, minimal_x_ax_labels, minimal_y_ax_labels) = get_optional_plot_vars(plot_task)

            if minimal_x_ax_labels is not True:  # check if minimal_x_ax_labels is None or has invalid type or is False
                minimal_x_ax_labels = False
                shared_x_axes = None  # set to None, so plotly uses the default (should be False?)
            else:
                shared_x_axes = True
            if minimal_y_ax_labels is not True:  # check if minimal_y_ax_labels is None or has invalid type or is False
                minimal_y_ax_labels = False
                shared_y_axes = None  # set to None, so plotly uses the default (should be False?)
            else:
                shared_y_axes = True

            age_types = param_df[csv_label.AGE_TYPE].drop_duplicates().values
            for age_type in age_types:
                # determine number of columns and rows
                param_df_page_roi = param_df[param_df[csv_label.AGE_TYPE] == age_type]

                if age_type == cfg.age_type.CALENDAR:
                    # columns/X: rising SoC
                    # rows/Y: temperature (if not grouped)
                    col_var = csv_label.AGE_SOC
                    row_var = None

                    # if group_temperatures:
                    #     row_var = None
                    # else:
                    #     row_var = csv_label.AGE_TEMPERATURE

                    # soc_vals = sorted(param_df_page_roi[csv_label.AGE_SOC].drop_duplicates().values)
                    # temperature_vals = sorted(param_df_page_roi[csv_label.AGE_TEMPERATURE].drop_duplicates().values)
                    # n_cols = len(soc_vals)
                    # n_rows = 1
                    # if not group_temperatures:
                    #     n_rows = n_rows * len(temperature_vals)
                elif age_type == cfg.age_type.CYCLIC:
                    # columns/X: rising C-rate combinations
                    # rows/Y: shrinking SoC-ranges
                    # repeated rows/Y: temperature (if not grouped)
                    col_var = csv_label.AGE_C_RATES
                    row_var = csv_label.AGE_SOC_RANGE

                    # c_rate_vals = param_df_page_roi[csv_label.AGE_C_RATES].drop_duplicates().values
                    # soc_range_vals = param_df_page_roi[csv_label.AGE_SOC_RANGE].drop_duplicates().values
                    # temperature_vals = sorted(param_df_page_roi[csv_label.AGE_TEMPERATURE].drop_duplicates().values)
                    # n_cols = len(c_rate_vals)
                    # n_rows = len(soc_range_vals)
                    # if not group_temperatures:
                    #     n_rows = n_rows * len(temperature_vals)
                elif age_type == cfg.age_type.PROFILE:
                    # columns/X: rising profile number
                    # rows/Y: temperature (if not grouped)
                    col_var = csv_label.AGE_PROFILE
                    row_var = None
                    # if group_temperatures:
                    #     row_var = None
                    # else:
                    #     row_var = csv_label.AGE_TEMPERATURE

                    # profile_vals = sorted(param_df_page_roi[csv_label.AGE_PROFILE].drop_duplicates().values)
                    # temperature_vals = sorted(param_df_page_roi[csv_label.AGE_TEMPERATURE].drop_duplicates().values)
                    # n_cols = len(profile_vals)
                    # n_rows = 1
                    # if not grou<p_temperatures:
                    #     n_rows = n_rows * len(>temperature_vals)
                else:
                    logging.log.error("Thread %u - unknown age_type %s in param_df" % (processor_number, age_type))
                    raise PlotException

                col_vals = []
                row_vals = []
                n_cols = 1
                n_rows = 1
                n_sub_rows = 1
                if col_var is not None:
                    col_vals = param_df_page_roi[col_var].drop_duplicates().values
                    n_cols = n_cols * len(col_vals)
                if row_var is not None:
                    row_vals = param_df_page_roi[row_var].drop_duplicates().values
                    n_sub_rows = len(row_vals)
                    n_rows = n_rows * n_sub_rows
                row_rep_var = csv_label.AGE_TEMPERATURE
                row_rep_vals = sorted(param_df_page_roi[row_rep_var].drop_duplicates().values)
                n_row_reps = len(row_rep_vals)
                # if (not group_temperatures) and (row_var != csv_label.AGE_TEMPERATURE):
                if not group_temperatures:
                    n_rows = n_rows * n_row_reps

                # generate empty figure
                if minimal_x_ax_labels:
                    subplot_v_spacing = ((SUBPLOT_V_SPACING_REL / 2.0) / n_rows)
                else:
                    subplot_v_spacing = (SUBPLOT_V_SPACING_REL / n_rows)
                if minimal_y_ax_labels:
                    subplot_h_spacing = ((SUBPLOT_H_SPACING_REL / 2.0) / n_cols)
                else:
                    subplot_h_spacing = (SUBPLOT_H_SPACING_REL / n_cols)
                plot_width = PLOT_WIDTH_PER_COLUMN * n_cols
                if n_rows > 1:
                    plot_height = PLOT_HEIGHT_PER_ROW * n_rows
                else:
                    plot_height = PLOT_HEIGHT_PER_ROW_SINGLE
                plot_title_y_pos = 1.0 - PLOT_TITLE_Y_POS_REL / plot_height
                subplot_titles = get_subplot_titles(n_cols, n_rows, n_sub_rows, n_row_reps, col_var, col_vals,
                                                    row_var, row_vals, row_rep_var, row_rep_vals, group_temperatures)
                fig = make_subplots(cols=n_cols, rows=n_rows, subplot_titles=subplot_titles,
                                    horizontal_spacing=subplot_h_spacing, vertical_spacing=subplot_v_spacing,
                                    shared_xaxes=shared_x_axes, shared_yaxes=shared_y_axes)

                age_min = None
                age_max = None
                age_col = None
                if group_by is not None:
                    age_col = group_by_aging_col
                    if type(age_col) is dict:
                        if age_type in age_col:
                            age_col = age_col.get(age_type)
                        else:
                            age_col = None  # current age_type not in group_by_aging_col -> don't use
                    if age_col is not None:
                        # walk through all dfs to find the maximum of group_by_aging_col of this aging type
                        param_df_age_type = param_df[param_df[csv_label.AGE_TYPE] == age_type]
                        for _, row in param_df_age_type.iterrows():
                            pid = row[csv_label.PARAMETER_ID]
                            pnr = row[csv_label.PARAMETER_NR]
                            df_cell: pd.DataFrame = df_dict[drt][pid - 1][pnr - 1]
                            if (df_cell is not None) and (age_col in df_cell.columns):
                                cell_min = df_cell[age_col].min()
                                cell_max = df_cell[age_col].max()
                                if (age_min is None) or (cell_min < age_min):
                                    age_min = cell_min
                                if (age_max is None) or (cell_max > age_max):
                                    age_max = cell_max

                dummy_x = None
                dummy_y = None
                dummy_col = None
                dummy_row = None
                for i_bg in range(2):
                    if (i_bg == 0) and not plot_all_in_background:
                        continue
                    # walk through sub-figures
                    for i_col in range(n_cols):
                        if len(col_vals) > 0:
                            pdf_col = param_df_page_roi[param_df_page_roi[col_var] == col_vals[i_col]]
                        else:
                            pdf_col = param_df_page_roi
                        for i_row_rep in range(n_row_reps):
                            if len(row_rep_vals) > 0:
                                pdf_rr = pdf_col[pdf_col[row_rep_var] == row_rep_vals[i_row_rep]]
                            else:
                                pdf_rr = pdf_col

                            colors = None
                            if i_bg > 0:  # only relevant in active plot:
                                if group_temperatures:
                                    temperature = row_rep_vals[i_row_rep]
                                    if temperature in TEMPERATURE_COLORS:
                                        colors = TEMPERATURE_COLORS.get(temperature)
                                if colors is None:
                                    colors = plot_colors
                                if (not hasattr(colors, "__len__")) or (isinstance(colors, str)):
                                    # noinspection PyTypeChecker
                                    colors = [colors for _ in range(len(y_vars))]  # repeat for each y_var

                            for i_sub_row in range(n_sub_rows):
                                if len(row_vals) > 0:
                                    pdf_row = pdf_rr[pdf_rr[row_var] == row_vals[i_sub_row]]
                                else:
                                    pdf_row = pdf_rr
                                i_row = i_sub_row
                                if not group_temperatures:
                                    i_row = i_row + i_row_rep * n_sub_rows
                                for i_cell in range(pdf_row.shape[0]):
                                    pdf_cell = pdf_row.iloc[i_cell]
                                    pid = pdf_cell[csv_label.PARAMETER_ID]
                                    pnr = pdf_cell[csv_label.PARAMETER_NR]
                                    cell_str = ""
                                    if i_bg > 0:  # only relevant in active plot:
                                        sid = pdf_cell[csv_label.SLAVE_ID]
                                        cid = pdf_cell[csv_label.CELL_ID]
                                        cell_str = "P%03u-%u (S%02u:C%02u)" % (pid, pnr, sid, cid)
                                        if group_temperatures:
                                            t_age = pdf_cell[csv_label.AGE_TEMPERATURE]
                                            cell_str = ("Cell aged at %u°C<br>" % t_age) + cell_str
                                    df_cell: pd.DataFrame = df_dict[drt][pid - 1][pnr - 1]

                                    # noinspection PyTypeChecker
                                    for i_filt in range(len(filt_cols)):
                                        filt_col = filt_cols[i_filt]
                                        if filt_col is None:
                                            continue  # skip
                                        filt_val = filt_vals[i_filt]
                                        # df_cell = df_cell[df_cell[filt_col] == filt_val]
                                        df_cell = df_cell[df_cell[filt_col].isin(filt_val)]

                                    group_by_list = []
                                    n_groups = 1
                                    group_by_filter = pd.DataFrame()
                                    if group_by is None:
                                        # check if we need to group by filter
                                        if len(filt_cols) > 0:
                                            used_filter_cols = [c for c in filt_cols if c is not None]
                                            group_by_filter = df_cell[used_filter_cols].drop_duplicates()
                                            n_groups = group_by_filter.shape[0]
                                            # for i in range(len(filt_cols)):
                                            #     n_filter_values = len(filt_vals[i])
                                            #     n_groups = n_groups * n_filter_values
                                            # if n_groups > 1:
                                            #     group_by_filter = True
                                    else:  # group by column -> typical for EIS, PULSE data
                                        group_by_list = df_cell[group_by].drop_duplicates().values
                                        n_groups = len(group_by_list)

                                    for i_group in range(n_groups):
                                        age_text = ""
                                        group_text = ""
                                        group_color = None
                                        if group_by is None:
                                            if group_by_filter.shape[0] == 0:
                                                df = df_cell
                                            else:
                                                df = df_cell
                                                filt_val_df = group_by_filter.iloc[i_group]
                                                used_filter_cols = [c for c in filt_cols if c is not None]
                                                for i_used_filt_col in range(len(used_filter_cols)):
                                                    filt_col = used_filter_cols[i_used_filt_col]
                                                    df = df[df[filt_col] == filt_val_df[filt_col]]
                                        else:
                                            df = df_cell[df_cell[group_by] == group_by_list[i_group]]

                                            if i_bg > 0:  # only relevant in active plot:
                                                val = df[group_by].iloc[0]
                                                if (age_min is not None) and (age_max is not None):
                                                    # find according aging color
                                                    age_val = df[age_col].iloc[0]
                                                    if age_col == csv_label.TIMESTAMP:
                                                        print_val = age_val / TIME_DIV
                                                        age_text = "Time: %.3f %s<br>" % (print_val, UNIT_TIME)
                                                    elif age_col == COL_EFC:
                                                        age_text = "EFC: %.3f cycles<br>" % age_val
                                                    else:
                                                        age_text = "%s: %s<br>" % (age_val, str(age_val))

                                                    age = (age_val - age_min) / (age_max - age_min)
                                                    if age < 0.0:
                                                        age = 0.0
                                                    elif age > 1.0:
                                                        age = 1.0
                                                    group_color = clr.get_aged_color(age, 1.0)

                                                # group_text = "group:   %s: %s<br>" % (group_by, str(val))
                                                if group_by == csv_label.TIMESTAMP:
                                                    val = val / TIME_DIV
                                                    group_text = "Time: %.3f %s<br>" % (val, UNIT_TIME)
                                                else:
                                                    group_text = "%s: %s<br>" % (group_by, str(val))

                                        if df.shape[0] == 0:
                                            continue  # empty data -> skip

                                        # get x-data
                                        x_data = df[x_var].copy()

                                        # modify x-data
                                        if x_div is not None:
                                            x_data = x_data / x_div

                                        # get group and filter text for hovertemplate
                                        filter_text = ""

                                        if i_bg > 0:  # only relevant in active plot:
                                            if len(filt_cols) > 0:
                                                # filter_text = "filter:   "
                                                filter_text_items = []
                                                for i_filt in range(len(filt_cols)):
                                                    filt_col = filt_cols[i_filt]
                                                    if filt_col is None:
                                                        continue  # skip
                                                    v = df[filt_col].iloc[0]
                                                    # noinspection PyTypeChecker
                                                    if all(df[filt_col] == v):
                                                        if filt_col == csv_label.EOC_CYC_CONDITION:
                                                            v = "%u (%s)" % (v, cfg.cyc_cond(v).name)
                                                        elif filt_col == csv_label.EOC_CYC_CHARGED:
                                                            chg_text = "???"
                                                            if v == 0:
                                                                chg_text = "dischg."
                                                            elif v == 1:
                                                                chg_text = "chg."
                                                            v = "%u (%s)" % (v, chg_text)
                                                        filter_text_items.append("%s: %s" % (filt_col, str(v)))
                                                    else:
                                                        v = df[filt_col].mean()
                                                        filter_text_items.append("%s: %s (mean)" % (filt_col, str(v)))
                                                filter_text = filter_text + ", ".join(filter_text_items) + "<br>"

                                        # for each y variable
                                        # noinspection PyTypeChecker
                                        for i_y_var in range(len(y_vars)):
                                            # get y-data
                                            y_var = y_vars[i_y_var]
                                            y_data = df[y_var].copy()

                                            # modify y-data
                                            if y_div is not None:
                                                y_data = y_data / y_div

                                            opacity_use = opacity
                                            line_style_use = DEFAULT_LINE_STYLE
                                            hover_append_str = ""
                                            hover_data = None
                                            if i_bg == 0:
                                                color_use = COLOR_BACKGROUND
                                            else:  # only relevant in active plot:
                                                hover_append_str = (age_text + filter_text + group_text
                                                                    + cell_str + "<br>")
                                                color_use = colors[i_y_var]
                                                if group_color is not None:
                                                    color_use = group_color
                                                elif (filt_colors is not None) and (len(filt_cols) > I_FILT_COLOR):
                                                    # first filter column is for color:
                                                    filt_col = filt_cols[I_FILT_COLOR]
                                                    if filt_col is not None:
                                                        v = df[filt_col].iloc[0]
                                                        if v in filt_vals[I_FILT_COLOR]:
                                                            i_color = filt_vals[I_FILT_COLOR].index(v)
                                                            color_use = filt_colors[i_color]

                                                # second filter column is for line opacity:
                                                if (filt_opacity is not None) and (len(filt_cols) > I_FILT_OPACITY):
                                                    filt_col = filt_cols[I_FILT_OPACITY]
                                                    if filt_col is not None:
                                                        v = df[filt_col].iloc[0]
                                                        if v in filt_vals[I_FILT_OPACITY]:
                                                            i_opacity = filt_vals[I_FILT_OPACITY].index(v)
                                                            opacity_use = filt_opacity[i_opacity]

                                                # third filter column is for line type:
                                                if (filt_linestyle is not None) and (len(filt_cols) > I_FILT_LINESTYLE):
                                                    filt_col = filt_cols[I_FILT_LINESTYLE]
                                                    if filt_col is not None:
                                                        v = df[filt_col].iloc[0]
                                                        if v in filt_vals[I_FILT_LINESTYLE]:
                                                            i_opacity = filt_vals[I_FILT_LINESTYLE].index(v)
                                                            line_style_use = filt_linestyle[i_opacity]

                                                if hover_data_col is not None:
                                                    hover_data = df[hover_data_col]

                                            if i_bg == 0:
                                                # plot background traces onto every subplot
                                                for ipc in range(n_cols):
                                                    for iprr in range(n_row_reps):
                                                        for ipsr in range(n_sub_rows):
                                                            ipr = ipsr
                                                            if not group_temperatures:
                                                                ipr = ipr + iprr * n_sub_rows
                                                            fig.add_trace(
                                                                go.Scatter(
                                                                    x=x_data, y=y_data, connectgaps=True,
                                                                    showlegend=False, hoverinfo='skip',
                                                                    line=dict(color=color_use,
                                                                              width=TRACE_BG_LINE_WIDTH),
                                                                    opacity=OPACITY_BACKGROUND, mode='lines',
                                                                ), row=(ipr + 1), col=(ipc + 1))
                                                pass
                                            else:
                                                # plot active traces onto dedicated subplot
                                                trace_mode = 'lines'
                                                if show_marker:
                                                    trace_mode = 'lines+markers'
                                                # if USE_MARKER or FORCE_MARKER:
                                                #     trace_mode = None
                                                #     if FORCE_MARKER:
                                                #         trace_mode = 'lines+markers'

                                                fig.add_trace(
                                                    go.Scatter(
                                                        x=x_data, y=y_data, connectgaps=True, showlegend=False,
                                                        line=dict(color=color_use, width=TRACE_LINE_WIDTH),
                                                        opacity=opacity_use, line_dash=line_style_use,
                                                        marker=MARKER_DEFAULT,
                                                        hovertemplate=hover_template_fun(
                                                            x_var, y_var, x_unit, y_unit, hover_append_str),
                                                        text=hover_data, mode=trace_mode,
                                                    ), row=(i_row + 1), col=(i_col + 1))
                                                # text=
                                                # name=
                                                if (age_col is not None) and (dummy_x is None):
                                                    valid_x = x_data[~x_data.isna()]
                                                    valid_y = y_data[~y_data.isna()]
                                                    if (valid_x.shape[0] > 0) and (valid_y.shape[0] > 0):
                                                        dummy_x = [valid_x.iloc[0], valid_x.iloc[1]]
                                                        dummy_y = [valid_y.iloc[0], valid_y.iloc[0]]
                                                        dummy_row = i_row
                                                        dummy_col = i_col
                if (age_col is not None) and (dummy_x is not None) and (dummy_y is not None):
                    age_col_text = age_col
                    if age_col_text == csv_label.TIMESTAMP:
                        age_col_text = "time"
                    elif age_col_text == COL_EFC:
                        age_col_text = "equivalent full cycles, EFC"
                    m = dict(colorscale='Viridis', size=3, line=dict(width=1), cmin=0, cmax=1, color=0.5,
                             colorbar=dict(title='Lifetime (' + age_col_text + '):', orientation='h', x=0.5, len=0.45,
                                           thickness=15, tickvals=[0, 1], ticktext=['new cell', 'aged cell']))
                    fig.add_trace(go.Scatter(x=dummy_x, y=dummy_y, showlegend=False, line=dict(color='black'),
                                             opacity=0, marker=m, legend="legend", hoverinfo='skip'),
                                  row=(dummy_row + 1), col=(dummy_col + 1))

                # style figure
                fig.update_xaxes(range=x_lim,
                                 ticks="outside",
                                 # ticklabelmode="period",
                                 tickcolor=MAJOR_GRID_COLOR,
                                 ticklen=10,
                                 # showticklabels=True,
                                 minor=dict(griddash='dot',
                                            gridcolor=MINOR_GRID_COLOR,
                                            ticklen=4),
                                 # title_text=x_ax_title,
                                 )
                if minimal_x_ax_labels:
                    for i_col in range(n_cols):
                        fig.update_xaxes(showticklabels=True, row=n_rows, col=(i_col + 1))  # show in last row
                        for i_row in range(n_rows - 1):
                            fig.update_xaxes(showticklabels=False, row=(i_row + 1), col=(i_col + 1))  # hide in others
                else:
                    fig.update_xaxes(showticklabels=True)
                if COMPACT_AX_LABELS or minimal_x_ax_labels:
                    for i_col in range(n_cols):
                        fig.update_xaxes(title_text=x_ax_title, row=n_rows, col=(i_col + 1))
                else:
                    fig.update_xaxes(title_text=x_ax_title)

                if (x_var == csv_label.EIS_FREQ) and USE_LOG_FOR_FREQ_X_AXIS:
                    fig.update_xaxes(type="log")

                fig.update_yaxes(range=y_lim,
                                 ticks="outside",
                                 tickcolor=MAJOR_GRID_COLOR,
                                 ticklen=10,
                                 # showticklabels=True,
                                 minor=dict(griddash='dot',
                                            gridcolor=MINOR_GRID_COLOR,
                                            ticklen=4),
                                 # title_text=y_ax_title,
                                 )
                if minimal_y_ax_labels:
                    for i_row in range(n_rows):
                        fig.update_yaxes(showticklabels=True, row=(i_row + 1), col=1)  # show in first col
                        for i_col in range(1, n_cols):
                            fig.update_yaxes(showticklabels=False, row=(i_row + 1), col=(i_col + 1))  # hide in others
                else:
                    fig.update_yaxes(showticklabels=True)
                if COMPACT_AX_LABELS or minimal_y_ax_labels:
                    for i_row in range(n_rows):
                        fig.update_yaxes(title_text=y_ax_title, row=(i_row + 1), col=1)
                else:
                    fig.update_yaxes(title_text=y_ax_title)

                fig.update_layout(title={'text': "<b>" + plot_title + "</b>",
                                         'y': plot_title_y_pos,
                                         'x': 0.5,
                                         'xanchor': 'center',
                                         'yanchor': 'top'},
                                  template=FIGURE_TEMPLATE,
                                  autosize=True,
                                  height=plot_height,
                                  width=plot_width,
                                  legend=dict(x=0, y=0),
                                  margin=dict(l=SUBPLOT_LR_MARGIN, r=SUBPLOT_LR_MARGIN,
                                              t=SUBPLOT_TOP_MARGIN, b=SUBPLOT_BOT_MARGIN,
                                              pad=SUBPLOT_PADDING)
                                  )
                # fig.update_layout(hovermode='x unified')
                # fig.update_xaxes(showspikes=True)
                # fig.update_yaxes(showspikes=True)
                if LARGE_FONT_SIZE:
                    fig.update_annotations(font_size=SUBPLOT_TITLE_FONT_SIZE)

                # save figure
                age_shortname = cfg.AGE_TYPE_SHORTNAMES.get(age_type)
                if (custom_filename is not None) and (type(custom_filename) is str):
                    filename_base = custom_filename + PLOT_FILENAME_CUSTOM_APPENDIX % (age_shortname, file_version)
                else:
                    drt_shortname = cfg.DATA_RECORD_SHORTNAMES.get(drt)
                    filename_base = PLOT_FILENAME_BASE % (PLOT_FILENAME_PREFIX, drt_shortname, y_vars[0], age_shortname,
                                                          file_version)
                if EXPORT_HTML or EXPORT_IMAGE:
                    if not os.path.exists(OUTPUT_DIR):
                        os.mkdir(OUTPUT_DIR)

                    if EXPORT_HTML:
                        filename = filename_base + ".html"
                        sub_version = 1
                        while True:
                            if os.path.isfile(filename):  # file already exists
                                sub_version = sub_version + 1
                                filename = filename_base + ("-%u" % sub_version) + ".html"
                            else:
                                break
                        fulL_name = OUTPUT_DIR + filename
                        logging.log.debug("%s - saving figure as html\n    %s" % (instance_text, fulL_name))
                        fig.write_html(fulL_name, auto_open=SHOW_IN_BROWSER)

                    if EXPORT_IMAGE:
                        filename = filename_base + "." + IMAGE_FORMAT
                        sub_version = 1
                        while True:
                            if os.path.isfile(filename):  # file already exists
                                sub_version = sub_version + 1
                                filename = filename_base + ("-%u" % sub_version) + "." + IMAGE_FORMAT
                            else:
                                break
                        fulL_name = OUTPUT_DIR + filename
                        logging.log.debug("%s - saving figure as image\n    %s" % (instance_text, fulL_name))
                        fig.write_image(fulL_name, format=IMAGE_FORMAT, engine=IMAGE_EXPORT_ENGINE,
                                        width=plot_width, height=plot_height, scale=PLOT_SCALE_FACTOR)

                # open figure in browser
                if SHOW_IN_BROWSER and (not EXPORT_HTML):
                    logging.log.debug("%s - open figure in browser" % instance_text)
                    # fig.show_dash(mode='inline')
                    fig.show()

                logging.log.debug("%s - saving/opening figure done" % instance_text)

        except PlotException:
            critical_error = True
        except Exception:
            critical_error = True
            logging.log.error("Thread %u - Python Error for %s, plot_task:\n%s\nError Message:\n%s"
                              % (processor_number, drt.name, plot_task, traceback.format_exc()))
        if critical_error:
            report_msg = (f"Thread %u - could not finish plot task because of critical error! (see log)"
                          % processor_number)
            report_level = config_logging.CRITICAL
        else:
            report_msg = (f"%s - finished (%u errors, %u warnings)"
                          % (instance_text, num_errors, num_warnings))
            report_level = config_logging.INFO
            if num_errors > 0:
                report_level = config_logging.ERROR
            elif num_warnings > 0:
                report_level = config_logging.WARNING

        report_entry = {"msg": report_msg, "level": report_level}
        rep_queue.put(report_entry)

    task_queue.close()
    logging.log.debug("exiting thread")


def get_next_plot_version():
    max_version = 0
    try:
        with os.scandir(OUTPUT_DIR) as iterator:
            re_str = PLOT_FILENAME_PREFIX + "\w+_v(\d+).\w+"
            re_pat = re.compile(re_str)
            for entry in iterator:
                re_match = re_pat.fullmatch(entry.name)
                if re_match:
                    this_version = int(re_match.group(1))
                    if this_version > max_version:
                        max_version = this_version
    except FileNotFoundError:
        pass
    next_version = max_version + 1
    return next_version


def read_data_records(f_queue, max_param_id, max_param_nr):
    df_dict = {}

    # read config files and generate param_df
    param_df = ht.generate_cell_param_df_from_cfgs(INPUT_DIR, max_param_id, max_param_nr)

    # since these data record files are not too big, read them one by one (might also parallelize this in the future?)
    while True:
        try:
            queue_entry = f_queue.get_nowait()
        except multiprocessing.queues.Empty:
            break  # no more files
        if queue_entry is None:
            break  # no more files

        filename_csv = queue_entry["filename"]
        drt = queue_entry["data_record_type"]
        if drt not in df_dict:
            df_dict.update({drt: [[None] * max_param_nr for _ in range(max_param_id)]})

        # slave_id = queue_entry[csv_label.SLAVE_ID]
        # cell_id = queue_entry[csv_label.CELL_ID]
        param_id = queue_entry[csv_label.PARAMETER_ID]
        param_nr = queue_entry[csv_label.PARAMETER_NR]
        # instance_string = "P%03u-%u (S%02u:C%02u)" % (param_id, param_nr, slave_id, cell_id)

        logging.log.debug("Reading '%s'" % filename_csv)
        df = pd.read_csv(INPUT_DIR + filename_csv, header=0, sep=cfg.CSV_SEP, engine="pyarrow")
        if USE_RELATIVE_TIME:
            if csv_label.TIMESTAMP in df.columns:
                df[csv_label.TIMESTAMP] = df[csv_label.TIMESTAMP] - cfg.EXPERIMENT_START_TIMESTAMP
        df_dict[drt][param_id - 1][param_nr - 1] = df
    f_queue.close()
    return df_dict, param_df


def add_custom_record_columns(df_dict, max_param_id, max_param_nr):
    if cfg.DataRecordType.CELL_EOC_FIXED in df_dict:
        for i_p_id in range(0, max_param_id):
            for i_p_nr in range(0, max_param_nr):
                df_dict[cfg.DataRecordType.CELL_EOC_FIXED][i_p_id][i_p_nr][COL_EFC] = 0.0
                df: pd.DataFrame = df_dict[cfg.DataRecordType.CELL_EOC_FIXED][i_p_id][i_p_nr]
                df.loc[:, COL_EFC] = ((df[csv_label.TOTAL_Q_CHG_SUM] + df[csv_label.TOTAL_Q_DISCHG_SUM])
                                      / (2.0 * cfg.CELL_CAPACITY_NOMINAL))

    if cfg.DataRecordType.CELL_PULSE_FIXED in df_dict:
        for i_p_id in range(0, max_param_id):
            for i_p_nr in range(0, max_param_nr):
                df_dict[cfg.DataRecordType.CELL_PULSE_FIXED][i_p_id][i_p_nr][COL_T_REL] = np.nan
                df_dict[cfg.DataRecordType.CELL_PULSE_FIXED][i_p_id][i_p_nr][COL_EFC] = np.nan
                df: pd.DataFrame = df_dict[cfg.DataRecordType.CELL_PULSE_FIXED][i_p_id][i_p_nr]
                t_sdbi_df = df[[csv_label.TIMESTAMP, csv_label.V_CELL, csv_label.SD_BLOCK_ID]].drop_duplicates(
                    subset=csv_label.SD_BLOCK_ID)

                df.loc[:, COL_T_REL] = t_sdbi_df[csv_label.TIMESTAMP]
                df[COL_T_REL].ffill(inplace=True)
                df.loc[:, COL_T_REL] = df[csv_label.TIMESTAMP] - df[COL_T_REL]

                df.loc[:, COL_DV] = t_sdbi_df[csv_label.V_CELL]
                df[COL_DV].ffill(inplace=True)
                df.loc[:, COL_DV] = df[csv_label.V_CELL] - df[COL_DV]

                if cfg.DataRecordType.CELL_EOC_FIXED in df_dict:
                    eoc_df = df_dict[cfg.DataRecordType.CELL_EOC_FIXED][i_p_id][i_p_nr]
                    if eoc_df is not None:
                        timestamps = df[csv_label.TIMESTAMP].drop_duplicates()
                        # this is *INSANELY* faster than looping through the timestamps
                        xf = pd.merge_asof(timestamps, eoc_df[[csv_label.TIMESTAMP, COL_EFC]],
                                           on=csv_label.TIMESTAMP, direction="nearest")
                        df[COL_EFC] = xf[COL_EFC][xf[csv_label.TIMESTAMP].isin(timestamps)]
                        df[COL_EFC].ffill(inplace=True)

    if cfg.DataRecordType.CELL_EIS_FIXED in df_dict:
        for i_p_id in range(0, max_param_id):
            for i_p_nr in range(0, max_param_nr):
                df_dict[cfg.DataRecordType.CELL_EIS_FIXED][i_p_id][i_p_nr][COL_EFC] = np.nan
                if cfg.DataRecordType.CELL_EOC_FIXED in df_dict:
                    df: pd.DataFrame = df_dict[cfg.DataRecordType.CELL_EIS_FIXED][i_p_id][i_p_nr]
                    eoc_df = df_dict[cfg.DataRecordType.CELL_EOC_FIXED][i_p_id][i_p_nr]
                    if eoc_df is not None:
                        timestamps = df[csv_label.TIMESTAMP].drop_duplicates()
                        # this is *INSANELY* faster than looping through the timestamps
                        xf = pd.merge_asof(timestamps, eoc_df[[csv_label.TIMESTAMP, COL_EFC]],
                                           on=csv_label.TIMESTAMP, direction="nearest")
                        df.loc[timestamps.index, COL_EFC] = xf[COL_EFC][xf[csv_label.TIMESTAMP].isin(timestamps)].values
                        df[COL_EFC].ffill(inplace=True)

    return df_dict


def get_optional_plot_vars(plot_task):
    filt_cols = []
    if PTL_FILT_COLUMNS in plot_task:
        if plot_task[PTL_FILT_COLUMNS] is not None:
            filt_cols = plot_task[PTL_FILT_COLUMNS]

    filt_vals = []
    if PTL_FILT_VALUES in plot_task:
        if plot_task[PTL_FILT_VALUES] is not None:
            filt_vals = plot_task[PTL_FILT_VALUES]

    filt_colors = None
    if PTL_FILT_COLORS in plot_task:
        if plot_task[PTL_FILT_COLORS] is not None:
            filt_colors = plot_task[PTL_FILT_COLORS]

    filt_opacity = None
    if PTL_FILT_OPACITY in plot_task:
        if plot_task[PTL_FILT_OPACITY] is not None:
            filt_opacity = plot_task[PTL_FILT_OPACITY]

    filt_linestyle = None
    if PTL_FILT_LINESTYLE in plot_task:
        if plot_task[PTL_FILT_LINESTYLE] is not None:
            filt_linestyle = plot_task[PTL_FILT_LINESTYLE]

    group_by = None
    if PTL_GROUP_BY in plot_task:
        if plot_task[PTL_GROUP_BY] is not None:
            group_by = plot_task[PTL_GROUP_BY]

    group_by_aging_col = None
    if PTL_GROUP_BY_AGING_COL in plot_task:
        if plot_task[PTL_GROUP_BY_AGING_COL] is not None:
            group_by_aging_col = plot_task[PTL_GROUP_BY_AGING_COL]

    group_temperatures = False
    if PTL_GROUP_TEMPERATURES in plot_task:
        if plot_task[PTL_GROUP_TEMPERATURES] is not None:
            group_temperatures = plot_task[PTL_GROUP_TEMPERATURES]

    plot_colors = TRACE_COLOR_DEFAULT
    if PTL_COLORS in plot_task:
        if plot_task[PTL_COLORS] is not None:
            plot_colors = plot_task[PTL_COLORS]

    opacity = TRACE_OPACITY_DEFAULT
    if PTL_OPACITY in plot_task:
        if plot_task[PTL_OPACITY] is not None:
            opacity = plot_task[PTL_OPACITY]

    show_marker = SHOW_MARKER_BY_DEFAULT
    if PTL_SHOW_MARKER in plot_task:
        if plot_task[PTL_SHOW_MARKER] is not None:
            show_marker = plot_task[PTL_SHOW_MARKER]

    x_ax_title = ""
    if PTL_X_AX_TITLE in plot_task:
        if plot_task[PTL_X_AX_TITLE] is not None:
            x_ax_title = plot_task[PTL_X_AX_TITLE]

    y_ax_title = ""
    if PTL_Y_AX_TITLE in plot_task:
        if plot_task[PTL_Y_AX_TITLE] is not None:
            y_ax_title = plot_task[PTL_Y_AX_TITLE]

    x_unit = ""
    if PTL_X_UNIT in plot_task:
        if plot_task[PTL_X_UNIT] is not None:
            x_unit = plot_task[PTL_X_UNIT]
    if x_unit != "":
        x_ax_title = x_ax_title + " [" + x_unit + "]"

    y_unit = ""
    if PTL_Y_UNIT in plot_task:
        if plot_task[PTL_Y_UNIT] is not None:
            y_unit = plot_task[PTL_Y_UNIT]
    if y_unit != "":
        y_ax_title = y_ax_title + " [" + y_unit + "]"

    x_div = None
    if PTL_X_DIV in plot_task:
        if plot_task[PTL_X_DIV] is not None:
            x_div = plot_task[PTL_X_DIV]

    y_div = None
    if PTL_Y_DIV in plot_task:
        if plot_task[PTL_Y_DIV] is not None:
            y_div = plot_task[PTL_Y_DIV]

    x_lim = None
    if PTL_X_LIMS in plot_task:
        if plot_task[PTL_X_LIMS] is not None:
            x_lim = plot_task[PTL_X_LIMS]

    y_lim = None
    if PTL_Y_LIMS in plot_task:
        if plot_task[PTL_Y_LIMS] is not None:
            y_lim = plot_task[PTL_Y_LIMS]

    plot_title = ""
    if PTL_TITLE in plot_task:
        if plot_task[PTL_TITLE] is not None:
            plot_title = plot_task[PTL_TITLE]

    hover_data_col = None
    if PTL_HOVER_DATA_COL in plot_task:
        if plot_task[PTL_HOVER_DATA_COL] is not None:
            hover_data_col = plot_task[PTL_HOVER_DATA_COL]

    hover_template_function = get_hover_default
    if PTL_HOVER_TEMPLATE_FUNCTION in plot_task:
        if plot_task[PTL_HOVER_TEMPLATE_FUNCTION] is not None:
            hover_template_function = plot_task[PTL_HOVER_TEMPLATE_FUNCTION]

    plot_all_in_background = False
    if PTL_PLOT_ALL_IN_BACKGROUND in plot_task:
        if plot_task[PTL_PLOT_ALL_IN_BACKGROUND] is not None:
            plot_all_in_background = plot_task[PTL_PLOT_ALL_IN_BACKGROUND]

    custom_filename = None
    if PTL_FILENAME in plot_task:
        if plot_task[PTL_FILENAME] is not None:
            custom_filename = PLOT_FILENAME_PREFIX + plot_task[PTL_FILENAME]  # PLOT_FILENAME_PREFIX to detect version

    minimal_x_ax_labels = None
    if PTL_MINIMAL_X_AX_LABELS in plot_task:
        if plot_task[PTL_MINIMAL_X_AX_LABELS] is not None:
            minimal_x_ax_labels = plot_task[PTL_MINIMAL_X_AX_LABELS]

    minimal_y_ax_labels = None
    if PTL_MINIMAL_Y_AX_LABELS in plot_task:
        if plot_task[PTL_MINIMAL_Y_AX_LABELS] is not None:
            minimal_y_ax_labels = plot_task[PTL_MINIMAL_Y_AX_LABELS]

    return (filt_cols, filt_vals, filt_colors, filt_opacity, filt_linestyle, group_by, group_by_aging_col,
            group_temperatures, plot_colors, opacity, show_marker, x_ax_title, y_ax_title, x_unit, y_unit, x_div, y_div,
            x_lim, y_lim, plot_title, hover_data_col, hover_template_function, plot_all_in_background, custom_filename,
            minimal_x_ax_labels, minimal_y_ax_labels)


def get_subplot_titles(n_cols, n_rows, n_sub_rows, n_row_reps, col_var, col_vals,
                       row_var, row_vals, row_rep_var, row_rep_vals, group_temperatures):
    subplot_titles = ['---' for _ in range(0, n_cols * n_rows)]
    for i_col in range(n_cols):
        col_text = None
        if len(col_vals) > 0:
            col_text = ht.get_age_val_text(col_var, col_vals[i_col])
        for i_row_rep in range(n_row_reps):
            row_rep_text = None
            if not group_temperatures:
                row_rep_text = ht.get_age_val_text(row_rep_var, row_rep_vals[i_row_rep])
            for i_sub_row in range(n_sub_rows):
                row_text = None
                if len(row_vals) > 0:
                    row_text = ht.get_age_val_text(row_var, row_vals[i_sub_row])
                combined_text = ", ".join(filter(None, [col_text, row_rep_text, row_text]))
                i_row = i_sub_row
                if not group_temperatures:
                    i_row = i_row_rep * n_sub_rows + i_row
                i_title = (i_row * n_cols) + i_col
                subplot_titles[i_title] = combined_text
    return subplot_titles


if __name__ == "__main__":
    run()
