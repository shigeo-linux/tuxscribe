import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject

PLAN_SYSTEM_NOVEL = """You are a developmental editor and story architect. Based on the project brief provided, create a detailed chapter-by-chapter plan.

For each chapter provide:
- Chapter number and a working title
- A 2-3 sentence synopsis covering: what happens, whose POV, what changes

You MUST use exactly this format for every entry:

CHAPTER 1: [Title]
[Synopsis]

CHAPTER 2: [Title]
[Synopsis]

(Continue for all chapters. No other headings or formatting.)

Aim for 20-35 chapters for a novel, 8-15 for non-fiction."""

PLAN_SYSTEM_SHORT_STORY = """You are a developmental editor and story architect. Based on the project brief provided, create a scene-by-scene plan for this short story.

For each scene provide:
- Scene number and a working title
- A 2-3 sentence synopsis covering: what happens, whose POV, what changes

You MUST use exactly this format for every entry:

SCENE 1: [Title]
[Synopsis]

SCENE 2: [Title]
[Synopsis]

(Continue for all scenes. No other headings or formatting.)

Aim for 3-8 scenes for a short story."""


SECTION_KEYWORDS = ('CHAPTER ', 'SCENE ', 'PART ', 'ACT ', 'SECTION ')


def _parse_plan_text(text):
    """Parse 'CHAPTER/SCENE/PART N: Title\nSynopsis' blocks into list of dicts."""
    chapters = []
    current = None
    synopsis_lines = []

    for line in text.splitlines():
        line = line.strip()
        # strip markdown bold markers
        line = line.lstrip('*#').rstrip('*').strip()
        if not line:
            if current and synopsis_lines:
                current['synopsis'] = ' '.join(synopsis_lines).strip()
                chapters.append(current)
                current = None
                synopsis_lines = []
            continue

        upper = line.upper()
        matched_keyword = next((kw for kw in SECTION_KEYWORDS if upper.startswith(kw)), None)

        if matched_keyword:
            if current and synopsis_lines:
                current['synopsis'] = ' '.join(synopsis_lines).strip()
                chapters.append(current)
                synopsis_lines = []

            rest = line[len(matched_keyword):].strip()
            if ':' in rest:
                num_part, title = rest.split(':', 1)
                try:
                    num = int(num_part.strip())
                except ValueError:
                    num = len(chapters) + 1
                title = title.strip()
            else:
                num = len(chapters) + 1
                title = rest

            current = {'number': num, 'title': title, 'synopsis': ''}
        elif current is not None:
            synopsis_lines.append(line)

    if current and synopsis_lines:
        current['synopsis'] = ' '.join(synopsis_lines).strip()
        chapters.append(current)

    return chapters


class ChapterRow(Gtk.ListBoxRow):
    def __init__(self, chapter_data):
        super().__init__()
        self.chapter_id = chapter_data['id']
        self.chapter_number = chapter_data['chapter_number']
        self._build(chapter_data)

    def _build(self, data):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_border_width(8)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        num_label = Gtk.Label(label=f"Chapter {data['chapter_number']}")
        num_label.get_style_context().add_class('chapter-number')
        num_label.set_width_chars(6)
        header.pack_start(num_label, False, False, 0)

        title_text = data['title'] or 'Untitled'
        title_label = Gtk.Label(label=title_text, xalign=0)
        title_label.set_ellipsize(3)
        header.pack_start(title_label, True, True, 0)

        status = data['status'] or 'planned'
        status_colors = {'planned': '#888', 'drafted': '#2980b9', 'revised': '#27ae60'}
        status_label = Gtk.Label()
        status_label.set_markup(f'<span color="{status_colors.get(status, "#888")}" size="small">{status}</span>')
        header.pack_end(status_label, False, False, 0)

        box.pack_start(header, False, False, 0)

        synopsis = data['synopsis'] or ''
        if synopsis:
            syn_label = Gtk.Label(label=synopsis, xalign=0)
            syn_label.set_ellipsize(3)
            syn_label.set_max_width_chars(80)
            syn_label.get_style_context().add_class('dim-label')
            box.pack_start(syn_label, False, False, 0)

        self.get_style_context().add_class('chapter-row')
        self.add(box)


