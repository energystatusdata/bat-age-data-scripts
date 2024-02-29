import config_main as cfg
import config_labels as csv_label
import pandas as pd
import numpy as np
import re
import os


def get_found_cells_text(slave_cell_found, pre_text):
    tmp = pre_text + "   Cells:   "
    for cell_id in range(0, cfg.NUM_CELLS_PER_SLAVE):
        tmp += "x"
    tmp += "\n"
    for slave_id in range(0, cfg.NUM_SLAVES_MAX):
        tmp += f"Slave %2u:   " % slave_id
        for cell_id in range(0, cfg.NUM_CELLS_PER_SLAVE):
            tmp += str(slave_cell_found[slave_id][cell_id])
        tmp += "\n"
    return tmp


def get_found_pools_text(slave_pool_found, pre_text):
    tmp = pre_text + "   Pools:   "
    for pool_id in range(0, cfg.NUM_POOLS_PER_TMGMT):
        tmp += "x"
    tmp += "\n"
    slave_id = 0
    tmp += f"Slave %2u:   " % slave_id
    for pool_id in range(0, cfg.NUM_POOLS_PER_TMGMT):
        tmp += str(slave_pool_found[slave_id][pool_id])
    tmp += "\n"
    return tmp


def get_found_slaves_text(slaves_found, pre_text):
    tmp = pre_text + "   Slaves:   "
    for slave_id in range(0, cfg.NUM_SLAVES_MAX):
        tmp += "%02u " % slave_id
    tmp += "\n   Found:    "
    for slave_id in range(0, cfg.NUM_SLAVES_MAX):
        tmp += str(slaves_found[slave_id]) + "  "
    tmp += "\n"
    return tmp


def get_age_op_text(age_type, temp, soc, chg_rate, dischg_rate, soc_min, soc_max, profile, cap_nom):
    return (get_age_temp_text(temp) + ", "
            + get_age_type_text(age_type, soc, chg_rate, dischg_rate, soc_min, soc_max, profile, cap_nom))


def get_age_val_text(age_var, age_val):
    if (age_var is None) or (age_val is None):
        return ""
    age_str = age_val
    if age_var == csv_label.AGE_TEMPERATURE:
        age_str = get_age_temp_text(age_val)
    elif age_var == csv_label.AGE_SOC:
        age_str = get_age_soc_text_percent(age_val)
    elif age_var == csv_label.AGE_PROFILE:
        age_str = get_age_profile_text(age_val)
    # AGE_C_RATES, AGE_SOC_RANGE -> age_val is age_str
    return age_str


def get_age_type_text(age_type, soc, chg_rate, dischg_rate, soc_min, soc_max, profile, cap_nom):
    if age_type == cfg.age_type.CYCLIC:
        return (f"cyclic aging (chg: %s, dischg: %s, SoC: %s - %s %%)"
                % (get_age_rate_text(chg_rate, True, cap_nom),
                   get_age_rate_text(dischg_rate, False, cap_nom),
                   get_age_soc_text(soc_min), get_age_soc_text(soc_max)))
    elif age_type == cfg.age_type.PROFILE:
        age_profile_text = "unknown"
        if profile < len(cfg.AGE_PROFILE_TEXTS):
            age_profile_text = cfg.AGE_PROFILE_TEXTS[int(profile)]
        return (f"profile aging (chg: %s, dischg: %s)"
                % (get_age_rate_text(chg_rate, True, cap_nom), age_profile_text))
    elif age_type == cfg.age_type.CALENDAR:
        return f"calendar aging (SoC: %s %%)" % get_age_soc_text(soc)
    elif age_type == cfg.age_type.MANUAL:
        return "manual operation"
    else:
        return "unknown mode of operation"


def get_age_temp_text(temp):
    if temp == cfg.AGE_TEMPERATURE_UNDEFINED:
        return "N/A °C"
    elif temp == cfg.AGE_TEMPERATURE_MANUAL:
        return "?? °C"
    else:
        return f"%u °C" % temp


