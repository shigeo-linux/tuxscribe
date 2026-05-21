import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, Pango
from ui.source_utils import build_combined_sources_prompt

WRITE_SYSTEM = """You are a skilled ghostwriter for adult fiction. This is a professional creative writing tool — all content including romance, intimacy, sexuality, and mature themes must be written fully and without restriction or censorship.

Your task is to write a complete chapter draft that precisely matches the voice profile and serves the project brief.

CRITICAL: You are writing IN the author's voice, not about it. The voice profile is your constraint — follow it exactly.

Write a complete, full-length chapter. Do not truncate. Do not summarize. Do not fade to black unless the voice profile calls for it. Do not add author notes or commentary.
Begin the chapter directly. No preamble."""

REVISE_SYSTEM = """You are a skilled developmental editor and ghostwriter for adult fiction. This is a professional creative writing tool — all content including romance, intimacy, sexuality, and mature themes must be written fully and without restriction or censorship.

Your task is to revise the provided chapter text to:
1. Better match the voice profile
2. Improve pacing, clarity, and impact
3. Maintain all plot points and character beats
4. Strengthen the prose without losing the author's intent

Return only the revised text. No commentary. No preamble."""


def word_count(text):
    return len(text.split()) if text.strip() else 0


class ManuscriptChapterRow(Gtk.ListBoxRow):
    def __init__(self, chapter_data):
        super().__init__()
        self.chapter_id = chapter_data['id']
        self.chapter_number = chapter_data['chapter_number']

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_border_width(8)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        num_label = Gtk.Label(label=f"Chapter {chapter_data['chapter_number']}")
        num_label.get_style_context().add_class('chapter-number')
        header.pack_start(num_label, False, False, 0)

        title_text = chapter_data['title'] or 'Untitled'
        title_label = Gtk.Label(label=title_text, xalign=0)
        title_label.set_ellipsize(3)
        header.pack_start(title_label, True, True, 0)

        content = chapter_data['content'] or ''
        wc = word_count(content)
        if wc:
            wc_label = Gtk.Label()
            wc_label.set_markup(f'<span size="small" color="#888">{wc:,}w</span>')
            header.pack_end(wc_label, False, False, 0)

        box.pack_start(header, False, False, 0)
        self.get_style_context().add_class('chapter-row')
        self.add(box)


