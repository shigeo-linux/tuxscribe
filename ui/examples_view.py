import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

ANALYSIS_SYSTEM = """You are a master prose stylist and literary analyst. Analyze the provided writing samples with forensic precision to build a detailed voice profile.

Your analysis must cover:
1. **Sentence Rhythm & Structure** — average length, variation patterns, use of fragments, compound sentences, cadence
2. **Vocabulary & Diction** — register (formal/informal), specificity, recurring word families, notable choices
3. **Point of View & Narrative Distance** — close/distant, free indirect discourse, reliability
4. **Descriptive Style** — sensory priorities, metaphor types, imagery density, what is/isn't described
5. **Dialogue Conventions** — attribution style, action beats, subtext, punctuation habits
6. **Pacing & Scene Construction** — scene vs. summary ratio, scene-ending technique, white space use
7. **Emotional Register** — how emotion is conveyed (shown vs. told), restraint level
8. **Signature Moves** — recurring patterns, structural habits, unique techniques
9. **Things to Replicate** — the most distinctive elements to capture
10. **Things to Avoid** — anything inconsistent or that breaks the dominant voice

Be specific. Quote briefly from the samples. This profile will govern AI-drafted chapters."""


class ExamplesView(Gtk.Box):
    def __init__(self, db, api_client):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self.api_client = api_client
        self.project_id = None
        self._analyzing = False

        self._build_ui()

    def _build_ui(self):
        # Instructions banner
        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        info.set_border_width(12)
        info.get_style_context().add_class('info-bar')

        info_label = Gtk.Label()
        info_label.set_markup(
            '<b>Paste 3–5 pages of your own prose here.</b> '
            'The more representative your examples, the better Tuxscribe learns your voice. '
            'Use writing you love — avoid rough drafts.'
        )
        info_label.set_line_wrap(True)
        info_label.set_xalign(0)
        info.pack_start(info_label, True, True, 0)
        self.pack_start(info, False, False, 0)

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_border_width(8)
        self.pack_start(toolbar, False, False, 0)

        self.word_count_label = Gtk.Label(label="0 words")
        self.word_count_label.get_style_context().add_class('dim-label')
        toolbar.pack_start(self.word_count_label, False, False, 0)

        toolbar.pack_start(Gtk.Box(), True, True, 0)

        self.save_btn = Gtk.Button(label="Save Examples")
        self.save_btn.connect('clicked', self._on_save)
        self.save_btn.set_sensitive(False)
        toolbar.pack_end(self.save_btn, False, False, 0)

        self.analyze_btn = Gtk.Button(label="Analyse Writing Style →")
        self.analyze_btn.get_style_context().add_class('action-btn')
        self.analyze_btn.connect('clicked', self._on_analyse)
        self.analyze_btn.set_sensitive(False)
        toolbar.pack_end(self.analyze_btn, False, False, 0)

        self.spinner = Gtk.Spinner()
        toolbar.pack_end(self.spinner, False, False, 0)

        sep = Gtk.Separator()
        self.pack_start(sep, False, False, 0)

        # Main paned: editor top, analysis bottom
        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        paned.set_vexpand(True)
        self.pack_start(paned, True, True, 0)

        # Writing examples text area
        scroll1 = Gtk.ScrolledWindow()
        scroll1.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.examples_view = Gtk.TextView()
        self.examples_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.examples_view.set_border_width(12)
        self.examples_view.set_pixels_above_lines(2)
        font_desc = self.examples_view.get_pango_context().get_font_description()

        self.examples_buf = self.examples_view.get_buffer()
        self.examples_buf.connect('changed', self._on_text_changed)
        scroll1.add(self.examples_view)

        paned.pack1(scroll1, True, True)
        paned.set_position(400)

        # Analysis result area
        analysis_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        analysis_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        analysis_header.set_border_width(8)
        analysis_label = Gtk.Label(label="Style Analysis", xalign=0)
        analysis_label.get_style_context().add_class('dim-label')
        analysis_header.pack_start(analysis_label, True, True, 0)
        analysis_box.pack_start(analysis_header, False, False, 0)

        sep2 = Gtk.Separator()
        analysis_box.pack_start(sep2, False, False, 0)

        scroll2 = Gtk.ScrolledWindow()
        scroll2.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.analysis_view = Gtk.TextView()
        self.analysis_view.set_editable(False)
        self.analysis_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.analysis_view.set_border_width(12)
        self.analysis_buf = self.analysis_view.get_buffer()
        scroll2.add(self.analysis_view)
        analysis_box.pack_start(scroll2, True, True, 0)

        paned.pack2(analysis_box, True, True)

    def load_project(self, project_id):
        self.project_id = project_id
        content = self.db.get_writing_examples(project_id)
        self.examples_buf.set_text(content or '')
        self.analysis_buf.set_text('')
        self._update_ui_state()

    def _on_text_changed(self, buf):
        self._update_ui_state()

    def _update_ui_state(self):
        text = self._get_examples_text()
        wc = len(text.split()) if text.strip() else 0
        self.word_count_label.set_text(f"{wc:,} words")

        has_content = wc > 50
        self.save_btn.set_sensitive(has_content)
        self.analyze_btn.set_sensitive(has_content and not self._analyzing)

    def _get_examples_text(self):
        buf = self.examples_buf
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

    def _on_save(self, btn):
        if not self.project_id:
            return
        text = self._get_examples_text()
        self.db.save_writing_examples(self.project_id, text)
        self._show_toast("Writing examples saved.")

    def _on_analyse(self, btn):
        if self._analyzing or not self.project_id:
            return

        text = self._get_examples_text()
        if not text.strip():
            return

        self.db.save_writing_examples(self.project_id, text)

        self._analyzing = True
        self.analyze_btn.set_sensitive(False)
        self.spinner.start()
        self.analysis_buf.set_text('Analysing your writing style...')

        messages = [
            {'role': 'user', 'content': f"Here are my writing samples:\n\n{text}\n\nPlease analyse my writing style."}
        ]

        self.api_client.stream_complete(
            messages=messages,
            system=ANALYSIS_SYSTEM,
            on_chunk=self._on_chunk,
            on_done=self._on_done,
            on_error=self._on_error,
        )

        self._analysis_text = ''

    def _on_chunk(self, text):
        self._analysis_text += text
        self.analysis_buf.set_text(self._analysis_text)
        # Scroll to end
        end = self.analysis_buf.get_end_iter()
        self.analysis_view.scroll_to_iter(end, 0, False, 0, 0)

    def _on_done(self):
        self._analyzing = False
        self.spinner.stop()
        self.analyze_btn.set_sensitive(True)

    def _on_error(self, error_msg):
        self._analyzing = False
        self.spinner.stop()
        self.analyze_btn.set_sensitive(True)
        self.analysis_buf.set_text(f"Error: {error_msg}")

    def _show_toast(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=False,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.run()
        dialog.destroy()

    def get_examples_text(self):
        return self._get_examples_text()