class ChaptersView(Gtk.Box):
    __gsignals__ = {
        'chapter-selected': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self, db, api_client):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self.api_client = api_client
        self.project_id = None
        self._selected_chapter_id = None
        self._generating = False

        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_border_width(8)
        self.pack_start(toolbar, False, False, 0)

        add_btn = Gtk.Button(label="+ Add Chapter")
        add_btn.connect('clicked', self._on_add_chapter)
        toolbar.pack_start(add_btn, False, False, 0)

        self.generate_plan_btn = Gtk.Button(label="Generate Plan from Brief")
        self.generate_plan_btn.get_style_context().add_class('action-btn')
        self.generate_plan_btn.connect('clicked', self._on_generate_plan)
        self.generate_plan_btn.set_sensitive(False)
        toolbar.pack_start(self.generate_plan_btn, False, False, 0)

        self.spinner = Gtk.Spinner()
        toolbar.pack_start(self.spinner, False, False, 0)

        sep = Gtk.Separator()
        self.pack_start(sep, False, False, 0)

        # Main paned: chapter list | edit panel
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_hexpand(True)
        paned.set_vexpand(True)
        self.pack_start(paned, True, True, 0)

        # Chapter list
        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        self.chapter_list = Gtk.ListBox()
        self.chapter_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.chapter_list.connect('row-selected', self._on_chapter_selected)
        scroll.add(self.chapter_list)

        list_box.pack_start(scroll, True, True, 0)
        paned.pack1(list_box, False, False)
        paned.set_position(340)

        # Edit panel
        self.edit_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._build_edit_panel()
        paned.pack2(self.edit_panel, True, True)

        self._show_no_selection()

    def _build_edit_panel(self):
        # Title area
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box.set_border_width(12)
        self.edit_panel.pack_start(title_box, False, False, 0)

        self.chapter_num_label = Gtk.Label(label="")
        self.chapter_num_label.get_style_context().add_class('chapter-number')
        title_box.pack_start(self.chapter_num_label, False, False, 0)

        self.title_entry = Gtk.Entry()
        self.title_entry.set_placeholder_text("Chapter title")
        self.title_entry.set_hexpand(True)
        self.title_entry.connect('changed', self._on_title_changed)
        title_box.pack_start(self.title_entry, True, True, 0)

        # Status combo
        self.status_combo = Gtk.ComboBoxText()
        for s in ('planned', 'drafted', 'revised'):
            self.status_combo.append(s, s.capitalize())
        self.status_combo.connect('changed', self._on_status_changed)
        title_box.pack_end(self.status_combo, False, False, 0)

        sep = Gtk.Separator()
        self.edit_panel.pack_start(sep, False, False, 0)

        # Synopsis
        synopsis_label = Gtk.Label(label="Synopsis", xalign=0)
        synopsis_label.set_margin_start(12)
        synopsis_label.set_margin_top(8)
        synopsis_label.get_style_context().add_class('dim-label')
        self.edit_panel.pack_start(synopsis_label, False, False, 0)

        synopsis_scroll = Gtk.ScrolledWindow()
        synopsis_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        synopsis_scroll.set_min_content_height(100)
        synopsis_scroll.set_max_content_height(200)

        self.synopsis_view = Gtk.TextView()
        self.synopsis_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.synopsis_view.set_border_width(8)
        self.synopsis_buf = self.synopsis_view.get_buffer()
        self.synopsis_buf.connect('changed', self._on_synopsis_changed)
        synopsis_scroll.add(self.synopsis_view)
        self.edit_panel.pack_start(synopsis_scroll, False, False, 0)

        sep2 = Gtk.Separator()
        self.edit_panel.pack_start(sep2, False, False, 0)

        # Notes label
        notes_label = Gtk.Label(label="Writing Notes (optional — additional direction for this chapter)", xalign=0)
        notes_label.set_margin_start(12)
        notes_label.set_margin_top(8)
        notes_label.get_style_context().add_class('dim-label')
        self.edit_panel.pack_start(notes_label, False, False, 0)

        notes_scroll = Gtk.ScrolledWindow()
        notes_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        notes_scroll.set_vexpand(True)

        self.notes_view = Gtk.TextView()
        self.notes_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.notes_view.set_border_width(8)
        self.notes_buf = self.notes_view.get_buffer()
        self.edit_panel.pack_start(notes_scroll, True, True, 0)
        notes_scroll.add(self.notes_view)

        # Bottom buttons
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.set_border_width(8)
        self.edit_panel.pack_start(bottom, False, False, 0)

        self.delete_chapter_btn = Gtk.Button(label="Delete Chapter")
        self.delete_chapter_btn.get_style_context().add_class('danger-btn')
        self.delete_chapter_btn.connect('clicked', self._on_delete_chapter)
        bottom.pack_start(self.delete_chapter_btn, False, False, 0)

        self.save_chapter_btn = Gtk.Button(label="Save")
        self.save_chapter_btn.get_style_context().add_class('action-btn')
        self.save_chapter_btn.connect('clicked', self._on_save_chapter)
        bottom.pack_end(self.save_chapter_btn, False, False, 0)

    def _show_no_selection(self):
        for child in self.edit_panel.get_children():
            child.set_sensitive(False)

        self.chapter_num_label.set_text("Select a chapter")
        self.title_entry.set_text('')
        self.synopsis_buf.set_text('')
        self.notes_buf.set_text('')

    def load_project(self, project_id):
        self.project_id = project_id
        self._selected_chapter_id = None
        self._refresh_list()
        self._update_generate_btn()
        self._show_no_selection()

    def _update_generate_btn(self):
        if not self.project_id:
            self.generate_plan_btn.set_sensitive(False)
            return
        brief_msgs = self.db.get_brief_messages(self.project_id)
        has_any_brief = len(brief_msgs) > 1  # more than just the opening message
        self.generate_plan_btn.set_sensitive(has_any_brief and not self._generating)

    def refresh_button_state(self):
        self._update_generate_btn()

    def _refresh_list(self):
        for child in self.chapter_list.get_children():
            self.chapter_list.remove(child)

        if not self.project_id:
            return

        chapters = self.db.get_chapters(self.project_id)
        for ch in chapters:
            row = ChapterRow(ch)
            self.chapter_list.add(row)

        self.chapter_list.show_all()

        if self._selected_chapter_id:
            for row in self.chapter_list.get_children():
                if row.chapter_id == self._selected_chapter_id:
                    self.chapter_list.select_row(row)
                    break

    def _on_chapter_selected(self, listbox, row):
        if row is None:
            self._selected_chapter_id = None
            self._show_no_selection()
            return

        self.save_current()
        self._selected_chapter_id = row.chapter_id
        self._load_chapter_into_editor(row.chapter_id)
        self.emit('chapter-selected', row.chapter_id)

    def _load_chapter_into_editor(self, chapter_id):
        ch = self.db.get_chapter(chapter_id)
        if not ch:
            return

        for child in self.edit_panel.get_children():
            child.set_sensitive(True)

        self.chapter_num_label.set_text(f"Chapter {ch['chapter_number']}:")
        self.title_entry.set_text(ch['title'] or '')
        self.synopsis_buf.set_text(ch['synopsis'] or '')
        self.notes_buf.set_text('')
        self.status_combo.set_active_id(ch['status'] or 'planned')

    def _on_title_changed(self, entry):
        pass  # saved on explicit save

    def _on_synopsis_changed(self, buf):
        pass

    def _on_status_changed(self, combo):
        pass

    def _on_save_chapter(self, btn):
        if not self._selected_chapter_id:
            return

        title = self.title_entry.get_text().strip()
        synopsis = self.synopsis_buf.get_text(
            self.synopsis_buf.get_start_iter(), self.synopsis_buf.get_end_iter(), False
        )
        status = self.status_combo.get_active_id() or 'planned'

        self.db.update_chapter(self._selected_chapter_id,
                               title=title, synopsis=synopsis, status=status)
        self._refresh_list()

    def _on_delete_chapter(self, btn):
        if not self._selected_chapter_id:
            return

        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Delete this chapter?",
        )
        dialog.format_secondary_text("The chapter plan entry will be removed. Manuscript content is kept.")
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            self.db.delete_chapter(self._selected_chapter_id)
            self.db.reorder_chapters(self.project_id)
            self._selected_chapter_id = None
            self._refresh_list()
            self._show_no_selection()

    def _on_add_chapter(self, btn):
        if not self.project_id:
            return

        chapters = self.db.get_chapters(self.project_id)
        next_num = max((c['chapter_number'] for c in chapters), default=0) + 1
        chapter_id = self.db.create_chapter(self.project_id, next_num, title='')
        self._selected_chapter_id = chapter_id
        self._refresh_list()
        self._load_chapter_into_editor(chapter_id)

    def _on_generate_plan(self, btn):
        if self._generating or not self.project_id:
            return

        brief_msgs = self.db.get_brief_messages(self.project_id)
        brief_text = '\n\n'.join(
            f"{'WRITER' if m['role'] == 'user' else 'EDITOR'}: {m['content']}"
            for m in brief_msgs
        )

        existing = self.db.get_chapters(self.project_id)
        if existing:
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=True,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Replace existing chapter plan?",
            )
            dialog.format_secondary_text(
                "This will delete all current chapter plan entries. Manuscript content will be kept separately."
            )
            response = dialog.run()
            dialog.destroy()
            if response != Gtk.ResponseType.YES:
                return

            for ch in existing:
                self.db.delete_chapter(ch['id'])

        self._generating = True
        self.generate_plan_btn.set_sensitive(False)
        self.spinner.start()

        proj = self.db.get_project(self.project_id)
        is_short_story = proj and proj['project_type'] == 'short_story'
        plan_system = PLAN_SYSTEM_SHORT_STORY if is_short_story else PLAN_SYSTEM_NOVEL
        plan_prompt = "Create a detailed scene-by-scene plan." if is_short_story else "Create a detailed chapter plan."

        messages = [{'role': 'user', 'content': f"Project brief:\n\n{brief_text}\n\n{plan_prompt}"}]

        self.api_client.complete_async(
            messages=messages,
            system=plan_system,
            on_done=self._on_plan_done,
            on_error=self._on_plan_error,
        )

    def _on_plan_done(self, text):
        self._generating = False
        self.spinner.stop()
        self.generate_plan_btn.set_sensitive(True)

        chapters = _parse_plan_text(text)
        for ch in chapters:
            self.db.create_chapter(
                self.project_id, ch['number'],
                title=ch['title'], synopsis=ch['synopsis']
            )

        self._refresh_list()

    def _on_plan_error(self, error_msg):
        self._generating = False
        self.spinner.stop()
        self.generate_plan_btn.set_sensitive(True)

        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Failed to generate chapter plan",
        )
        dialog.format_secondary_text(error_msg)
        dialog.run()
        dialog.destroy()

    def save_current(self):
        if not self._selected_chapter_id:
            return
        title = self.title_entry.get_text().strip()
        synopsis = self.synopsis_buf.get_text(
            self.synopsis_buf.get_start_iter(), self.synopsis_buf.get_end_iter(), False
        )
        status = self.status_combo.get_active_id() or 'planned'
        self.db.update_chapter(self._selected_chapter_id,
                               title=title, synopsis=synopsis, status=status)

    def get_chapters(self):
        if not self.project_id:
            return []
        return self.db.get_chapters(self.project_id)
