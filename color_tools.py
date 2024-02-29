# Various helper functions related to colors (e.g., for plots).

import re
import numpy as np
from plotly.express.colors import sample_colorscale


re_pat_color_rgb = re.compile(f"rgb\((\d+),\s?(\d+),\s?(\d+)\)")
re_pat_color_css = re.compile(f"#([0-9a-fA-F][0-9a-fA-F])([0-9a-fA-F][0-9a-fA-F])([0-9a-fA-F][0-9a-fA-F])")


def get_aged_color(i, i_max):
    ratio = i / i_max
    return sample_colorscale('Viridis', ratio)[0]


def get_aged_colors(i_max):
    return sample_colorscale('Viridis', np.linspace(0, 1, i_max))


def generate_fault_cm(original_cm, fault_color, fault_color_factor):
    new_cm = original_cm.copy()
    for i in range(0, len(original_cm)):
        # print(original_cm[i])
        old_color = get_rgb_from_css(original_cm[i])
        new_color = fault_color + (1.0 - fault_color_factor) * old_color
        new_cm[i] = get_css_from_rgb(new_color)
    return new_cm


def get_rgb_from_css(css_string):
    re_match = re_pat_color_css.fullmatch(css_string)
    if re_match:
        return np.array([int(re_match.group(1), base=16),  # r
                         int(re_match.group(2), base=16),  # g
                         int(re_match.group(3), base=16)])  # b
    return np.array([127, 127, 127])  # error


def get_css_from_rgb(rgb):
    return f"#%02x%02x%02x" % (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def get_rgb(rgb_string):
    re_match = re_pat_color_rgb.fullmatch(rgb_string)
    if re_match:
        return np.array([int(re_match.group(1)), int(re_match.group(2)), int(re_match.group(3))])  # r, g, b
    return np.array([127, 127, 127])  # error -> fall back to gray


def get_rgb_string(rgb):
    return f"rgb(%u,%u,%u)" % (rgb[0], rgb[1], rgb[2])
