import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

CHUNK_SIZE = 250_000  # characters per chunk (~60k tokens, safely under 128k limit)

SUMMARISE_SYSTEM = """You are a research assistant. Summarise the provided source document for a writer who will use it as research material.

Your summary should:
- Cover all key facts, arguments, events, characters, and themes
- Preserve specific names, dates, places, and details that a writer might reference
- Be comprehensive but concise — aim for 400-800 words
- Be written in clear prose, not bullet points

Return only the summary. No preamble."""

COMBINE_SYSTEM = """You are a research assistant. You are given several partial summaries of consecutive sections of the same document. Combine them into one cohesive, well-structured summary for a writer who will use it as research material.

Cover all key facts, arguments, events, characters, and themes across all sections. Preserve specific names, dates, places, and details. Aim for 600-1000 words. Return only the combined summary. No preamble."""


def extract_pdf_text(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("pypdf not installed. Run: pip3 install --user pypdf")
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return '\n\n'.join(pages)


class SourcesView(Gtk.Box):
    def __init__(self, db, api_client):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self.api_client = api_client
        self.project_id = None
        self._selected_source_id = None
        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_border_width(8)
        self.pack_start(toolbar, False, False, 0)

        toolbar.pack_start(Gtk.Label(label="Research Sources", xalign=0), False, False, 0)

        self.spinner = Gtk.Spinner()
        toolbar.pack_end(self.spinner, False, False, 0)

        self.import_btn = Gtk.Button(label="Import PDF")
        self.import_btn.get_style_context().add_class('action-btn')
        self.import_btn.connect('clicked', self._on_import)
        self.import_btn.set_sensitive(False)
        toolbar.pack_end(self.import_btn, False, False, 0)

        self.summarise_btn = Gtk.Button(label="Summarise for AI")
        self.summarise_btn.connect('clicked', self._on_summarise)
        self.summarise_btn.set_sensitive(False)
        toolbar.pack_end(self.summarise_btn, False, False, 0)

        sep = Gtk.Separator()
        self.pack_start(sep, False, False, 0)

        # Info bar
        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        info.set_border_width(12)
        info.get_style_context().add_class('info-bar')
        info_label = Gtk.Label()
        info_label.set_markup(
            'Import PDF files as research sources. The AI will read them when writing or revising chapters.'
        )
        info_label.set_line_wrap(True)
        info_label.set_xalign(0)
        info.pack_start(info_label, True, True, 0)
        self.pack_start(info, False, False, 0)

        # Split pane: source list on left, preview on right
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        self.pack_start(paned, True, True, 0)

        # Left: source list + citation form
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left.set_size_request(280, -1)

        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_scroll.set_vexpand(True)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_placeholder(self._make_placeholder())
        self.listbox.connect('row-selected', self._on_source_selected)
        list_scroll.add(self.listbox)
        left.pack_start(list_scroll, True, True, 0)

        sep_cite = Gtk.Separator()
        left.pack_start(sep_cite, False, False, 0)

        cite_frame = Gtk.Frame(label=" Reference Citation ")
        cite_frame.set_border_width(6)
        cite_grid = Gtk.Grid()
        cite_grid.set_column_spacing(8)
        cite_grid.set_row_spacing(5)
        cite_grid.set_border_width(8)
        cite_frame.add(cite_grid)

        for i, (lbl, attr) in enumerate([
            ("Title",     "cite_title_entry"),
            ("Author",    "cite_author_entry"),
            ("Year",      "cite_year_entry"),
            ("City",      "cite_city_entry"),
            ("Publisher", "cite_publisher_entry"),
        ]):
            cite_grid.attach(Gtk.Label(label=lbl, xalign=1), 0, i, 1, 1)
            entry = Gtk.Entry()
            entry.set_hexpand(True)
            entry.set_sensitive(False)
            cite_grid.attach(entry, 1, i, 1, 1)
            setattr(self, attr, entry)

        self.save_cite_btn = Gtk.Button(label="Save Citation")
        self.save_cite_btn.get_style_context().add_class('action-btn')
        self.save_cite_btn.connect('clicked', self._on_save_citation)
        self.save_cite_btn.set_sensitive(False)
        cite_grid.attach(self.save_cite_btn, 1, 5, 1, 1)

        left.pack_start(cite_frame, False, False, 0)
        paned.pack1(left, False, False)
        paned.set_position(300)

        # Right: text preview
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        preview_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        preview_header.set_border_width(8)
        self.preview_label = Gtk.Label(label="Select a source to preview", xalign=0)
        preview_header.pack_start(self.preview_label, True, True, 0)
        right.pack_start(preview_header, False, False, 0)

        sep3 = Gtk.Separator()
        right.pack_start(sep3, False, False, 0)

        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_vexpand(True)
        preview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.preview_view = Gtk.TextView()
        self.preview_view.set_editable(False)
        self.preview_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.preview_view.set_left_margin(16)
        self.preview_view.set_right_margin(16)
        self.preview_view.set_top_margin(12)
        self.preview_view.set_bottom_margin(12)
        self.preview_buf = self.preview_view.get_buffer()
        preview_scroll.add(self.preview_view)
        right.pack_start(preview_scroll, True, True, 0)

        paned.pack2(right, True, True)

    def _make_placeholder(self):
        label = Gtk.Label()
        label.set_markup('<span color="#aaa">No sources imported</span>')
        label.set_margin_top(24)
        label.show()
        return label

    def load_project(self, project_id):
        self.project_id = project_id
        self.import_btn.set_sensitive(True)
        self.preview_buf.set_text('')
        self.preview_label.set_text("Select a source to preview")
        self._refresh()

    def _refresh(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        if not self.project_id:
            return

        for row in self.db.get_sources(self.project_id):
            self.listbox.add(self._make_row(row['id'], row['filename']))

        self.listbox.show_all()

    def _make_row(self, source_id, filename):
        row = Gtk.ListBoxRow()
        row.source_id = source_id
        row.get_style_context().add_class('chapter-row')

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_border_width(6)

        label = Gtk.Label(label=os.path.basename(filename), xalign=0)
        label.set_ellipsize(3)
        label.set_hexpand(True)
        box.pack_start(label, True, True, 0)

        del_btn = Gtk.Button(label="Remove")
        del_btn.get_style_context().add_class('danger-btn')
        del_btn.connect('clicked', self._on_remove, source_id)
        box.pack_end(del_btn, False, False, 0)

        row.add(box)
        return row

    def _on_source_selected(self, listbox, row):
        if row is None:
            self._selected_source_id = None
            self.summarise_btn.set_sensitive(False)
            self.save_cite_btn.set_sensitive(False)
            for entry in (self.cite_title_entry, self.cite_author_entry,
                          self.cite_year_entry, self.cite_city_entry, self.cite_publisher_entry):
                entry.set_text('')
                entry.set_sensitive(False)
            self.preview_buf.set_text('')
            self.preview_label.set_text("Select a source to preview")
            return
        self._selected_source_id = row.source_id
        self.summarise_btn.set_sensitive(True)
        self._show_preview(row.source_id)

    def _show_preview(self, source_id):
        sources = self.db.get_all_source_content(self.project_id)
        for r in sources:
            if r['id'] == source_id:
                summary = r['summary'] or ''
                content = r['content']
                if summary:
                    display = f"=== AI SUMMARY ===\n\n{summary}\n\n=== FULL TEXT ===\n\n{content}"
                    self.preview_label.set_markup(f"<b>{r['filename']}</b>  <span color='green'>✓ summarised</span>")
                else:
                    display = content
                    self.preview_label.set_markup(f"<b>{r['filename']}</b>  <span color='#aaa'>not yet summarised</span>")
                self.preview_buf.set_text(display)

                # Populate citation fields
                self.cite_title_entry.set_text(r['cite_title'] or '')
                self.cite_author_entry.set_text(r['cite_author'] or '')
                self.cite_year_entry.set_text(r['cite_year'] or '')
                self.cite_city_entry.set_text(r['cite_city'] or '')
                self.cite_publisher_entry.set_text(r['cite_publisher'] or '')
                for entry in (self.cite_title_entry, self.cite_author_entry,
                              self.cite_year_entry, self.cite_city_entry, self.cite_publisher_entry):
                    entry.set_sensitive(True)
                self.save_cite_btn.set_sensitive(True)
                break

    def _on_save_citation(self, btn):
        if not self._selected_source_id:
            return
        self.db.save_source_citation(
            self._selected_source_id,
            self.cite_title_entry.get_text().strip(),
            self.cite_author_entry.get_text().strip(),
            self.cite_year_entry.get_text().strip(),
            self.cite_publisher_entry.get_text().strip(),
            self.cite_city_entry.get_text().strip(),
        )

    def _on_summarise(self, btn):
        if not self._selected_source_id:
            return
        content = self.db.get_source_content(self._selected_source_id)
        self.summarise_btn.set_sensitive(False)
        self.import_btn.set_sensitive(False)
        self.spinner.start()

        self._chunks = [content[i:i + CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE)]
        self._chunk_summaries = []
        self._summarise_source_id = self._selected_source_id
        self._process_next_chunk()

    def _process_next_chunk(self):
        idx = len(self._chunk_summaries)
        total = len(self._chunks)

        if idx >= total:
            if total == 1:
                self._finalise_summary(self._chunk_summaries[0])
            else:
                self._combine_chunk_summaries()
            return

        self.preview_label.set_text(
            f"Summarising part {idx + 1} of {total}…" if total > 1 else "Summarising…"
        )
        self.api_client.complete_async(
            messages=[{'role': 'user', 'content': f"Summarise this section of a document:\n\n{self._chunks[idx]}"}],
            system=SUMMARISE_SYSTEM,
            on_done=self._on_chunk_done,
            on_error=self._on_summarise_error,
        )

    def _on_chunk_done(self, summary):
        self._chunk_summaries.append(summary)
        self._process_next_chunk()

    def _combine_chunk_summaries(self):
        self.preview_label.set_text("Combining summaries…")
        combined = '\n\n---\n\n'.join(
            f"Part {i + 1}:\n{s}" for i, s in enumerate(self._chunk_summaries)
        )
        self.api_client.complete_async(
            messages=[{'role': 'user', 'content': f"Combine these partial summaries into one:\n\n{combined}"}],
            system=COMBINE_SYSTEM,
            on_done=self._finalise_summary,
            on_error=self._on_summarise_error,
        )

    def _finalise_summary(self, summary):
        self.spinner.stop()
        self.import_btn.set_sensitive(True)
        self.db.save_source_summary(self._summarise_source_id, summary)
        if self._selected_source_id == self._summarise_source_id:
            self.summarise_btn.set_sensitive(True)
            self._show_preview(self._summarise_source_id)

    def _on_summarise_error(self, error_msg):
        self.spinner.stop()
        self.import_btn.set_sensitive(True)
        self.summarise_btn.set_sensitive(True)
        self.preview_label.set_text("Summarisation failed")
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Could not summarise source",
        )
        dialog.format_secondary_text(error_msg)
        dialog.run()
        dialog.destroy()

    def _on_import(self, btn):
        if not self.project_id:
            return

        dialog = Gtk.FileChooserDialog(
            title="Import PDF",
            transient_for=self.get_toplevel(),
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )
        dialog.set_select_multiple(True)

        f = Gtk.FileFilter()
        f.set_name("PDF files")
        f.add_mime_type("application/pdf")
        f.add_pattern("*.pdf")
        dialog.add_filter(f)

        response = dialog.run()
        filenames = dialog.get_filenames()
        dialog.destroy()

        if response != Gtk.ResponseType.OK or not filenames:
            return

        errors = []
        for path in filenames:
            try:
                content = extract_pdf_text(path)
                if not content.strip():
                    errors.append(f"{os.path.basename(path)}: no text could be extracted (may be a scanned image PDF)")
                    continue
                self.db.add_source(self.project_id, os.path.basename(path), content)
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")

        self._refresh()

        if errors:
            msg = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text="Some files could not be imported",
            )
            msg.format_secondary_text('\n'.join(errors))
            msg.run()
            msg.destroy()

    def _on_remove(self, btn, source_id):
        self.db.delete_source(source_id)
        self.preview_buf.set_text('')
        self.preview_label.set_text("Select a source to preview")
        self._refresh()