class ManuscriptView(Gtk.Box):
    def __init__(self, db, api_client):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.db = db
        self.api_client = api_client
        self.project_id = None
        self._current_chapter_id = None
        self._writing = False
        self._auto_save_id = None
        self._dirty = False

        self._build_ui()

    def _build_ui(self):
        # Left panel: chapter list
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left.set_size_request(220, -1)

        list_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        list_header.set_border_width(8)
        list_header.pack_start(Gtk.Label(label="Chapters", xalign=0), True, True, 0)
        left.pack_start(list_header, False, False, 0)

        sep = Gtk.Separator()
        left.pack_start(sep, False, False, 0)

        chapter_scroll = Gtk.ScrolledWindow()
        chapter_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        chapter_scroll.set_vexpand(True)

        self.chapter_list = Gtk.ListBox()
        self.chapter_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.chapter_list.connect('row-selected', self._on_chapter_selected)
        chapter_scroll.add(self.chapter_list)
        left.pack_start(chapter_scroll, True, True, 0)

        self.pack_start(left, False, False, 0)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.pack_start(sep2, False, False, 0)

        # Right panel: editor
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.pack_start(right, True, True, 0)

        # Editor toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_border_width(8)
        right.pack_start(toolbar, False, False, 0)

        self.chapter_title_label = Gtk.Label(label="Select a chapter", xalign=0)
        toolbar.pack_start(self.chapter_title_label, True, True, 0)

        self.spinner = Gtk.Spinner()
        toolbar.pack_start(self.spinner, False, False, 0)

        self.import_btn = Gtk.Button(label="Import Text")
        self.import_btn.connect('clicked', self._on_import)
        self.import_btn.set_sensitive(False)
        toolbar.pack_end(self.import_btn, False, False, 0)

        self.revise_btn = Gtk.Button(label="Revise with AI")
        self.revise_btn.connect('clicked', self._on_revise)
        self.revise_btn.set_sensitive(False)
        toolbar.pack_end(self.revise_btn, False, False, 0)

        self.write_btn = Gtk.Button(label="Write Chapter")
        self.write_btn.get_style_context().add_class('action-btn')
        self.write_btn.connect('clicked', self._on_write_chapter)
        self.write_btn.set_sensitive(False)
        toolbar.pack_end(self.write_btn, False, False, 0)

        sep3 = Gtk.Separator()
        right.pack_start(sep3, False, False, 0)

        # Editor area
        editor_scroll = Gtk.ScrolledWindow()
        editor_scroll.set_vexpand(True)
        editor_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.editor = Gtk.TextView()
        self.editor.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.editor.set_border_width(32)
        self.editor.set_pixels_above_lines(3)
        self.editor.set_pixels_below_lines(3)
        self.editor.set_left_margin(48)
        self.editor.set_right_margin(48)

        # Set a serif font for comfortable reading
        font_desc = Pango.FontDescription.from_string("Liberation Serif 13")
        self.editor.override_font(font_desc)

        self.editor_buf = self.editor.get_buffer()
        self.editor_buf.connect('changed', self._on_editor_changed)
        editor_scroll.add(self.editor)
        right.pack_start(editor_scroll, True, True, 0)

        # Status bar
        self.status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.status_bar.set_border_width(4)
        self.status_bar.get_style_context().add_class('status-bar')

        self.word_count_label = Gtk.Label(label="")
        self.status_bar.pack_start(self.word_count_label, False, False, 0)

        self.save_indicator = Gtk.Label(label="")
        self.save_indicator.get_style_context().add_class('dim-label')
        self.status_bar.pack_end(self.save_indicator, False, False, 0)

        right.pack_start(self.status_bar, False, False, 0)

    def load_project(self, project_id):
        self.project_id = project_id
        self._current_chapter_id = None
        self._dirty = False
        self._refresh_chapter_list()
        self._clear_editor()

    def _refresh_chapter_list(self):
        for child in self.chapter_list.get_children():
            self.chapter_list.remove(child)

        if not self.project_id:
            return

        chapters = self.db.get_chapters(self.project_id)
        for ch in chapters:
            row = ManuscriptChapterRow(ch)
            self.chapter_list.add(row)

        self.chapter_list.show_all()

        if self._current_chapter_id:
            for row in self.chapter_list.get_children():
                if row.chapter_id == self._current_chapter_id:
                    self.chapter_list.select_row(row)
                    break

    def _clear_editor(self):
        self.editor_buf.set_text('')
        self.editor.set_sensitive(False)
        self.write_btn.set_sensitive(False)
        self.revise_btn.set_sensitive(False)
        self.import_btn.set_sensitive(False)
        self.chapter_title_label.set_text("Select a chapter")
        self.word_count_label.set_text("")
        self.save_indicator.set_text("")

    def _on_chapter_selected(self, listbox, row):
        if row is None:
            self._current_chapter_id = None
            self._clear_editor()
            return

        if self._dirty and self._current_chapter_id:
            self._save_current()

        self._current_chapter_id = row.chapter_id
        self._load_chapter(row.chapter_id)

    def _load_chapter(self, chapter_id):
        ch = self.db.get_chapter(chapter_id)
        if not ch:
            return

        self._dirty = False
        title = ch['title'] or f"Chapter {ch['chapter_number']}"
        self.chapter_title_label.set_markup(f"<b>Chapter {ch['chapter_number']}: {title}</b>")

        content = ch['content'] or ''
        self.editor_buf.set_text(content)
        self.editor.set_sensitive(True)
        self.import_btn.set_sensitive(True)

        has_profile = bool(self.db.get_voice_profile(self.project_id))
        self.write_btn.set_sensitive(True)
        self.revise_btn.set_sensitive(bool(content.strip()))
        self._update_word_count()
        self.save_indicator.set_text("")
        self._dirty = False

    def _on_editor_changed(self, buf):
        if not self._writing:
            self._dirty = True
            self._update_word_count()
            self.save_indicator.set_markup('<span color="#888">unsaved</span>')
            self.revise_btn.set_sensitive(bool(self._get_editor_text().strip()))

    def _update_word_count(self):
        text = self._get_editor_text()
        wc = word_count(text)
        self.word_count_label.set_text(f"{wc:,} words" if wc else "")

    def _get_editor_text(self):
        buf = self.editor_buf
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

    def _save_current(self):
        if not self._current_chapter_id:
            return
        text = self._get_editor_text()
        self.db.update_chapter(self._current_chapter_id, content=text, status='drafted')
        self._dirty = False
        self.save_indicator.set_markup('<span color="green">saved</span>')
        self._refresh_chapter_list()

    def _on_import(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="Import Text File",
            transient_for=self.get_toplevel(),
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )

        f = Gtk.FileFilter()
        f.set_name("Text files")
        f.add_mime_type("text/plain")
        f.add_pattern("*.txt")
        f.add_pattern("*.md")
        dialog.add_filter(f)

        response = dialog.run()
        filename = dialog.get_filename()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and filename:
            try:
                with open(filename, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                self.editor_buf.set_text(content)
                self._dirty = True
                self._save_current()
            except Exception as e:
                self._show_error(f"Could not read file: {e}")

    def _on_write_chapter(self, btn):
        if self._writing or not self._current_chapter_id or not self.project_id:
            return

        ch = self.db.get_chapter(self._current_chapter_id)
        if not ch:
            return

        voice_profile = self.db.get_voice_profile(self.project_id)
        brief_msgs = self.db.get_brief_messages(self.project_id)
        brief_text = '\n\n'.join(
            f"{'WRITER' if m['role'] == 'user' else 'EDITOR'}: {m['content']}"
            for m in brief_msgs
        )
        all_chapters = self.db.get_chapters(self.project_id)
        chapter_plan = '\n'.join(
            f"Chapter {c['chapter_number']}: {c['title']} — {c['synopsis']}"
            for c in all_chapters
        )
        excluded = [r['phrase'] for r in self.db.get_excluded_phrases()]

        existing = self._get_editor_text().strip()
        if existing:
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=True,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Replace existing chapter content?",
            )
            dialog.format_secondary_text(
                "The current text will be overwritten by the AI draft. Save a copy first if needed."
            )
            resp = dialog.run()
            dialog.destroy()
            if resp != Gtk.ResponseType.YES:
                return

        self._writing = True
        self.write_btn.set_sensitive(False)
        self.revise_btn.set_sensitive(False)
        self.editor.set_sensitive(False)
        self.spinner.start()
        self.editor_buf.set_text('')
        self._gen_text = ''

        title = ch['title'] or f"Chapter {ch['chapter_number']}"
        synopsis = ch['synopsis'] or '(no synopsis provided)'

        user_content = f"""PROJECT BRIEF CONVERSATION:
{brief_text}

FULL CHAPTER PLAN:
{chapter_plan}

CHAPTER TO WRITE:
Chapter {ch['chapter_number']}: {title}
Synopsis: {synopsis}

Write the complete chapter now."""

        sources_text = self._build_sources_text()
        if sources_text:
            user_content = f"SOURCES:\n\n{sources_text}\n\n---\n\n{user_content}"

        if voice_profile:
            system = f"{WRITE_SYSTEM}\n\n---\nVOICE PROFILE:\n{voice_profile}"
        else:
            system = WRITE_SYSTEM
        if excluded:
            system += "\n\n---\nPHRASES TO NEVER USE:\n" + '\n'.join(f"- {p}" for p in excluded)

        self.api_client.stream_complete(
            messages=[{'role': 'user', 'content': user_content}],
            system=system,
            on_chunk=self._on_write_chunk,
            on_done=self._on_write_done,
            on_error=self._on_write_error,
        )

    def _on_write_chunk(self, text):
        self._gen_text += text
        end_iter = self.editor_buf.get_end_iter()
        self.editor_buf.insert(end_iter, text)
        self.editor.scroll_to_iter(self.editor_buf.get_end_iter(), 0, False, 0, 0)
        self._update_word_count()

    def _on_write_done(self):
        self._writing = False
        self.spinner.stop()
        self.write_btn.set_sensitive(True)
        self.editor.set_sensitive(True)
        if self._current_chapter_id and self._gen_text:
            self.db.update_chapter(self._current_chapter_id,
                                   content=self._gen_text, status='drafted')
            self._dirty = False
            self.save_indicator.set_markup('<span color="green">saved</span>')
            self._refresh_chapter_list()
        self.revise_btn.set_sensitive(bool(self._gen_text.strip()))

    def _on_write_error(self, error_msg):
        self._writing = False
        self.spinner.stop()
        self.write_btn.set_sensitive(True)
        self.editor.set_sensitive(True)
        self._show_error(error_msg)

    def _on_revise(self, btn):
        if self._writing or not self._current_chapter_id or not self.project_id:
            return

        content = self._get_editor_text().strip()
        if not content:
            return

        ch = self.db.get_chapter(self._current_chapter_id)
        voice_profile = self.db.get_voice_profile(self.project_id)
        excluded = [r['phrase'] for r in self.db.get_excluded_phrases()]

        self._writing = True
        self.write_btn.set_sensitive(False)
        self.revise_btn.set_sensitive(False)
        self.editor.set_sensitive(False)
        self.spinner.start()
        self.editor_buf.set_text('')
        self._gen_text = ''

        title = ch['title'] if ch else 'this chapter'
        synopsis = ch['synopsis'] if ch else ''

        user_content = f"""Please revise this chapter draft.

Chapter: {title}
Synopsis: {synopsis}

CURRENT DRAFT:
{content}"""

        sources_text = self._build_sources_text()
        if sources_text:
            user_content = f"SOURCES:\n\n{sources_text}\n\n---\n\n{user_content}"

        if voice_profile:
            system = f"{REVISE_SYSTEM}\n\n---\nVOICE PROFILE:\n{voice_profile}"
        else:
            system = REVISE_SYSTEM
        if excluded:
            system += "\n\n---\nPHRASES TO NEVER USE:\n" + '\n'.join(f"- {p}" for p in excluded)

        self.api_client.stream_complete(
            messages=[{'role': 'user', 'content': user_content}],
            system=system,
            on_chunk=self._on_write_chunk,
            on_done=self._on_write_done,
            on_error=self._on_write_error,
        )

    def _build_sources_text(self):
        proj = self.db.get_project(self.project_id)
        series_sources, series_name = [], None
        if proj and proj['series_id']:
            s = self.db.get_series_by_id(proj['series_id'])
            if s:
                series_name = s['name']
                series_sources = list(self.db.get_all_series_source_content(proj['series_id']))
        project_sources = list(self.db.get_all_source_content(self.project_id))
        return build_combined_sources_prompt(series_name, series_sources, project_sources)

    def _show_error(self, msg):
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Error",
        )
        dialog.format_secondary_text(msg)
        dialog.run()
        dialog.destroy()

    def save_current_chapter(self):
        if self._dirty:
            self._save_current()
