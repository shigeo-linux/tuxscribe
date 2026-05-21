import os
import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib


FORMATS = [
    ('epub', 'EPUB', '.epub', 'Best for e-readers (Kindle, Kobo, etc.)'),
    ('docx', 'DOCX', '.docx', 'Microsoft Word / LibreOffice'),
    ('pdf',  'PDF',  '.pdf',  'Print-ready PDF with formatting'),
]


class ExportView(Gtk.Box):
    def __init__(self, db):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self.project_id = None
        self._exporting = False
        self._build_ui()

    def _build_ui(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        inner.set_border_width(28)
        scroll.add(inner)
        self.pack_start(scroll, True, True, 0)

        # ── Book metadata ──────────────────────────────────────────
        meta_frame = Gtk.Frame(label=" Book Metadata ")
        meta_inner = Gtk.Grid()
        meta_inner.set_column_spacing(12)
        meta_inner.set_row_spacing(8)
        meta_inner.set_border_width(14)
        meta_frame.add(meta_inner)

        meta_inner.attach(Gtk.Label(label="Title", xalign=1), 0, 0, 1, 1)
        self.title_entry = Gtk.Entry()
        self.title_entry.set_hexpand(True)
        self.title_entry.set_placeholder_text("Book title")
        meta_inner.attach(self.title_entry, 1, 0, 1, 1)

        meta_inner.attach(Gtk.Label(label="Author", xalign=1), 0, 1, 1, 1)
        self.author_entry = Gtk.Entry()
        self.author_entry.set_placeholder_text("Author name")
        meta_inner.attach(self.author_entry, 1, 1, 1, 1)

        inner.pack_start(meta_frame, False, False, 0)

        # ── Stats ──────────────────────────────────────────────────
        self.stats_label = Gtk.Label(xalign=0)
        self.stats_label.get_style_context().add_class('dim-label')
        inner.pack_start(self.stats_label, False, False, 0)

        # ── Format selection ───────────────────────────────────────
        fmt_frame = Gtk.Frame(label=" Export Format ")
        fmt_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        fmt_inner.set_border_width(14)
        fmt_frame.add(fmt_inner)

        self._fmt_radios = {}
        first_btn = None
        for key, label, ext, desc in FORMATS:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            rb = Gtk.RadioButton.new_with_label_from_widget(first_btn, label)
            rb.set_tooltip_text(desc)
            if first_btn is None:
                first_btn = rb
            self._fmt_radios[key] = rb
            row.pack_start(rb, False, False, 0)
            desc_label = Gtk.Label(label=desc)
            desc_label.get_style_context().add_class('dim-label')
            desc_label.set_xalign(0)
            row.pack_start(desc_label, False, False, 0)
            fmt_inner.pack_start(row, False, False, 0)

        inner.pack_start(fmt_frame, False, False, 0)

        # ── Output path ────────────────────────────────────────────
        path_frame = Gtk.Frame(label=" Save Location ")
        path_inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        path_inner.set_border_width(14)
        path_frame.add(path_inner)

        self.path_entry = Gtk.Entry()
        self.path_entry.set_hexpand(True)
        self.path_entry.set_text(os.path.expanduser('~/Documents'))
        path_inner.pack_start(self.path_entry, True, True, 0)

        browse_btn = Gtk.Button(label="Browse…")
        browse_btn.connect('clicked', self._on_browse)
        path_inner.pack_start(browse_btn, False, False, 0)

        inner.pack_start(path_frame, False, False, 0)

        # ── Options ────────────────────────────────────────────────
        opts_frame = Gtk.Frame(label=" Options ")
        opts_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        opts_inner.set_border_width(14)
        opts_frame.add(opts_inner)

        self.refs_check = Gtk.CheckButton(label="Include References page (lists imported sources)")
        self.refs_check.set_active(True)
        opts_inner.pack_start(self.refs_check, False, False, 0)

        inner.pack_start(opts_frame, False, False, 0)

        # ── Export button & status ─────────────────────────────────
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        self.export_btn = Gtk.Button(label="Export Manuscript")
        self.export_btn.get_style_context().add_class('action-btn')
        self.export_btn.connect('clicked', self._on_export)
        self.export_btn.set_sensitive(False)
        action_box.pack_start(self.export_btn, False, False, 0)

        self.spinner = Gtk.Spinner()
        action_box.pack_start(self.spinner, False, False, 0)

        inner.pack_start(action_box, False, False, 0)

        self.status_label = Gtk.Label(xalign=0)
        self.status_label.set_line_wrap(True)
        inner.pack_start(self.status_label, False, False, 0)


    def load_project(self, project_id):
        self.project_id = project_id
        proj = self.db.get_project(project_id)
        if proj:
            self.title_entry.set_text(proj['name'] or '')

        self._update_stats()
        self.export_btn.set_sensitive(True)
        self.status_label.set_text('')

    def _update_stats(self):
        if not self.project_id:
            self.stats_label.set_text('')
            return
        chapters = self.db.get_chapters(self.project_id)
        with_content = [c for c in chapters if (c['content'] or '').strip()]
        total_words = sum(
            len((c['content'] or '').split()) for c in with_content
        )
        self.stats_label.set_text(
            f"{len(chapters)} chapters total · "
            f"{len(with_content)} with content · "
            f"{total_words:,} words"
        )

    def _get_selected_format(self):
        for key, rb in self._fmt_radios.items():
            if rb.get_active():
                return key
        return 'epub'

    def _on_browse(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="Choose export folder",
            transient_for=self.get_toplevel(),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )
        current = self.path_entry.get_text()
        if os.path.isdir(current):
            dialog.set_current_folder(current)

        resp = dialog.run()
        folder = dialog.get_filename()
        dialog.destroy()

        if resp == Gtk.ResponseType.OK and folder:
            self.path_entry.set_text(folder)

    def _on_export(self, btn):
        if self._exporting or not self.project_id:
            return

        title = self.title_entry.get_text().strip() or 'Untitled'
        author = self.author_entry.get_text().strip()
        fmt = self._get_selected_format()
        folder = self.path_entry.get_text().strip()

        if not os.path.isdir(folder):
            self._set_status(f'Folder not found: {folder}', error=True)
            return

        ext = {k: e for k, _, e, _ in FORMATS}[fmt]
        safe_title = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in title)
        filename = f'{safe_title}{ext}'
        output_path = os.path.join(folder, filename)

        chapters = [
            dict(c) for c in self.db.get_chapters(self.project_id)
            if (c['content'] or '').strip()
        ]

        if not chapters:
            self._set_status('No chapters with content to export.', error=True)
            return

        include_refs = self.refs_check.get_active()
        sources = []
        if include_refs:
            sources = [dict(r) for r in self.db.get_sources_for_references(self.project_id)]

        self._exporting = True
        self.export_btn.set_sensitive(False)
        self.spinner.start()
        self._set_status('Exporting…')

        def run():
            try:
                import importlib
                import exporter
                importlib.reload(exporter)
                if fmt == 'epub':
                    exporter.export_epub(chapters, title, author, output_path, sources=sources)
                elif fmt == 'docx':
                    exporter.export_docx(chapters, title, author, output_path, sources=sources)
                elif fmt == 'pdf':
                    exporter.export_pdf(chapters, title, author, output_path, sources=sources)
                GLib.idle_add(self._on_export_done, output_path)
            except Exception as e:
                GLib.idle_add(self._on_export_error, str(e))

        threading.Thread(target=run, daemon=True).start()

    def _on_export_done(self, output_path):
        self._exporting = False
        self.spinner.stop()
        self.export_btn.set_sensitive(True)
        self._set_status(f'✓ Saved to {output_path}', error=False)

        # Offer to open the folder
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.YES_NO,
            text='Export complete',
        )
        dialog.format_secondary_text(f'Saved to:\n{output_path}\n\nOpen folder?')
        resp = dialog.run()
        dialog.destroy()
        if resp == Gtk.ResponseType.YES:
            import subprocess
            subprocess.Popen(['xdg-open', os.path.dirname(output_path)])

    def _on_export_error(self, error_msg):
        self._exporting = False
        self.spinner.stop()
        self.export_btn.set_sensitive(True)
        self._set_status(error_msg, error=True)

    def _set_status(self, msg, error=False):
        if error:
            self.status_label.set_markup(f'<span color="red">{msg}</span>')
        else:
            self.status_label.set_markup(f'<span color="#444">{msg}</span>')
