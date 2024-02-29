# Minimal code example to read, filter, and plot a data record. See comments marked with ToDo

import pandas as pd  # easy and fast processing of large data sets
# import numpy as np  # also helpful for processing and analyzing data
import matplotlib.pyplot as plt  # plotting data

import config_main as cfg
import config_labels as csv_label

# input_dir = cfg.CSV_RESULT_DIR
input_dir = "D:\\bat\\analysis\\preprocessing\\result_12\\"  # ToDo: adjust input directory
filename = "cell_log_age_30s_P060_2_S16_C01.csv"  # ToDo: which file do you want to read and plot?
# filename = "cell_logext_P001_3_S05_C06.csv"
# filename = "cell_logext_P021_2_S03_C08.csv"
# filename = "pool_log_T00_P0.csv"
# filename = "slave_log_T00.csv"
# ...


def run():
    # in case you only want to load specific columns (to reduce RAM usage and speed up reading/processing):
    # LOAD_VARIABLES = [csv_label.TIMESTAMP, csv_label.DELTA_Q, ]
    # df = pd.read_csv(input_dir + filename, header=0, sep=cfg.CSV_SEP, usecols=LOAD_VARIABLES, engine="pyarrow")

    df = pd.read_csv(input_dir + filename, header=0, sep=cfg.CSV_SEP, engine="pyarrow")

    print("set a breakpoint here to view the data frame")

    # ToDo: do stuff here if you want ...

    # e.g., filter and show cell voltage, current and delta_Q values in a certain time window:
    x_var = csv_label.TIMESTAMP
    x_label = "Time [s]"
    y_vars = [csv_label.V_CELL, csv_label.I_CELL, csv_label.DELTA_Q]
    y_labels = ["Cell voltage [V]", "Cell current [A]", "ΔQ [Ah]"]

    t_start = 30 * 24 * 60 * 60  # from 20 days after the experiment (log_age data set)
    # t_start = t_start + cfg.EXPERIMENT_START_TIMESTAMP # use for all data sets except log_age (absolute timestamp)
    t_end = t_start + 60 * 60  # to 60 minutes later

    load_vars = y_vars.copy()
    load_vars.append(x_var)

    ix = df[(df[x_var] > t_start) & (df[x_var] < t_end)].index  # get indexes in this window
    tv_df = df.loc[ix, load_vars]  # data frame for time + voltage in this window
    print(tv_df)  # show in the console

    num_plots = len(y_vars)
    plts = []
    fig = plt.figure()
    for i in range(num_plots):
        if i > 0:
            my_plt = fig.add_subplot(num_plots, 1, i + 1, sharex=plts[i - 1])
        else:
            my_plt = fig.add_subplot(num_plots, 1, i + 1)
        my_plt.plot(tv_df[x_var], tv_df[y_vars[i]], c="b")
        my_plt.set_xlabel(x_label)
        my_plt.set_ylabel(y_labels[i])
        my_plt.grid()
        plts.append(my_plt)

    plt.show()

    print("set a breakpoint here to view and edit the data frame in the debugger")


if __name__ == "__main__":
    run()