def get_age_rate_text(rate, is_chg, cap_nom):
    if is_chg:
        sign = "+"
    else:
        sign = "-"
    if rate == cfg.AGE_RATE_UNDEFINED:
        return f"%s? C = %s? A" % (sign, sign)
    else:
        return f"%s%.2f C = %s%.1f A" % (sign, rate, sign, rate * cap_nom)


def get_age_rate_text_short(rate, is_chg):
    if is_chg:
        sign = "+"
        unit = "Cc"
    else:
        sign = "-"
        unit = "Cd"
    if rate == cfg.AGE_RATE_UNDEFINED:
        return f"%s? %s" % (sign, unit)
    else:
        return f"%s%.2f %s" % (sign, rate, unit)


def get_age_soc_text(soc):
    if soc == cfg.AGE_SOC_UNDEFINED:
        return "N/A"
    elif soc == cfg.AGE_SOC_MANUAL:
        return "??"
    else:
        return f"%u" % soc


def get_age_soc_text_percent(soc):
    return get_age_soc_text(soc) + " %"


def get_age_profile_text(profile):
    if (profile >= 0) and (profile < len(cfg.AGE_PROFILE_TEXTS_SHORT)):
        return cfg.AGE_PROFILE_TEXTS_SHORT[int(profile)]
    else:
        return "N/A"


def get_soc_from_v_cell(v_cell):
    if v_cell >= 4.15:
        return 100
    elif v_cell >= 4.0:
        return 90
    elif v_cell >= 3.7:
        return 50
    elif v_cell >= 3.2:
        return 10
    elif v_cell >= 2.4:
        return 0
    return cfg.AGE_SOC_UNDEFINED


def get_v_idle_from_soc(soc, chg_flag):  # chg_flag: -1 for discharging, 0 for idle, 1 for charging
    if chg_flag == -1:  # discharging limit
        if soc == 0:
            return 2.5
        elif soc == 10:
            return 3.249
        else:
            return np.nan
    elif chg_flag == 0:  # calendar aging
        if soc == 10:
            return 3.3
        elif soc == 50:
            return 3.736
        elif soc == 90:
            return 4.089
        elif soc == 100:
            return 4.2
        else:
            return np.nan
    elif chg_flag == 1:  # charging limit
        if soc == 90:
            return 4.092
        elif soc == 100:
            return 4.2
        else:
            return np.nan

    return np.nan


def find_files_of_type(input_dir, data_record_type):
    filenames = []
    items = []
    info_matrix = []

    if data_record_type in cfg.DATA_RECORD_BASE_TYPE:
        base_type = cfg.DATA_RECORD_BASE_TYPE.get(data_record_type)
        if base_type == cfg.DataRecordBaseType.CELL:
            filenames, items, info_matrix, message = find_cell_files_of_type(input_dir, data_record_type)
        elif base_type == cfg.DataRecordBaseType.POOL:
            filenames, items, info_matrix, message = find_pool_files_of_type(input_dir, data_record_type)
        elif (base_type == cfg.DataRecordBaseType.TMGMT_SLAVE) or (base_type == cfg.DataRecordBaseType.CYCLER_SLAVE):
            filenames, items, info_matrix, message = find_slave_files_of_type(input_dir, data_record_type)
        else:
            message = "Error: unknown Data Record Type"
    else:
        message = "Error: unknown Data Record Base Type"
    return filenames, items, info_matrix, message


