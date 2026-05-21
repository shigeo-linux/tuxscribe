import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

POPULAR_MODELS = [
    ('openrouter/auto', 'Auto Router (OpenRouter)'),
    ('anthropic/claude-3.5-sonnet', 'Claude 3.5 Sonnet (OpenRouter)'),
    ('anthropic/claude-3-opus', 'Claude 3 Opus (OpenRouter)'),
    ('openai/gpt-4o', 'GPT-4o (OpenRouter)'),
    ('google/gemini-pro-1.5', 'Gemini Pro 1.5 (OpenRouter)'),
    ('meta-llama/llama-3.1-70b-instruct', 'Llama 3.1 70B (OpenRouter)'),
    ('mistralai/mistral-large', 'Mistral Large (OpenRouter)'),
    ('deepseek-v4-pro', 'DeepSeek V4 Pro ★ Adult Fiction'),
    ('deepseek-chat', 'DeepSeek Chat (DeepSeek)'),
]


class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent, config):
        super().__init__(title="Settings", transient_for=parent, modal=True)
        self.config = config
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(520, 380)

        content = self.get_content_area()
        content.set_spacing(0)
        content.set_border_width(0)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_border_width(24)
        content.pack_start(box, True, True, 0)

        # API Key
        api_frame = Gtk.Frame(label="OpenRouter API")
        api_frame.set_label_align(0, 0.5)
        api_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        api_inner.set_border_width(12)
        api_frame.add(api_inner)

        key_label = Gtk.Label(label="API Key", xalign=0)
        key_label.get_style_context().add_class("dim-label")
        api_inner.pack_start(key_label, False, False, 0)

        self.api_key_entry = Gtk.Entry()
        self.api_key_entry.set_visibility(False)
        self.api_key_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.api_key_entry.set_text(config.api_key or '')
        self.api_key_entry.set_placeholder_text("sk-or-v1-...")
        api_inner.pack_start(self.api_key_entry, False, False, 0)

        hint = Gtk.Label()
        hint.set_markup('<small><a href="https://openrouter.ai/keys">Get your API key at openrouter.ai/keys</a></small>')
        hint.set_xalign(0)
        api_inner.pack_start(hint, False, False, 0)

        box.pack_start(api_frame, False, False, 0)

        # DeepSeek API Key
        ds_frame = Gtk.Frame(label="DeepSeek API (optional — for adult fiction)")
        ds_frame.set_label_align(0, 0.5)
        ds_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        ds_inner.set_border_width(12)
        ds_frame.add(ds_inner)

        ds_key_label = Gtk.Label(label="API Key", xalign=0)
        ds_key_label.get_style_context().add_class("dim-label")
        ds_inner.pack_start(ds_key_label, False, False, 0)

        self.deepseek_key_entry = Gtk.Entry()
        self.deepseek_key_entry.set_visibility(False)
        self.deepseek_key_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.deepseek_key_entry.set_text(config.deepseek_api_key or '')
        self.deepseek_key_entry.set_placeholder_text("sk-...")
        ds_inner.pack_start(self.deepseek_key_entry, False, False, 0)

        ds_hint = Gtk.Label()
        ds_hint.set_markup('<small><a href="https://platform.deepseek.com/api_keys">Get your key at platform.deepseek.com</a></small>')
        ds_hint.set_xalign(0)
        ds_inner.pack_start(ds_hint, False, False, 0)

        box.pack_start(ds_frame, False, False, 0)

        # Model selection
        model_frame = Gtk.Frame(label="Model")
        model_frame.set_label_align(0, 0.5)
        model_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        model_inner.set_border_width(12)
        model_frame.add(model_inner)

        model_label = Gtk.Label(label="AI Model", xalign=0)
        model_label.get_style_context().add_class("dim-label")
        model_inner.pack_start(model_label, False, False, 0)

        self.model_combo = Gtk.ComboBoxText.new_with_entry()
        current_model = config.model
        found = False
        for model_id, model_name in POPULAR_MODELS:
            self.model_combo.append(model_id, model_name)
            if model_id == current_model:
                found = True

        if found:
            self.model_combo.set_active_id(current_model)
        else:
            entry = self.model_combo.get_child()
            entry.set_text(current_model)

        model_inner.pack_start(self.model_combo, False, False, 0)

        model_note = Gtk.Label()
        model_note.set_markup('<small>Or type any OpenRouter model ID (e.g. <i>mistralai/mixtral-8x7b</i>)</small>')
        model_note.set_xalign(0)
        model_inner.pack_start(model_note, False, False, 0)

        box.pack_start(model_frame, False, False, 0)

        self.show_all()

    def get_values(self):
        api_key = self.api_key_entry.get_text().strip()
        deepseek_key = self.deepseek_key_entry.get_text().strip()
        active_id = self.model_combo.get_active_id()
        if active_id:
            model = active_id
        else:
            model = self.model_combo.get_child().get_text().strip()
        return api_key, deepseek_key, model
