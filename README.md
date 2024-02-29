# Example scripts for using and visualizing the battery aging data
Python example scripts for processing the battery aging data published in [insert description and link here]

- **config_main.py**:  
  IMPORTANT! Before starting, adjust file paths, e.g., define where the .csv files are stored.


- **read_dataframe_example.py**:  
  Simple example to read, filter, and plot a data record.
- **plot_result_data_comparison.py**:  
  Generate plots for the result data sets (EOC/EIS/PULSE). Use default configuration or adjust the PLOT_TASKS_LIST according to your needs.
- **check_plausibility.py**:  
  This script is used to generate the *"Battery Aging Data Plausibility Check"* spreadsheet.  
- **generate_log_age.py**:  
  This script can be used to generate custom log_age files according to your needs, e.g., with reduced or increased temporal resolution, or additional columns.


- **config_labels.py**:  
  Definition of data column labels. Not all columns of the published records are defined here, you can add them if you need them.
- **color_tools.py**:  
  Various color-related tools for plots. Usually no need to change this.
- **config_logging.py**:  
  Log configuration. Usually no need to change this.