def find_cell_files_of_type(input_dir, data_record_type):
    filenames = []
    items = []
    info_matrix = [[" "] * cfg.NUM_CELLS_PER_SLAVE for _ in range(cfg.NUM_SLAVES_MAX)]
    message = "Found these %s files:\n" % data_record_type.name

    if data_record_type in cfg.DATA_RECORD_REGEX_PATTERN:
        re_str_log_csv = cfg.DATA_RECORD_REGEX_PATTERN.get(data_record_type)
        re_pat_log_csv = re.compile(re_str_log_csv)
        with os.scandir(input_dir) as iterator:
            for entry in iterator:
                re_match_log_csv = re_pat_log_csv.fullmatch(entry.name)
                if re_match_log_csv:
                    if data_record_type == cfg.DataRecordType.CELL_LOG_AGE:
                        resolution = int(re_match_log_csv.group(1))
                        param_id = int(re_match_log_csv.group(2))
                        param_nr = int(re_match_log_csv.group(3))
                        slave_id = int(re_match_log_csv.group(4))
                        cell_id = int(re_match_log_csv.group(5))
                        item = {"resolution_s": resolution,
                                csv_label.PARAMETER_ID: param_id,
                                csv_label.PARAMETER_NR: param_nr,
                                csv_label.SLAVE_ID: slave_id,
                                csv_label.CELL_ID: cell_id,
                                "filename": entry.name}
                    else:
                        param_id = int(re_match_log_csv.group(1))
                        param_nr = int(re_match_log_csv.group(2))
                        slave_id = int(re_match_log_csv.group(3))
                        cell_id = int(re_match_log_csv.group(4))
                        item = {csv_label.PARAMETER_ID: param_id,
                                csv_label.PARAMETER_NR: param_nr,
                                csv_label.SLAVE_ID: slave_id,
                                csv_label.CELL_ID: cell_id,
                                "filename": entry.name}
                    filenames.append(entry.name)
                    items.append(item)
                    if (slave_id < 0) or (slave_id >= cfg.NUM_SLAVES_MAX):
                        message = message + "Found unusual slave_id: %u\n" % slave_id
                    else:
                        if (cell_id < 0) or (cell_id >= cfg.NUM_CELLS_PER_SLAVE):
                            message = message + "Found unusual cell_id: %u\n" % cell_id
                        else:
                            if info_matrix[slave_id][cell_id] == "x":
                                message = message + "Found more than one entry for S%02u:C%02u\n" % (slave_id, cell_id)
                            else:
                                info_matrix[slave_id][cell_id] = "x"

        # List found slaves/cells for user
        message = message + get_found_cells_text(info_matrix, "") + "... in directory: %s\n" % input_dir
    else:
        message = "Error: unsupported Data Record Type (cell)"

    return filenames, items, info_matrix, message


def find_pool_files_of_type(input_dir, data_record_type):
    filenames = []
    items = []
    info_matrix = [[" "] * cfg.NUM_CELLS_PER_SLAVE for _ in range(cfg.NUM_SLAVES_MAX)]
    message = "Found these %s files:\n" % data_record_type.name

    if data_record_type in cfg.DATA_RECORD_REGEX_PATTERN:
        re_str_log_csv = cfg.DATA_RECORD_REGEX_PATTERN.get(data_record_type)
        re_pat_log_csv = re.compile(re_str_log_csv)
        with os.scandir(input_dir) as iterator:
            for entry in iterator:
                re_match_log_csv = re_pat_log_csv.fullmatch(entry.name)
                if re_match_log_csv:
                    slave_id = int(re_match_log_csv.group(1))
                    pool_id = int(re_match_log_csv.group(2))
                    item = {csv_label.SLAVE_ID: slave_id, csv_label.POOL_ID: pool_id, "filename": entry.name}
                    filenames.append(entry.name)
                    items.append(item)
                    if slave_id != 0:
                        message = message + "Found unusual slave_id: %u\n" % slave_id
                    else:
                        if (pool_id < 0) or (pool_id >= cfg.NUM_POOLS_PER_TMGMT):
                            message = message + "Found unusual pool_id: %u\n" % pool_id
                        else:
                            if info_matrix[slave_id][pool_id] == "x":
                                message = message + "Found more than one entry for T%02u:P%2u\n" % (slave_id, pool_id)
                            else:
                                info_matrix[slave_id][pool_id] = "x"

        # List found slaves/pools for user
        message = message + get_found_pools_text(info_matrix, "") + "... in directory: %s\n" % input_dir
    else:
        message = "Error: unsupported Data Record Type (pool)"

    return filenames, items, info_matrix, message


