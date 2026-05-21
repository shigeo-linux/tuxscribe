import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ui.sources_view import extract_pdf_text, SUMMARISE_SYSTEM, COMBINE_SYSTEM, CHUNK_SIZE


class SeriesSourcesDialog(Gtk.Dialog):
    def __init__(self, parent, db, api_client, series_id, series_name):
        super().__init__(
            title=f"Series Sources — {series_name}",
            transient_for=parent,
            modal=True,
        )
        self.db = db
        self.api_client = api_client
        self.series_id = series_id
        self.series_name = series_name
        self._selected_source_id = None

        self.set_default_size(900, 600)
        self.add_button("Close", Gtk.ResponseType.CLOSE)

        content = self.get_content_area()
        content.set_spacing(0)

        # Info bar
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        info_box.set_border_width(10)
        info_box.get_style_context().add_class('info-bar')
        info_label = Gtk.Label()
        info_label.set_markup(
            'Series sources (series bible, character sheets, world-building) are available '
            'to the AI in <b>every book</b> in this series.'
        )
        info_label.set_line_wrap(True)
        info_label.set_xalign(0)
        info_box.pack_start(info_label, True, True, 0)
        content.pack_start(info_box, False, False, 0)

        content.pack_start(Gtk.Separator(), False, False, 0)

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_border_width(8)

        self.spinner = Gtk.Spinner()
        toolbar.pack_end(self.spinner, False, False, 0)

        self.import_btn = Gtk.Button(label="Import PDF")
        self.import_btn.get_style_context().add_class('action-btn')
        self.import_btn.connect('clicked', self._on_import)
        toolbar.pack_end(self.import_btn, False, False, 0)

        self.summarise_btn = Gtk.Button(label="Summarise for AI")
        self.summarise_btn.connect('clicked', self._on_summarise)
        self.summarise_btn.set_sensitive(False)
        toolbar.pack_end(self.summarise_btn, False, False, 0)

        content.pack_start(toolbar, False, False, 0)
        content.pack_start(Gtk.Separator(), False, False, 0)

        # Split pane
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        content.pack_start(paned, True, True, 0)

        # Left: source list
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left.set_size_request(260, -1)

        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_scroll.set_vexpand(True)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_placeholder(self._make_placeholder())
        self.listbox.connect('row-selected', self._on_source_selected)
        list_scroll.add(self.listbox)
        left.pack_start(list_scroll, True, True, 0)

        paned.pack1(left, False, False)
        paned.set_position(280)

        # Right: preview
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        preview_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        preview_header.set_border_width(8)
        self.preview_label = Gtk.Label(label="Select a source to preview", xalign=0)
        preview_header.pack_start(self.preview_label, True, True, 0)
        right.pack_start(preview_header, False, False, 0)
        right.pack_start(Gtk.Separator(), False, False, 0)

        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_vexpand(True)
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

        self._refresh()
        self.show_all()

    def _make_placeholder(self):
        label = Gtk.Label()
        label.set_markup('<span color="#aaa">No sources imported</span>')
        label.set_margin_top(24)
        label.show()
        return label

    def _refresh(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        for row in self.db.get_series_sources(self.series_id):
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
            self.preview_buf.set_text('')
            self.preview_label.set_text("Select a source to preview")
            return
        self._selected_source_id = row.source_id
        self.summarise_btn.set_sensitive(True)
        self._show_preview(row.source_id)

    def _show_preview(self, source_id):
        for r in self.db.get_all_series_source_content(self.series_id):
            if r['id'] == source_id:
                summary = r['summary'] or ''
                content = r['content']
                if summary:
                    display = f"=== AI SUMMARY ===\n\n{summary}\n\n=== FULL TEXT ===\n\n{content}"
                    self.preview_label.set_markup(
                        f"<b>{r['filename']}</b>  <span color='green'>✓ summarised</span>"
                    )
                else:
                    display = content
                    self.preview_label.set_markup(
                        f"<b>{r['filename']}</b>  <span color='#aaa'>not yet summarised</span>"
                    )
                self.preview_buf.set_text(display)
                break

    def _on_import(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="Import PDF",
            transient_for=self,
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
                    errors.append(f"{os.path.basename(path)}: no text could be extracted")
                    continue
                self.db.add_series_source(self.series_id, os.path.basename(path), content)
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")

        self._refresh()

        if errors:
            msg = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text="Some files could not be imported",
            )
            msg.format_secondary_text('\n'.join(errors))
            msg.run()
            msg.destroy()

    def _on_summarise(self, btn):
        if not self._selected_source_id:
            return
        content = self.db.get_series_source_content(self._selected_source_id)
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
        self.db.save_series_source_summary(self._summarise_source_id, summary)
        if self._selected_source_id == self._summarise_source_id:
            self.summarise_btn.set_sensitive(True)
            self._show_preview(self._summarise_source_id)

    def _on_summarise_error(self, error_msg):
        self.spinner.stop()
        self.import_btn.set_sensitive(True)
        self.summarise_btn.set_sensitive(True)
        self.preview_label.set_text("Summarisation failed")
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Could not summarise source",
        )
        dialog.format_secondary_text(error_msg)
        dialog.run()
        dialog.destroy()

    def _on_remove(self, btn, source_id):
        self.db.delete_series_source(source_id)
        self.preview_buf.set_text('')
        self.preview_label.set_text("Select a source to preview")
        self._refresh()
