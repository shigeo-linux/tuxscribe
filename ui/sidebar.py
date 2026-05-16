import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject


class Sidebar(Gtk.Box):
    __gsignals__ = {
        'project-selected': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        'project-deleted': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self, db):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self._project_ids = []
        self._selected_id = None
        self._row_project_map = {}  # row widget -> project_id

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

        # New Project button
        new_btn = Gtk.Button(label="+ New Project")
        new_btn.get_style_context().add_class('new-project-btn')
        new_btn.connect('clicked', self._on_new_project)
        self.pack_start(new_btn, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(sep, False, False, 0)

        # Project list
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        # activate_on_single_click fires row-activated on every single click,
        # even on an already-selected row, and never auto-fires at init time.
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect('row-activated', self._on_row_activated)
        self.listbox.get_style_context().add_class('sidebar')
        scroll.add(self.listbox)

        self.pack_start(scroll, True, True, 0)

        self.refresh()

    def refresh(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        self._project_ids = []
        self._row_project_map = {}
        projects = self.db.get_projects()

        for proj in projects:
            row = self._make_row(proj['id'], proj['name'])
            self.listbox.add(row)
            self._row_project_map[row] = proj['id']
            self._project_ids.append(proj['id'])

        self.listbox.show_all()

        # Restore visual highlight without re-emitting project-selected
        if self._selected_id and self._selected_id in self._project_ids:
            idx = self._project_ids.index(self._selected_id)
            row = self.listbox.get_row_at_index(idx)
            if row:
                self.listbox.select_row(row)

    def _make_row(self, project_id, name):
        row = Gtk.ListBoxRow()
        row.get_style_context().add_class('project-row')

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

    def _on_new_project(self, btn):
        dialog = Gtk.Dialog(
            title="New Project",
            transient_for=self.get_toplevel(),
            modal=True,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.set_default_size(380, 160)

        box = dialog.get_content_area()
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        inner.set_border_width(16)
        box.pack_start(inner, True, True, 0)

        inner.pack_start(Gtk.Label(label="Project name:", xalign=0), False, False, 0)
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

        dialog.show_all()
        response = dialog.run()
        name = entry.get_text().strip()
        project_type = 'short_story' if radio_short.get_active() else 'novel'
        dialog.destroy()

        if response == Gtk.ResponseType.OK and name:
            project_id = self.db.create_project(name, project_type)
            self._selected_id = project_id
            self.refresh()
            self.emit('project-selected', project_id)

    def _on_row_menu(self, btn, project_id, name):
        menu = Gtk.Menu()

        rename_item = Gtk.MenuItem(label="Rename")
        rename_item.connect('activate', self._on_rename, project_id)
        menu.append(rename_item)

        sep = Gtk.SeparatorMenuItem()
        menu.append(sep)

        delete_item = Gtk.MenuItem(label="Delete Project")
        delete_item.connect('activate', self._on_delete, project_id)
        menu.append(delete_item)

        menu.show_all()
        menu.popup_at_widget(btn, 3, 4, None)

    def _on_rename(self, item, project_id):
        proj = self.db.get_project(project_id)
        dialog = Gtk.Dialog(
            title="Rename Project",
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
