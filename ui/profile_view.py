import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

PROFILE_SYSTEM = """You are a master writing coach and style analyst. Your task is to synthesise a project brief and writing style analysis into a single, authoritative Voice Profile.

This Voice Profile will be injected into every AI writing prompt for this project. It must be:
- Comprehensive but scannable
- Specific, not generic
- Actionable (a skilled author can follow it precisely)
- Protective of the author's unique voice

Structure the profile with these sections:

# VOICE PROFILE: [Project Title]

## SENTENCE RHYTHM
[Specific guidance on sentence construction, length variation, rhythm]

## VOCABULARY & DICTION
[Word choices, register, what to use and avoid]

## POINT OF VIEW
[POV conventions, narrative distance, interiority]

## DESCRIPTIVE TECHNIQUE
[Sensory priorities, imagery, metaphor, density of detail]

## DIALOGUE
[Attribution style, punctuation, action beats, subtext approach]

## PACING
[Scene construction, summary use, chapter rhythm]

## EMOTIONAL REGISTER
[How emotion is conveyed, restraint level, reader relationship]

## SIGNATURE MOVES
[The author's most distinctive techniques — replicate these]

## TONAL CONSISTENCY
[The overall emotional and atmospheric world of this project]

## STRICT PROHIBITIONS
[What must never appear — clichés, styles foreign to this voice, structural violations]"""

PROFILE_USER_TEMPLATE = """Here is the project brief conversation and writing samples. Create the Voice Profile.

=== PROJECT BRIEF ===
{brief}

=== WRITING EXAMPLES ===
{examples}

Generate the complete Voice Profile now."""


def _brief_to_text(messages):
    lines = []
    for m in messages:
        role = "WRITER" if m['role'] == 'user' else "EDITOR"
        lines.append(f"{role}: {m['content']}")
    return '\n\n'.join(lines)


