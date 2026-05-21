import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject

from ui.series_sources_dialog import SeriesSourcesDialog


class Sidebar(Gtk.Box):
    __gsignals__ = {
        'project-selected': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        'project-deleted': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self, db):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self._selected_id = None
        self._project_ids = []
        self._row_project_map = {}   # ListBoxRow -> project_id
        self._api_client = None      # set by main_window after creation

        self.get_style_context().add_class('sidebar')

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        header.get_style_context().add_class('sidebar-header')

        title = Gtk.Label(label="Tuxscribe")
        title.get_style_context().add_class('sidebar-title')
        title.set_xalign(0)
        header.pack_start(title, False, False, 0)

        tagline = Gtk.Label(label="your writing companion")
        tagline.get_style_context().add_class('dim-label')
        tagline.set_xalign(0)
        header.pack_start(tagline, False, False, 0)

        self.pack_start(header, False, False, 0)

        # Buttons row
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.set_border_width(8)

        new_proj_btn = Gtk.Button(label="+ New Book")
        new_proj_btn.get_style_context().add_class('new-project-btn')
        new_proj_btn.connect('clicked', self._on_new_project)
        btn_box.pack_start(new_proj_btn, True, True, 0)

        new_series_btn = Gtk.Button(label="+ Series")
        new_series_btn.get_style_context().add_class('new-series-btn')
        new_series_btn.connect('clicked', self._on_new_series)
        btn_box.pack_start(new_series_btn, False, False, 0)

        self.pack_start(btn_box, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(sep, False, False, 0)

        # Project/series list
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect('row-activated', self._on_row_activated)
        self.listbox.get_style_context().add_class('sidebar')
        scroll.add(self.listbox)

        self.pack_start(scroll, True, True, 0)

        self.refresh()

    def set_api_client(self, api_client):
        self._api_client = api_client

    def refresh(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        self._project_ids = []
        self._row_project_map = {}

        # Series groups first
        for series in self.db.get_series():
            self._add_series_header(series['id'], series['name'])
            for proj in self.db.get_series_projects(series['id']):
                row = self._make_project_row(proj['id'], proj['name'], indented=True)
                self.listbox.add(row)
                self._row_project_map[row] = proj['id']
                self._project_ids.append(proj['id'])
            add_row = self._make_add_book_row(series['id'])
            self.listbox.add(add_row)

        # Standalone projects
        standalone = self.db.get_projects_without_series()
        if standalone:
            if self.db.get_series():
                sep_row = Gtk.ListBoxRow()
                sep_row.set_selectable(False)
                sep_row.set_activatable(False)
                sep_row.add(Gtk.Separator())
                sep_row.get_style_context().add_class('sidebar-separator-row')
                self.listbox.add(sep_row)
            for proj in standalone:
                row = self._make_project_row(proj['id'], proj['name'], indented=False)
                self.listbox.add(row)
                self._row_project_map[row] = proj['id']
                self._project_ids.append(proj['id'])

        self.listbox.show_all()

        if self._selected_id and self._selected_id in self._project_ids:
            idx = self._project_ids.index(self._selected_id)
            for row, pid in self._row_project_map.items():
                if pid == self._selected_id:
                    self.listbox.select_row(row)
                    break

    def _add_series_header(self, series_id, name):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        row.get_style_context().add_class('series-header-row')

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.set_border_width(4)

        label = Gtk.Label(xalign=0)
        label.set_markup(f'<span size="small" weight="bold">{GLib_escape(name)}</span>')
        label.set_ellipsize(3)
        label.set_hexpand(True)
        box.pack_start(label, True, True, 0)

        menu_btn = Gtk.Button()
        menu_btn.set_relief(Gtk.ReliefStyle.NONE)
        menu_btn.set_image(
            Gtk.Image.new_from_icon_name('view-more-symbolic', Gtk.IconSize.MENU)
        )
        menu_btn.connect('clicked', self._on_series_menu, series_id, name)
        box.pack_end(menu_btn, False, False, 0)

        row.add(box)
        self.listbox.add(row)

    def _make_add_book_row(self, series_id):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        row._add_series_id = series_id
        row.get_style_context().add_class('add-book-row')

        btn = Gtk.Button(label="+ Add Book")
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.get_style_context().add_class('add-book-btn')
        btn.connect('clicked', lambda b: self._on_new_project(b, series_id=series_id))
        row.add(btn)
        return row

    def _make_project_row(self, project_id, name, indented):
        row = Gtk.ListBoxRow()
        row.get_style_context().add_class('project-row')
        if indented:
            row.get_style_context().add_class('book-row-indented')

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        label = Gtk.Label(label=name, xalign=0)
        label.set_ellipsize(3)
        label.get_style_context().add_class('project-name-label')
        box.pack_start(label, True, True, 0)

        menu_btn = Gtk.Button()
        menu_btn.set_relief(Gtk.ReliefStyle.NONE)
        menu_btn.set_image(
            Gtk.Image.new_from_icon_name('view-more-symbolic', Gtk.IconSize.MENU)
        )
        menu_btn.connect('clicked', self._on_row_menu, project_id, name)
        box.pack_end(menu_btn, False, False, 0)

        row.add(box)
        return row

    def _on_row_activated(self, listbox, row):
        project_id = self._row_project_map.get(row)
        if project_id is not None:
            self._selected_id = project_id
            self.emit('project-selected', project_id)

    # ── Series dialogs ────────────────────────────────────────────

    def _on_new_series(self, btn):
        dialog = Gtk.Dialog(
            title="New Series",
            transient_for=self.get_toplevel(),
            modal=True,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.set_default_size(360, 140)

        box = dialog.get_content_area()
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        inner.set_border_width(16)
        box.pack_start(inner, True, True, 0)

        inner.pack_start(Gtk.Label(label="Series name:", xalign=0), False, False, 0)
        entry = Gtk.Entry()
        entry.set_activates_default(True)
        entry.set_placeholder_text("e.g. The Forgotten Shore Series")
        inner.pack_start(entry, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        name = entry.get_text().strip()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and name:
            self.db.create_series(name)
            self.refresh()

    def _on_series_menu(self, btn, series_id, name):
        menu = Gtk.Menu()

        rename_item = Gtk.MenuItem(label="Rename Series")
        rename_item.connect('activate', self._on_rename_series, series_id)
        menu.append(rename_item)

        sources_item = Gtk.MenuItem(label="Series Sources…")
        sources_item.connect('activate', self._on_series_sources, series_id)
        menu.append(sources_item)

        menu.append(Gtk.SeparatorMenuItem())

        delete_item = Gtk.MenuItem(label="Delete Series")
        delete_item.connect('activate', self._on_delete_series, series_id, name)
        menu.append(delete_item)

        menu.show_all()
        menu.popup_at_widget(btn, 3, 4, None)

    def _on_rename_series(self, item, series_id):
        s = self.db.get_series_by_id(series_id)
        dialog = Gtk.Dialog(
            title="Rename Series",
            transient_for=self.get_toplevel(),
            modal=True,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        dialog.set_default_response(Gtk.ResponseType.OK)

        box = dialog.get_content_area()
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.set_border_width(16)
        box.pack_start(inner, True, True, 0)

        inner.pack_start(Gtk.Label(label="New name:", xalign=0), False, False, 0)
        entry = Gtk.Entry()
        entry.set_text(s['name'])
        entry.set_activates_default(True)
        inner.pack_start(entry, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        new_name = entry.get_text().strip()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and new_name:
            self.db.rename_series(series_id, new_name)
            self.refresh()

    def _on_series_sources(self, item, series_id):
        s = self.db.get_series_by_id(series_id)
        dlg = SeriesSourcesDialog(
            self.get_toplevel(),
            self.db,
            self._api_client,
            series_id,
            s['name'],
        )
        dlg.run()
        dlg.destroy()

    def _on_delete_series(self, item, series_id, name):
        books = self.db.get_series_projects(series_id)
        secondary = (
            f"This series contains {len(books)} book(s). They will become standalone projects."
            if books else
            "The series will be permanently deleted."
        )
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f'Delete series "{name}"?',
        )
        dialog.format_secondary_text(secondary)
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            self.db.delete_series(series_id)
            self.refresh()

    # ── Project dialogs ───────────────────────────────────────────

    def _on_new_project(self, btn, series_id=None):
        dialog = Gtk.Dialog(
            title="New Book",
            transient_for=self.get_toplevel(),
            modal=True,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.set_default_size(400, -1)

        box = dialog.get_content_area()
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        inner.set_border_width(16)
        box.pack_start(inner, True, True, 0)

        inner.pack_start(Gtk.Label(label="Book title:", xalign=0), False, False, 0)
        entry = Gtk.Entry()
        entry.set_activates_default(True)
        entry.set_placeholder_text("e.g. The Forgotten Shore")
        inner.pack_start(entry, False, False, 0)

        inner.pack_start(Gtk.Label(label="Project type:", xalign=0), False, False, 0)
        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        radio_novel = Gtk.RadioButton.new_with_label(None, "Chapter Book / Novel")
        radio_short = Gtk.RadioButton.new_with_label_from_widget(radio_novel, "Short Story")
        type_box.pack_start(radio_novel, False, False, 0)
        type_box.pack_start(radio_short, False, False, 0)
        inner.pack_start(type_box, False, False, 0)

        # Series picker
        all_series = self.db.get_series()
        series_combo = None
        series_ids = []
        if all_series:
            inner.pack_start(Gtk.Label(label="Add to series:", xalign=0), False, False, 0)
            series_combo = Gtk.ComboBoxText()
            series_combo.append_text("(No series — standalone)")
            series_ids = [None]
            for s in all_series:
                series_combo.append_text(s['name'])
                series_ids.append(s['id'])
            # Pre-select the series if called from an Add Book button
            if series_id is not None and series_id in series_ids:
                series_combo.set_active(series_ids.index(series_id))
            else:
                series_combo.set_active(0)
            inner.pack_start(series_combo, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        name = entry.get_text().strip()
        project_type = 'short_story' if radio_short.get_active() else 'novel'

        chosen_series_id = series_id  # default: whatever was passed in
        if series_combo is not None:
            idx = series_combo.get_active()
            if idx >= 0:
                chosen_series_id = series_ids[idx]

        dialog.destroy()

        if response == Gtk.ResponseType.OK and name:
            project_id = self.db.create_project(name, project_type, chosen_series_id)
            self._selected_id = project_id
            self.refresh()
            self.emit('project-selected', project_id)

    def _on_row_menu(self, btn, project_id, name):
        proj = self.db.get_project(project_id)
        menu = Gtk.Menu()

        rename_item = Gtk.MenuItem(label="Rename")
        rename_item.connect('activate', self._on_rename, project_id)
        menu.append(rename_item)

        all_series = self.db.get_series()
        if all_series:
            if proj['series_id']:
                move_item = Gtk.MenuItem(label="Remove from Series")
                move_item.connect('activate', lambda i: self._move_to_series(project_id, None))
            else:
                move_item = Gtk.MenuItem(label="Move to Series…")
                move_item.connect('activate', self._on_move_to_series, project_id)
            menu.append(move_item)

        menu.append(Gtk.SeparatorMenuItem())

        delete_item = Gtk.MenuItem(label="Delete Project")
        delete_item.connect('activate', self._on_delete, project_id)
        menu.append(delete_item)

        menu.show_all()
        menu.popup_at_widget(btn, 3, 4, None)

    def _move_to_series(self, project_id, series_id):
        self.db.set_project_series(project_id, series_id)
        self.refresh()

    def _on_move_to_series(self, item, project_id):
        all_series = self.db.get_series()
        dialog = Gtk.Dialog(
            title="Move to Series",
            transient_for=self.get_toplevel(),
            modal=True,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        dialog.set_default_response(Gtk.ResponseType.OK)

        box = dialog.get_content_area()
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.set_border_width(16)
        box.pack_start(inner, True, True, 0)

        inner.pack_start(Gtk.Label(label="Select series:", xalign=0), False, False, 0)
        combo = Gtk.ComboBoxText()
        series_ids = []
        for s in all_series:
            combo.append_text(s['name'])
            series_ids.append(s['id'])
        combo.set_active(0)
        inner.pack_start(combo, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        idx = combo.get_active()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and idx >= 0:
            self._move_to_series(project_id, series_ids[idx])

    def _on_rename(self, item, project_id):
        proj = self.db.get_project(project_id)
        dialog = Gtk.Dialog(
            title="Rename Book",
            transient_for=self.get_toplevel(),
            modal=True,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        dialog.set_default_response(Gtk.ResponseType.OK)

        box = dialog.get_content_area()
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.set_border_width(16)
        box.pack_start(inner, True, True, 0)

        inner.pack_start(Gtk.Label(label="New name:", xalign=0), False, False, 0)
        entry = Gtk.Entry()
        entry.set_text(proj['name'])
        entry.set_activates_default(True)
        inner.pack_start(entry, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        new_name = entry.get_text().strip()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and new_name:
            self.db.rename_project(project_id, new_name)
            self.refresh()

    def _on_delete(self, item, project_id):
        proj = self.db.get_project(project_id)
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f'Delete "{proj["name"]}"?',
        )
        dialog.format_secondary_text(
            "This will permanently delete the project and all its content."
        )
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            if self._selected_id == project_id:
                self._selected_id = None
            self.db.delete_project(project_id)
            self.refresh()
            self.emit('project-deleted', project_id)


def GLib_escape(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