def find_slave_files_of_type(input_dir, data_record_type):
    filenames = []
    items = []
    info_matrix = [" " for _ in range(cfg.NUM_SLAVES_MAX)]
    message = "Found these %s files:\n" % data_record_type.name

    if data_record_type in cfg.DATA_RECORD_REGEX_PATTERN:
        re_str_log_csv = cfg.DATA_RECORD_REGEX_PATTERN.get(data_record_type)
        re_pat_log_csv = re.compile(re_str_log_csv)
        with os.scandir(input_dir) as iterator:
            for entry in iterator:
                re_match_log_csv = re_pat_log_csv.fullmatch(entry.name)
                if re_match_log_csv:
                    slave_id = int(re_match_log_csv.group(1))
                    slave_base_type = cfg.DATA_RECORD_BASE_TYPE.get(data_record_type)
                    item = {csv_label.SLAVE_ID: slave_id, "filename": entry.name, "slave_base_type": slave_base_type}
                    filenames.append(entry.name)
                    items.append(item)
                    if (slave_id < 0) or (slave_id >= cfg.NUM_SLAVES_MAX):
                        message = message + "Found unusual slave_id: %u\n" % slave_id
                    else:
                        if info_matrix[slave_id] == "x":
                            str_slave_type = "S"
                            if slave_base_type == cfg.DataRecordBaseType.TMGMT_SLAVE:
                                str_slave_type = "T"
                            message = message + "Found more than one entry for %s:%02u\n" % (str_slave_type, slave_id)
                        else:
                            info_matrix[slave_id] = "x"

        # List found slaves/cells for user
        message = message + get_found_slaves_text(info_matrix, "") + "... in directory: %s\n" % input_dir
    else:
        message = "Error: unsupported Data Record Type (slave)"

    return filenames, items, info_matrix, message