class ProfileView(Gtk.Box):
    def __init__(self, db, api_client):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self.api_client = api_client
        self.project_id = None
        self._generating = False

        self._build_ui()

    def _build_ui(self):
        # Status bar
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.status_box.set_border_width(12)
        self.pack_start(self.status_box, False, False, 0)

        self.status_label = Gtk.Label(label="No voice profile generated yet.")
        self.status_label.set_xalign(0)
        self.status_box.pack_start(self.status_label, True, True, 0)

        self.spinner = Gtk.Spinner()
        self.status_box.pack_start(self.spinner, False, False, 0)

        self.generate_btn = Gtk.Button(label="Generate Voice Profile")
        self.generate_btn.get_style_context().add_class('action-btn')
        self.generate_btn.connect('clicked', self._on_generate)
        self.generate_btn.set_sensitive(False)
        self.status_box.pack_end(self.generate_btn, False, False, 0)

        self.regen_btn = Gtk.Button(label="Regenerate")
        self.regen_btn.connect('clicked', self._on_generate)
        self.regen_btn.set_sensitive(False)
        self.status_box.pack_end(self.regen_btn, False, False, 0)

        sep = Gtk.Separator()
        self.pack_start(sep, False, False, 0)

        # Requirements info
        self.req_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.req_bar.set_border_width(10)
        self.req_bar.get_style_context().add_class('info-bar')

        self.req_label = Gtk.Label()
        self.req_label.set_xalign(0)
        self.req_label.set_line_wrap(True)
        self.req_bar.pack_start(self.req_label, True, True, 0)
        self.pack_start(self.req_bar, False, False, 0)

        # Profile text view
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.profile_view = Gtk.TextView()
        self.profile_view.set_editable(True)
        self.profile_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.profile_view.set_border_width(16)
        self.profile_buf = self.profile_view.get_buffer()
        self.profile_buf.connect('changed', self._on_profile_changed)
        scroll.add(self.profile_view)
        self.pack_start(scroll, True, True, 0)

        # Save button for manual edits
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom_bar.set_border_width(8)
        self.pack_start(bottom_bar, False, False, 0)

        self.word_count_label = Gtk.Label(label="")
        self.word_count_label.get_style_context().add_class('dim-label')
        bottom_bar.pack_start(self.word_count_label, True, True, 0)

        self.save_profile_btn = Gtk.Button(label="Save Edits")
        self.save_profile_btn.connect('clicked', self._on_save_edits)
        self.save_profile_btn.set_sensitive(False)
        bottom_bar.pack_end(self.save_profile_btn, False, False, 0)

        self._profile_dirty = False

    def load_project(self, project_id):
        self.project_id = project_id
        self._profile_dirty = False

        profile = self.db.get_voice_profile(project_id)
        self.profile_buf.set_text(profile or '')

        self._update_ui_state()

    def _update_ui_state(self):
        if not self.project_id:
            return

        brief_msgs = self.db.get_brief_messages(self.project_id)
        examples = self.db.get_writing_examples(self.project_id)
        profile = self.db.get_voice_profile(self.project_id)

        user_brief_words = sum(
            len(m['content'].split()) for m in brief_msgs if m['role'] == 'user'
        )
        example_words = len(examples.split()) if examples.strip() else 0

        has_brief = user_brief_words >= 200
        has_examples = example_words >= 100
        can_generate = has_brief and has_examples

        reqs = []
        if not has_brief:
            reqs.append(f"Brief needs more content ({user_brief_words}/200 words in the Brief tab)")
        if not has_examples:
            reqs.append(f"Writing examples needed ({example_words}/100 words in Writing Examples tab)")

        if reqs:
            self.req_bar.set_visible(True)
            self.req_label.set_markup(
                '<b>Requirements not met:</b> ' + ' · '.join(reqs)
            )
        else:
            self.req_bar.set_visible(False)

        self.generate_btn.set_sensitive(can_generate and not self._generating and not profile)
        self.regen_btn.set_sensitive(can_generate and not self._generating and bool(profile))

        if profile:
            self.status_label.set_markup('<span color="green">✓ Voice profile active</span>')
        else:
            self.status_label.set_text("No voice profile generated yet.")

        # Word count
        text = self._get_profile_text()
        wc = len(text.split()) if text.strip() else 0
        self.word_count_label.set_text(f"{wc:,} words" if wc else "")

    def _on_generate(self, btn):
        if self._generating or not self.project_id:
            return

        brief_msgs = self.db.get_brief_messages(self.project_id)
        examples = self.db.get_writing_examples(self.project_id)

        brief_text = _brief_to_text(brief_msgs)
        if not brief_text.strip() or not examples.strip():
            return

        self._generating = True
        self.generate_btn.set_sensitive(False)
        self.regen_btn.set_sensitive(False)
        self.spinner.start()
        self.profile_buf.set_text('Generating your voice profile...\n')
        self._gen_text = ''

        messages = [{
            'role': 'user',
            'content': PROFILE_USER_TEMPLATE.format(
                brief=brief_text,
                examples=examples,
            )
        }]

        self.api_client.stream_complete(
            messages=messages,
            system=PROFILE_SYSTEM,
            on_chunk=self._on_chunk,
            on_done=self._on_done,
            on_error=self._on_error,
        )

    def _on_chunk(self, text):
        self._gen_text += text
        self.profile_buf.set_text(self._gen_text)
        end = self.profile_buf.get_end_iter()
        self.profile_view.scroll_to_iter(end, 0, False, 0, 0)

    def _on_done(self):
        self._generating = False
        self.spinner.stop()
        if self._gen_text and self.project_id:
            self.db.save_voice_profile(self.project_id, self._gen_text)
        self._profile_dirty = False
        self.save_profile_btn.set_sensitive(False)
        self._update_ui_state()

    def _on_error(self, error_msg):
        self._generating = False
        self.spinner.stop()
        self.profile_buf.set_text(f"Error: {error_msg}")
        self._update_ui_state()

    def _on_profile_changed(self, buf):
        if not self._generating:
            self._profile_dirty = True
            self.save_profile_btn.set_sensitive(True)
            wc = len(self._get_profile_text().split())
            self.word_count_label.set_text(f"{wc:,} words" if wc else "")

    def _on_save_edits(self, btn):
        if not self.project_id:
            return
        text = self._get_profile_text()
        self.db.save_voice_profile(self.project_id, text)
        self._profile_dirty = False
        self.save_profile_btn.set_sensitive(False)
        self._update_ui_state()

    def _get_profile_text(self):
        buf = self.profile_buf
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

    def refresh_requirements(self):
        self._update_ui_state()
