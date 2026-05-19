#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import GLib, Gdk, Gtk, Gio

GLib.set_prgname('com.tuxscribe.app')
Gdk.set_program_class('com.tuxscribe.app')

from ui.main_window import MainWindow


class BookmothApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id='com.tuxscribe.app',
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )

    def do_activate(self):
        existing = self.get_windows()
        if existing:
            existing[0].present()
            return
        win = MainWindow(self)
        win.show_all()


def main():
    app = BookmothApp()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
