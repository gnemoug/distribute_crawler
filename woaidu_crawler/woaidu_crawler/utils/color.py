#!/usr/bin/python
#-*- coding:utf-8 -*-
"""
    Sets up the terminal color scheme.
"""

import os
import sys

from woaidu_crawler.utils import termcolors

def supports_color():
    """
    Returns True if the running system's terminal supports color, and False
    otherwise.
    """
    unsupported_platform = (sys.platform in ('win32', 'Pocket PC'))
    # isatty is not always implemented, #6223.
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    #sys.stdout:File objects corresponding to the interpreter’s standard output,
    #isatty():判断file obj是否链接到了一个tty(终端)设备上
    if unsupported_platform or not is_a_tty:
        return False
    return True

def color_style():
    """Returns a Style object with the  color scheme."""
    if not supports_color():
        style = no_style()
    else:
        SPIDER_COLORS = os.environ.get('SPIDER_COLORS', '')
        #返回默认的palette,DARK_PALETTE
        color_settings = termcolors.parse_color_setting(SPIDER_COLORS)
        if color_settings:
            class dummy: pass
            style = dummy()
            # The nocolor palette has all available roles.
            # Use that pallete as the basis for populating
            # the palette as defined in the environment.
            for role in termcolors.PALETTES[termcolors.NOCOLOR_PALETTE]:
                format = color_settings.get(role,{})
                setattr(style, role, termcolors.make_style(**format))
            # For backwards compatibility,
            # set style for ERROR_OUTPUT == ERROR
            style.ERROR_OUTPUT = style.ERROR
        else:
            style = no_style()
    return style

def no_style():
    """Returns a Style object that has no colors."""
    class dummy:
        def __getattr__(self, attr):
            return lambda x: x
    return dummy()