def generate_cell_param_df_from_cfgs(input_dir, max_param_id, max_param_nr):
    cfg_data = np.full((max_param_id, max_param_nr), None)

    _, items, _, message = find_files_of_type(input_dir, cfg.DataRecordType.CFG_CELL)

    # I. collect cfg_data of ALL parameters in array[param_id][param_nr]
    last_valid_cfg_i_param_id = None
    last_valid_cfg_i_param_nr = None
    for item in items:
        # slave_id = item[csv_label.SLAVE_ID]
        # cell_id = item[csv_label.CELL_ID]
        param_id = item[csv_label.PARAMETER_ID]
        param_nr = item[csv_label.PARAMETER_NR]
        i_param_id = param_id - 1
        i_param_nr = param_nr - 1
        filename_cfg = item["filename"]

        # open and read relevant cfg data
        cfg_df = pd.read_csv(input_dir + filename_cfg, header=0, sep=cfg.CSV_SEP, engine="pyarrow")
        cfg_df = cfg_df.iloc[0, :].copy()

        age_type = cfg_df[csv_label.AGE_TYPE]

        cfg_df.loc[csv_label.CFG_AGE_V] = -1  # don't set to nan, so the cfg_df's can be compared with any/all()
        cfg_df.loc[csv_label.CFG_AGE_V_MIN] = -1
        cfg_df.loc[csv_label.CFG_AGE_V_MAX] = -1
        cfg_df.loc[csv_label.CFG_AGE_SOC_MIN] = -1
        cfg_df.loc[csv_label.CFG_AGE_SOC_MAX] = -1
        cfg_df.loc[csv_label.AGE_SOC_RANGE] = "?-?"
        cfg_df.loc[csv_label.AGE_V_RANGE] = "?-?"
        cfg_df.loc[csv_label.AGE_C_RATES] = "?-?"
        if age_type == cfg.age_type.CALENDAR:
            # add v idle to cfg
            cfg_df.loc[csv_label.CFG_AGE_V] = get_v_idle_from_soc(cfg_df[csv_label.AGE_SOC], 0)
        elif age_type == cfg.age_type.CYCLIC:
            # add soc max and min to cfg
            v_min = cfg_df[csv_label.V_MIN_CYC]
            v_max = cfg_df[csv_label.V_MAX_CYC]
            cfg_df.loc[csv_label.CFG_AGE_V_MIN] = v_min
            cfg_df.loc[csv_label.CFG_AGE_V_MAX] = v_max
            soc_min = get_soc_from_v_cell(v_min)
            soc_max = get_soc_from_v_cell(v_max)
            cfg_df.loc[csv_label.CFG_AGE_SOC_MIN] = soc_min
            cfg_df.loc[csv_label.CFG_AGE_SOC_MAX] = soc_max
            cfg_df.loc[csv_label.AGE_SOC_RANGE] = csv_label.AGE_SOC_RANGE_RE_SHORT % (soc_min, soc_max)
            cfg_df.loc[csv_label.AGE_V_RANGE] = csv_label.AGE_V_RANGE_RE_SHORT % (v_min, v_max)
            cc = cfg_df[csv_label.AGE_CHG_RATE]
            cd = cfg_df[csv_label.AGE_DISCHG_RATE]
            cfg_df.loc[csv_label.AGE_C_RATES] = csv_label.AGE_C_RATES_RE_SHORT % (cc, cd)
        elif age_type == cfg.age_type.PROFILE:
            # add soc max and min to cfg (and chg rate?)
            age_profile = int(cfg_df[csv_label.AGE_PROFILE])
            i_chg_rate = round(cfg_df[csv_label.I_CHG_MAX_CYC] / cfg.CELL_CAPACITY_NOMINAL, 2)
            cfg_df.loc[csv_label.AGE_CHG_RATE] = i_chg_rate
            soc_min = cfg.AGE_PROFILE_SOC_MIN[age_profile]
            soc_max = cfg.AGE_PROFILE_SOC_MAX[age_profile]
            cfg_df.loc[csv_label.CFG_AGE_SOC_MIN] = soc_min
            cfg_df.loc[csv_label.CFG_AGE_SOC_MAX] = soc_max
            v_min = get_v_idle_from_soc(soc_min, -1)
            v_max = get_v_idle_from_soc(soc_max, 1)
            cfg_df.loc[csv_label.CFG_AGE_V_MIN] = v_min
            cfg_df.loc[csv_label.CFG_AGE_V_MAX] = v_max
            cfg_df.loc[csv_label.AGE_SOC_RANGE] = csv_label.AGE_SOC_RANGE_RE_SHORT % (soc_min, soc_max)
            cfg_df.loc[csv_label.AGE_V_RANGE] = csv_label.AGE_V_RANGE_RE_SHORT % (v_min, v_max)

        cfg_data[i_param_id][i_param_nr] = cfg_df

        last_valid_cfg_i_param_id = i_param_id
        last_valid_cfg_i_param_nr = i_param_nr

    if (last_valid_cfg_i_param_id is None) or (last_valid_cfg_i_param_nr is None):
        return pd.DataFrame()  # no valid config

    # II. collect param_df
    cfg_param_df_drop_col = [csv_label.SD_BLOCK_ID]  # , csv_label.SLAVE_ID, csv_label.CELL_ID
    # noinspection PyTypeChecker
    cfg_a: pd.Series = cfg_data[last_valid_cfg_i_param_id][last_valid_cfg_i_param_nr].copy()
    cfg_a.drop(cfg_param_df_drop_col, inplace=True)
    param_df = pd.DataFrame(columns=cfg_a.index.tolist())
    for i_param_id in range(0, max_param_id):
        for i_param_nr in range(0, max_param_nr):
            if cfg_data[i_param_id][i_param_nr] is not None:
                # noinspection PyTypeChecker
                cfg_a: pd.Series = cfg_data[i_param_id][i_param_nr].copy()
                cfg_a.drop(cfg_param_df_drop_col, inplace=True)
                i_new = param_df.shape[0]
                param_df.loc[i_new, :] = cfg_a

    int_cols = [csv_label.SLAVE_ID, csv_label.CELL_ID, csv_label.PARAMETER_ID, csv_label.PARAMETER_NR,
                csv_label.CFG_CELL_USED, csv_label.CFG_CELL_TYPE, csv_label.CFG_T_SNS_TYPE,
                csv_label.AGE_TYPE, csv_label.AGE_PROFILE]
    string_cols = [csv_label.AGE_SOC_RANGE, csv_label.AGE_V_RANGE, csv_label.AGE_C_RATES]
    for col in param_df.columns:
        if col in int_cols:
            param_df[col] = param_df[col].astype(int)
        elif col not in string_cols:
            param_df[col] = param_df[col].astype(float)

    return param_df
