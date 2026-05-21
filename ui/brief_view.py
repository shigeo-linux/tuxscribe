import gi
import json
import os
from datetime import datetime
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango
from ui.source_utils import build_combined_sources_prompt

EDITOR_SYSTEM = """You are a developmental editor helping a writer develop their novel or long-form fiction project. This is a professional creative writing tool for adult fiction authors. All content — including romance, intimacy, sexuality, violence, and mature themes — is within scope and should be discussed openly and without restriction.

Your role is to guide a rich, in-depth creative conversation that builds a comprehensive project brief. Ask thoughtful, specific questions — one or two at a time — covering:
- Premise and core concept
- Main characters and their arcs, motivations, flaws
- Setting, world, and time period
- Tone, mood, and atmosphere
- Central conflict and themes
- Romance and intimacy arcs (heat level, key scenes, emotional beats)
- Narrative structure and POV
- Target audience and genre conventions
- The emotional experience you want readers to have

Be encouraging, curious, and precise. When the writer gives you a scene or situation, engage with it directly — analyse it, suggest how to develop it, discuss pacing and emotional beats, and offer concrete creative advice. Ask follow-up questions when more detail would genuinely help, but don't hide behind questions when you can give useful guidance directly.

When enough detail has accumulated (typically after 600+ words of user input), offer to produce a structured project summary.

Do not write full chapters — but you may write short illustrative snippets (a paragraph or two) to demonstrate a suggested approach when helpful."""

SUMMARY_PROMPT = """Based on our conversation, write a comprehensive, structured project brief with these sections:

**TITLE & GENRE**
**PREMISE** (2-3 paragraphs)
**MAIN CHARACTERS** (one paragraph each)
**SETTING & WORLD**
**TONE & ATMOSPHERE**
**CENTRAL CONFLICT & THEMES**
**NARRATIVE STRUCTURE**
**TARGET AUDIENCE**

Write this as a definitive reference document for all future AI-assisted writing on this project."""


def word_count(text):
    return len(text.split()) if text.strip() else 0


