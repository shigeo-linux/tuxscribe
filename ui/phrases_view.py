import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


class PhrasesView(Gtk.Box):
    def __init__(self, db):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_border_width(8)
        self.pack_start(toolbar, False, False, 0)
        toolbar.pack_start(Gtk.Label(label="Phrases to Avoid", xalign=0), False, False, 0)

        sep = Gtk.Separator()
        self.pack_start(sep, False, False, 0)

        # Info bar
        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        info.set_border_width(12)
        info.get_style_context().add_class('info-bar')
        info_label = Gtk.Label()
        info_label.set_markup(
            'Add words or phrases you want the AI to <b>never</b> use when writing or revising chapters. '
            'These apply to <b>all projects</b>. One phrase per entry.'
        )
        info_label.set_line_wrap(True)
        info_label.set_xalign(0)
        info.pack_start(info_label, True, True, 0)
        self.pack_start(info, False, False, 0)

        # Add phrase input row
        add_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        add_row.set_border_width(12)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text('e.g. "suddenly", "it was as if", "he smiled warmly"')
        self.entry.set_hexpand(True)
        self.entry.connect('activate', self._on_add)
        add_row.pack_start(self.entry, True, True, 0)

        add_btn = Gtk.Button(label="Add Phrase")
        add_btn.get_style_context().add_class('action-btn')
        add_btn.connect('clicked', self._on_add)
        add_row.pack_start(add_btn, False, False, 0)

        self.pack_start(add_row, False, False, 0)

        sep2 = Gtk.Separator()
        self.pack_start(sep2, False, False, 0)

        # Phrase list
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.set_placeholder(self._make_placeholder())
        scroll.add(self.listbox)
        self.pack_start(scroll, True, True, 0)

    def _make_placeholder(self):
        label = Gtk.Label()
        label.set_markup('<span color="#aaa">No phrases added yet</span>')
        label.set_margin_top(24)
        label.show()
        return label

    def load_project(self, project_id):
        pass  # phrases are global — no per-project loading needed

    def _refresh(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        for row in self.db.get_excluded_phrases():
            self.listbox.add(self._make_row(row['id'], row['phrase']))

        self.listbox.show_all()

    def _make_row(self, phrase_id, phrase):
        row = Gtk.ListBoxRow()
        row.get_style_context().add_class('chapter-row')

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_border_width(4)

        label = Gtk.Label(label=phrase, xalign=0)
        label.set_hexpand(True)
        box.pack_start(label, True, True, 0)

        del_btn = Gtk.Button(label="Remove")
        del_btn.get_style_context().add_class('danger-btn')
        del_btn.connect('clicked', self._on_remove, phrase_id)
        box.pack_end(del_btn, False, False, 0)

        row.add(box)
        return row

    def _on_add(self, widget):
        phrase = self.entry.get_text().strip()
        if not phrase:
            return
        self.db.add_excluded_phrase(phrase)
        self.entry.set_text('')
        self._refresh()

    def _on_remove(self, btn, phrase_id):
        self.db.delete_excluded_phrase(phrase_id)
        self._refresh()
