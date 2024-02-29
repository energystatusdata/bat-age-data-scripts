# This class configures the logger used in most other files. Usually, there is no need to change anything here.

import os
from logging import *
import coloredlogs


logging_level = DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
logging_format = "%(asctime)s.%(msecs)03d\t%(levelname)s\t%(message)s"  # if wanted, adjust the log output format
logging_dateformat = "%Y-%m-%d\t%H:%M:%S"
writing_mode = 'a'  # 'w' = (over)write -> didn't work properly?, 'a' = append


class bat_data_logger:
    def __init__(self, filename):
        self.filename = filename

        directory = os.path.dirname(self.filename)
        if not os.path.exists(directory):
            os.mkdir(directory)

        # Create a logger
        self.log = getLogger(__name__)
        self.log.setLevel(logging_level)

        # Formatter
        coloredFormatter = coloredlogs.ColoredFormatter(
            fmt='%(message)s',
            level_styles=dict(
                debug=dict(color='white'),
                info=dict(color='blue'),
                warning=dict(color='yellow', bright=True),
                error=dict(color='red', bold=True, bright=True),
                critical=dict(color='black', bold=True, background='red'),
            ),
            field_styles=dict(
                name=dict(color='white'),
                asctime=dict(color='white'),
                funcName=dict(color='white'),
                lineno=dict(color='white'),
            )
        )

        # stdout logger
        self.stdout_handler = StreamHandler()
        self.stdout_handler.setLevel(logging_level)
        self.stdout_handler.setFormatter(coloredFormatter)

        # file logger
        self.file_handler = FileHandler(self.filename, mode=writing_mode)
        self.file_handler.setLevel(logging_level)
        self.file_handler.setFormatter(Formatter(fmt=logging_format, datefmt=logging_dateformat))

        # add handlers
        self.log.addHandler(self.stdout_handler)
        self.log.addHandler(self.file_handler)