class BriefView(Gtk.Box):
    def __init__(self, db, api_client):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self.api_client = api_client
        self.project_id = None
        self._messages = []
        self._streaming = False
        self._assistant_buffer = None

        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_border_width(8)
        self.pack_start(toolbar, False, False, 0)

        toolbar.pack_start(Gtk.Label(label="Talk to your Editor", xalign=0), False, False, 0)

        self.word_count_label = Gtk.Label(label="")
        self.word_count_label.get_style_context().add_class('dim-label')
        toolbar.pack_start(self.word_count_label, True, True, 0)

        self.summary_btn = Gtk.Button(label="Generate Brief Summary")
        self.summary_btn.get_style_context().add_class('action-btn')
        self.summary_btn.connect('clicked', self._on_summary)
        self.summary_btn.set_sensitive(False)
        toolbar.pack_end(self.summary_btn, False, False, 0)

        self.import_btn = Gtk.Button(label="Import JSON")
        self.import_btn.connect('clicked', self._on_import)
        self.import_btn.set_sensitive(False)
        toolbar.pack_end(self.import_btn, False, False, 0)

        self.export_btn = Gtk.Button(label="Export JSON")
        self.export_btn.connect('clicked', self._on_export)
        self.export_btn.set_sensitive(False)
        toolbar.pack_end(self.export_btn, False, False, 0)

        self.clear_btn = Gtk.Button(label="Clear")
        self.clear_btn.connect('clicked', self._on_clear)
        toolbar.pack_end(self.clear_btn, False, False, 0)

        sep = Gtk.Separator()
        self.pack_start(sep, False, False, 0)

        # Chat scroll area
        self.chat_scroll = Gtk.ScrolledWindow()
        self.chat_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.chat_scroll.set_vexpand(True)

        self.chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.chat_box.set_border_width(12)
        self.chat_scroll.add(self.chat_box)
        self.pack_start(self.chat_scroll, True, True, 0)

        sep2 = Gtk.Separator()
        self.pack_start(sep2, False, False, 0)

        # Input area
        input_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        input_bar.set_border_width(10)
        self.pack_start(input_bar, False, False, 0)

        input_scroll = Gtk.ScrolledWindow()
        input_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        input_scroll.set_min_content_height(60)
        input_scroll.set_max_content_height(160)
        input_scroll.set_hexpand(True)
        input_scroll.set_shadow_type(Gtk.ShadowType.NONE)
        input_scroll.get_style_context().add_class('chat-input-scroll')

        self.input_view = Gtk.TextView()
        self.input_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.input_view.set_accepts_tab(False)
        self.input_view.get_style_context().add_class('chat-input')
        self.input_view.connect('key-press-event', self._on_key_press)
        input_scroll.add(self.input_view)
        input_bar.pack_start(input_scroll, True, True, 0)

        self.send_btn = Gtk.Button(label="Send")
        self.send_btn.get_style_context().add_class('action-btn')
        self.send_btn.connect('clicked', self._on_send)
        self.send_btn.set_sensitive(False)
        input_bar.pack_start(self.send_btn, False, False, 0)

        self.spinner = Gtk.Spinner()
        input_bar.pack_start(self.spinner, False, False, 0)

    def load_project(self, project_id):
        self.project_id = project_id
        self._messages = []

        for child in self.chat_box.get_children():
            self.chat_box.remove(child)

        rows = self.db.get_brief_messages(project_id)
        for row in rows:
            self._messages.append({'role': row['role'], 'content': row['content']})
            self._add_bubble(row['role'], row['content'])

        self.send_btn.set_sensitive(True)
        self.export_btn.set_sensitive(True)
        self.import_btn.set_sensitive(True)
        self._update_word_count()

        if not self._messages:
            self._start_conversation()

        self.chat_box.show_all()
        self._scroll_to_bottom()

    def _start_conversation(self):
        opener = ("Welcome! I'm your editor. Tell me about the project you're working on — "
                  "what's the core idea, and what kind of story do you want to tell?")
        self._add_bubble('assistant', opener)
        self._messages.append({'role': 'assistant', 'content': opener})
        self.db.add_brief_message(self.project_id, 'assistant', opener)
        self.chat_box.show_all()

    def _add_bubble(self, role, text, streaming=False):
        is_user = role == 'user'

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        outer.set_border_width(2)

        bubble = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        bubble.set_border_width(8)

        label = Gtk.Label(label=text)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_xalign(0)
        label.set_selectable(True)
        label.set_max_width_chars(80)

        bubble.add(label)

        if is_user:
            bubble.get_style_context().add_class('chat-message-user')
            outer.pack_end(bubble, False, True, 0)
        else:
            bubble.get_style_context().add_class('chat-message-assistant')
            outer.pack_start(bubble, False, True, 0)

        self.chat_box.pack_start(outer, False, False, 0)

        if streaming:
            self._assistant_buffer = label

        return label

    def _scroll_to_bottom(self):
        adj = self.chat_scroll.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

    def _on_key_press(self, widget, event):
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if not (event.state & Gdk.ModifierType.SHIFT_MASK):
                self._on_send(None)
                return True
        return False

    def _on_send(self, btn):
        if self._streaming or not self.project_id:
            return

        buf = self.input_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
        if not text:
            return

        buf.set_text('')
        self._messages.append({'role': 'user', 'content': text})
        self.db.add_brief_message(self.project_id, 'user', text)
        self._add_bubble('user', text)
        self.chat_box.show_all()
        self._scroll_to_bottom()
        self._update_word_count()

        self._start_streaming()

    def _start_streaming(self):
        self._streaming = True
        self.send_btn.set_sensitive(False)
        self.spinner.start()

        self._add_bubble('assistant', '', streaming=True)
        self.chat_box.show_all()

        self._current_response = ''

        system = EDITOR_SYSTEM
        if self.project_id:
            sources_text = self._build_sources_text()
            if sources_text:
                system = f"{EDITOR_SYSTEM}\n\n---\nSOURCES:\n\n{sources_text}"

        self.api_client.stream_complete(
            messages=self._messages,
            system=system,
            on_chunk=self._on_chunk,
            on_done=self._on_done,
            on_error=self._on_error,
        )

    def _on_chunk(self, text):
        self._current_response += text
        if self._assistant_buffer:
            self._assistant_buffer.set_text(self._current_response)
        self._scroll_to_bottom()

    def _on_done(self):
        self._streaming = False
        self.spinner.stop()
        self.send_btn.set_sensitive(True)
        self._assistant_buffer = None

        if self._current_response:
            self._messages.append({'role': 'assistant', 'content': self._current_response})
            self.db.add_brief_message(self.project_id, 'assistant', self._current_response)
            self._update_word_count()
            self._current_response = ''

    def _on_error(self, error_msg):
        self._streaming = False
        self.spinner.stop()
        self.send_btn.set_sensitive(True)
        self._assistant_buffer = None
        self._show_error(error_msg)

    def _on_summary(self, btn):
        if self._streaming or not self.project_id:
            return

        self._messages.append({'role': 'user', 'content': SUMMARY_PROMPT})
        self._add_bubble('user', '(Generating project brief summary...)')
        self.chat_box.show_all()
        self._start_streaming()

    def _on_clear(self, btn):
        if not self.project_id:
            return
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text='Clear the entire brief conversation?',
        )
        dialog.format_secondary_text("This cannot be undone.")
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            self.db.clear_brief_messages(self.project_id)
            self._messages = []
            for child in self.chat_box.get_children():
                self.chat_box.remove(child)
            self._start_conversation()
            self.chat_box.show_all()
            self._update_word_count()

    def _update_word_count(self):
        total = sum(word_count(m['content']) for m in self._messages if m['role'] == 'user')
        color = 'green' if total >= 500 else 'orange'
        self.word_count_label.set_markup(
            f'<span color="{color}">{total} words of context</span>'
            f'<span color="gray"> (500+ recommended)</span>'
        )
        self.summary_btn.set_sensitive(total >= 100)

    def _on_import(self, btn):
        if not self.project_id:
            return

        dialog = Gtk.FileChooserDialog(
            title="Import Brief Chat",
            transient_for=self.get_toplevel(),
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )
        f = Gtk.FileFilter()
        f.set_name("JSON files")
        f.add_pattern("*.json")
        dialog.add_filter(f)

        response = dialog.run()
        path = dialog.get_filename()
        dialog.destroy()

        if response != Gtk.ResponseType.OK or not path:
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            messages = data.get('messages', [])
            if not messages:
                raise ValueError("No messages found in file.")
            for m in messages:
                if m.get('role') not in ('user', 'assistant') or not m.get('content'):
                    raise ValueError("File contains invalid message format.")
        except Exception as e:
            msg = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Could not read file",
            )
            msg.format_secondary_text(str(e))
            msg.run()
            msg.destroy()
            return

        if self._messages:
            confirm = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Replace existing chat?",
            )
            confirm.format_secondary_text(
                f"This will replace the current conversation with {len(messages)} imported messages."
            )
            resp = confirm.run()
            confirm.destroy()
            if resp != Gtk.ResponseType.YES:
                return

        self.db.clear_brief_messages(self.project_id)
        for m in messages:
            self.db.add_brief_message(self.project_id, m['role'], m['content'])

        self._messages = []
        for child in self.chat_box.get_children():
            self.chat_box.remove(child)
        rows = self.db.get_brief_messages(self.project_id)
        for row in rows:
            self._messages.append({'role': row['role'], 'content': row['content']})
            self._add_bubble(row['role'], row['content'])
        self.chat_box.show_all()
        self._scroll_to_bottom()
        self._update_word_count()

    def _on_export(self, btn):
        if not self.project_id or not self._messages:
            return

        proj = self.db.get_project(self.project_id)
        proj_name = proj['name'] if proj else 'brief'
        safe_name = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in proj_name).strip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_filename = f"{safe_name}_brief_{timestamp}.json"

        dialog = Gtk.FileChooserDialog(
            title="Export Brief Chat",
            transient_for=self.get_toplevel(),
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        dialog.set_current_name(default_filename)
        dialog.set_do_overwrite_confirmation(True)

        f = Gtk.FileFilter()
        f.set_name("JSON files")
        f.add_pattern("*.json")
        dialog.add_filter(f)

        response = dialog.run()
        path = dialog.get_filename()
        dialog.destroy()

        if response != Gtk.ResponseType.OK or not path:
            return

        rows = self.db.get_brief_messages(self.project_id)
        data = {
            'project': proj_name,
            'exported_at': datetime.now().isoformat(),
            'messages': [
                {
                    'role': r['role'],
                    'content': r['content'],
                    'created_at': r['created_at'],
                }
                for r in rows
            ],
        }

        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            msg = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Could not save file",
            )
            msg.format_secondary_text(str(e))
            msg.run()
            msg.destroy()

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
        err_bar = Gtk.InfoBar()
        err_bar.set_message_type(Gtk.MessageType.ERROR)
        err_bar.get_content_area().pack_start(
            Gtk.Label(label=msg), True, True, 0
        )
        err_bar.add_button("Dismiss", Gtk.ResponseType.CLOSE)
        err_bar.connect('response', lambda bar, _: bar.destroy())
        self.pack_start(err_bar, False, False, 0)
        err_bar.show_all()
